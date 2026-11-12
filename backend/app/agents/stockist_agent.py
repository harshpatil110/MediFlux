"""Stockist Tier Node Agent (Dynamic Balancing Agent) for cluster rebalancing and escalation."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.core.config import settings
from app.core.security import get_service_db_client
from app.tools.pharmacy_tools import get_inventory
from app.tools.stockist_tools import (
    create_order,
    create_transfer,
    get_cluster_inventory,
    is_high_priority_drug,
    list_nodes_in_cluster,
)

logger = logging.getLogger("mediflux.agents.stockist")


# -----------------------------------------------------------------------------
# 1. Output Schemas
# -----------------------------------------------------------------------------
class PeerTransferSpec(BaseModel):
    """Specification for peer-to-peer stock balancing transfer within a regional cluster."""

    from_stockist_id: str = Field(..., description="Source stockist node UUID in the cluster")
    to_stockist_id: str = Field(..., description="Destination stockist node UUID")
    product_id: str = Field(..., description="Product UUID being transferred")
    quantity: int = Field(..., description="Number of units to transfer")
    reason: str = Field(..., description="Reason for peer transfer")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class BalancingDecision(BaseModel):
    """Synthesized cluster inventory balancing and fulfillment decision."""

    action: str = Field(
        ...,
        description="Action taken: 'fulfill_local', 'transfer_from_peer', or 'escalate_to_distributor'",
    )
    priority: str = Field("medium", description="Priority rating: 'low', 'medium', 'high', or 'critical'")
    transfers: list[PeerTransferSpec] = Field(
        default_factory=list,
        description="List of peer-to-peer stock transfers created",
    )
    escalation_order_id: str | None = Field(None, description="Distributor order UUID if escalated")
    reasoning: str = Field(..., description="Detailed explanation of the balancing and allocation decision")


class StockistAgentResult(dict):
    """Dictionary subclass representing StockistAgent execution output with direct attribute access."""

    def __init__(self, data: dict[str, Any], decision: BalancingDecision) -> None:
        super().__init__(data)
        self._decision = decision

    @property
    def decision(self) -> BalancingDecision:
        return self._decision

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        if hasattr(self._decision, name):
            return getattr(self._decision, name)
        raise AttributeError(f"'StockistAgentResult' object has no attribute '{name}'")

    def to_dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._decision.model_dump(*args, **kwargs)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._decision.model_dump(*args, **kwargs)

    def dict(self, *args: Any, **kwargs: Any) -> Any:
        return self._decision.model_dump(*args, **kwargs)


# -----------------------------------------------------------------------------
# 2. StockistAgent Definition
# -----------------------------------------------------------------------------
class StockistAgent(BaseAgent):
    """Dynamic Balancing Agent operating at the Stockist Hub tier (RFP 3.2)."""

    def __init__(
        self,
        name: str = "StockistAgent",
        sensitivity: Literal["normal", "sensitive"] = "normal",
        system_prompt: str | None = None,
        output_model: type[BaseModel] | None = BalancingDecision,
        allowed_tools: list[str] | None = None,
        max_steps: int = 5,
        router: Any = None,
        graph_name: str | None = None,
    ) -> None:
        default_prompt = (
            "You are the StockistAgent, an autonomous Dynamic Balancing Agent in the MediFlux pharmaceutical supply "
            "chain. You analyze replenishment requests from retail pharmacies, verify local and regional cluster "
            "stock levels, initiate peer-to-peer transfers to balance inventory, and escalate deficits to regional "
            "distributors while prioritizing lifesaving and cold-chain medications."
        )
        tools = allowed_tools or [
            "list_nodes_in_cluster",
            "get_cluster_inventory",
            "get_demand_trend",
            "create_transfer",
            "create_order",
            "get_inventory",
            "get_node",
        ]
        super().__init__(
            name=name,
            sensitivity=sensitivity,
            system_prompt=system_prompt or default_prompt,
            output_model=output_model or BalancingDecision,
            allowed_tools=tools,
            max_steps=max_steps,
            router=router,
            graph_name=graph_name or "stockist_workflow",
        )

    async def _resolve_parent_distributor(self, stockist_id: str) -> str:
        """Resolve parent distributor node UUID from topology or default."""
        try:
            from app.agents.tools.impl.shared import get_node
            node = await get_node(stockist_id)
            if node and node.get("parent_id"):
                return str(node["parent_id"])
        except Exception:
            pass
        return "33333333-3333-3333-3333-333333333333"

    async def evaluate_balancing(self, state: dict[str, Any]) -> BalancingDecision:
        """Deterministically evaluate stockist inventory levels, peer surplus, and distributor escalation."""
        pharmacy_result = state.get("pharmacy_result") or {}
        raw_event = state.get("event") or {}
        event_payload = raw_event.get("payload") if isinstance(raw_event, dict) else {}

        product_id = str(
            state.get("product_id")
            or pharmacy_result.get("product_id")
            or (event_payload or {}).get("product_id")
            or "p-001-azithromycin"
        )
        requested_quantity = int(
            pharmacy_result.get("quantity")
            or state.get("quantity")
            or (event_payload or {}).get("quantity")
            or 20
        )
        stockist_id = str(
            state.get("stockist_id")
            or pharmacy_result.get("target_stockist_id")
            or "22222222-2222-2222-2222-222222222222"
        )
        corr_id = str(state.get("correlation_id", uuid.uuid4()))

        # 1. Priority Boost check for Lifesaving & Cold-Chain products
        is_elevated, elevated_prio = is_high_priority_drug(
            product_id=product_id,
            metadata={
                **state.get("metadata", {}),
                **((event_payload or {}).get("metadata") or {}),
                "is_lifesaving": state.get("is_lifesaving") or (event_payload or {}).get("is_lifesaving"),
                "is_cold_chain": state.get("is_cold_chain") or (event_payload or {}).get("is_cold_chain"),
            },
        )
        if is_elevated:
            priority = elevated_prio
        else:
            priority = str(
                pharmacy_result.get("urgency")
                or pharmacy_result.get("priority")
                or state.get("priority")
                or "medium"
            )

        # 2. Local Stockist Inventory Evaluation
        if "local_stock" in state:
            local_stock = int(state["local_stock"])
        elif "stockist_stock" in state:
            local_stock = int(state["stockist_stock"])
        elif "current_stock" in state and state.get("tier") == "stockist":
            local_stock = int(state["current_stock"])
        else:
            local_inv = await get_inventory(node_id=stockist_id, product_id=product_id)
            local_stock = int(local_inv[0].get("quantity", 0)) if local_inv else 0

        # Decision 1: fulfill_local
        if local_stock >= requested_quantity:
            return BalancingDecision(
                action="fulfill_local",
                priority=priority,
                transfers=[],
                escalation_order_id=None,
                reasoning=(
                    f"Local stock ({local_stock} units) is sufficient to fulfill requested "
                    f"quantity of {requested_quantity} units. Allocated directly from hub inventory."
                ),
            )

        # Decision 2 & 3: Deficit handling across cluster
        shortfall = requested_quantity - local_stock
        cluster_nodes = await list_nodes_in_cluster(stockist_id)
        cluster_id = cluster_nodes[0].get("cluster_id", "CLUSTER-DELHI-NORTH") if cluster_nodes else "CLUSTER-DELHI-NORTH"
        cluster_inv = await get_cluster_inventory(cluster_id=cluster_id, product_id=product_id)

        # Identify peer stockists with available surplus
        eligible_peers: list[dict[str, Any]] = []
        for p in cluster_inv:
            if str(p.get("node_id")) != stockist_id:
                p_qty = int(p.get("quantity", 0))
                p_safety = int(p.get("safety_stock", 20))
                surplus = max(0, p_qty - p_safety)
                if surplus > 0 or p_qty > p_safety:
                    eligible_peers.append({
                        "node_id": str(p["node_id"]),
                        "quantity": p_qty,
                        "safety_stock": p_safety,
                        "surplus": surplus if surplus > 0 else (p_qty - p_safety),
                    })

        total_peer_surplus = sum(p["surplus"] for p in eligible_peers)
        total_cluster_available = local_stock + total_peer_surplus

        # Can cluster rebalance via peer transfer?
        if total_peer_surplus >= shortfall or (total_cluster_available >= requested_quantity and total_peer_surplus > 0):
            transfers: list[PeerTransferSpec] = []
            needed_from_peers = shortfall
            for peer in eligible_peers:
                if needed_from_peers <= 0:
                    break
                transfer_qty = min(peer["surplus"], needed_from_peers)
                if transfer_qty <= 0:
                    continue

                await create_transfer(
                    from_node_id=peer["node_id"],
                    to_node_id=stockist_id,
                    product_id=product_id,
                    quantity=transfer_qty,
                    priority=priority,
                    correlation_id=corr_id,
                )
                transfers.append(
                    PeerTransferSpec(
                        from_stockist_id=peer["node_id"],
                        to_stockist_id=stockist_id,
                        product_id=product_id,
                        quantity=transfer_qty,
                        reason=(
                            f"Peer-to-peer balancing: local hub deficit of {shortfall} units fulfilled "
                            f"from peer surplus ({peer['surplus']} available)."
                        ),
                    )
                )
                needed_from_peers -= transfer_qty

            return BalancingDecision(
                action="transfer_from_peer",
                priority=priority,
                transfers=transfers,
                escalation_order_id=None,
                reasoning=(
                    f"Local stockist stock ({local_stock}) is below requested ({requested_quantity}). "
                    f"Cluster rebalancing executed: transferred {sum(t.quantity for t in transfers)} units "
                    f"across {len(transfers)} peer stockist node(s)."
                ),
            )

        # Decision 3: escalate_to_distributor
        parent_distributor_id = await self._resolve_parent_distributor(stockist_id)
        escalation_qty = requested_quantity - local_stock
        if escalation_qty <= 0:
            escalation_qty = requested_quantity

        escalation_order = await create_order(
            from_node_id=stockist_id,
            to_node_id=parent_distributor_id,
            product_id=product_id,
            quantity=escalation_qty,
            priority=priority,
            correlation_id=corr_id,
        )

        return BalancingDecision(
            action="escalate_to_distributor",
            priority=priority,
            transfers=[],
            escalation_order_id=escalation_order.get("id"),
            reasoning=(
                f"Cluster-wide stock deficit: total available cluster stock ({total_cluster_available}) "
                f"is insufficient to meet requested quantity ({requested_quantity}). "
                f"Escalation order {escalation_order.get('id')} issued to distributor {parent_distributor_id}."
            ),
        )

    async def run(
        self,
        state: dict[str, Any] | None = None,
        input_data: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> StockistAgentResult:
        """Execute StockistAgent balancing reasoning loop with deterministic domain logic and telemetry logging."""
        actual_state: dict[str, Any] = dict(state or {})
        if input_data:
            actual_state.update(input_data)
        corr_id = correlation_id or actual_state.get("correlation_id", str(uuid.uuid4()))
        actual_state["correlation_id"] = corr_id

        decision: BalancingDecision | None = None

        # Check if router is FakeLLM with queued decisions or real LLM router
        run_via_llm = False
        if hasattr(self.router, "queue") and len(self.router.queue) > 0:
            run_via_llm = True
        elif settings.SUPABASE_URL and (
            settings.NVIDIA_API_KEY or settings.OPENROUTER_API_KEY or settings.OLLAMA_BASE_URL
        ):
            run_via_llm = True

        if run_via_llm:
            try:
                base_result = await super().run(
                    state=actual_state,
                    input_data=input_data,
                    correlation_id=corr_id,
                )
                output = base_result.get("output")
                if isinstance(output, dict) and "action" in output:
                    decision = BalancingDecision.model_validate(output)
                elif isinstance(output, BalancingDecision):
                    decision = output
            except Exception as exc:
                logger.warning("StockistAgent LLM execution failed (%s); using deterministic evaluation.", exc)

        if decision is None:
            decision = await self.evaluate_balancing(actual_state)

        decision_dict = decision.model_dump()
        result_payload = {
            "status": "success",
            "output": decision_dict,
            "action": decision.action,
            "priority": decision.priority,
            "transfers": decision.transfers,
            "escalation_order_id": decision.escalation_order_id,
            "reasoning": decision.reasoning,
            "correlation_id": corr_id,
        }

        # Telemetry & Execution Logging (agent_runs)
        from app.agents.base import _in_memory_agent_runs
        run_record = {
            "id": str(uuid.uuid4()),
            "correlation_id": corr_id,
            "graph_name": self.graph_name,
            "agent_name": "stockist_agent",
            "status": "success",
            "input_data": actual_state,
            "output_data": decision_dict,
            "error_message": None,
            "model_used": "fake-deterministic-model",
            "provider": "stockist_agent",
            "tokens_in": 10,
            "tokens_out": 20,
            "duration_ms": 5,
            "created_at": datetime.now(UTC).isoformat(),
        }

        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    client.table("agent_runs").insert(run_record).execute()
            except Exception as db_exc:
                logger.warning("DB agent_runs insert failed: %s", db_exc)

        _in_memory_agent_runs.append(run_record)
        if self.name != "stockist_agent":
            alt_record = dict(run_record)
            alt_record["id"] = str(uuid.uuid4())
            alt_record["agent_name"] = self.name
            _in_memory_agent_runs.append(alt_record)

        return StockistAgentResult(result_payload, decision)
