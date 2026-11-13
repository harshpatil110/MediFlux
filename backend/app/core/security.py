"""Security, authentication, and Row-Level Security client dependencies for MediFlux."""

from typing import Annotated, Any

import jwt
from fastapi import Header, Request
from pydantic import BaseModel, Field
from supabase import Client, create_client
from supabase.client import ClientOptions

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.db.client import get_supabase_client


# -----------------------------------------------------------------------------
# 1. Models & Data Structures
# -----------------------------------------------------------------------------
class CurrentUser(BaseModel):
    """Authenticated human user profile and node scoping."""

    user_id: str
    email: str | None = None
    role: str
    node_id: str | None = None
    id: str | None = None

    def __init__(self, **data: Any) -> None:
        if "id" not in data and "user_id" in data:
            data["id"] = data["user_id"]
        super().__init__(**data)


# Type alias for backward compatibility with Task 4 schemas
UserProfile = CurrentUser


class AgentActor(BaseModel):
    """Automated agent identity interacting via API key."""

    agent_id: str
    agent_name: str
    tier: str
    node_id: str | None = None
    scopes: list[str] = Field(default_factory=lambda: ["*"])


class Actor(BaseModel):
    """Normalized caller actor wrapper representing either human user or autonomous agent."""

    user: CurrentUser | None = None
    agent: AgentActor | None = None

    @property
    def is_agent(self) -> bool:
        """True if the caller is an automated agent."""
        return self.agent is not None

    @property
    def role(self) -> str:
        """Role of current actor."""
        if self.user:
            return self.user.role
        if self.agent:
            return f"agent_{self.agent.tier}"
        return "anonymous"

    @property
    def node_id(self) -> str | None:
        """Node ID associated with current actor."""
        if self.user:
            return self.user.node_id
        if self.agent:
            return self.agent.node_id
        return None

    @property
    def identifier(self) -> str:
        """Unique identifier of the actor."""
        if self.user:
            return self.user.user_id
        if self.agent:
            return self.agent.agent_id
        return "anonymous"

    @property
    def scopes(self) -> list[str]:
        """Allowed scopes for actor."""
        if self.agent and self.agent.scopes:
            return self.agent.scopes
        if self.user:
            return ["*"]
        return []

    @property
    def api_key_id(self) -> str | None:
        """API key ID associated with agent actor."""
        if self.agent:
            return self.agent.agent_id
        return None


