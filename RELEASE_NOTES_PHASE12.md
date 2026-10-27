# OPENMONTAGE — PHASE 12 RELEASE NOTES & WINDOWS USER GUIDE
**Version:** 1.0.0-Release (Windows 64-bit)  
**Target Hardware:** ASUS VivoBook (Intel Core i7-13620H, 16 GB RAM, Intel Iris Xe Graphics, Windows 11)  
**Architecture:** Local-first, zero cloud dependencies, bounded memory footprint (<8 GB peak RAM), zero CUDA/NVIDIA requirements.

---

## 1. Executive Summary & Release Highlights

OpenMontage Phase 12 completes the final transition from an interactive multi-process development environment into a dependable, production-packaged desktop application for Windows.

### Key New Capabilities
1. **One-Click Windows Launcher (`OpenMontage.bat` & `OpenMontage-Silent.vbs`)**:
   - Single-click desktop entry that eliminates the need to manually open multiple PowerShell terminals.
   - Automatically performs preflight dependency checks (Python 3.10+, Node.js 18+, FFmpeg).
   - Prevents duplicate daemon processes via single-instance port checking (binds strictly to `127.0.0.1:8000`).
   - Serves the integrated production React Studio directly from the FastAPI backend and launches the default browser.
   - Clean shutdown handler on `Ctrl+C` terminating all child and worker processes without orphaned background tasks.

2. **Clean Storage Decoupling (`%LOCALAPPDATA%\OpenMontage`)**:
   - Application installation directories and binaries remain strictly read-only.
   - User projects, settings, SQLite job queues (`jobs.db`), render caches, and editing memory preferences are stored in Windows standard user data locations (`%LOCALAPPDATA%\OpenMontage`).
   - Upgrades and uninstalls never touch or delete user projects or media files.

3. **Segmented Rendering & Incremental Render Caching (`lib/render/segmented_engine.py`)**:
   - Resolves the long-timeline rendering performance bottleneck on CPU architectures.
   - Computes deterministic SHA-256 cut fingerprints based on source media, in/out points, transitions, overlays, audio tracks, and canvas dimensions.
   - Caches pre-rendered segments. When an editor modifies a single cut on the timeline, only the modified segment is re-rendered; unaffected segments are reused directly from cache.
   - Final export uses stream-copy concatenation (`ffmpeg -c copy`) for loss-free, instantaneous assembly.

4. **Audio Waveform Timeline Visualizer (`lib/ai/waveform_extractor.py` & `Timeline.tsx`)**:
   - Extracts downsampled mono PCM peak amplitudes (<10 KB JSON payload) using FFmpeg.
   - Renders hardware-accelerated, responsive SVG waveforms directly on the React timeline.
   - Supports fluid zooming, horizontal scrolling, clip boundary alignment, and playhead synchronization without decoding massive raw audio files in browser memory.

5. **Priority Export Queue Manager (`lib/api/jobs.py`)**:
   - Supports multi-job export queues with priority scheduling (`priority=5` for interactive previews, `priority=10` for long batch exports).
   - Telemetry reports 1-based queue positions, total queued counts, elapsed times, and job progress.
   - Full cancellation support cleanly terminating FFmpeg/Remotion process trees.

6. **Localhost Security Guard (`backlot/server.py`)**:
   - Hardened Starlette middleware blocking cross-origin drive-by mutations (`POST`, `PUT`, `DELETE`, `PATCH`) from untrusted origins or external websites.
   - Strict CORS whitelist restricted to local loopback origins (`localhost`, `127.0.0.1`).

7. **Production Windows Installer & Standalone Bundle (`installer/openmontage_setup.iss` & `scripts/build_windows_dist.py`)**:
   - Inno Setup 6 installer script configured for per-user installation (`PrivilegesRequired=lowest`), requiring no administrator privileges.
   - Standalone ZIP archive (`dist/OpenMontage-v1.0.0-Windows.zip`, 161.5 MB) containing pre-built React frontend, backend engine, and launchers.

---

## 2. Windows Installation & Quick-Start Guide

### Prerequisites
- **Operating System:** Windows 10 (21H2+) or Windows 11 64-bit.
- **CPU:** Intel Core i5/i7/i9 (11th Gen+) or AMD Ryzen 5000+ (6+ physical cores recommended).
- **RAM:** 16 GB system memory (minimum 8 GB free for rendering).
- **External Dependencies:**
  - Python 3.10, 3.11, or 3.12 (with `python` in PATH).
  - FFmpeg 6.0+ (with `ffmpeg` and `ffprobe` in PATH).
  - Node.js 18+ or 20+ (with `node` and `npm` in PATH, required for Remotion motion graphics).

### Installation Options

#### Option A: One-Click Installer (Inno Setup)
1. Run `OpenMontage-Setup-v1.0.0.exe`.
2. Follow on-screen prompts (installs to `%LOCALAPPDATA%\Programs\OpenMontage` without admin prompts).
3. Check **Create Desktop Shortcut**.
4. Click **Finish** to automatically launch OpenMontage.

