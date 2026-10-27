"""OpenMontage Storage Paths & Application Data Governance (Phase 12).

Separates application binaries from user data in compliance with Windows standards.
Routes settings, preferences, databases, logs, and caches to %LOCALAPPDATA%\\OpenMontage
while preserving backward compatibility with workspace development directories.
"""

from __future__ import annotations

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent


class StoragePaths:
    """Manages application storage locations and user data isolation."""

    def __init__(self, base_data_dir: Optional[Path] = None) -> None:
        self._explicit_base = base_data_dir is not None
        if base_data_dir:
            self._root = Path(base_data_dir).resolve()
        elif "OPENMONTAGE_DATA_DIR" in os.environ:
            self._root = Path(os.environ["OPENMONTAGE_DATA_DIR"]).resolve()
        else:
            # On Windows, check LOCALAPPDATA for production installs
            local_appdata = os.environ.get("LOCALAPPDATA")
            is_installed = getattr(sys, "frozen", False) or not (REPO_ROOT / ".git").is_dir()
            
            if local_appdata and is_installed:
                self._root = Path(local_appdata) / "OpenMontage"
            else:
                # In development/workspace mode, default to REPO_ROOT for zero-friction dev
                self._root = REPO_ROOT

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create required application storage trees safely."""
        for d in (self.projects_dir, self.config_dir, self.cache_dir, self.logs_dir, self.models_dir):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning("Could not create directory %s: %s", d, e)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def projects_dir(self) -> Path:
        if not self._explicit_base:
            custom = os.environ.get("OPENMONTAGE_PROJECTS_DIR")
            if custom:
                return Path(custom).resolve()
        return self._root / "projects"

    @property
    def config_dir(self) -> Path:
        return self._root / "config"

    @property
    def jobs_db_path(self) -> Path:
        return self.config_dir / "jobs.db"

    @property
    def settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def cache_dir(self) -> Path:
        return self._root / ".cache"

    @property
    def logs_dir(self) -> Path:
        return self._root / "logs"

    @property
    def models_dir(self) -> Path:
        custom = os.environ.get("OPENMONTAGE_MODELS_DIR")
        if custom:
            return Path(custom).resolve()
        return self._root / "models"

    def get_all_project_dirs(self) -> list[Path]:
        """Discover projects across both configured storage and dev workspace."""
        found: dict[str, Path] = {}

        # Primary configured projects directory
        if self.projects_dir.is_dir():
            for entry in self.projects_dir.iterdir():
                if entry.is_dir() and not entry.name.startswith((".", "_")):
                    found[entry.name] = entry

        # Fallback / legacy workspace projects directory
        legacy_dir = REPO_ROOT / "projects"
        if legacy_dir.is_dir() and legacy_dir.resolve() != self.projects_dir.resolve():
            for entry in legacy_dir.iterdir():
                if entry.is_dir() and not entry.name.startswith((".", "_")) and entry.name not in found:
                    found[entry.name] = entry

        return list(found.values())

    def resolve_project_dir(self, project_id: str) -> Optional[Path]:
        """Locate project directory across primary and legacy paths."""
        p = self.projects_dir / project_id
        if p.is_dir():
            return p
        legacy = REPO_ROOT / "projects" / project_id
        if legacy.is_dir():
            return legacy
        return None

    def migrate_projects(self, source_dir: Path, overwrite: bool = False) -> int:
        """Migrate projects from a source directory to primary storage without data loss."""
        if not source_dir.is_dir():
            return 0
        migrated = 0
        for item in source_dir.iterdir():
            if item.is_dir() and not item.name.startswith((".", "_")):
                dest = self.projects_dir / item.name
                if not dest.exists() or overwrite:
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                    migrated += 1
                    logger.info("Migrated project %s to %s", item.name, dest)
        return migrated


_instance: Optional[StoragePaths] = None


def get_storage() -> StoragePaths:
    """Obtain the global StoragePaths singleton."""
    global _instance
    if _instance is None:
        _instance = StoragePaths()
    return _instance
