"""Behavioral checks for imported measurements, calculations, and safe reports."""

import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze import COLUMNS, analyze, read_samples, render_html

ROOT = Path(__file__).resolve().parents[1]


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.samples = read_samples(ROOT / "data" / "demo.csv")

    def csv_with(self, changes=None, headers=COLUMNS):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "input.csv"
        row = dict(zip(COLUMNS, ["2026-11-24T08:00:00+03:00", "AP-Test",
                                10, 5, 100, 20, 0, 25, 30, -60]))
        row.update(changes or {})
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            writer.writerow(row)
        return path

    def test_shared_wan_is_counted_once(self):
        report = analyze(self.samples)
        latest = report["latest"]
        self.assertEqual(report["snapshot_count"], 2)
        self.assertEqual(latest["connected_clients"], 1000)
        self.assertEqual(latest["active_clients"], 250)
        self.assertEqual(latest["wan_capacity_mbps"], 100)
        self.assertEqual(latest["wan_utilization_pct"], 96)
        self.assertAlmostEqual(latest["equal_share_ceiling_mbps"], 0.4)
        self.assertEqual(sum(i["scope"] == "Shared WAN" for i in latest["findings"]), 1)

    def test_healthy_and_congested_snapshots_have_distinct_statuses(self):
        report = analyze(self.samples)
        self.assertEqual(report["snapshots"][0]["status"], "within_thresholds")
        self.assertEqual(report["latest"]["status"], "critical")
        issues = {(item["scope"], item["metric"], item["severity"])
                  for item in report["latest"]["findings"]}
        self.assertIn(("Conference", "dns_ms", "critical"), issues)
        self.assertIn(("Rooms-East", "rssi_dbm", "critical"), issues)

    def test_latest_uses_timestamp_not_csv_order(self):
        self.assertEqual(analyze(list(reversed(self.samples)))["latest"]["captured_at"],
                         "2026-11-24T17:00:00+00:00")

    def test_conflicting_shared_wan_values_are_rejected(self):
        rows = copy.deepcopy(self.samples)
        rows[1]["wan_load_mbps"] = 80
        with self.assertRaisesRegex(ValueError, "site-wide WAN"):
            analyze(rows)

    def test_no_active_clients_has_no_division_error(self):
        report = analyze(read_samples(self.csv_with({"active_clients": 0})))
        self.assertIsNone(report["latest"]["equal_share_ceiling_mbps"])
        self.assertIn("no active clients", render_html(report))

    def test_missing_header_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "headers"):
            read_samples(self.csv_with(headers=COLUMNS[:-1]))

    def test_duplicate_header_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicated"):
            read_samples(self.csv_with(headers=COLUMNS + ("ap_name",)))

    def test_nonfinite_measurements_are_rejected(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite"):
                read_samples(self.csv_with({"latency_ms": value}))

    def test_inconsistent_counts_and_ranges_are_rejected(self):
        cases = ({"active_clients": 11}, {"connected_clients": 1.5},
                 {"wan_capacity_mbps": 0}, {"packet_loss_pct": 101},
                 {"wan_load_mbps": 101}, {"dns_ms": -1}, {"rssi_dbm": 10})
        for change in cases:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "CSV row 2"):
                read_samples(self.csv_with(change))

    def test_timezone_required(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            read_samples(self.csv_with({"captured_at": "2026-11-24T08:00:00"}))

    def test_same_instant_and_ap_is_a_duplicate_even_with_different_offsets(self):
        path = self.csv_with()
        with path.open("a", encoding="utf-8") as stream:
            stream.write("2026-11-24T05:00:00Z,AP-Test,10,5,100,20,0,25,30,-60\n")
        with self.assertRaisesRegex(ValueError, "duplicate AP"):
            read_samples(path)

    def test_empty_csv_is_rejected(self):
        path = self.csv_with()
        path.write_text(",".join(COLUMNS) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "at least one"):
            read_samples(path)

    def test_imported_names_are_escaped_in_html(self):
        rows = copy.deepcopy(self.samples)
        rows[-1]["ap_name"] = '<script>alert("test")</script>'
        output = render_html(analyze(rows))
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)

    def test_cli_writes_reports_outside_project_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            html_path = Path(directory) / "result.html"
            json_path = Path(directory) / "result.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "analyze.py"), str(ROOT / "data/demo.csv"),
                 "--output", str(html_path), "--json", str(json_path)],
                cwd=directory, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Network health report", html_path.read_text())
            self.assertEqual(json.loads(json_path.read_text())["latest"]["connected_clients"], 1000)

    def test_cli_does_not_overwrite_input(self):
        path = self.csv_with()
        before = path.read_bytes()
        result = subprocess.run([sys.executable, str(ROOT / "analyze.py"), str(path),
                                 "--output", str(path)], capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
