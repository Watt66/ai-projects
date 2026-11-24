# Network Health Analyzer

A Python portfolio project for investigating hotel or small-business Wi-Fi complaints from exported measurements. It produces an offline HTML report and optional JSON with evidence and practical next checks.

**Status:** working starter prototype using synthetic data. This is rule-based automation; it does not use an AI model. An AI-assisted draft was used to start this project. Personal learning and extensions should be recorded in `LEARNING_LOG.md`.

## Run it

Requires Python 3.10 or newer; no third-party packages, API keys, or paid services.

```bash
git clone https://github.com/Watt66/ai-projects.git
cd ai-projects/network-health-analyzer
python analyze.py data/demo.csv --output report.html --json report.json
python -m unittest discover -s tests -v
```

While the project is under review, check out its pull request branch before entering the project folder:

```bash
git switch portfolio/network-health-analyzer
```

On Windows, use `py` if the `python` command is unavailable. Open `report.html` in a browser. A generated example is included in `examples/report.html`; its inputs are entirely fictional.

## What the example demonstrates

The evening snapshot has three APs, 1,000 connected clients, 250 active clients, and one shared 100 Mbps internet connection at 96% utilization. The theoretical equal-share capacity is `100 / 250 = 0.40 Mbps` per active client before overhead. This is a capacity illustration, not a measured client speed or a bandwidth recommendation.

The report also identifies high DNS response time on one AP and packet loss, latency, and weak sampled signal on another. These symptoms suggest investigation paths; they do not establish a root cause.

## Measurement contract

One file represents one site. One row represents measurements associated with an AP at a timestamp. Every AP row for that timestamp must repeat the **same site-wide WAN capacity and load**. WAN values are counted once per timestamp. AP client counts must be disjoint to avoid double-counting roaming clients; snapshots should be captured together. Missing APs are not inferred or filled in.

| CSV field | Meaning |
| --- | --- |
| `captured_at` | ISO 8601 timestamp including UTC offset, e.g. `2026-11-24T20:00:00+03:00` |
| `ap_name` | A nonempty access point alias |
| `connected_clients` | Associated devices on this AP |
| `active_clients` | Devices actively using traffic, using a consistent definition across APs |
| `wan_capacity_mbps` | Configured shared site internet capacity in Mbps |
| `wan_load_mbps` | Measured total site WAN traffic in Mbps over the same interval |
| `packet_loss_pct` | Internet-target packet loss measured from a client on this AP, 0–100 |
| `latency_ms` | Internet-target round-trip time from the sampled client |
| `dns_ms` | DNS lookup duration from the sampled client |
| `rssi_dbm` | Representative client signal level, negative dBm; not every client's signal |

Use the same test target and sampling interval when comparing APs or times. A controller export will need column mapping to this format. The tool does not collect live measurements, identify devices, or change settings.

## Starter investigation thresholds

These are transparent heuristics for a demo, not Wi-Fi standards, vendor capacity limits, or SLA promises. Tune `RULES` in `analyze.py` to the environment and application requirements.

| Metric | Warning | Critical |
| --- | --- | --- |
| Shared WAN utilization | ≥85% | ≥95% |
| Packet loss | ≥1% | ≥3% |
| Internet round-trip latency | ≥100 ms | ≥200 ms |
| DNS lookup duration | ≥150 ms | ≥500 ms |
| Sampled RSSI | ≤−70 dBm | ≤−80 dBm |

High client counts alone do not trigger an AP overload diagnosis. Radio airtime, retry rates, channel utilization, hardware, and application requirements are not present in this data.

## Validation and design

- Checks timestamps, duplicate AP samples, numeric ranges, nonfinite values, and consistent WAN measurements.
- Converts timestamps to UTC before sorting or deduplicating.
- Uses active client counts for the equal-share illustration; handles zero active clients.
- Escapes imported text before inserting it into HTML; HTML uses no external assets or scripts.
- Keeps historical snapshots separate from the latest summary.
- Includes behavioral unit and CLI tests, plus a GitHub Actions workflow for Python 3.10 and 3.12.

## Make this your own

1. Run the demo, explain the calculation, and record your observations in `LEARNING_LOG.md`.
2. Add configurable thresholds through a JSON settings file and cover an actual boundary case.
3. Add a small, anonymized home-lab measurement set and document how you collected it.
4. Add a controller-export adapter and compare its output with a manual calculation.
5. Later, add a separate AI explanation layer that cites measurements and does not change the numeric rules. Evaluate it on invented support cases first.

Do not include guest identifiers or workplace exports in a public portfolio. Use synthetic or approved anonymized samples.

## License

Covered by the repository's MIT license in `../LICENSE`.
