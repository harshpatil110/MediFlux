"""Root alias for Sovereign Prescription graph."""

import sys
from pathlib import Path

# Add backend directory to sys.path if not present
backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.graphs.prescription import (  # noqa: E402
    DrugItem,
    PrescriptionParsedData,
    PrescriptionState,
    build_prescription_graph,
    clear_prescription_store,
    decision_node,
    doctor_verification_node,
    get_prescription,
    list_compliance_logs,
    prescription_graph,
    prescription_parser_node,
    run_prescription_graph,
    save_compliance_log,
    save_prescription,
    schedule_compliance_node,
)

__all__ = [
    "DrugItem",
    "PrescriptionParsedData",
    "PrescriptionState",
    "build_prescription_graph",
    "clear_prescription_store",
    "decision_node",
    "doctor_verification_node",
    "get_prescription",
    "list_compliance_logs",
    "prescription_graph",
    "prescription_parser_node",
    "run_prescription_graph",
    "save_compliance_log",
    "save_prescription",
    "schedule_compliance_node",
]
