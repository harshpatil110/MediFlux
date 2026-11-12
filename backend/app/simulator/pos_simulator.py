"""Retail Point-of-Sale (POS) Traffic Simulator Engine for MediFlux Supply Chain.

Supports simulation modes:
- single: Emits 1 single SaleEvent for a selected pharmacy and product.
- steady: Emits sales across active pharmacies at a background rate (e.g. 2/sec).
- burst: Simulates sudden demand spike for a product/region (e.g. 50 sales in 5s).
- stockout_run: Emits continuous sales for a product at a pharmacy until inventory drops below safety stock.
"""

import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.api.v1.endpoints.inventory import DEFAULT_INVENTORY
from app.api.v1.endpoints.nodes import DEFAULT_NODES
from app.api.v1.endpoints.products import DEFAULT_PRODUCTS
from app.events.service import get_in_memory_stock

logger = logging.getLogger("mediflux.simulator.pos")


class POSSimulator:
    """High-performance POS event traffic simulator."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str = "http://127.0.0.1:8000",
        app: Any = None,
        mode: str = "single",
        rate: float = 2.0,
        duration_seconds: int = 10,
        intensity: int = 50,
        target_pharmacy_id: str | None = None,
        target_product_id: str | None = None,
        region: str | None = None,
    ) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.app = app
        self.mode = mode
        self.rate = max(0.1, rate)
        self.duration_seconds = duration_seconds
        self.intensity = intensity
        self.target_pharmacy_id = target_pharmacy_id
        self.target_product_id = target_product_id
        self.region = region

        self.simulation_id = str(uuid.uuid4())
        self.is_running = False
        self._stop_requested = False
        self.events_sent = 0
        self.errors_count = 0
        self.last_event_time: str | None = None
        self.last_error: str | None = None
        self._managed_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Obtain an HTTPX async client, either injected, ASGI in-process, or network-bound."""
        if self.client is not None:
            return self.client
        if self._managed_client is not None:
            return self._managed_client

        if self.app is not None:
            from httpx import ASGITransport

            self._managed_client = httpx.AsyncClient(
                transport=ASGITransport(app=self.app),
                base_url=self.base_url or "http://test",
                timeout=10.0,
            )
        else:
            self._managed_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=10.0,
            )
        return self._managed_client

    async def close(self) -> None:
        """Clean up managed HTTP client if instantiated."""
        if self._managed_client is not None:
            await self._managed_client.aclose()
            self._managed_client = None

    def _resolve_sale_target(
        self,
        pharmacy_id: str | None = None,
        product_id: str | None = None,
        region: str | None = None,
    ) -> tuple[str, str, str]:
        """Resolve valid (pharmacy_id, product_id, batch_id) tuple from catalog/inventory."""
        target_pharm = pharmacy_id or self.target_pharmacy_id
        target_prod = product_id or self.target_product_id
        target_region = region or self.region

        # Filter pharmacies
        pharmacies = [n for n in DEFAULT_NODES if n.get("tier") == "pharmacy"]
        if target_region:
            reg_pharms = [p for p in pharmacies if p.get("region", "").lower() == target_region.lower()]
            if reg_pharms:
                pharmacies = reg_pharms

        if not target_pharm:
            target_pharm = pharmacies[0]["id"] if pharmacies else "11111111-1111-1111-1111-111111111111"

        # Filter products
        if not target_prod:
            target_prod = DEFAULT_PRODUCTS[0]["id"] if DEFAULT_PRODUCTS else "p-001-azithromycin"

        # Find matching batch in inventory
        matching_inv = [
            inv for inv in DEFAULT_INVENTORY
            if str(inv.get("node_id")) == str(target_pharm) and str(inv.get("product_id")) == str(target_prod)
        ]

        if matching_inv:
            batch_id = str(matching_inv[0]["batch_id"])
        else:
            # Fallback to any inventory batch or default
            inv_for_prod = [inv for inv in DEFAULT_INVENTORY if str(inv.get("product_id")) == str(target_prod)]
            batch_id = str(inv_for_prod[0]["batch_id"]) if inv_for_prod else "b-azi-2026-01"

        return str(target_pharm), str(target_prod), str(batch_id)

    async def emit_sale(
        self,
        pharmacy_id: str,
        product_id: str,
        batch_id: str,
        quantity: int = 1,
    ) -> dict[str, Any]:
        """Emit a single SaleEvent to /api/v1/events/sale."""
        client = await self._get_client()
        corr_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())

        payload = {
            "event_id": event_id,
            "pharmacy_id": str(pharmacy_id),
            "product_id": str(product_id),
            "batch_id": str(batch_id),
            "quantity": quantity,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "pos_simulator",
        }

        try:
            resp = await client.post(
                "/api/v1/events/sale",
                json=payload,
                headers={"X-Correlation-ID": corr_id},
            )
            resp.raise_for_status()
            data = resp.json()

            self.events_sent += 1
            self.last_event_time = datetime.now(UTC).isoformat()
            return data
        except Exception as exc:
            self.errors_count += 1
            self.last_error = str(exc)
            logger.error("POSSimulator sale emit error: %s", exc)
            raise

    async def run_single(
        self,
        pharmacy_id: str | None = None,
        product_id: str | None = None,
        quantity: int = 1,
    ) -> dict[str, Any]:
        """Execute simulation mode: single."""
        self.is_running = True
        try:
            pharm, prod, batch = self._resolve_sale_target(pharmacy_id, product_id)
            res = await self.emit_sale(pharmacy_id=pharm, product_id=prod, batch_id=batch, quantity=quantity)
            return {"status": "completed", "mode": "single", "events_sent": 1, "last_result": res}
        finally:
            self.is_running = False

    async def run_steady(
        self,
        rate: float | None = None,
        duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Execute simulation mode: steady background sales."""
        effective_rate = rate or self.rate
        effective_duration = duration_seconds or self.duration_seconds
        interval = 1.0 / effective_rate

        self.is_running = True
        self._stop_requested = False
        start_time = asyncio.get_event_loop().time()

        try:
            while not self._stop_requested:
                now = asyncio.get_event_loop().time()
                if (now - start_time) >= effective_duration:
                    break

                # Pick random active pharmacy and product
                pharm, prod, batch = self._resolve_sale_target()
                qty = random.choice([1, 1, 1, 2, 3])
                try:
                    await self.emit_sale(pharmacy_id=pharm, product_id=prod, batch_id=batch, quantity=qty)
                except Exception as exc:
                    logger.warning("Steady mode sale failed: %s", exc)

                await asyncio.sleep(interval)

            return {
                "status": "stopped" if self._stop_requested else "completed",
                "mode": "steady",
                "events_sent": self.events_sent,
                "duration_seconds": round(asyncio.get_event_loop().time() - start_time, 2),
            }
        finally:
            self.is_running = False

    async def run_burst(
        self,
        intensity: int | None = None,
        region: str | None = None,
        product_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute simulation mode: burst demand surge."""
        burst_count = intensity or self.intensity
        target_reg = region or self.region
        target_prod = product_id or self.target_product_id

        self.is_running = True
        self._stop_requested = False
        start_time = asyncio.get_event_loop().time()

        try:
            pharmacies = [n for n in DEFAULT_NODES if n.get("tier") == "pharmacy"]
            if target_reg:
                filtered = [p for p in pharmacies if p.get("region", "").lower() == target_reg.lower()]
                if filtered:
                    pharmacies = filtered

            for _ in range(burst_count):
                if self._stop_requested:
                    break
                selected_pharm = random.choice(pharmacies)["id"] if pharmacies else "11111111-1111-1111-1111-111111111111"
                pharm, prod, batch = self._resolve_sale_target(
                    pharmacy_id=selected_pharm,
                    product_id=target_prod,
                    region=target_reg,
                )
                try:
                    await self.emit_sale(pharmacy_id=pharm, product_id=prod, batch_id=batch, quantity=1)
                except Exception as exc:
                    logger.warning("Burst mode sale error: %s", exc)
                # Small yield to avoid overwhelming event loop
                await asyncio.sleep(0.01)

            return {
                "status": "stopped" if self._stop_requested else "completed",
                "mode": "burst",
                "events_sent": self.events_sent,
                "duration_seconds": round(asyncio.get_event_loop().time() - start_time, 2),
            }
        finally:
            self.is_running = False

    async def run_stockout_run(
        self,
        pharmacy_id: str | None = None,
        product_id: str | None = None,
        safety_stock_threshold: int = 10,
    ) -> dict[str, Any]:
        """Execute simulation mode: stockout_run (continuous sales until stock drops below safety stock)."""
        pharm, prod, batch = self._resolve_sale_target(pharmacy_id, product_id)
        self.is_running = True
        self._stop_requested = False
        start_time = asyncio.get_event_loop().time()
        max_safety_iterations = 200  # Guardrail against infinite loops

        try:
            iterations = 0
            while not self._stop_requested and iterations < max_safety_iterations:
                iterations += 1
                current_stock = get_in_memory_stock(pharm, prod, batch)

                # If current stock is already at or below safety stock threshold, stop
                if current_stock <= safety_stock_threshold and current_stock > 0:
                    break

                try:
                    await self.emit_sale(pharmacy_id=pharm, product_id=prod, batch_id=batch, quantity=2)
                except Exception as exc:
                    logger.warning("Stockout run sale failed: %s", exc)
                    break

                # Check new stock
                new_stock = get_in_memory_stock(pharm, prod, batch)
                if new_stock <= safety_stock_threshold:
                    break

                await asyncio.sleep(0.02)

            return {
                "status": "completed",
                "mode": "stockout_run",
                "pharmacy_id": pharm,
                "product_id": prod,
                "events_sent": self.events_sent,
                "final_stock": get_in_memory_stock(pharm, prod, batch),
                "duration_seconds": round(asyncio.get_event_loop().time() - start_time, 2),
            }
        finally:
            self.is_running = False

    async def run(self) -> dict[str, Any]:
        """Execute simulation based on configured mode."""
        if self.mode == "single":
            return await self.run_single(self.target_pharmacy_id, self.target_product_id)
        if self.mode == "steady":
            return await self.run_steady(self.rate, self.duration_seconds)
        if self.mode == "burst":
            return await self.run_burst(self.intensity, self.region, self.target_product_id)
        if self.mode == "stockout_run":
            return await self.run_stockout_run(self.target_pharmacy_id, self.target_product_id)
        raise ValueError(f"Unknown simulation mode: {self.mode}")

    def stop(self) -> None:
        """Signal the running simulation task to stop."""
        self._stop_requested = True
        self.is_running = False

    def get_status(self) -> dict[str, Any]:
        """Retrieve real-time telemetry and status of simulator."""
        return {
            "simulation_id": self.simulation_id,
            "status": "running" if self.is_running else ("stopped" if self._stop_requested else "idle"),
            "mode": self.mode,
            "rate": self.rate,
            "events_sent": self.events_sent,
            "errors_count": self.errors_count,
            "last_event_time": self.last_event_time,
            "last_error": self.last_error,
            "target_node_id": self.target_pharmacy_id,
            "target_product_id": self.target_product_id,
        }
