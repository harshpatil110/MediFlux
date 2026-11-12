"""Module contract, declared kinds, and schemas for dynamic business rules."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ModuleKind = Literal[
    "margin_rules",
    "volume_discount",
    "credit_check_rules",
    "price_ceiling",
    "traceability_rules",
    "adapter",
]

ModuleStatus = Literal["staging", "active", "retired"]


class ModuleVersion(BaseModel):
    """Represents a specific version of a dynamic business rule or adapter module."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Unique module identifier, e.g. margin_rules")
    version: int = Field(default=1, description="Sequential integer version")
    kind: str = Field(..., description="Category of rule or adapter")
    source_code: str = Field(..., description="Executable Python code adhering to def run(input: dict) -> dict")
    tests_source: str = Field(..., description="Executable verification code def test_run() or test assertions")
    status: ModuleStatus = Field(default="staging", description="staging, active, or retired")
    checksum: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = Field(default="system")


class ModuleExecutionRequest(BaseModel):
    """Input payload to invoke an active dynamic module."""

    module_name: str
    input_data: dict[str, Any] = Field(default_factory=dict)


class ModuleExecutionResponse(BaseModel):
    """Output payload from dynamic module execution."""

    module_name: str
    version: int
    output: dict[str, Any]
    execution_time_ms: float
    status: str = "success"
