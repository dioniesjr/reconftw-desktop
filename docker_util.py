"""Shared Docker helpers for desktop scanner apps."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

LogFn = Callable[[str], None]


def _run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        r = _run(["docker", "info"], timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def start_docker_desktop(log: LogFn) -> bool:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "Docker Desktop.exe",
    ]
    for path in candidates:
        if path.exists():
            log(f"Starting Docker Desktop...")
            subprocess.Popen(
                [str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            break
    else:
        log("Docker Desktop not found. Install it from https://www.docker.com/products/docker-desktop/")
        return False

    for i in range(60):
        if docker_available():
            log("Docker is ready.")
            return True
        time.sleep(3)
        if i % 5 == 0:
            log("Waiting for Docker to start...")
    log("Docker did not become ready in time. Open Docker Desktop manually, then try again.")
    return False


def ensure_docker(log: LogFn) -> bool:
    if docker_available():
        return True
    log("Docker is not running yet.")
    return start_docker_desktop(log)


def image_exists(image: str) -> bool:
    r = _run(["docker", "image", "inspect", image], timeout=30)
    return r.returncode == 0


def pull_image(image: str, log: LogFn) -> bool:
    log(f"Downloading scanner engine ({image})...")
    log("First time only. This can take several minutes.")
    proc = subprocess.Popen(
        ["docker", "pull", image],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
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
    _run(["docker", "rm", "-f", name], timeout=60)


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
