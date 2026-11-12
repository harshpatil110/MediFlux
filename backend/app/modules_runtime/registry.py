"""Module registry: version management, test validation, atomic hot-swapping, and execution."""

import hashlib
import logging
import uuid
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client
from app.modules_runtime.contract import ModuleVersion
from app.modules_runtime.guard import (
    ASTGuard,
    ModuleExecutionError,
    SubprocessRunner,
)

logger = logging.getLogger("mediflux.modules.registry")


class ModuleRegistry:
    """Manages versioned dynamic modules with static safety checks, test execution, and atomic hot-swapping."""

    def __init__(self) -> None:
        # In-memory storage for active modules and full version history
        self._active_modules: dict[str, ModuleVersion] = {}
        self._all_versions: dict[str, list[ModuleVersion]] = {}

    def create_version(
        self,
        name: str,
        kind: str,
        code: str,
        tests_source: str,
        created_by: str = "system",
    ) -> ModuleVersion:
        """Validate safety with AST guard and register a new version with 'staging' status."""
        # 1. Enforce static AST security policies on code and tests
        ASTGuard.validate_code(code)
        ASTGuard.validate_code(tests_source)

        # 2. Determine sequential version number
        existing_versions = self.list_versions(name)
        next_ver = max([v.version for v in existing_versions], default=0) + 1

        checksum = hashlib.sha256(code.encode("utf-8")).hexdigest()

        mod_version = ModuleVersion(
            id=str(uuid.uuid4()),
            name=name,
            version=next_ver,
            kind=kind,
            source_code=code,
            tests_source=tests_source,
            status="staging",
            checksum=checksum,
            created_by=created_by,
        )

        # 3. Persist to database if available
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                client.table("modules").insert({
                    "id": mod_version.id,
                    "name": mod_version.name,
                    "version": mod_version.version,
                    "kind": mod_version.kind,
                    "source_code": mod_version.source_code,
                    "tests_source": mod_version.tests_source,
                    "status": mod_version.status,
                    "checksum": mod_version.checksum,
                    "created_by": mod_version.created_by,
                }).execute()
            except Exception as exc:
                logger.warning("DB modules insert failed (%s); stored in local memory.", exc)

        if name not in self._all_versions:
            self._all_versions[name] = []
        self._all_versions[name].append(mod_version)

        logger.info("Created module version: name=%s version=%d status=staging", name, next_ver)
        return mod_version

    def run_tests(self, name: str, version: int) -> bool:
        """Run the module's tests inside an isolated subprocess."""
        mod = self.get_version(name, version)
        if not mod:
            raise ModuleExecutionError(f"Module '{name}' version {version} not found")

        logger.info("Executing tests for module: %s v%d", name, version)
        return SubprocessRunner.execute_tests(
            source_code=mod.source_code,
            tests_source=mod.tests_source,
        )

    def activate(self, name: str, version: int) -> ModuleVersion:
        """Run tests, retire current active version, and atomically activate the target version."""
        # 1. Verify tests pass first
        self.run_tests(name, version)

        # 2. Retire current active version
        current_active = self._active_modules.get(name)
        if current_active:
            current_active.status = "retired"
            self._update_db_status(current_active.id, "retired")

        # 3. Activate target version
        target = self.get_version(name, version)
        if not target:
            raise ModuleExecutionError(f"Module '{name}' version {version} not found")

        target.status = "active"
        self._update_db_status(target.id, "active")

        # 4. Atomic in-memory cache update (instant hot-swap)
        self._active_modules[name] = target
        logger.info("Module [%s] hot-swapped to active version v%d", name, version)
        return target

    def rollback(self, name: str) -> ModuleVersion:
        """Retire the current active version and roll back to the previous stable version."""
        current_active = self._active_modules.get(name)
        if not current_active:
            raise ModuleExecutionError(f"No active version found to roll back for '{name}'")

        # Find previous version
        versions = sorted(self.list_versions(name), key=lambda v: v.version)
        previous_candidates = [v for v in versions if v.version < current_active.version]

        if not previous_candidates:
            raise ModuleExecutionError(f"No prior version exists to roll back module '{name}'")

        target_prev = previous_candidates[-1]

        # Retire current
        current_active.status = "retired"
        self._update_db_status(current_active.id, "retired")

        # Activate target previous
        target_prev.status = "active"
        self._update_db_status(target_prev.id, "active")

        self._active_modules[name] = target_prev
        logger.info(
            "Module [%s] rolled back from v%d to v%d",
            name,
            current_active.version,
            target_prev.version,
        )
        return target_prev

    def run_module(self, name: str, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the currently active version of a module in an isolated subprocess."""
        active_mod = self.get_active(name)
        if not active_mod:
            raise ModuleExecutionError(f"No active module found for '{name}'")

        result, duration_ms = SubprocessRunner.execute_module(
            source_code=active_mod.source_code,
            input_data=input_data,
        )
        logger.debug("Module [%s v%d] executed in %.2fms", name, active_mod.version, duration_ms)
        return result

    def get_active(self, name: str) -> ModuleVersion | None:
        """Fetch the active version of a module from cache or database."""
        if name in self._active_modules:
            return self._active_modules[name]

        # Attempt to load from database
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                res = (
                    client.table("modules")
                    .select("*")
                    .eq("name", name)
                    .eq("status", "active")
                    .order("version", desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    row = res.data[0]
                    mod = ModuleVersion(
                        id=row["id"],
                        name=row["name"],
                        version=row["version"],
                        kind=row["kind"],
                        source_code=row["source_code"],
                        tests_source=row["tests_source"],
                        status="active",
                        checksum=row.get("checksum"),
                        created_by=row.get("created_by", "system"),
                    )
                    self._active_modules[name] = mod
                    return mod
            except Exception as exc:
                logger.debug("DB fetch active module failed: %s", exc)

        return None

    def get_version(self, name: str, version: int) -> ModuleVersion | None:
        """Retrieve a specific version of a module."""
        for v in self.list_versions(name):
            if v.version == version:
                return v
        return None

    def list_versions(self, name: str) -> list[ModuleVersion]:
        """Return all versions for a module."""
        return self._all_versions.get(name, [])

    def list_active_modules(self) -> list[ModuleVersion]:
        """Return all currently active modules."""
        return list(self._active_modules.values())

    def _update_db_status(self, module_id: str, new_status: str) -> None:
        """Update module status in Supabase if configured."""
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                client.table("modules").update({"status": new_status}).eq("id", module_id).execute()
            except Exception as exc:
                logger.debug("DB status update failed: %s", exc)

    def clear(self) -> None:
        """Clear registry in-memory state (testing helper)."""
        self._active_modules.clear()
        self._all_versions.clear()


# Global Singleton Registry Instance
module_registry = ModuleRegistry()
