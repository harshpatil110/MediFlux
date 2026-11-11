"""Safe dynamic code execution loader invoking AST guard prior to execution."""

import types
from typing import Any

from app.modules_runtime.guard import StaticASTGuard
from app.modules_runtime.registry import module_registry


class SafeModuleLoader:
    """Safely compiles and executes modules validated by StaticASTGuard."""

    @staticmethod
    def load_and_execute(
        module_name: str,
        source_code: str,
        context_globals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate safety with AST guard, then execute code into a isolated module namespace."""
        # 1. Enforce AST safety check
        StaticASTGuard.validate_code(source_code)

        # 2. Prepare namespace
        module = types.ModuleType(module_name)
        namespace = module.__dict__
        if context_globals:
            namespace.update(context_globals)

        # 3. Compile and execute
        compiled_code = compile(source_code, filename=f"<dynamic:{module_name}>", mode="exec")
        exec(compiled_code, namespace)  # noqa: S102

        # 4. Save to registry
        module_registry.register(name=module_name, code=source_code)

        return namespace

