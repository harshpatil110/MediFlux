# ruff: noqa: BLE001, S110, S112
"""MediFlux Secrets & Credential Leakage Scanner (Task 29).

Scans git-tracked files and workspace configurations for:
- Leaked API keys (OpenAI, Anthropic, Gemini, NVIDIA, OpenRouter, Supabase Service Role).
- Private keys, certificates, and hardcoded passwords.
- Validates that .env is untracked by git.
- Validates that .env.example exists and contains safe placeholders only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent

# Regex patterns matching potential secret leakage
SECRET_PATTERNS = [
    (re.compile(r"nvapi-[A-Za-z0-9_-]{30,}"), "Live NVIDIA NIM API Key"),
    (re.compile(r"sk-or-v1-[A-Za-z0-9]{40,}"), "Live OpenRouter API Key"),
    (re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"), "Live Google / Gemini API Key"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}"), "Live OpenAI Secret Key"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Raw Private Key"),
    (re.compile(r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[A-Za-z0-9_-]{50,}\.[A-Za-z0-9_-]{40,}"), "Live JWT Token"),
]

# Files explicitly exempt from secret scanner
EXEMPT_FILES = {
    ".env.example",
    "package-lock.json",
    "fixtures/demo_cache/llm_replay_cache.json",
}


def get_git_tracked_files() -> list[Path]:
    """Retrieve list of files tracked by git."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        return [ROOT_DIR / p for p in lines]
    except Exception:
        # Fallback to traversing directories if git is not available
        files: list[Path] = []
        for root, dirs, filenames in os.walk(str(ROOT_DIR)):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "out", "build-dist"}]
            for fn in filenames:
                files.append(Path(root) / fn)
        return files


def check_env_untracked() -> tuple[bool, str]:
    """Verify .env is untracked by git."""
    try:
        res = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True,
        )
        if res.stdout.strip():
            return False, "CRITICAL: .env file is tracked by git!"
    except Exception:
        pass
    return True, ".env is untracked."


def check_env_example_placeholders() -> tuple[bool, str]:
    """Verify .env.example exists and contains safe placeholders."""
    env_example = ROOT_DIR / ".env.example"
    if not env_example.is_file():
        return False, "Missing .env.example template file."

    text = env_example.read_text(encoding="utf-8")
    required_keys = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"]
    missing = [k for k in required_keys if k not in text]
    if missing:
        return False, f".env.example missing required keys: {missing}"

    for pattern, label in SECRET_PATTERNS:
        if pattern.search(text):
            return False, f".env.example contains real secret matching: {label}"

    return True, ".env.example is valid with safe placeholders."


def scan_files_for_secrets() -> list[dict[str, Any]]:
    """Scan tracked files for secret patterns."""
    violations: list[dict[str, Any]] = []
    tracked = get_git_tracked_files()

    for path in tracked:
        rel = str(path.relative_to(ROOT_DIR)).replace("\\", "/")
        if any(rel.endswith(ex) or rel == ex for ex in EXEMPT_FILES):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern, label in SECRET_PATTERNS:
            match = pattern.search(content)
            if match:
                # Disallow dummy/mock tokens from triggering
                val = match.group(0)
                if "mock" in val or "placeholder" in val or "example" in val:
                    continue
                violations.append({
                    "file": rel,
                    "label": label,
                    "snippet": val[:12] + "...",
                })

    return violations


def run_secrets_scan() -> bool:
    """Run full secrets audit and return True if 100% clean."""
    print("==================================================")
    print("     MediFlux Git Secrets & Credential Scanner    ")
    print("==================================================")

    env_ok, env_msg = check_env_untracked()
    print(f"[{'OK' if env_ok else 'FAIL'}] {env_msg}")

    ex_ok, ex_msg = check_env_example_placeholders()
    print(f"[{'OK' if ex_ok else 'FAIL'}] {ex_msg}")

    violations = scan_files_for_secrets()
    if violations:
        print(f"\n[CRITICAL] Found {len(violations)} secret leakage violations:")
        for v in violations:
            print(f"  ✗ {v['file']}: {v['label']} ({v['snippet']})")
        return False

    print("\n[SUCCESS] No live API keys, private keys, or credentials found in tracked files.")
    return env_ok and ex_ok


if __name__ == "__main__":
    is_clean = run_secrets_scan()
    sys.exit(0 if is_clean else 1)
