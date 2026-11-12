"""Compliance and verification tools for prescription analysis and Schedule H validation (Task 19)."""

import logging
import re
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client
from app.tools.pharmacy_tools import load_doctor_registry, load_drug_schedules
from app.tools.registry import tool

logger = logging.getLogger("mediflux.tools.compliance")


# -----------------------------------------------------------------------------
# Tool 1: lookup_schedule
# -----------------------------------------------------------------------------
@tool(
    name="lookup_schedule",
    description="Look up drug schedule class in CDSCO drug schedules without guessing. Returns schedule_class ('OTC', 'H', 'H1', 'X', 'unknown').",
)
def lookup_schedule(drug_name: str) -> dict[str, Any]:
    """Look up drug schedule classification against CDSCO schedules and product catalog.

    CRITICAL RULE: If a drug is not found, MUST return schedule_class='unknown' and
    MUST NOT guess or hallucinate a classification.
    """
    if not drug_name or not str(drug_name).strip():
        return {
            "drug_name": drug_name or "",
            "schedule_class": "unknown",
            "requires_prescription": True,
            "product_id": None,
            "sku": None,
            "matched": False,
            "reason": "Empty or missing drug name",
        }

    clean_name = str(drug_name).strip()
    norm_query = re.sub(r"[^a-z0-9]", "", clean_name.lower())
    base_query = re.sub(r"\d+\s*(?:mg|g|ml|mcg|iu|cap|tab).*", "", clean_name.lower()).strip()

    schedules = load_drug_schedules()

    # Database query fallback if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("drug_schedules")
                    .select("*")
                    .ilike("drug_name", f"%{clean_name}%")
                    .execute()
                )
                if res.data:
                    for row in res.data:
                        sch_type = str(row.get("schedule_class") or row.get("schedule_type") or "")
                        norm_sch = "H" if "h" in sch_type.lower() else ("OTC" if "otc" in sch_type.lower() else sch_type)
                        return {
                            "drug_name": clean_name,
                            "schedule_class": norm_sch,
                            "requires_prescription": bool(row.get("requires_prescription", True)),
                            "product_id": str(row.get("product_id") or row.get("id") or ""),
                            "sku": row.get("sku"),
                            "matched": True,
                            "reason": f"Matched in drug_schedules: {row.get('drug_name')}",
                        }
        except Exception as exc:
            logger.debug("Database drug_schedules query failed: %s", exc)

    # In-memory fixture lookup
    for item in schedules:
        p_name = str(item.get("product_name", ""))
        sku = str(item.get("sku", ""))
        p_norm = re.sub(r"[^a-z0-9]", "", p_name.lower())
        sku_norm = re.sub(r"[^a-z0-9]", "", sku.lower())

        # Exact or substring word containment or base drug name (e.g. 'paracetamol' in 'Paracetamol 650mg Tablets')
        base_match = bool(base_query and len(base_query) >= 4 and base_query in p_name.lower())
        if (norm_query and norm_query in p_norm) or (p_norm and p_norm in norm_query) or (sku_norm and norm_query == sku_norm) or base_match:
            sch_raw = str(item.get("schedule_type", "Schedule H")).strip()
            if "schedule h1" in sch_raw.lower() or "h1" in sch_raw.lower():
                sch_class = "H1"
            elif "schedule h" in sch_raw.lower() or sch_raw.upper() == "H":
                sch_class = "H"
            elif "schedule x" in sch_raw.lower() or sch_raw.upper() == "X":
                sch_class = "X"
            elif "otc" in sch_raw.lower():
                sch_class = "OTC"
            else:
                sch_class = sch_raw

            req_rx = bool(item.get("requires_prescription", sch_class != "OTC"))
            return {
                "drug_name": clean_name,
                "schedule_class": sch_class,
                "requires_prescription": req_rx,
                "product_id": item.get("product_id") or f"p-{sku.lower()}" if sku else None,
                "sku": sku or None,
                "matched": True,
                "reason": f"Matched schedule for '{p_name}' ({sch_class})",
            }

    # Strict compliance rule: NEVER GUESS or HALLUCINATE
    return {
        "drug_name": clean_name,
        "schedule_class": "unknown",
        "requires_prescription": True,
        "product_id": None,
        "sku": None,
        "matched": False,
        "reason": f"Drug '{clean_name}' not listed in CDSCO drug schedules or product catalog",
    }


# -----------------------------------------------------------------------------
# Tool 2: verify_doctor
# -----------------------------------------------------------------------------
@tool(
    name="verify_doctor",
    description="Verifies physician credentials and active registration against the national or mock doctor registry.",
)
def verify_doctor(
    registration_no: str | None,
    doctor_name: str | None = None,
) -> dict[str, Any]:
    """Verify physician credentials against national/mock doctor registry.

    Returns verified=True if found and active, else False with structured failure reason.
    """
    if not registration_no or str(registration_no).strip().upper() in ("NONE", "NULL", "MISSING", "BLANK", ""):
        return {
            "verified": False,
            "reason": "missing_registration_number",
            "doctor_record": None,
        }

    clean_reg = str(registration_no).strip().upper()
    registry = load_doctor_registry()

    # 1. Database check if configured
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                res = (
                    client.table("doctor_registry")
                    .select("*")
                    .eq("registration_no", clean_reg)
                    .execute()
                )
                if not res.data:
                    res = (
                        client.table("doctor_registry")
                        .select("*")
                        .eq("license_number", clean_reg)
                        .execute()
                    )
                if res.data:
                    doc = res.data[0]
                    is_active = doc.get("status", "active") == "active"
                    if is_active:
                        return {
                            "verified": True,
                            "reason": "verified_in_registry",
                            "doctor_record": doc,
                        }
                    return {
                        "verified": False,
                        "reason": "unknown_or_inactive_doctor",
                        "doctor_record": doc,
                    }
        except Exception as exc:
            logger.debug("Database doctor_registry query failed: %s", exc)

    # 2. In-memory registry check
    for doc in registry:
        lic = str(doc.get("license_number", "")).strip().upper()
        doc_id = str(doc.get("doctor_id", "")).strip().upper()
        reg_field = str(doc.get("registration_no", "")).strip().upper()

        if clean_reg in (lic, doc_id, reg_field):
            status = str(doc.get("status", "active")).lower()
            if status in ("active", "verified") and doc.get("verified", True) is not False:
                return {
                    "verified": True,
                    "reason": "verified_in_registry",
                    "doctor_record": doc,
                }
            return {
                "verified": False,
                "reason": "unknown_or_inactive_doctor",
                "doctor_record": doc,
            }

    return {
        "verified": False,
        "reason": "unknown_or_inactive_doctor",
        "doctor_record": None,
    }
