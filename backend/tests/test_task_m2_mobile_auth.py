"""Task M2: Authentication, Secure Session, and Role-Aware Navigation Verification Tests.

Validates:
1. Backend GET /api/v1/me and GET /api/v1/auth/me profile & bound node resolution.
2. Permission resolution (can_view_approvals, can_decide_approvals) across roles.
3. POST /api/v1/auth/login with demo roles and email/password.
4. POST /api/v1/auth/refresh token rotation and expired token 401 handling.
5. TOKEN_EXPIRED error structure on invalid/expired tokens.
6. Presence and structure of mobile auth files (roleMap.ts, AuthContext.tsx, RoleNodeHeaderBadge.tsx, supabase.ts, settings.tsx, login.tsx).
"""

from __future__ import annotations

from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MOBILE_DIR = ROOT_DIR / "mobile"


class TestMobileAuthTaskM2:
    """Automated test suite verifying full compliance of Task M2."""

    def test_mobile_m2_file_structure(self) -> None:
        """Verify presence of all Task M2 required files and components."""
        required_paths = [
            MOBILE_DIR / "src" / "lib" / "supabase.ts",
            MOBILE_DIR / "src" / "lib" / "storage.ts",
            MOBILE_DIR / "src" / "features" / "auth" / "roleMap.ts",
            MOBILE_DIR / "src" / "features" / "auth" / "AuthContext.tsx",
            MOBILE_DIR / "src" / "components" / "RoleNodeHeaderBadge.tsx",
            MOBILE_DIR / "app" / "_layout.tsx",
            MOBILE_DIR / "app" / "(tabs)" / "_layout.tsx",
            MOBILE_DIR / "app" / "(auth)" / "login.tsx",
            MOBILE_DIR / "app" / "(auth)" / "settings.tsx",
            MOBILE_DIR / ".env.local",
            MOBILE_DIR / ".env.example",
        ]
        for path in required_paths:
            assert path.exists(), f"Required Task M2 file missing: {path}"

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self) -> None:
        """Verify GET /api/v1/me returns 401 without authorization header."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/me")
            assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_pharmacy_role(self) -> None:
        """Verify GET /api/v1/me returns pharmacy role with view-only approvals permission."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-pharmacist-token"}
            res = await client.get("/api/v1/me", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert data["role"] == "pharmacy"
            assert data["email"] == "pharmacy@mediflux.in"
            assert data["node_id"] is not None
            assert "Apollo Pharmacy" in data["node_name"]
            assert data["permissions"]["can_view_approvals"] is True
            assert data["permissions"]["can_decide_approvals"] is False

    @pytest.mark.asyncio
    async def test_get_me_stockist_role(self) -> None:
        """Verify GET /api/v1/me returns stockist role with can_decide_approvals=True."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-stockist-token"}
            res = await client.get("/api/v1/me", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert data["role"] == "stockist"
            assert data["email"] == "stockist@mediflux.in"
            assert data["permissions"]["can_view_approvals"] is True
            assert data["permissions"]["can_decide_approvals"] is True

    @pytest.mark.asyncio
    async def test_get_me_admin_role(self) -> None:
        """Verify GET /api/v1/me returns admin role with full decision rights."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer mock-admin-token"}
            res = await client.get("/api/v1/me", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert data["role"] == "admin"
            assert data["permissions"]["can_decide_approvals"] is True

    @pytest.mark.asyncio
    async def test_auth_login_demo_role(self) -> None:
        """Verify POST /api/v1/auth/login works for quick-login role selector."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/v1/auth/login", json={"role": "pharmacy"})
            assert res.status_code == 200
            data = res.json()
            assert data["access_token"] == "mock-pharmacist-token"
            assert data["user"]["role"] == "pharmacy"

    @pytest.mark.asyncio
    async def test_auth_login_credentials(self) -> None:
        """Verify POST /api/v1/auth/login works with seeded demo email and password."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "pharmacy@mediflux.in", "password": "PharmPassword123!"},
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data

    @pytest.mark.asyncio
    async def test_auth_login_invalid_password(self) -> None:
        """Verify POST /api/v1/auth/login rejects wrong password with 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "pharmacy@mediflux.in", "password": "WrongPassword999!"},
            )
            assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_refresh_token_success(self) -> None:
        """Verify POST /api/v1/auth/refresh returns a fresh access token."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "ref-mock-pharmacist-token"},
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_auth_refresh_token_expired(self) -> None:
        """Verify POST /api/v1/auth/refresh returns 401 TOKEN_EXPIRED when expired token is sent."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "expired-token-simulated"},
            )
            assert res.status_code == 401
            body = res.json()
            error_code = body.get("error", {}).get("code") or body.get("detail", {}).get("code")
            assert error_code == "TOKEN_EXPIRED"

    @pytest.mark.asyncio
    async def test_expired_token_on_protected_route(self) -> None:
        """Verify calling protected /api/v1/me with expired token returns 401 TOKEN_EXPIRED."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": "Bearer token-expired-xyz"}
            res = await client.get("/api/v1/me", headers=headers)
            assert res.status_code == 401
            body = res.json()
            error_code = body.get("error", {}).get("code") or body.get("detail", {}).get("code")
            assert error_code == "TOKEN_EXPIRED"