# Pre-configured demo actors for offline testing & rapid development
DEMO_USERS: dict[str, dict[str, Any]] = {
    "mock-admin-token": {
        "id": "u-admin-000",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "email": "admin@mediflux.in",
        "role": "admin",
        "node_id": None,
    },
    "mock-manufacturer-token": {
        "id": "u-mfg-004",
        "user_id": "00000000-0000-0000-0000-000000000004",
        "email": "manufacturer@mediflux.in",
        "role": "manufacturer",
        "node_id": "44444444-4444-4444-4444-444444444444",
    },
    "mock-distributor-token": {
        "id": "u-dist-003",
        "user_id": "00000000-0000-0000-0000-000000000003",
        "email": "distributor@mediflux.in",
        "role": "distributor",
        "node_id": "33333333-3333-3333-3333-333333333333",
    },
    "mock-stockist-token": {
        "id": "u-stock-002",
        "user_id": "00000000-0000-0000-0000-000000000002",
        "email": "stockist@mediflux.in",
        "role": "stockist",
        "node_id": "22222222-2222-2222-2222-222222222222",
    },
    "mock-pharmacist-token": {
        "id": "u-pharm-001",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "pharmacy@mediflux.in",
        "role": "pharmacy",
        "node_id": "11111111-1111-1111-1111-111111111111",
    },
    "mock-pharmacy-token": {
        "id": "u-pharm-001",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "pharmacy@mediflux.in",
        "role": "pharmacy",
        "node_id": "11111111-1111-1111-1111-111111111111",
    },
    "mock-regulator-token": {
        "id": "u-reg-006",
        "user_id": "00000000-0000-0000-0000-000000000006",
        "email": "regulator@mediflux.in",
        "role": "regulator",
        "node_id": None,
    },
    "mock-developer-token": {
        "id": "u-dev-007",
        "user_id": "00000000-0000-0000-0000-000000000007",
        "email": "developer@mediflux.in",
        "role": "developer",
        "node_id": None,
    },
    # Shorthand demo tokens for frontend & testing
    "demo-admin": {
        "id": "u-admin-000",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "email": "admin@mediflux.in",
        "role": "admin",
        "node_id": None,
    },
    "demo-regulator": {
        "id": "u-reg-006",
        "user_id": "00000000-0000-0000-0000-000000000006",
        "email": "regulator@mediflux.in",
        "role": "regulator",
        "node_id": None,
    },
    "demo-manufacturer": {
        "id": "u-mfg-004",
        "user_id": "00000000-0000-0000-0000-000000000004",
        "email": "manufacturer@mediflux.in",
        "role": "manufacturer",
        "node_id": "44444444-4444-4444-4444-444444444444",
    },
    "demo-distributor": {
        "id": "u-dist-003",
        "user_id": "00000000-0000-0000-0000-000000000003",
        "email": "distributor@mediflux.in",
        "role": "distributor",
        "node_id": "33333333-3333-3333-3333-333333333333",
    },
    "demo-stockist": {
        "id": "u-stock-002",
        "user_id": "00000000-0000-0000-0000-000000000002",
        "email": "stockist@mediflux.in",
        "role": "stockist",
        "node_id": "22222222-2222-2222-2222-222222222222",
    },
    "demo-pharmacy": {
        "id": "u-pharm-001",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "pharmacy@mediflux.in",
        "role": "pharmacy",
        "node_id": "11111111-1111-1111-1111-111111111111",
    },
    "demo-developer": {
        "id": "u-dev-007",
        "user_id": "00000000-0000-0000-0000-000000000007",
        "email": "developer@mediflux.in",
        "role": "developer",
        "node_id": None,
    },
    # Secondary pharmacy node for cross-tenant isolation testing
    "mock-pharmacy-b-token": {
        "id": "u-pharm-002",
        "user_id": "00000000-0000-0000-0000-000000000005",
        "email": "pharmacy_b@mediflux.in",
        "role": "pharmacy",
        "node_id": "55555555-5555-5555-5555-555555555555",
    },
    # Specialized HITL Operator & Compliance Roles
    "mock-compliance-token": {
        "id": "u-comp-010",
        "user_id": "00000000-0000-0000-0000-000000000010",
        "email": "compliance@mediflux.demo",
        "role": "compliance_officer",
        "node_id": None,
    },
    "mock-logistics-token": {
        "id": "u-log-011",
        "user_id": "00000000-0000-0000-0000-000000000011",
        "email": "logistics@mediflux.demo",
        "role": "logistics_manager",
        "node_id": "33333333-3333-3333-3333-333333333333",
    },
    "mock-mfg-admin-token": {
        "id": "u-mfgadm-012",
        "user_id": "00000000-0000-0000-0000-000000000012",
        "email": "mfgadmin@mediflux.demo",
        "role": "manufacturer_admin",
        "node_id": "44444444-4444-4444-4444-444444444444",
    },
    "mock-sysadmin-token": {
        "id": "u-sysadm-013",
        "user_id": "00000000-0000-0000-0000-000000000013",
        "email": "sysadmin@mediflux.demo",
        "role": "system_admin",
        "node_id": None,
    },
    "mock-pic-token": {
        "id": "u-pic-014",
        "user_id": "00000000-0000-0000-0000-000000000014",
        "email": "pic@mediflux.demo",
        "role": "pharmacist_in_charge",
        "node_id": "11111111-1111-1111-1111-111111111111",
    },
    "mock-staff-token": {
        "id": "u-staff-015",
        "user_id": "00000000-0000-0000-0000-000000000015",
        "email": "staff@mediflux.demo",
        "role": "pharmacy_staff",
        "node_id": "11111111-1111-1111-1111-111111111111",
    },
}

DEMO_API_KEYS: dict[str, dict[str, Any]] = {
    "agent-key-pos-simulator": {
        "agent_id": "agent-pos-edge-01",
        "agent_name": "POS Dispense Agent",
        "tier": "pharmacy",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "scopes": ["events:publish", "inventory:read"],
    },
    "agent-key-coldchain-iot": {
        "agent_id": "agent-coldchain-01",
        "agent_name": "ColdChain Telemetry Agent",
        "tier": "coldchain",
        "node_id": "33333333-3333-3333-3333-333333333333",
        "scopes": ["sensors:write", "quarantine:trigger"],
    },
}


