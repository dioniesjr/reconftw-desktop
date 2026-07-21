"""Create a Desktop shortcut that launches the GUI with no console window."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ReconFTW Desktop"
ICON_REL = r"assets\reconftw.ico"


def create_shortcut() -> Path:
    root = Path(__file__).resolve().parent
    app = root / "app.py"
    icon = root / ICON_REL
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    link = desktop / f"{APP_NAME}.lnk"

    pyw = Path(sys.executable).with_name("pythonw.exe")
    if not pyw.exists():
        pyw = Path(sys.executable)

    try:
        import win32com.client  # type: ignore
    except ImportError:
        # PowerShell fallback
        ps = (
            f"$ws=New-Object -ComObject WScript.Shell; "
            f"$s=$ws.CreateShortcut('{link}'); "
            f"$s.TargetPath='{pyw}'; $s.Arguments='\"{app}\"'; "
            f"$s.WorkingDirectory='{root}'; "
            f"$s.IconLocation='{icon},0'; $s.Save()"
        )
        os.system(f'powershell -NoProfile -Command "{ps}"')
        return link

    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(link))
    sc.Targetpath = str(pyw)
    sc.Arguments = f'"{app}"'
    sc.WorkingDirectory = str(root)
    sc.Description = APP_NAME
    if icon.exists():
        sc.IconLocation = f"{icon},0"
    sc.save()
    return link


if __name__ == "__main__":
    print(create_shortcut())
