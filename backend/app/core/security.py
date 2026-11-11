"""Security and authentication helper utilities."""

from typing import Annotated

from fastapi import Header, HTTPException, status


async def verify_auth_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Validate Bearer authentication header.

    During Phase 1 foundation, permits mock/anon tokens for local health and test suites.
    """
    if not authorization:
        # Allows unauthenticated public endpoints in early development if needed
        return "anonymous"

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication header format. Expected 'Bearer <token>'",
        )

    token = parts[1]
    return token

