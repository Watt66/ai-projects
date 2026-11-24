"""Analyze exported Wi-Fi measurements without contacting the network."""

import argparse
import csv
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import sys


COLUMNS = (
    "captured_at", "ap_name", "connected_clients", "active_clients",
    "wan_capacity_mbps", "wan_load_mbps", "packet_loss_pct",
    "latency_ms", "dns_ms", "rssi_dbm",
)
# Starter investigation thresholds, not vendor limits or service guarantees.
RULES = (
    ("wan_utilization_pct", "WAN utilization", "%", 85, 95, False,
     "Check WAN traffic and repeat measurements at peak and quiet times."),
    ("packet_loss_pct", "Packet loss", "%", 1, 3, False,
     "Compare gateway and internet packet loss on wired and wireless clients."),
    ("latency_ms", "Internet latency", " ms", 100, 200, False,
     "Compare wired and wireless latency to the same target; inspect congestion."),
    ("dns_ms", "DNS lookup time", " ms", 150, 500, False,
     "Repeat uncached DNS lookups; compare the configured resolver with an approved alternative."),
    ("rssi_dbm", "Representative client signal", " dBm", -70, -80, True,
     "Measure signal at affected client locations and check AP placement and interference."),
)


def read_samples(path):
    """Validate a single site's CSV, preserving shared-WAN snapshot semantics."""
    samples = []
    seen = set()
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(reader.fieldnames) != set(COLUMNS):
            raise ValueError("CSV headers must be exactly: " + ",".join(COLUMNS))
        if len(reader.fieldnames) != len(COLUMNS):
            raise ValueError("CSV headers must not be duplicated")
        for line, raw in enumerate(reader, start=2):
            try:
                if None in raw or any(value is None for value in raw.values()):
                    raise ValueError("wrong number of CSV fields")
                stamp = datetime.fromisoformat(raw["captured_at"].strip().replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("captured_at must include a timezone")
                row = {"captured_at": stamp.astimezone(timezone.utc).isoformat(),
                       "ap_name": raw["ap_name"].strip()}
                if not row["ap_name"]:
                    raise ValueError("ap_name is required")
                for name in COLUMNS[2:]:
                    number = float(raw[name])
                    if not math.isfinite(number):
                        raise ValueError(name + " must be finite")
                    if name.endswith("clients"):
                        if number < 0 or not number.is_integer():
                            raise ValueError(name + " must be a nonnegative integer")
                        number = int(number)
                    elif name == "rssi_dbm":
                        if not -127 <= number <= -1:
                            raise ValueError("rssi_dbm must be between -127 and -1")
                    elif number < 0:
                        raise ValueError(name + " must be nonnegative")
                    row[name] = number
                if row["wan_capacity_mbps"] <= 0:
                    raise ValueError("wan_capacity_mbps must be positive")
                if row["wan_load_mbps"] > row["wan_capacity_mbps"]:
                    raise ValueError("WAN load cannot exceed configured capacity")
                if row["packet_loss_pct"] > 100:
                    raise ValueError("packet_loss_pct cannot exceed 100")
                if row["active_clients"] > row["connected_clients"]:
                    raise ValueError("active_clients cannot exceed connected_clients")
                key = (row["captured_at"], row["ap_name"])
                if key in seen:
                    raise ValueError("duplicate AP within a timestamp")
                seen.add(key)
                samples.append(row)
            except (ValueError, OverflowError) as exc:
                raise ValueError(f"CSV row {line}: {exc}") from exc
    if not samples:
        raise ValueError("CSV must contain at least one measurement")
    return samples


def findings(metrics, scope):
    """Return evidence and investigation steps for threshold crossings."""
    result = []
    for key, label, unit, warning, critical, lower_is_worse, action in RULES:
        if key not in metrics:
            continue
        value = metrics[key]
        critical_hit = value <= critical if lower_is_worse else value >= critical
        warning_hit = value <= warning if lower_is_worse else value >= warning
        if warning_hit:
            result.append({"scope": scope, "metric": key,
                           "severity": "critical" if critical_hit else "warning",
                           "evidence": f"{label}: {value:g}{unit}", "next_step": action})
    return result


def analyze(samples):
    """Group by timestamp; count WAN capacity once, never once per AP."""
    grouped = {}
    for row in samples:
        grouped.setdefault(row["captured_at"], []).append(row)
    snapshots = []
    for stamp, rows in sorted(grouped.items()):
        capacity, load = rows[0]["wan_capacity_mbps"], rows[0]["wan_load_mbps"]
        if any((row["wan_capacity_mbps"], row["wan_load_mbps"]) != (capacity, load)
               for row in rows):
            raise ValueError(f"{stamp}: all AP rows must repeat the same site-wide WAN capacity and load")
        active = sum(row["active_clients"] for row in rows)
        # Equal-share ceiling assumes all active clients use the link simultaneously.
        summary = {
            "captured_at": stamp, "ap_count": len(rows),
            "connected_clients": sum(row["connected_clients"] for row in rows),
            "active_clients": active, "wan_capacity_mbps": capacity,
            "wan_load_mbps": load, "wan_utilization_pct": load / capacity * 100,
            "equal_share_ceiling_mbps": capacity / active if active else None,
        }
        issues = findings({"wan_utilization_pct": summary["wan_utilization_pct"]}, "Shared WAN")
        for row in rows:
            issues.extend(findings(row, row["ap_name"]))
        summary["status"] = ("critical" if any(i["severity"] == "critical" for i in issues)
                             else "warning" if issues else "within_thresholds")
        summary["findings"] = issues
        summary["access_points"] = sorted(rows, key=lambda row: row["ap_name"])
        snapshots.append(summary)
    return {"schema_version": 1, "measurement_count": len(samples),
            "snapshot_count": len(snapshots), "latest": snapshots[-1], "snapshots": snapshots}


def render_html(report):
    """Build an offline report; all imported strings are escaped."""
    esc = lambda value: html.escape(str(value), quote=True)
    latest = report["latest"]
    share = latest["equal_share_ceiling_mbps"]
    share_label = f"{share:.2f} Mbps" if share is not None else "N/A (no active clients)"
    sections = []
    for snapshot in reversed(report["snapshots"]):
        ap_rows = "".join(
            "<tr>" + "".join(f"<td>{esc(row[key])}</td>" for key in
                            ("ap_name", "connected_clients", "active_clients", "packet_loss_pct",
                             "latency_ms", "dns_ms", "rssi_dbm")) + "</tr>"
            for row in snapshot["access_points"])
        issue_rows = "".join(
            f'<li><strong class="{issue["severity"]}">{esc(issue["severity"].upper())}</strong>'
            f' · {esc(issue["scope"])} · {esc(issue["evidence"])}<p>{esc(issue["next_step"])}</p></li>'
            for issue in snapshot["findings"])
        sections.append(
            f'<section><h2>{esc(snapshot["captured_at"])}</h2>'
            f'<p>Shared WAN: {snapshot["wan_load_mbps"]:g} / {snapshot["wan_capacity_mbps"]:g} Mbps'
            f' ({snapshot["wan_utilization_pct"]:.1f}%) · Status: {esc(snapshot["status"])}</p>'
            '<div class="table-wrap"><table><caption>Measurements by access point</caption>'
            '<thead><tr><th>Access point</th><th>Connected</th><th>Active</th><th>Loss %</th>'
            '<th>Latency ms</th><th>DNS ms</th><th>Signal dBm</th></tr></thead>'
            f'<tbody>{ap_rows}</tbody></table></div><h3>Investigation steps</h3>'
            + (f'<ul>{issue_rows}</ul>' if issue_rows else '<p>No configured threshold crossed.</p>')
            + '</section>')
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Network health report</title><style>'
        '*{box-sizing:border-box}body{margin:0;background:#edf3f5;color:#18323d;'
        'font:16px/1.6 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:28px 20px}'
        'header{background:#123f4b;color:#fff;padding:28px;border-radius:14px}'
        'h1{margin:0;font-size:2rem}h2{font-size:1.2rem}section,.cards article{background:white;'
        'border:1px solid #d3e0e5;border-radius:12px;padding:20px;margin-top:20px}'
        '.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}'
        '.cards strong{display:block;font-size:1.6rem}.table-wrap{overflow-x:auto}'
        'table{border-collapse:collapse;width:100%}caption{text-align:left;font-weight:bold}'
        'td,th{text-align:left;border-bottom:1px solid #dce5e8;padding:10px;white-space:nowrap}'
        '.critical{color:#a52130}.warning{color:#835500}li{margin:14px 0}li p{margin:4px 0}'
        'footer{margin:24px 0;color:#46616d}</style><main><header>'
        '<p>IT SUPPORT / PYTHON AUTOMATION</p><h1>Network health report</h1>'
        '<p>Symptoms, evidence, and practical next checks.</p></header><div class="cards">'
        f'<article>Latest WAN utilization<strong>{latest["wan_utilization_pct"]:.1f}%</strong></article>'
        f'<article>Latest connected clients<strong>{latest["connected_clients"]}</strong></article>'
        f'<article>Latest active clients<strong>{latest["active_clients"]}</strong></article>'
        f'<article>Equal-share ceiling<strong>{esc(share_label)}</strong></article></div>'
        '<p>The equal-share ceiling divides configured WAN capacity by active clients. '
        'It assumes simultaneous, equal demand; it is not a measured client speed.</p>'
        + "".join(sections)
        + '<footer>Thresholds are investigation heuristics. Measurements alone do not prove a root cause. '
        'RSSI represents a sampled client, not every client on an AP. '
        'No network connections or device changes are made by this tool.</footer></main></html>'
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Single-site measurements CSV")
    parser.add_argument("--output", type=Path, default=Path("report.html"))
    parser.add_argument("--json", dest="json_output", type=Path, help="Optional machine-readable report")
    args = parser.parse_args(argv)
    paths = [args.csv.resolve(), args.output.resolve()]
    if args.json_output:
        paths.append(args.json_output.resolve())
    if len(set(paths)) != len(paths):
        parser.error("Input CSV, HTML output, and JSON output must use different paths")
    try:
        report = analyze(read_samples(args.csv))
        args.output.write_text(render_html(report), encoding="utf-8")
        if args.json_output:
            args.json_output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError, UnicodeError, csv.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    latest = report["latest"]
    print(f'Latest: {latest["status"]}; WAN {latest["wan_utilization_pct"]:.1f}%; '
          f'{len(latest["findings"])} findings. HTML: {args.output}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
