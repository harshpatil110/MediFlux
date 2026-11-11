"""Base agent abstraction for MediFlux supply chain actors."""

from abc import ABC, abstractmethod
from typing import Any

from app.events.models import DomainEvent


class BasePharmaAgent(ABC):
    """Abstract base agent providing event handling and decision logic."""

    def __init__(self, agent_id: str, tier: str, name: str) -> None:
        self.agent_id = agent_id
        self.tier = tier
        self.name = name

    @abstractmethod
    async def process_event(self, event: DomainEvent) -> list[DomainEvent]:
        """Process an incoming domain event and return any triggered downstream events."""

    @abstractmethod
    async def evaluate_state(self) -> dict[str, Any]:
        """Inspect agent's internal state, inventory, and pending orders."""
