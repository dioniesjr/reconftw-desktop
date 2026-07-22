"""Build plain-language HTML reports from ReconFTW and Sn1per result folders."""
from __future__ import annotations

import html as html_lib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Item:
    title: str
    severity: str
    plain: str
    detail: str = ""


def _esc(s: str) -> str:
    return html_lib.escape(s)


def _read_text(path: Path, limit: int = 4000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not data:
            return ""
        return data[:limit]
    except Exception:
        return ""


def _nonempty_files(root: Path, patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        for p in root.rglob(pattern):
            if p.is_file() and p.stat().st_size > 0:
                found.append(p)
    return sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)


def _render(title: str, target: str, source: Path, items: list[Item], extra_html: str = "") -> str:
    colors = {
        "Critical": "#b42318",
        "High": "#d92d20",
        "Medium": "#dc6803",
        "Low": "#ca8a04",
        "Info": "#175cd3",
        "Good": "#067647",
        "Noise": "#667085",
    }
    cards = []
    for it in items:
        cards.append(
            f"""
            <article class="card">
              <div class="row">
                <span class="pill" style="background:{colors.get(it.severity, '#444')}">{_esc(it.severity)}</span>
                <h2>{_esc(it.title)}</h2>
              </div>
              <p>{_esc(it.plain)}</p>
              {f'<pre>{_esc(it.detail[:1200])}</pre>' if it.detail else ''}
            </article>
            """
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(title)}</title>
  <style>
    body {{ margin:0; font-family: Segoe UI, system-ui, sans-serif; background:#f6f7f9; color:#101828; line-height:1.5; }}
    .wrap {{ max-width:920px; margin:0 auto; padding:28px 18px 60px; }}
    .hero, .card {{ background:#fff; border:1px solid #eaecf0; border-radius:14px; padding:16px 18px; margin:12px 0; }}
    h1 {{ margin:0 0 8px; font-size:28px; }}
    h2 {{ margin:0; font-size:18px; }}
    .sub {{ color:#667085; }}
    .row {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .pill {{ color:#fff; font-size:12px; font-weight:700; border-radius:999px; padding:4px 10px; text-transform:uppercase; }}
    pre {{ background:#f2f4f7; padding:10px; border-radius:8px; overflow:auto; white-space:pre-wrap; font-size:12px; }}
    code {{ background:#f2f4f7; padding:2px 6px; border-radius:6px; }}
    ul {{ margin:8px 0 0 18px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>{_esc(title)}</h1>
      <p class="sub">
        Target: <strong>{_esc(target)}</strong><br/>
        Generated: {_esc(datetime.now().strftime("%Y-%m-%d %H:%M"))}<br/>
        Source folder: {_esc(str(source))}
      </p>
      <p>This page explains the scan in everyday language. Empty folders usually mean that check found nothing, or that stage did not run yet.</p>
    </div>
    {''.join(cards)}
    {extra_html}
  </div>
</body>
</html>
"""


def explain_empty_folders(root: Path) -> list[Item]:
    items: list[Item] = []
    empty = []
    for d in sorted([p for p in root.rglob("*") if p.is_dir()]):
        has_file = any(f.is_file() and f.stat().st_size > 0 for f in d.rglob("*"))
        # only top-ish empty dirs relative to root (depth <= 3)
        rel = d.relative_to(root)
        if len(rel.parts) <= 2 and not has_file:
            empty.append(str(rel))
    if empty:
        shown = ", ".join(empty[:20])
        more = f" (+{len(empty)-20} more)" if len(empty) > 20 else ""
        items.append(
            Item(
                title="Why some folders are empty",
                severity="Info",
                plain=(
                    "These tools create category folders in advance. An empty folder usually means "
                    "no findings for that category, or that scan stage did not finish. "
                    f"Empty examples: {shown}{more}."
                ),
            )
        )
    return items


def make_reconftw_readable(result_dir: Path) -> Path:
    # result_dir may be .../ReconFTW/domain or .../ReconFTW/domain/domain
    domain_dir = result_dir
    nested = [p for p in result_dir.glob("*") if p.is_dir() and (p / "osint").exists() or (p / "subdomains").exists() or (p / "webs").exists()]
    if nested:
        domain_dir = nested[0]
    target = domain_dir.name

    items: list[Item] = [
        Item(
            title="Scan overview",
            severity="Info",
            plain=(
                f"ReconFTW mapped publicly visible information about {target}. "
                "This is mostly reconnaissance (discovery), not confirmed hacking exploits."
            ),
        )
    ]
    items.extend(explain_empty_folders(result_dir))

    mapping = [
        ("subdomains/subdomains.txt", "Subdomains found", "These are other hostnames under the same domain."),
        ("webs/webs.txt", "Live websites", "Websites that answered and can be tested next."),
        ("webs/webs_all.txt", "All discovered web URLs", "Broader list of web endpoints discovered."),
        ("osint/emails.txt", "Email addresses", "Public emails found during OSINT."),
        ("osint/domain_info_general.txt", "Domain registration info", "WHOIS-style information about the domain."),
        ("osint/dorks.txt", "Search engine dork hits", "Interesting public search findings."),
        ("osint/passwords.txt", "Possible leaked password clues", "Review carefully. May be outdated or unrelated."),
        ("osint/3rdparts_misconfigurations.txt", "Third-party misconfigurations", "Possible cloud/service exposure hints."),
        ("vulns", "Vulnerability notes", "If files exist here, review them first."),
        ("hosts", "Host / IP mapping", "IP and host correlation."),
        ("screenshots", "Screenshots", "Visual snapshots of discovered sites."),
    ]

    interesting = 0
    for rel, title, plain in mapping:
        path = domain_dir / rel
        if path.is_dir():
            files = [f for f in path.glob("*") if f.is_file() and f.stat().st_size > 0]
            if files:
                interesting += 1
                preview = "\n".join(f.name for f in files[:12])
                items.append(Item(title=title, severity="Info", plain=f"{plain} Found {len(files)} file(s).", detail=preview))
            else:
                items.append(Item(title=title, severity="Noise", plain=f"{plain} Folder exists but is empty for this scan."))
            continue
        if path.is_file():
            content = _read_text(path)
            if content:
                interesting += 1
                lines = [ln for ln in content.splitlines() if ln.strip()]
                items.append(
                    Item(
                        title=title,
                        severity="Info",
                        plain=f"{plain} Count: {len(lines)}.",
                        detail="\n".join(lines[:40]),
                    )
                )
            else:
                items.append(Item(title=title, severity="Noise", plain=f"{plain} File exists but is empty."))

    if interesting == 0:
        items.insert(
            1,
            Item(
                title="This scan looks incomplete",
                severity="Low",
                plain=(
                    "Folders were created, but almost no useful data was written. "
                    "Common causes: Quick/soft mode, missing API keys, rate limits, or the scan stopped early. "
                    "Try Standard or Deep mode and leave the app open until it fully finishes."
                ),
            ),
        )

    out = result_dir / "START_HERE_readable.html"
    out.write_text(_render("Readable ReconFTW report", target, result_dir, items), encoding="utf-8")
    return out


def make_sn1per_readable(result_dir: Path) -> Path:
    target = result_dir.name
    workspace = result_dir / "workspace" / target
    root = workspace if workspace.exists() else result_dir

    items: list[Item] = [
        Item(
            title="Scan overview",
            severity="Info",
            plain=(
                f"Sn1per scanned {target}. Real findings are usually under the workspace folder. "
                "Top-level empty folders are placeholders Sn1per always creates."
            ),
        )
    ]
    items.extend(explain_empty_folders(result_dir))

    # Prefer workspace paths
    checks = [
        (root / "vulnerabilities", "Possible vulnerabilities", "Review these first. Confirm before treating as confirmed bugs."),
        (root / "web", "Web recon files", "Headers, URLs, tech fingerprints, spiders, and related web checks."),
        (root / "domains", "Domains / hostnames", "Hostnames discovered around the target."),
        (root / "ips", "IP addresses", "IP inventory related to the target."),
        (root / "nmap", "Port scan data", "Open ports and service probes."),
        (root / "screenshots", "Screenshots", "Visual captures of pages."),
        (root / "credentials", "Credential findings", "Only treat as sensitive if content is real and non-empty."),
        (root / "reports", "Generated reports", "Any auto-built report files."),
        (result_dir / "output", "Raw scanner output", "Technical logs from tools Sn1per ran."),
        (result_dir / "scans", "Scan logs", "Process logs for each stage."),
    ]

    useful = 0
    for path, title, plain in checks:
        if not path.exists():
            continue
        if path.is_dir():
            files = [f for f in path.rglob("*") if f.is_file() and f.stat().st_size > 0]
            if not files:
                items.append(Item(title=title, severity="Noise", plain=f"{plain} This folder is empty."))
                continue
            useful += 1
            # Highlight vulnerability-like filenames
            hot = [f for f in files if any(k in f.name.lower() for k in ("vuln", "xss", "sql", "rce", "lfi", "ssrf", "critical", "high"))]
            preview_files = hot[:8] + [f for f in files if f not in hot][:8]
            detail_parts = []
            for f in preview_files:
                snippet = _read_text(f, 500)
                detail_parts.append(f"## {f.name}\n{snippet if snippet else '(binary or empty text)'}")
            sev = "Medium" if hot else "Info"
            items.append(
                Item(
                    title=title,
                    severity=sev,
                    plain=f"{plain} Non-empty files: {len(files)}."
                    + (f" Potential issue-named files: {len(hot)}." if hot else ""),
                    detail="\n\n".join(detail_parts)[:3500],
                )
            )
        else:
            content = _read_text(path)
            if content:
                useful += 1
                items.append(Item(title=title, severity="Info", plain=plain, detail=content[:1500]))

    if useful == 0:
        items.insert(
            1,
            Item(
                title="No useful loot found yet",
                severity="Low",
                plain=(
                    "Sn1per created its folder template, but almost no filled result files were found. "
                    "Re-run after Docker is healthy, and keep the scan window open until completion."
                ),
            ),
        )
    else:
        items.append(
            Item(
                title="Where to look on disk",
                severity="Good",
                plain=(
                    f"Start in: {root}. "
                    "Ignore empty top-level folders like credentials/nmap/reports unless they later get files."
                ),
            )
        )

    out = result_dir / "START_HERE_readable.html"
    out.write_text(_render("Readable Sn1per report", target, result_dir, items), encoding="utf-8")
    return out


def make_folder_readable(result_dir: Path, kind: str) -> Path:
    kind = kind.lower()
    if kind == "reconftw":
        return make_reconftw_readable(result_dir)
    if kind == "sn1per":
        return make_sn1per_readable(result_dir)
    raise ValueError(f"Unsupported kind: {kind}")
