"""Create a Desktop shortcut that launches the GUI with no console window."""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import win32com.client  # type: ignore
except ImportError:
    win32com = None


def create_shortcut(name: str, target: Path, workdir: Path, icon: Path | None = None) -> Path:
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    link = desktop / f"{name}.lnk"

    # Prefer pythonw for console-less launch
    pyw = Path(sys.executable).with_name("pythonw.exe")
    if not pyw.exists():
        pyw = Path(sys.executable)

    if win32com is None:
        # Fallback: write a .bat that starts pythonw hidden via VBS companion
        vbs = desktop / f"Launch {name}.vbs"
        vbs.write_text(
            f'CreateObject("Wscript.Shell").Run """{pyw}"" ""{target}""", 0, False\n',
            encoding="utf-8",
        )
        return vbs

    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(link))
    sc.Targetpath = str(pyw)
    sc.Arguments = f'"{target}"'
    sc.WorkingDirectory = str(workdir)
    sc.Description = name
    if icon and icon.exists():
        sc.IconLocation = str(icon)
    sc.save()
    return link


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    app = root / "app.py"
    name = os.environ.get("SCANNER_SHORTCUT_NAME", root.name.replace("-", " ").title())
    path = create_shortcut(name, app, root)
    print(path)
