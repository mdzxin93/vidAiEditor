"""OpenMontage Windows Distribution Builder (Phase 12).

Automates:
1. React Studio frontend production compilation (vite build).
2. Clean distribution tree staging in dist/OpenMontage-Windows-Portable.
3. Verification of launcher scripts and dependencies.
4. Packaging into a ready-to-run ZIP distribution.
"""

from __future__ import annotations

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

# Safe stdout on Windows command lines
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
STAGE_DIR = DIST_DIR / "OpenMontage-v1.0.0-Windows"


def build_distribution() -> int:
    print("=" * 65)
    print("    OPENMONTAGE — WINDOWS PRODUCTION RELEASE PACKAGER")
    print("=" * 65)

    # 1. Compile Frontend Assets
    frontend_dir = REPO_ROOT / "frontend"
    print("\n[1/4] Building React Studio frontend production bundle...")
    npm_cmd = shutil.which("npm") or "npm"
    res = subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] Frontend build failed:\n{res.stderr}")
        return 1
    print("  [OK] Frontend bundle successfully compiled into frontend/dist")

    # 2. Stage Distribution Directory
    print(f"\n[2/4] Staging clean application tree in {STAGE_DIR.name}...")
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Core Directories to copy
    dirs_to_copy = [
        ("backlot", STAGE_DIR / "backlot"),
        ("lib", STAGE_DIR / "lib"),
        ("tools", STAGE_DIR / "tools"),
        ("pipeline_defs", STAGE_DIR / "pipeline_defs"),
        ("frontend/dist", STAGE_DIR / "frontend" / "dist"),
        ("scripts", STAGE_DIR / "scripts"),
        ("installer", STAGE_DIR / "installer"),
    ]

    for src_rel, dst_path in dirs_to_copy:
        src_path = REPO_ROOT / src_rel
        if src_path.is_dir():
            shutil.copytree(
                src_path,
                dst_path,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.tmp"),
            )
            print(f"  [OK] Copied {src_rel}/ -> {dst_path.relative_to(STAGE_DIR)}")

    # Copy Launchers and Documentation
    files_to_copy = [
        "OpenMontage.bat",
        "OpenMontage-Silent.vbs",
        "README.md",
        "PROJECT_CONTEXT.md",
        "AGENT_GUIDE.md",
        "requirements.txt",
    ]

    for f_name in files_to_copy:
        src_f = REPO_ROOT / f_name
        if src_f.is_file():
            shutil.copy2(src_f, STAGE_DIR / f_name)
            print(f"  [OK] Copied {f_name}")

    # Copy Remotion Composer (excluding node_modules cache and renders)
    remotion_src = REPO_ROOT / "remotion-composer"
    remotion_dst = STAGE_DIR / "remotion-composer"
    if remotion_src.is_dir():
        print("  - Copying remotion-composer (core composition templates)...")
        shutil.copytree(
            remotion_src,
            remotion_dst,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("node_modules/.cache", "renders", "*.tmp", ".remotion*"),
        )
        print("  [OK] remotion-composer staged.")

    # 3. Create Sample Config and Empty Structure
    (STAGE_DIR / "config").mkdir(parents=True, exist_ok=True)
    (STAGE_DIR / "models").mkdir(parents=True, exist_ok=True)
    (STAGE_DIR / "projects").mkdir(parents=True, exist_ok=True)

    # 4. Create Compressed ZIP Archive
    zip_path = DIST_DIR / "OpenMontage-v1.0.0-Windows.zip"
    print(f"\n[3/4] Packaging into compressed distribution archive: {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(STAGE_DIR):
            for file in files:
                abs_p = Path(root) / file
                rel_p = abs_p.relative_to(STAGE_DIR.parent)
                zf.write(abs_p, rel_p)

    archive_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] Created {zip_path.name} ({archive_size_mb:.1f} MB)")

    # 5. Validation Check
    print("\n[4/4] Verifying distribution bundle integrity...")
    assert (STAGE_DIR / "OpenMontage.bat").is_file(), "Launcher bat missing!"
    assert (STAGE_DIR / "frontend" / "dist" / "index.html").is_file(), "Frontend index.html missing!"
    assert (STAGE_DIR / "scripts" / "launcher.py").is_file(), "Launcher script missing!"
    print("  [OK] All distribution files verified successfully.")

    print("\n" + "=" * 65)
    print("  BUILD COMPLETE: Production Windows package ready in dist/")
    print(f"  Staging Folder: {STAGE_DIR}")
    print(f"  ZIP Archive:    {zip_path}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(build_distribution())
