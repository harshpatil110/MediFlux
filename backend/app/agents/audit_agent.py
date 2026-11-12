"""Audit Agent generating regulatory plain-language audit explanations with non-blocking guarantees."""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import BaseAgent
from app.core.config import settings

logger = logging.getLogger("mediflux.agents.audit")


class AuditExplanation(BaseModel):
    """Structured response model for plain-language audit explanation."""

    explanation: str = Field(
        ...,
        description="A concise 1-2 sentence plain-language compliance and business summary of the action.",
    )


class AuditAgent(BaseAgent):
    """Autonomous audit agent summarizing compliance-critical supply chain events for regulators."""

    def __init__(
        self,
        name: str = "AuditAgent",
        router: Any = None,
    ) -> None:
        super().__init__(
            name=name,
            graph_name="audit_subsystem",
            router=router,
            system_prompt=(
                "You are the MediFlux Compliance and Audit Explanation Agent.\n"
                "Generate a clear, professional 1-2 sentence plain-language summary "
                "explaining why this action occurred, for CDSCO and regulatory audit inspection.\n"
                "Focus on clinical safety, patient benefit, and supply chain continuity."
            ),
        )

    async def generate_explanation(
        self,
        actor: str,
        action: str,
        entity_type: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Calls LLM Router to generate a 1-2 sentence plain language summary for regulatory audits.

        FALLBACK GUARANTEE: Wraps LLM call in a try/except block with a 2-second timeout.
        If it fails, times out, or LLM keys are unconfigured, returns "" immediately.
        """
        # Fast non-blocking check when offline
        if (
            not settings.NVIDIA_API_KEY
            and not settings.OPENROUTER_API_KEY
            and not settings.OLLAMA_BASE_URL
        ):
            return ""

        prompt = (
            f"Event Action: {action}\n"
            f"Actor: {actor}\n"
            f"Entity Type: {entity_type}\n"
            f"Payload Summary: {payload or {}}\n\n"
            "Provide a concise 1-2 sentence explanation suitable for a regulatory compliance log."
        )

        async def _call_llm() -> str:
            try:
                response = await self.router.complete(
                    agent=self.name,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_model=AuditExplanation,
                    task_type="audit_explanation",
                )
                if response.data and hasattr(response.data, "explanation"):
                    return str(response.data.explanation).strip()
                if response.raw_text:
                    return response.raw_text.strip()
                return ""
            except Exception as exc:
                logger.warning("Audit explanation generation failed (%s); defaulting to empty string.", exc)
                return ""

        try:
            return await asyncio.wait_for(_call_llm(), timeout=2.0)
        except TimeoutError:
            logger.warning("AuditAgent LLM explanation timed out (>2.0s); falling back to empty string.")
            return ""
        except Exception as exc:
            logger.warning("Unexpected error in AuditAgent (%s); returning empty string.", exc)
            return ""


# Singleton instance
audit_agent = AuditAgent()


async def generate_explanation(
    actor: str,
    action: str,
    entity_type: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """Non-blocking helper calling AuditAgent.generate_explanation."""
    return await audit_agent.generate_explanation(
        actor=actor,
        action=action,
        entity_type=entity_type,
        payload=payload,
    )
