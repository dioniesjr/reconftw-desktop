# ReconFTW Desktop

Click-to-run Windows desktop app. No terminal needed.

## Requirements
- Windows 10/11
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Python 3.10+ (for first install / building)

## Quick start
1. Install Docker Desktop and open it once.
2. Double-click `Launch.vbs` **or** the Desktop shortcut.
3. Click **First-time Setup** (downloads the scanner engine once).
4. Enter a target and start scanning.
5. Open results from `Documents` path shown in the app (`%USERPROFILE%\ScannerResults`).

## Create Desktop shortcut
```
py -3 make_shortcut.py
```

## Build a standalone .exe (optional)
```
py -3 -m PyInstaller --noconfirm --windowed --onefile --name "ReconFTWDesktop" app.py
```
Then copy `dist\*.exe` to your Desktop.

## Legal
Only scan systems you own or have written permission to test.
Upstream tools remain under their original licenses.
