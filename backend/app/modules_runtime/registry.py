"""In-memory and persistent registry for dynamic supply-chain modules."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ModuleMetadata(BaseModel):
    """Metadata describing an installed dynamic module."""

    name: str
    version: str = "1.0.0"
    author: str = "system"
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active: bool = True


class ModuleRegistry:
    """Registry maintaining active and verified dynamic modules."""

    def __init__(self) -> None:
        self._modules: dict[str, dict[str, Any]] = {}

    def register(self, name: str, code: str, metadata: ModuleMetadata | None = None) -> None:
        """Register a verified dynamic module."""
        meta = metadata or ModuleMetadata(name=name)
        self._modules[name] = {
            "code": code,
            "metadata": meta,
        }

    def get(self, name: str) -> dict[str, Any] | None:
        """Retrieve registered module."""
        return self._modules.get(name)

    def list_all(self) -> list[ModuleMetadata]:
        """List metadata of all registered modules."""
        return [entry["metadata"] for entry in self._modules.values()]


module_registry = ModuleRegistry()
