"""Safe Project Persistence, Atomic File Writing & Recovery (Phase 11).

Provides:
- Atomic JSON writing via temporary file and atomic replace.
- Backup creation (.bak) before writing critical metadata.
- Recovery from incomplete, 0-byte, or corrupted JSON files.
- Path traversal protection and safe filename sanitization.
- Checksum validation for media files and artifacts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("openmontage.persistence")

CURRENT_PROJECT_SCHEMA_VERSION = "2.0"


class PersistenceError(Exception):
    """Raised when atomic write or recovery fails."""


def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters and path traversal segments."""
    cleaned = Path(filename).name
    # Remove null bytes and path separators
    cleaned = cleaned.replace("\0", "").replace("/", "").replace("\\", "")
    # Fallback if empty or solely special characters
    if not cleaned or cleaned in (".", ".."):
        return "unnamed_file"
    return cleaned


def resolve_safe_path(base_dir: Path, relative_path: str | Path) -> Path:
    """Resolve a path relative to base_dir and ensure it does not escape base_dir."""
    base_resolved = base_dir.resolve()
    target_resolved = (base_dir / relative_path).resolve()
    try:
        target_resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise PermissionError(f"Path traversal detected: {relative_path} attempts to escape {base_dir}") from exc
    return target_resolved


def compute_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of file for integrity validation."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Cannot compute checksum; file not found: {file_path}")
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_json_atomic(
    target_path: Path,
    data: Any,
    indent: int = 2,
    backup: bool = True,
) -> None:
    """Atomically write data to target_path using a temp file and replace.
    
    If target_path already exists and backup is True, creates a .bak snapshot.
    Uses fsync to ensure data is physically committed to disk before renaming.
    """
    target_path = Path(target_path).resolve()
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    backup_path = target_dir / f"{target_path.name}.bak"

    # Step 1: Backup existing file if requested and present
    if backup and target_path.is_file() and target_path.stat().st_size > 0:
        try:
            shutil.copy2(target_path, backup_path)
        except Exception as e:
            logger.warning("Could not create backup of %s: %s", target_path, e)

    # Step 2: Write to a temp file in the same directory (ensures same filesystem for atomic rename)
    temp_file = None
    try:
        temp_fd, temp_path_str = tempfile.mkstemp(
            prefix=f".{target_path.stem}_tmp_",
            suffix=".json",
            dir=target_dir,
        )
        temp_file = Path(temp_path_str)

        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Step 3: Atomic replace
        os.replace(temp_file, target_path)
    except Exception as e:
        if temp_file and temp_file.exists():
            with tempfile.suppress():
                temp_file.unlink(missing_ok=True)
        raise PersistenceError(f"Failed to atomically write {target_path}: {e}") from e


_MISSING = object()


def read_json_with_recovery(
    target_path: Path,
    default: Any = _MISSING,
    default_factory: Optional[Callable[[], Any]] = None,
) -> Any:
    """Read JSON file with automatic fallback to .bak if primary is corrupted or empty."""
    target_path = Path(target_path).resolve()
    backup_path = target_path.parent / f"{target_path.name}.bak"

    # Try reading primary file
    if target_path.is_file() and target_path.stat().st_size > 0:
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning("Primary JSON file %s is corrupted (%s). Attempting recovery from backup...", target_path, e)

    # Primary failed or missing, try backup
    if backup_path.is_file() and backup_path.stat().st_size > 0:
        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                recovered_data = json.load(f)
            logger.info("Successfully recovered data from backup: %s", backup_path)
            # Restore recovered data to primary path
            write_json_atomic(target_path, recovered_data, backup=False)
            return recovered_data
        except Exception as e:
            logger.error("Backup recovery also failed for %s: %s", backup_path, e)

    # Both failed or neither exists
    if default is not _MISSING:
        return default
    if default_factory is not None:
        return default_factory()
    raise FileNotFoundError(f"JSON file {target_path} not found and no valid backup available.")