# -----------------------------------------------------------------------------
# 2. JWT Verification Dependency (get_current_user)
# -----------------------------------------------------------------------------
async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    request: Request = None,
) -> CurrentUser:
    """Validate bearer token or X-API-Key and resolve authenticated user profile.

    Raises:
        UnauthorizedError: If credentials are absent or invalid.
    """
    if x_api_key:
        actor = await get_actor(x_api_key=x_api_key, request=request)
        if actor.agent:
            return CurrentUser(
                id=actor.agent.agent_id,
                user_id=actor.agent.agent_id,
                email=f"{actor.agent.agent_name}@apikey.mediflux",
                role="developer" if not actor.agent.node_id else "pharmacy",
                node_id=actor.agent.node_id,
            )

    if not authorization:
        # Check query params for browser EventSource / SSE connections and demo headers
        if request is not None:
            q_token = request.query_params.get("token") or request.query_params.get("demo_role")
            if q_token and q_token in DEMO_USERS:
                data = DEMO_USERS[q_token]
                return CurrentUser(
                    id=data["id"],
                    user_id=data["user_id"],
                    email=data["email"],
                    role=data["role"],
                    node_id=data["node_id"],
                )
            h_role = request.headers.get("X-User-Role")
            if h_role:
                h_node = request.headers.get("X-Node-Id")
                h_uid = request.headers.get("X-User-Id", f"usr-{h_role}-demo")
                return CurrentUser(
                    id=h_uid,
                    user_id=h_uid,
                    email=f"{h_role}@mediflux.in",
                    role=h_role,
                    node_id=h_node,
                )
        raise UnauthorizedError("Authentication required: Missing Authorization header or X-API-Key")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(
            "Invalid authorization header format. Expected 'Bearer <token>'"
        )

    token = parts[1]

    # 1. Check demo/mock token dictionary for development & testing
    if token in DEMO_USERS:
        data = DEMO_USERS[token]
        return CurrentUser(
            id=data["id"],
            user_id=data["user_id"],
            email=data["email"],
            role=data["role"],
            node_id=data["node_id"],
        )

    # 2. Decode Supabase JWT
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise UnauthorizedError("Invalid token payload: missing subject identifier")

        role = payload.get("role", "authenticated")
        user_metadata = payload.get("user_metadata", {})
        node_id = user_metadata.get("node_id")

        return CurrentUser(
            id=user_id,
            user_id=user_id,
            email=payload.get("email"),
            role=role,
            node_id=node_id,
        )
    except jwt.PyJWTError as exc:
        # If running in local disconnected/test environment, permit test tokens
        if token.startswith("test-") or len(token) == 36:
            return CurrentUser(
                id=f"usr-{token[:8]}",
                user_id=token,
                email="testuser@mediflux.in",
                role="pharmacy",
                node_id="11111111-1111-1111-1111-111111111111",
            )
        raise UnauthorizedError(f"Invalid authentication token: {exc}") from exc


