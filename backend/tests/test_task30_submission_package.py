"""Test suite for Task 30: MediFlux MVP Submission Package & Quality Standards.

Verifies:
  1. All submission artifacts exist, are non-empty, and contain required sections.
  2. docs/openapi.json is valid OpenAPI 3.x with registered endpoints.
  3. Empirical numbers in docs/BENCHMARKS.md match docs/benchmark_results.json.
  4. Token numbers in docs/TOKEN_AND_COST_REPORT.md match docs/token_report_results.json.
  5. Security check (scripts/check_secrets.py) passes with zero leaked credentials.
  6. In-process demo runner executes all 10 acts successfully in deterministic replay mode.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def test_submission_documentation_files_exist() -> None:
    """Verify all required RFP documentation files exist and are non-empty."""
    required_docs = [
        "docs/BENCHMARKS.md",
        "docs/TOKEN_AND_COST_REPORT.md",
        "docs/ARCHITECTURE.md",
        "docs/POST_MVP.md",
        "docs/SECURITY_AND_COMPLIANCE.md",
        "docs/DEMO_SCRIPT.md",
        "docs/openapi.json",
        "docs/benchmark_results.json",
        "docs/token_report_results.json",
        "docs/specs/task-30-spec.md",
        "README.md",
        "docs/HOW_AI_BUILT_THIS.md",
    ]

    for doc in required_docs:
        doc_path = ROOT_DIR / doc
        assert doc_path.exists(), f"Missing required submission file: {doc}"
        assert doc_path.stat().st_size > 100, f"File {doc} appears empty or truncated"


def test_openapi_json_schema_validity() -> None:
    """Verify docs/openapi.json is valid JSON with required OpenAPI fields."""
    openapi_file = ROOT_DIR / "docs" / "openapi.json"
    assert openapi_file.exists(), "docs/openapi.json does not exist"

    with open(openapi_file, encoding="utf-8") as f:
        schema = json.load(f)

    assert "openapi" in schema, "OpenAPI version missing"
    assert "info" in schema, "API info block missing"
    assert "paths" in schema, "API paths block missing"
    paths = schema["paths"]
    assert len(paths) >= 20, f"Expected at least 20 endpoints registered, got {len(paths)}"

    # Core required endpoints
    assert "/api/v1/events/sale" in paths or "/api/v1/events" in paths
    assert "/api/v1/simulator/pos" in paths
    assert "/api/v1/adapters/generate" in paths or "/api/v1/adapters" in paths
    assert "/api/v1/modules" in paths
    assert "/api/v1/audit/verify" in paths


def test_benchmarks_match_raw_measurements() -> None:
    """Verify docs/BENCHMARKS.md matches values in docs/benchmark_results.json."""
    json_path = ROOT_DIR / "docs" / "benchmark_results.json"
    md_path = ROOT_DIR / "docs" / "BENCHMARKS.md"

    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    md_content = md_path.read_text(encoding="utf-8")

    # Check hardware fingerprint reflects in MD
    hw = data["hardware"]
    assert str(hw["cpu_count_logical"]) in md_content
    assert hw["os"] in md_content

    # Check single-event p50 latency for concurrency 1
    single = data["benchmarks"]["event_ingestion"]
    c1_p50 = str(single[0]["p50_ms"])
    assert c1_p50 in md_content, f"p50 latency {c1_p50} ms not found in BENCHMARKS.md"


def test_token_report_matches_raw_telemetry() -> None:
    """Verify docs/TOKEN_AND_COST_REPORT.md matches docs/token_report_results.json."""
    json_path = ROOT_DIR / "docs" / "token_report_results.json"
    md_path = ROOT_DIR / "docs" / "TOKEN_AND_COST_REPORT.md"

    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    md_content = md_path.read_text(encoding="utf-8")

    casc = data["per_cascade_summary"]
    total_tokens_str = f"{casc['total_tokens']}"
    assert total_tokens_str in md_content, f"Total cascade tokens {total_tokens_str} not in report"


def test_secrets_check_passes() -> None:
    """Verify check_secrets.py runs cleanly without finding committed credentials."""
    python_bin = sys.executable
    res = subprocess.run(
        [python_bin, "-m", "scripts.check_secrets"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"check_secrets failed:\n{res.stdout}\n{res.stderr}"


@pytest.mark.asyncio
async def test_demo_runner_all_acts_in_process() -> None:
    """Verify all 10 demo steps execute cleanly against in-process FastAPI app in replay mode."""
    from app.core.config import settings

    orig_demo = settings.DEMO_MODE
    orig_cache = settings.LLM_CACHE_MODE

    try:
        settings.DEMO_MODE = True
        settings.LLM_CACHE_MODE = "replay"

        from scripts.run_demo import (
            execute_act_1,
            execute_act_2,
            execute_act_3,
            execute_act_4,
            execute_act_5,
            execute_act_6,
            execute_act_7,
            execute_act_8,
            execute_act_9,
            execute_act_10,
        )

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            assert await execute_act_1(client) is True
            assert await execute_act_2(client) is True
            assert await execute_act_3(client) is True
            assert await execute_act_4(client) is True
            assert await execute_act_5(client) is True
            assert await execute_act_6(client) is True
            assert await execute_act_7(client) is True
            assert await execute_act_8(client) is True
            assert await execute_act_9(client) is True
            assert await execute_act_10(client) is True
    finally:
        settings.DEMO_MODE = orig_demo
        settings.LLM_CACHE_MODE = orig_cache
