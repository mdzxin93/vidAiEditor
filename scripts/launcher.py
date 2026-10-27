"""OpenMontage One-Click Windows Launcher (Phase 12).

Orchestrates:
1. Runtime component verification (Python 3.10+, Node.js 18+, FFmpeg).
2. Single-instance detection (prevents accidental duplicate daemons).
3. Local data directories initialization (%LOCALAPPDATA%\\OpenMontage).
4. FastAPI backend startup bound strictly to 127.0.0.1:8000.
5. Direct serving of compiled React Studio.
6. Automatic browser launch to http://127.0.0.1:8000.
7. Clean, graceful shutdown of application-owned processes.
"""

from __future__ import annotations

import os
import sys
import time
import socket
import signal
import shutil
import logging
import urllib.request
import webbrowser
import subprocess
from pathlib import Path

# Safe stdout on Windows command lines
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("openmontage.launcher")

REPO_ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = 8000
SERVER_URL = f"http://{HOST}:{PORT}"


def is_port_in_use(host: str, port: int) -> bool:
    """Check if the target server port is currently occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def check_running_openmontage(host: str, port: int) -> bool:
    """Verify if a running process on the port is indeed OpenMontage."""
    health_url = f"http://{host}:{port}/api/health"
    try:
        req = urllib.request.Request(health_url, headers={"User-Agent": "OpenMontage-Launcher"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                return "openmontage" in body.lower() or "backlot" in body.lower()
    except Exception:
        pass
    return False


def verify_runtime_components() -> list[str]:
    """Inspect required external tools and report human-friendly errors."""
    issues = []

    # 1. Python version
    if sys.version_info < (3, 10):
        issues.append(f"Python 3.10+ required. Current version is {sys.version.split()[0]}.")

    # 2. FFmpeg binary
    if not shutil.which("ffmpeg"):
        issues.append("FFmpeg executable not found in PATH. Video rendering and probing requires FFmpeg.")

    # 3. Node.js (for Remotion CLI rendering)
    if not shutil.which("node"):
        issues.append("Node.js executable not found in PATH. Remotion video rendering requires Node.js (v18+).")

    return issues


def main() -> int:
    print("=" * 65)
    print("           OPENMONTAGE AI VIDEO EDITOR — WINDOWS LAUNCHER")
    print("=" * 65)

    # 1. Verify runtime dependencies
    issues = verify_runtime_components()
    if issues:
        print("\n[ERROR] Missing required runtime dependencies:")
        for iss in issues:
            print(f"  • {iss}")
        print("\nPlease install missing tools or update your PATH environment variable.")
        input("\nPress Enter to exit...")
        return 1

    # 2. Single-Instance Check
    if is_port_in_use(HOST, PORT):
        if check_running_openmontage(HOST, PORT):
            print(f"\n[INFO] OpenMontage is already running on {SERVER_URL}.")
            print("Opening application in your default browser...")
            webbrowser.open(SERVER_URL)
            return 0
        else:
            print(f"\n[ERROR] Port {PORT} is occupied by another application.")
            print(f"Please terminate the conflicting process or configure a different port.")
            input("\nPress Enter to exit...")
            return 1

    # 3. Initialize Storage Paths
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from lib.storage_paths import get_storage
        storage = get_storage()
        print(f"[OK] Application Data Directory: {storage.root}")
        print(f"[OK] Projects Directory:         {storage.projects_dir}")
        print(f"[OK] Job Queue Database:         {storage.jobs_db_path}")
    except Exception as e:
        logger.warning("Could not initialize custom storage paths: %s", e)

    # 4. Start Backend Process
    print(f"\n[INFO] Starting OpenMontage server on {SERVER_URL}...")
    server_cmd = [
        sys.executable,
        "-m", "uvicorn",
        "backlot.server:app",
        "--host", HOST,
        "--port", str(PORT),
        "--log-level", "warning",
    ]

    proc = subprocess.Popen(
        server_cmd,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # 6. Wait for Health Check
    ready = False
    for _ in range(40):  # Wait up to 10 seconds
        time.sleep(0.25)
        if check_running_openmontage(HOST, PORT):
            ready = True
            break
        if proc.poll() is not None:
            break

    if not ready:
        print("[ERROR] Server failed to start within timeout.")
        if proc.poll() is not None:
            out, _ = proc.communicate()
            print(f"Server output:\n{out}")
        input("\nPress Enter to exit...")
        return 1

    print("\n" + "=" * 65)
    print(f"  [OK] OpenMontage Studio is ready at: {SERVER_URL}")
    print("  [OK] Serving integrated React Studio & AI Backend")
    print("  [OK] Localhost security guard active (127.0.0.1)")
    print("=" * 65)
    print("Opening your browser now... Press Ctrl+C in this window to stop OpenMontage.\n")

    webbrowser.open(SERVER_URL)

    # 7. Lifecycle & Clean Shutdown Handler
    def shutdown_handler(signum, frame):
        print("\n[INFO] Shutting down OpenMontage gracefully...")
        try:
            # Terminate server process tree
            import psutil
            parent = psutil.Process(proc.pid)
            children = parent.children(recursive=True)
            for ch in children:
                try:
                    ch.terminate()
                except Exception:
                    pass
            parent.terminate()
            parent.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        print("[OK] OpenMontage shut down cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        proc.wait()
    except KeyboardInterrupt:
        shutdown_handler(None, None)

    return 0


if __name__ == "__main__":
    sys.exit(main())
