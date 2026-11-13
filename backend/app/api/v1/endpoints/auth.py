"""Authentication, demo user profiles, and session management endpoints."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import CurrentUser, get_current_user, get_service_db_client

logger = logging.getLogger("mediflux.api.auth")

router = APIRouter(tags=["Authentication & Profiles"])

# ---------------------------------------------------------------------------
# Demo Users Master Directory (All 7 Roles)
# ---------------------------------------------------------------------------

SEEDED_DEMO_USERS: list[dict[str, Any]] = [
    {
        "id": "u-admin-000",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "email": "admin@mediflux.in",
        "password": "AdminPassword123!",
        "role": "admin",
        "role_name": "Network Control Tower Admin",
        "full_name": "Dr. Rajesh Varma",
        "node_id": None,
        "node_name": "National Control Tower",
        "tier": "network",
        "region": "National",
        "token": "mock-admin-token",
        "allowed_routes": [
            "/overview",
            "/cascade",
            "/agents",
            "/approvals",
            "/adapter-forge",
            "/regulatory-lab",
            "/prescriptions",
            "/cold-chain",
            "/audit",
            "/copilot",
            "/developer",
        ],
    },
    {
        "id": "u-reg-006",
        "user_id": "00000000-0000-0000-0000-000000000006",
        "email": "regulator@mediflux.in",
        "password": "RegPassword123!",
        "role": "regulator",
        "role_name": "CDSCO / NPPA Regulatory Officer",
        "full_name": "Smt. Priya Sharma",
        "node_id": None,
        "node_name": "National Regulatory Directorate",
        "tier": "regulatory",
        "region": "National",
        "token": "mock-regulator-token",
        "allowed_routes": [
            "/overview",
            "/cascade",
            "/regulatory-lab",
            "/prescriptions",
            "/cold-chain",
            "/audit",
            "/copilot",
        ],
    },
    {
        "id": "u-mfg-004",
        "user_id": "00000000-0000-0000-0000-000000000004",
        "email": "manufacturer@mediflux.in",
        "password": "MfgPassword123!",
        "role": "manufacturer",
        "role_name": "Plant Operations Manager",
        "full_name": "Vikram Malhotra",
        "node_id": "44444444-4444-4444-4444-444444444444",
        "node_name": "Sun Pharma Formulation Plant - Baddi",
        "tier": "manufacturer",
        "region": "HP-Baddi",
        "token": "mock-manufacturer-token",
        "allowed_routes": [
            "/overview",
            "/cascade",
            "/agents",
            "/approvals",
            "/adapter-forge",
            "/cold-chain",
            "/copilot",
        ],
    },
    {
        "id": "u-dist-003",
        "user_id": "00000000-0000-0000-0000-000000000003",
        "email": "distributor@mediflux.in",
        "password": "DistPassword123!",
        "role": "distributor",
        "role_name": "Regional Logistics Director",
        "full_name": "Amitabh Sengupta",
        "node_id": "33333333-3333-3333-3333-333333333333",
        "node_name": "Northern India Regional Depot",
        "tier": "distributor",
        "region": "HR-Gurugram",
        "token": "mock-distributor-token",
        "allowed_routes": [
            "/overview",
            "/cascade",
            "/agents",
            "/approvals",
            "/cold-chain",
            "/copilot",
        ],
    },
    {
        "id": "u-stock-002",
        "user_id": "00000000-0000-0000-0000-000000000002",
        "email": "stockist@mediflux.in",
        "password": "StockPassword123!",
        "role": "stockist",
        "role_name": "Hub Inventory Manager",
        "full_name": "Harish Khurana",
        "node_id": "22222222-2222-2222-2222-222222222222",
        "node_name": "North Delhi Stockist Hub",
        "tier": "stockist",
        "region": "DL-Delhi-North",
        "token": "mock-stockist-token",
        "allowed_routes": [
            "/overview",
            "/cascade",
            "/agents",
            "/approvals",
            "/cold-chain",
            "/copilot",
        ],
    },
    {
        "id": "u-pharm-001",
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "pharmacy@mediflux.in",
        "password": "PharmPassword123!",
        "role": "pharmacy",
        "role_name": "Retail Pharmacist",
        "full_name": "Ananya Joshi, B.Pharm",
        "node_id": "11111111-1111-1111-1111-111111111111",
        "node_name": "Apollo Pharmacy - Connaught Place",
        "tier": "pharmacy",
        "region": "DL-Delhi-Central",
        "token": "mock-pharmacist-token",
        "allowed_routes": [
            "/overview",
            "/cascade",
            "/approvals",
            "/adapter-forge",
            "/prescriptions",
            "/cold-chain",
            "/copilot",
        ],
    },
    {
        "id": "u-dev-007",
        "user_id": "00000000-0000-0000-0000-000000000007",
        "email": "developer@mediflux.in",
        "password": "DevPassword123!",
        "role": "developer",
        "role_name": "Platform Integration Engineer",
        "full_name": "Rohan Deshmukh",
        "node_id": None,
        "node_name": "Developer Sandbox & Gateway",
        "tier": "developer",
        "region": "Global",
        "token": "mock-developer-token",
        "allowed_routes": [
            "/overview",
            "/agents",
            "/adapter-forge",
            "/audit",
            "/copilot",
            "/developer",
        ],
    },
]

DEMO_USERS_BY_EMAIL = {u["email"].lower(): u for u in SEEDED_DEMO_USERS}
DEMO_USERS_BY_ROLE = {u["role"]: u for u in SEEDED_DEMO_USERS}
DEMO_USERS_BY_ID = {u["id"]: u for u in SEEDED_DEMO_USERS}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str | None = None
    password: str | None = None
    role: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token: str | None = None
    token_type: str = "bearer"
    user: dict[str, Any]

    def model_post_init(self, __context: Any) -> None:
        if self.token is None:
            self.token = self.access_token


class EnrichedUserProfile(BaseModel):
    id: str
    user_id: str
    email: str | None = None
    role: str
    role_name: str | None = None
    full_name: str | None = None
    node_id: str | None = None
    node_name: str | None = None
    tier: str | None = None
    region: str | None = None
    allowed_routes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/auth/demo-users",
    summary="List Seeded Demo Users Across All 7 Supply Chain Roles",
    description="Retrieve all 7 seeded demo users with role credentials, node mappings, and route access matrices.",
)
@router.get(
    "/demo-users",
    summary="List Seeded Demo Users (Alias)",
    include_in_schema=False,
)
async def list_demo_users() -> list[dict[str, Any]]:
    """Return seeded demo users enriched with topology details."""
    users = []
    for u in SEEDED_DEMO_USERS:
        d = dict(u)
        d["label"] = d.get("role_name") or d.get("role", "").title()
        d["description"] = d.get("description") or f"Seeded account for {d['label']}."
        users.append(d)

    # If Supabase is connected, optionally verify/enrich node names
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = client.table("nodes").select("id, name, tier, region").execute()
                node_map = {n["id"]: n for n in (res.data or [])}
                for u in users:
                    if u.get("node_id") and u["node_id"] in node_map:
                        u["node_name"] = node_map[u["node_id"]].get("name", u["node_name"])
                        u["tier"] = node_map[u["node_id"]].get("tier", u["tier"])
                        u["region"] = node_map[u["node_id"]].get("region", u["region"])
        except Exception as exc:
            logger.debug("Supabase node enrichment in demo-users skipped: %s", exc)

    return users


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    summary="Authenticate User or Demo Role",
    description="Authenticate via Supabase Auth or instant seeded demo user quick-login.",
)
async def login(body: LoginRequest) -> LoginResponse:
    """Log in user and return access token + role profile."""
    # 1. Match by role selector (e.g. quick-login as "pharmacy" or "regulator")
    if body.role and body.role in DEMO_USERS_BY_ROLE:
        demo = DEMO_USERS_BY_ROLE[body.role]
        return LoginResponse(
            access_token=demo["token"],
            token_type="bearer",
            user=demo,
        )

    # 2. Match by email in seeded demo users
    if body.email:
        email_clean = body.email.strip().lower()
        if email_clean in DEMO_USERS_BY_EMAIL:
            demo = DEMO_USERS_BY_EMAIL[email_clean]
            # If password provided, verify it matches
            if body.password and body.password != demo["password"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials for demo user.",
                )
            return LoginResponse(
                access_token=demo["token"],
                token_type="bearer",
                user=demo,
            )

    # 3. Try Supabase Auth if credentials provided and configured
    if body.email and body.password and settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
        try:
            from supabase import create_client

            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
            res = client.auth.sign_in_with_password({
                "email": body.email,
                "password": body.password,
            })
            if res and res.session:
                token = res.session.access_token
                user_obj = res.user
                meta = getattr(user_obj, "user_metadata", {}) or {}
                role = meta.get("role", "pharmacy")
                node_id = meta.get("node_id")

                user_dict = {
                    "id": str(user_obj.id),
                    "user_id": str(user_obj.id),
                    "email": user_obj.email,
                    "role": role,
                    "role_name": role.title(),
                    "node_id": node_id,
                    "token": token,
                }
                return LoginResponse(
                    access_token=token,
                    token_type="bearer",
                    user=user_dict,
                )
        except Exception as exc:
            logger.warning("Supabase auth sign_in failed: %s", exc)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email, password, or demo role specified.",
    )


@router.get(
    "/auth/me",
    response_model=EnrichedUserProfile,
    summary="Get Enriched Profile for Authenticated User",
)
@router.get(
    "/me",
    response_model=EnrichedUserProfile,
    summary="Get Current User Profile (Alias)",
)
async def get_my_profile(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> EnrichedUserProfile:
    """Retrieve full profile with assigned node topology and allowed navigation routes."""
    # Find matching demo template if available
    matching_demo: dict[str, Any] | None = None
    if current_user.email and current_user.email.lower() in DEMO_USERS_BY_EMAIL:
        matching_demo = DEMO_USERS_BY_EMAIL[current_user.email.lower()]
    elif current_user.role in DEMO_USERS_BY_ROLE:
        matching_demo = DEMO_USERS_BY_ROLE[current_user.role]

    role_name = matching_demo.get("role_name", current_user.role.title()) if matching_demo else current_user.role.title()
    full_name = matching_demo.get("full_name", current_user.email or current_user.role.title()) if matching_demo else (current_user.email or current_user.role)
    node_name = matching_demo.get("node_name", "Assigned Node") if matching_demo else "Assigned Node"
    tier = matching_demo.get("tier", current_user.role) if matching_demo else current_user.role
    region = matching_demo.get("region", "National") if matching_demo else "National"
    allowed_routes = matching_demo.get("allowed_routes", []) if matching_demo else [
        "/overview", "/cascade", "/copilot"
    ]

    return EnrichedUserProfile(
        id=current_user.id or current_user.user_id,
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role,
        role_name=role_name,
        full_name=full_name,
        node_id=current_user.node_id,
        node_name=node_name,
        tier=tier,
        region=region,
        allowed_routes=allowed_routes,
    )