#### Option B: Standalone Portable Package
1. Extract `dist/OpenMontage-v1.0.0-Windows.zip` to your preferred folder (e.g. `C:\Tools\OpenMontage`).
2. Double-click `OpenMontage.bat` (or `OpenMontage-Silent.vbs` for a background windowless console).
3. The launcher will automatically verify dependencies, initialize database directories, start the backend server, and open your browser to `http://127.0.0.1:8000/`.

---

## 3. Workflow & Usage

1. **Launch**: Double-click `OpenMontage.bat`.
2. **Create Project**: Click **New Project** in the React Studio, name your project, and select the output resolution (16:9 Landscape or 9:16 Vertical Reel).
3. **Import Footage**: Drag and drop your raw MP4/MOV/WAV files into the Media Bin. The backend extracts audio waveforms and thumbnail previews in the background.
4. **Autonomous AI Planning**:
   - Enter your creative instructions (e.g., *"Create an energetic 60-second summary highlighting key insights with text titles and smooth transitions"*).
   - The local SmolVLM and whisper transcription pipeline analyzes content, detects scenes, and structures the editorial cut plan.
5. **Timeline Editing**:
   - Inspect synchronized audio waveforms on the timeline.
   - Adjust cut boundaries, trim clips, add B-roll inserts, and modify text cards.
6. **Preview & Export**:
   - Click **Preview** for fast, prioritized rendering.
   - Click **Export MP4** to submit a full-resolution render to the persistent SQLite export queue.
   - Progress and queue position update live in the header.

---

## 4. Phase 11 Long-Video Verification Audit Findings

### Investigation of the 10-Minute Video Render Job
- **Job ID:** `job_1791981464_bf4461` (from Phase 11 validation run).
- **Verification Method:** Checked SQLite database `config/jobs.db` and output logs.
- **Findings:**
  - Stage 1 (Multimodal Video Analysis, 600s footage): **Passed** in 24.8s.
  - Stage 2 (Autonomous Script & Editorial Planning): **Passed** in 18.2s.
  - Stage 3 (Full 10-Minute Monolithic Remotion Render): Timed out at exactly 600.0s.
- **Root Cause Analysis:**
  - Rasterizing 18,000 frames (600s @ 30fps) on an Intel Core i7-13620H CPU with integrated graphics renders at ~10 fps.
  - Total CPU render time required is ~1800s (~30 minutes).
  - The previous default Remotion timeout in `tools/video/video_compose.py` was hardcoded to 600.0s.
- **Remediation Implemented in Phase 12:**
  - **Dynamic Timeout Scaling:** Scaled timeout formula to `max(600.0, total_duration_sec * 3.5)` in `tools/video/video_compose.py`.
  - **Segmented Render Engine:** Implemented `SegmentedRenderEngine` in `lib/render/segmented_engine.py` to break long timelines into 5-30s independent chunks with incremental caching, avoiding monolithic re-renders.

---

## 5. Security Architecture & Threat Mitigations

| Threat Vector | Mitigation Strategy | Status |
|---------------|---------------------|--------|
| **Localhost Exposure** | Server strictly binds to `127.0.0.1` (never `0.0.0.0`). External network interfaces cannot access OpenMontage. | **Active** |
| **Drive-By Browser Exploits (CSRF/DNS Rebinding)** | `localhost_security_guard` middleware inspects `Origin` and `Host` headers; blocks cross-origin state-mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`) with HTTP 403 Forbidden. | **Active** |
| **Path Traversal Attacks** | Project directories and asset paths strictly resolved and validated using `Path.resolve()` against authorized storage roots. | **Active** |
| **Orphaned Process Flooding** | Process tree termination handles all Remotion/FFmpeg child processes on job cancellation and application exit. | **Active** |

---

## 6. Hardware Compatibility & Known Limitations

- **Hardware Acceleration:** While Intel QuickSync Video (QSV) is supported when enabled in FFmpeg, all core pipelines default to software `libx264` and `aac` codecs to guarantee 100% universal hardware compatibility across all Windows PCs without driver crashes.
- **CPU Render Speeds:** On an Intel Core i7 CPU without dedicated GPU, complex React motion graphics render at approximately 10–15 frames per second (approx. 2x real-time for 30fps output). Use **Preview Mode** during interactive editing for sub-second turnaround.
- **Remotion Licensing:** Remotion is free for individuals and small businesses (under $1M annual revenue) under the Remotion Company License. Enterprise users must acquire a commercial Remotion license. FFmpeg is distributed under LGPL v2.1/GPL v3.

---

## 7. Verification Summary & Test Results

- **Automated Test Coverage:** **43 out of 43 tests passing (100% green)**
  - `tests/test_release_phase12.py`: 10/10 passed (Storage isolation, waveform extraction, cut fingerprinting, incremental evaluation, priority queueing, security guard, models status, React serving).
  - `tests/test_reliability_phase11.py`: 16/16 passed (SQLite queue persistence, process cancellation, checkpoint recovery, cache invalidation, low memory guards).
  - `tests/test_editor_api.py`: 8/8 passed (CRUD endpoints, media upload, timeline undo/redo, QA inspection).
  - `tests/test_editing_memory.py`: 9/9 passed (Approved preference learning, explicit instruction overrides, dataset exporter).
