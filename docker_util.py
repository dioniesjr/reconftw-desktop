"""Shared Docker helpers for desktop scanner apps."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

LogFn = Callable[[str], None]

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def docker_exe() -> str | None:
    """Resolve docker.exe even when PATH is incomplete (common for Desktop shortcuts)."""
    found = shutil.which("docker")
    if found:
        return found
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Docker"
        / "Docker"
        / "resources"
        / "bin"
        / "docker.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Docker"
        / "Docker"
        / "resources"
        / "docker.exe",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def docker_desktop_exe() -> Path | None:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "Docker Desktop.exe",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def docker_status() -> tuple[bool, str]:
    """Return (ok, detail). ok means the engine accepts commands."""
    exe = docker_exe()
    if not exe:
        return False, "docker.exe not found. Reinstall Docker Desktop."

    # Fast checks first (avoid long hangs on broken engines)
    try:
        r = _run([exe, "version", "--format", "{{.Server.Version}}"], timeout=8)
    except subprocess.TimeoutExpired:
        return False, "Docker engine timed out. It is open but stuck."
    except Exception as exc:
        return False, f"Docker check failed: {exc}"

    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    if r.returncode == 0 and (r.stdout or "").strip():
        return True, f"Docker engine ready (v{(r.stdout or '').strip()})"

    low = out.lower()
    if "500 internal server error" in low or "dockerdesktoplinuxengine" in low:
        return (
            False,
            "Docker Desktop is open, but its engine service is stuck/stopped. "
            "Use Repair Docker (or Restart from Docker Desktop).",
        )
    if "cannot connect" in low or "pipe" in low or "error during connect" in low:
        return False, "Docker engine is not accepting connections yet."
    if out:
        return False, out[:240]
    return False, "Docker engine is not ready."


def docker_available() -> bool:
    ok, _ = docker_status()
    return ok


def _kill_docker_processes() -> None:
    for name in (
        "Docker Desktop",
        "Docker Desktop.exe",
        "com.docker.backend",
        "com.docker.backend.exe",
        "docker-desktop",
    ):
        subprocess.run(
            ["taskkill", "/F", "/IM", name],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )


def repair_docker(log: LogFn) -> bool:
    """Best-effort repair when UI is open but API returns 500 / service stopped."""
    desk = docker_desktop_exe()
    if not desk:
        log("Docker Desktop not found. Install it from https://www.docker.com/products/docker-desktop/")
        return False

    log("Repairing Docker engine...")
    log("Closing stuck Docker processes...")
    _kill_docker_processes()
    time.sleep(2)

    # Try starting the Windows service (may need admin; ignore failure)
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Start-Service com.docker.service -ErrorAction SilentlyContinue"],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )

    log("Starting Docker Desktop again...")
    try:
        # Prefer elevated start so com.docker.service can come up
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Start-Process -FilePath '{desk}' -Verb RunAs",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        subprocess.Popen([str(desk)], creationflags=CREATE_NO_WINDOW)

    for i in range(40):
        ok, detail = docker_status()
        if ok:
            log(detail)
            log("Docker repair succeeded.")
            return True
        time.sleep(3)
        if i % 4 == 0:
            log("Waiting for Docker engine...")
            log(detail)

    log("Docker is still stuck.")
    log("Do this once: open Docker Desktop → Troubleshoot (bug icon) → Restart.")
    log("If that fails, right-click Docker Desktop → Run as administrator.")
    return False


def start_docker_desktop(log: LogFn) -> bool:
    ok, detail = docker_status()
    if ok:
        log(detail)
        return True

    # If Docker UI exists but engine is broken, repair instead of endless wait
    if "stuck" in detail.lower() or "500" in detail.lower() or "service" in detail.lower():
        log(detail)
        return repair_docker(log)

    desk = docker_desktop_exe()
    if not desk:
        log("Docker Desktop not found. Install it from https://www.docker.com/products/docker-desktop/")
        return False

    log("Starting Docker Desktop...")
    subprocess.Popen([str(desk)], creationflags=CREATE_NO_WINDOW)

    for i in range(40):
        ok, detail = docker_status()
        if ok:
            log(detail)
            return True
        time.sleep(3)
        if i % 4 == 0:
            log("Waiting for Docker to start...")
            log(detail)

    log("Normal start did not work. Trying repair...")
    return repair_docker(log)


def ensure_docker(log: LogFn) -> bool:
    ok, detail = docker_status()
    if ok:
        log(detail)
        return True
    log(detail)
    return start_docker_desktop(log)


def image_exists(image: str) -> bool:
    exe = docker_exe()
    if not exe:
        return False
    r = _run([exe, "image", "inspect", image], timeout=30)
    return r.returncode == 0


def pull_image(image: str, log: LogFn) -> bool:
    exe = docker_exe()
    if not exe:
        log("docker.exe not found.")
        return False
    log(f"Downloading scanner engine ({image})...")
    log("First time only. This can take several minutes.")
    proc = subprocess.Popen(
        [exe, "pull", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if line:
            log(line[:180])
    code = proc.wait()
    if code == 0:
        log("Download complete.")
        return True
    log("Download failed. Check your internet connection and Docker Desktop.")
    return False


def ensure_image(image: str, log: LogFn) -> bool:
    if image_exists(image):
        log("Scanner engine already installed.")
        return True
    return pull_image(image, log)


def stop_container(name: str) -> None:
    exe = docker_exe()
    if not exe:
        return
    _run([exe, "rm", "-f", name], timeout=60)


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_url(url: str) -> None:
    if os.name == "nt":
        os.startfile(url)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", url])
