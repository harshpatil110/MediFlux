"""Static AST Security Guard for generated dynamic modules.

Strict constraint: NO WASM Sandbox. Static Python AST inspection ensures safety.
"""

import ast
from typing import Any

from app.core.errors import ModuleSecurityViolation

# Prohibited dangerous modules and builtins
DISALLOWED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "requests",
    "urllib",
    "http.client",
    "ftplib",
    "telnetlib",
    "pickle",
    "ctypes",
    "importlib",
}

DISALLOWED_BUILTINS = {
    "eval",
    "exec",
    "compile",
    "open",
    "__import__",
    "input",
    "breakpoint",
}


class StaticASTGuard(ast.NodeVisitor):
    """Inspects Python Abstract Syntax Trees for dangerous operations."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in DISALLOWED_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Prohibited module import '{alias.name}'"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in DISALLOWED_MODULES:
                self.violations.append(
                    f"Line {node.lineno}: Prohibited module import from '{node.module}'"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        # Check direct calls to disallowed builtins
        if isinstance(node.func, ast.Name) and node.func.id in DISALLOWED_BUILTINS:
            self.violations.append(
                f"Line {node.lineno}: Prohibited builtin call '{node.func.id}()'"
            )
        self.generic_visit(node)

    @classmethod
    def validate_code(cls, source_code: str) -> None:
        """Parse source code into an AST and assert that no safety violations exist.

        Raises:
            ModuleSecurityViolation: If forbidden imports or calls are discovered.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as err:
            raise ModuleSecurityViolation(f"Syntax error during AST safety check: {err}") from err

        guard = cls()
        guard.visit(tree)

        if guard.violations:
            violation_details = "; ".join(guard.violations)
            raise ModuleSecurityViolation(
                f"Static AST Guard rejected code due to violations: {violation_details}"
            )

