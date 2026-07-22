"""ReconFTW Desktop - full domain recon GUI (no terminal needed)."""
from __future__ import annotations

import os
import subprocess
import threading
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path

import customtkinter as ctk

import docker_util
from folder_readable import make_reconftw_readable

APP_TITLE = "ReconFTW Desktop"
IMAGE = "six2dez/reconftw:main"
RESULTS = Path.home() / "ScannerResults" / "ReconFTW"


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title(APP_TITLE)
        self.geometry("860x720")
        self.minsize(740, 580)
        RESULTS.mkdir(parents=True, exist_ok=True)

        ctk.CTkLabel(self, text="ReconFTW Desktop", font=ctk.CTkFont(size=28, weight="bold")).pack(
            padx=24, pady=(22, 4), anchor="w"
        )
        ctk.CTkLabel(
            self,
            text="Scan an entire domain: subdomains, ports, crawling, vulns, XSS/SQLi, and more.",
            text_color="#A0A8B5",
        ).pack(padx=24, pady=(0, 16), anchor="w")

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=24)
        ctk.CTkLabel(form, text="Domain to scan", anchor="w").pack(fill="x")
        self.target = ctk.CTkEntry(form, height=42, placeholder_text="example.com  (no https://)")
        self.target.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(form, text="Scan depth", anchor="w").pack(fill="x")
        self.mode = ctk.CTkSegmentedButton(form, values=["Quick", "Standard", "Deep"])
        self.mode.set("Standard")
        self.mode.pack(fill="x", pady=(4, 12))

        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x")
        self.btn_setup = ctk.CTkButton(row, text="1. First-time Setup", height=40, command=self.setup)
        self.btn_setup.pack(side="left", padx=(0, 8))
        self.btn_scan = ctk.CTkButton(row, text="2. Start Full Scan", height=40, fg_color="#238636", command=self.scan)
        self.btn_scan.pack(side="left", padx=(0, 8))
        self.btn_results = ctk.CTkButton(row, text="Open Results", height=40, fg_color="#444C56", command=lambda: docker_util.open_folder(RESULTS))
        self.btn_results.pack(side="left", padx=(0, 8))
        self.btn_readable = ctk.CTkButton(row, text="Make Readable Report", height=40, fg_color="#8250DF", command=self.make_readable)
        self.btn_readable.pack(side="left")

        ctk.CTkLabel(
            self,
            text="After a scan, open START_HERE_readable.html. Empty folders usually mean no findings for that stage.",
            text_color="#8B949E",
            wraplength=800,
            justify="left",
        ).pack(padx=24, pady=(10, 6), anchor="w")

        self.status = ctk.CTkLabel(self, text="Ready", text_color="#3FB950", anchor="w")
        self.status.pack(fill="x", padx=24)
        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(fill="x", padx=24, pady=(6, 6))
        self.progress.set(0)
        self.log = ctk.CTkTextbox(self)
        self.log.pack(fill="both", expand=True, padx=24, pady=(8, 24))
        self._busy = False
        self.after(200, lambda: (self.write("Welcome to ReconFTW Desktop."), self.write(f"Results: {RESULTS}")))

    def write(self, msg: str) -> None:
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def set_status(self, text: str, ok: bool = True) -> None:
        self.status.configure(text=text, text_color="#3FB950" if ok else "#F85149")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for b in (self.btn_setup, self.btn_scan, self.btn_results, self.btn_readable):
            b.configure(state=state)
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(1 if self.status.cget("text").startswith("Scan finished") else 0)

    def _run(self, fn) -> None:
        if self._busy:
            return
        self._set_busy(True)

        def worker() -> None:
            try:
                fn()
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _build_readable(self, out_dir: Path, log) -> Path | None:
        try:
            report = make_reconftw_readable(out_dir)
            log(f"Readable report: {report}")
            docker_util.open_url(report.as_uri())
            return report
        except Exception as exc:
            log(f"Readable report failed: {exc}")
            return None

    def make_readable(self) -> None:
        initial = RESULTS
        dirs = sorted([p for p in RESULTS.glob("*") if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        if dirs:
            initial = dirs[0]
        chosen = filedialog.askdirectory(title="Choose ReconFTW result folder", initialdir=str(initial))
        if not chosen:
            return
        path = Path(chosen)

        def job() -> None:
            log = lambda m: self.after(0, lambda msg=m: self.write(msg))
            self.after(0, lambda: self.set_status("Building readable report...", True))
            report = self._build_readable(path, log)
            ok = report is not None
            self.after(0, lambda: self.set_status("Readable report ready" if ok else "Readable report failed", ok))
            if report:
                self.after(0, lambda: messagebox.showinfo(APP_TITLE, f"Readable report opened.\n\n{report}"))

        self._run(job)

    def setup(self) -> None:
        def job() -> None:
            log = lambda m: self.after(0, lambda msg=m: self.write(msg))
            self.after(0, lambda: self.set_status("Setting up...", True))
            if not docker_util.ensure_docker(log):
                self.after(0, lambda: self.set_status("Docker needed", False))
                return
            ok = docker_util.ensure_image(IMAGE, log)
            self.after(0, lambda: self.set_status("Setup complete" if ok else "Setup failed", ok))
            if ok:
                self.after(0, lambda: messagebox.showinfo(APP_TITLE, "Setup complete. Enter a domain and click Start Full Scan."))

        self._run(job)

    def scan(self) -> None:
        domain = self.target.get().strip().removeprefix("https://").removeprefix("http://").split("/")[0]
        if not domain or "." not in domain:
            messagebox.showwarning(APP_TITLE, "Enter a valid domain like example.com")
            return
        mode = self.mode.get()
        extra = []
        if mode == "Quick":
            extra = ["--soft"]
        elif mode == "Deep":
            extra = ["--deep"]

        def job() -> None:
            log = lambda m: self.after(0, lambda msg=m: self.write(msg))
            self.after(0, lambda: self.set_status(f"Scanning {domain} ({mode})...", True))
            if not docker_util.ensure_docker(log):
                self.after(0, lambda: self.set_status("Docker needed", False))
                return
            if not docker_util.ensure_image(IMAGE, log):
                self.after(0, lambda: self.set_status("Setup needed", False))
                return
            out_dir = RESULTS / domain.replace(":", "_")
            out_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{out_dir}:/reconftw/Recon",
                IMAGE,
                "-d", domain,
                "-r",
                *extra,
            ]
            log(f"Full scan started for {domain}")
            log("This may take a while. Activity will appear below.")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line:
                    log(line[:220])
            proc.wait()
            report = self._build_readable(out_dir, log)
            self.after(0, lambda: self.set_status("Scan finished", True))
            docker_util.open_folder(out_dir)
            msg = f"Scan finished for {domain}."
            if report:
                msg += f"\n\nOpen this first:\n{report.name}"
            self.after(0, lambda: messagebox.showinfo(APP_TITLE, msg))

        self._run(job)


if __name__ == "__main__":
    App().mainloop()