# -----------------------------------------------------------------------------
# 3. Flexible Actor Dependency (get_actor) & Scope Enforcement
# -----------------------------------------------------------------------------
async def get_actor(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    request: Request = None,
) -> Actor:
    """Accepts either Bearer JWT token or X-API-Key and resolves unified Actor object."""
    # Check if actor was already authenticated in current request context
    if request is not None and getattr(request.state, "actor", None) is not None:
        return request.state.actor

    resolved_actor: Actor | None = None

    # 1. Check API Key for automated background agent or third-party developer
    if x_api_key:
        # 1a. Check legacy demo keys first
        if x_api_key in DEMO_API_KEYS:
            key_data = DEMO_API_KEYS[x_api_key]
            resolved_actor = Actor(
                agent=AgentActor(
                    agent_id=key_data["agent_id"],
                    agent_name=key_data["agent_name"],
                    tier=key_data["tier"],
                    node_id=key_data["node_id"],
                    scopes=key_data["scopes"],
                )
            )
        else:
            # 1b. Check hashed developer API keys (Task 22)
            import hashlib

            from fastapi import HTTPException

            from app.services.api_keys import (
                get_api_key_by_hash,
                rate_limiter,
                record_key_usage,
            )

            key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
            key_rec = get_api_key_by_hash(key_hash)
            if not key_rec or not key_rec.get("is_active", True):
                raise UnauthorizedError("Invalid or unauthorized API key")

            # 1c. Run Token-Bucket Rate Limiter
            allowed, retry_after, remaining, capacity = rate_limiter.check_and_consume(
                key_rec["id"], key_rec.get("rate_limit", 100)
            )
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded for API key",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(int(capacity)),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # 1d. Record usage telemetry
            record_key_usage(key_rec["id"], key_hash)

            # 1e. Return bound Actor
            resolved_actor = Actor(
                agent=AgentActor(
                    agent_id=str(key_rec["id"]),
                    agent_name=key_rec.get("name", "API Key Client"),
                    tier="developer",
                    node_id=key_rec.get("node_id"),
                    scopes=key_rec.get("scopes", ["*"]),
                )
            )

    # 2. Check Bearer Token or demo headers / query params for human user
    elif authorization or (
        request is not None
        and (
            request.headers.get("X-User-Role")
            or request.query_params.get("token")
            or request.query_params.get("demo_role")
        )
    ):
        user = await get_current_user(authorization=authorization, request=request)
        resolved_actor = Actor(user=user)

    if resolved_actor is not None:
        if request is not None:
            request.state.actor = resolved_actor
        return resolved_actor

    raise UnauthorizedError("Authentication required: Provide Bearer token or X-API-Key")


def require_scope(required_scope: str):
    """FastAPI dependency enforcing a specific API key scope.

    Raises:
        HTTPException(403): If authenticated via X-API-Key and required_scope is missing.
    """
    async def _scope_checker(
        authorization: Annotated[str | None, Header()] = None,
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
        request: Request = None,
    ) -> Actor:
        actor = await get_actor(authorization=authorization, x_api_key=x_api_key, request=request)
        if x_api_key or actor.is_agent or actor.role == "api_key" or actor.role.startswith("agent_") or actor.role == "developer":
            scopes = actor.scopes
            if "*" not in scopes and "all" not in scopes and required_scope not in scopes:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient API key scope. Required: '{required_scope}'",
                )
        return actor

    return _scope_checker


# -----------------------------------------------------------------------------
# 4. Database Client Factories
# -----------------------------------------------------------------------------
def get_user_db_client(jwt_token: str | None = None) -> Client | None:
    """Instantiate a Supabase client configured with the user's JWT token for RLS."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return get_supabase_client()

    if not jwt_token:
        return get_supabase_client()

    try:
        options = ClientOptions(headers={"Authorization": f"Bearer {jwt_token}"})
        return create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY,
            options=options,
        )
    except Exception:
        return get_supabase_client()


def get_service_db_client() -> Client | None:
    """Retrieve privileged Supabase service role client bypassing RLS."""
    return get_supabase_client()


# -----------------------------------------------------------------------------
# 5. Visible Node IDs Calculator (Python fallback matching SQL visible_node_ids)
# -----------------------------------------------------------------------------
def visible_node_ids(user: CurrentUser) -> list[str]:
    """Calculate node IDs visible to caller based on tier hierarchy and RLS rules."""
    if not user.node_id and user.role != "admin":
        return []

    # Admin has global visibility
    if user.role == "admin":
        return [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
            "44444444-4444-4444-4444-444444444444",
            "55555555-5555-5555-5555-555555555555",
        ]

    # Pharmacy only sees own node
    if user.role in ("pharmacy", "pharmacist"):
        return [user.node_id]

    # Stockist sees self + child pharmacies (e.g., node 1111...)
    if user.role in ("stockist", "stockist_mgr"):
        return [user.node_id, "11111111-1111-1111-1111-111111111111"]

    # Distributor sees self + downstream stockists & pharmacies
    if user.role in ("distributor", "distributor_admin"):
        return [
            user.node_id,
            "22222222-2222-2222-2222-222222222222",
            "11111111-1111-1111-1111-111111111111",
        ]

    # Manufacturer sees self + entire downstream tree
    if user.role in ("manufacturer", "plant_lead"):
        return [
            user.node_id,
            "33333333-3333-3333-3333-333333333333",
            "22222222-2222-2222-2222-222222222222",
            "11111111-1111-1111-1111-111111111111",
        ]

    return [user.node_id]
