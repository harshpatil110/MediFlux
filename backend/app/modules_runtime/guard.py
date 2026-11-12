"""Restricted Execution Guard: static AST analysis and isolated subprocess execution.

Strict constraints:
- NO WASM Sandbox.
- Static Python AST inspection enforces whitelist and blocks dangerous builtins/dunders.
- Cross-platform isolated subprocess execution (works on Windows, Linux, macOS without Unix-only resource limits).
"""

import ast
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any

from app.core.errors import MediFluxError

logger = logging.getLogger("mediflux.modules.guard")

# Whitelist of permitted imports
ALLOWED_MODULES = {
    "json",
    "math",
    "datetime",
    "decimal",
    "re",
    "typing",
    "statistics",
}

# Forbidden dangerous built-in functions
FORBIDDEN_BUILTINS = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "input",
    "breakpoint",
}

# Forbidden dunder attributes
FORBIDDEN_DUNDERS = {
    "__subclasses__",
    "__class__",
    "__bases__",
    "__mro__",
    "__globals__",
    "__code__",
    "__dict__",
    "__builtins__",
    "__import__",
}


# -----------------------------------------------------------------------------
# 1. Custom Exceptions
# -----------------------------------------------------------------------------
class GuardViolationError(MediFluxError):
    """Raised when source code violates static AST security policies."""


class ModuleTimeoutError(MediFluxError):
    """Raised when dynamic module execution exceeds hard timeout limit."""


class ModuleExecutionError(MediFluxError):
    """Raised when dynamic module execution produces runtime or output errors."""


# -----------------------------------------------------------------------------
# 2. Static AST Guard
# -----------------------------------------------------------------------------
class ASTGuard(ast.NodeVisitor):
    """Static AST analyzer verifying source code conforms to safety policies."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module not in ALLOWED_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Prohibited module import '{alias.name}'. "
                    f"Allowed modules: {sorted(ALLOWED_MODULES)}"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module not in ALLOWED_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Prohibited module import from '{node.module}'. "
                    f"Allowed modules: {sorted(ALLOWED_MODULES)}"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct calls to forbidden builtins
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_BUILTINS:
            self.violations.append(
                f"Line {node.lineno}: Prohibited call to built-in function '{node.func.id}()'"
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Block forbidden dunder attributes and dangerous introspections
        attr = node.attr
        if attr in FORBIDDEN_DUNDERS or (attr.startswith("__") and attr.endswith("__")):
            self.violations.append(
                f"Line {node.lineno}: Prohibited access to dunder attribute '{attr}'"
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Block string constants attempting to access forbidden dunder names
        if isinstance(node.value, str) and (
            node.value in FORBIDDEN_DUNDERS or (node.value.startswith("__") and node.value.endswith("__"))
        ):
            self.violations.append(
                f"Line {node.lineno}: Prohibited reference to dunder string '{node.value}'"
            )
        self.generic_visit(node)

    @classmethod
    def validate_code(cls, source_code: str) -> None:
        """Parse source code and raise GuardViolationError if any security policy is breached."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as exc:
            raise GuardViolationError(f"Syntax error during static AST analysis: {exc}") from exc

        guard = cls()
        guard.visit(tree)

        if guard.violations:
            details = "; ".join(guard.violations)
            logger.warning("ASTGuard rejected code: %s", details)
            raise GuardViolationError(f"Static AST Guard security policy violated: {details}")


# -----------------------------------------------------------------------------
# 3. Cross-Platform Isolated Subprocess Runner
# -----------------------------------------------------------------------------
RUNNER_WRAPPER = """
import sys
import json

{source_code}

if __name__ == '__main__':
    try:
        raw_in = sys.stdin.read()
        payload = json.loads(raw_in) if raw_in.strip() else {{}}
        if 'run' not in globals():
            sys.stderr.write("Module contract violation: function 'run(input: dict) -> dict' not found.")
            sys.exit(1)
        output = run(payload)
        if not isinstance(output, dict):
            sys.stderr.write(f"Module contract violation: run() must return a dict, got {{type(output).__name__}}.")
            sys.exit(1)
        sys.stdout.write(json.dumps(output))
    except Exception as exc:
        sys.stderr.write(f"Runtime error in module execution: {{exc}}")
        sys.exit(1)
"""

TEST_WRAPPER = """
import sys
import json

{source_code}

{tests_source}

if __name__ == '__main__':
    try:
        if 'test_run' in globals():
            test_run()
        sys.stdout.write(json.dumps({{"status": "passed"}}))
    except Exception as exc:
        sys.stderr.write(f"Module test execution failed: {{exc}}")
        sys.exit(1)
"""


class SubprocessRunner:
    """Executes validated Python module code in an isolated subprocess with strict limits."""

    MAX_OUTPUT_BYTES = 1_048_576  # 1 MB output limit

    @classmethod
    def execute_module(
        cls,
        source_code: str,
        input_data: dict[str, Any],
        timeout: float = 2.0,
    ) -> tuple[dict[str, Any], float]:
        """Execute module in an isolated Python subprocess passing JSON via stdin."""
        script = RUNNER_WRAPPER.format(source_code=source_code)
        input_json = json.dumps(input_data)

        # Isolated environment: minimal variables, stripping API keys and secrets
        clean_env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
        }

        start_time = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-c", script],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=clean_env,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("Module execution timed out after %.2fms (timeout %.2fs)", duration_ms, timeout)
            raise ModuleTimeoutError(f"Module execution timed out after {timeout} seconds") from exc
        except Exception as exc:
            raise ModuleExecutionError(f"Subprocess invocation failure: {exc}") from exc

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if len(proc.stdout) > cls.MAX_OUTPUT_BYTES:
            raise ModuleExecutionError(
                f"Module stdout exceeded maximum allowed limit ({cls.MAX_OUTPUT_BYTES} bytes)"
            )

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or f"Process exited with code {proc.returncode}"
            logger.error("Module execution failed: %s", err_msg)
            raise ModuleExecutionError(f"Module execution failed: {err_msg}")

        try:
            result_data = json.loads(proc.stdout)
            return result_data, duration_ms
        except json.JSONDecodeError as exc:
            raise ModuleExecutionError(f"Failed to parse module JSON output: {proc.stdout}") from exc

    @classmethod
    def execute_tests(
        cls,
        source_code: str,
        tests_source: str,
        timeout: float = 3.0,
    ) -> bool:
        """Execute verification code for a module in an isolated subprocess."""
        script = TEST_WRAPPER.format(source_code=source_code, tests_source=tests_source)
        clean_env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        }

        try:
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=clean_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise ModuleTimeoutError(f"Module tests timed out after {timeout}s") from exc

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or f"Exit code {proc.returncode}"
            logger.warning("Module tests failed: %s", err_msg)
            raise ModuleExecutionError(f"Module unit tests failed: {err_msg}")

        return True
