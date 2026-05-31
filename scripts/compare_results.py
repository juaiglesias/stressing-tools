#!/usr/bin/env python3
"""
Reads k6 JSON output files from a results directory and prints a comparison table.
Saves a Markdown report to reports/.

Usage:
  python3 scripts/compare_results.py results/ [--timestamp TS] [--scenario NAME]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone


def _parse_ts(ts_str: str) -> datetime:
    ts_str = re.sub(r'(\.\d{6})\d+', r'\1', ts_str)
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def parse_k6_json(path: str) -> dict:
    """Parse a k6 NDJSON output file and extract key metrics."""
    duration_values = []
    failed_count = 0
    first_ts = None
    last_ts = None

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "Point":
                continue

            ts_str = obj.get("data", {}).get("time", "")
            if ts_str:
                try:
                    ts = _parse_ts(ts_str)
                    if first_ts is None or ts < first_ts:
                        first_ts = ts
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
                except ValueError:
                    pass

            metric = obj.get("metric", "")
            val = obj.get("data", {}).get("value", 0)

            if metric == "http_req_duration":
                duration_values.append(val)
            elif metric == "http_req_failed":
                failed_count += int(val)

    if not duration_values:
        return {}

    duration_values.sort()
    n = len(duration_values)

    duration_seconds = (
        (last_ts - first_ts).total_seconds()
        if first_ts and last_ts and last_ts > first_ts
        else 1.0
    )

    def percentile(p):
        idx = int(n * p / 100)
        return duration_values[min(idx, n - 1)]

    return {
        "p50": round(percentile(50), 2),
        "p95": round(percentile(95), 2),
        "p99": round(percentile(99), 2),
        "total_requests": n,
        "failed": failed_count,
        "error_rate": round(failed_count / n * 100, 3) if n else 0,
        "throughput": round(n / duration_seconds, 1),
    }


def _parse_mem_mb(mem_usage_str: str) -> float:
    used = mem_usage_str.split(" / ")[0].strip()
    for suffix, factor in [("GiB", 1024), ("MiB", 1), ("kB", 1/1024), ("MB", 1), ("GB", 1024), ("B", 1/1048576)]:
        if used.endswith(suffix):
            return float(used[: -len(suffix)]) * factor
    return 0.0


def parse_stats_file(path: str) -> dict:
    """Parse docker stats JSONL and return peak/avg CPU% and memory (MB)."""
    cpu_vals, mem_vals = [], []
    try:
        with open(path) as f:
            for line in f:
                brace = line.find('{')
                if brace < 0:
                    continue
                line = line[brace:]
                try:
                    obj = json.loads(line)
                    cpu_vals.append(float(obj.get("CPUPerc", "0%").replace("%", "")))
                    mem_vals.append(_parse_mem_mb(obj.get("MemUsage", "0B / 0B")))
                except (ValueError, IndexError, KeyError, json.JSONDecodeError):
                    continue
    except FileNotFoundError:
        return {}
    if not cpu_vals:
        return {}
    return {
        "peak_cpu": round(max(cpu_vals), 1),
        "avg_cpu": round(sum(cpu_vals) / len(cpu_vals), 1),
        "peak_mem_mb": round(max(mem_vals), 1),
        "avg_mem_mb": round(sum(mem_vals) / len(mem_vals), 1),
    }


def extract_metadata(filename: str):
    """Extract target and scenario from filename: <target>_<scenario>_<ts>.json"""
    base = os.path.basename(filename).replace(".json", "")
    parts = base.split("_")
    if len(parts) >= 4:
        scenario = parts[-3]
        target = "_".join(parts[:-3])
        return target, scenario
    return base, "unknown"


def render_table(rows: list[dict], headers: list[str]) -> str:
    col_widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            col_widths[h] = max(col_widths[h], len(str(row.get(h, ""))))

    sep = "| " + " | ".join("-" * col_widths[h] for h in headers) + " |"
    header_row = "| " + " | ".join(h.ljust(col_widths[h]) for h in headers) + " |"

    lines = [header_row, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir")
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args()

    results_dir = args.results_dir
    if not os.path.isdir(results_dir):
        print(f"ERROR: {results_dir} is not a directory")
        sys.exit(1)

    files = sorted(f for f in os.listdir(results_dir) if f.endswith(".json"))

    if args.timestamp:
        files = [f for f in files if args.timestamp in f]
    if args.scenario:
        files = [f for f in files if f"_{args.scenario}_" in f]

    if not files:
        print("No result files found.")
        sys.exit(0)

    by_scenario = defaultdict(list)
    for fname in files:
        target, scenario = extract_metadata(fname)
        fpath = os.path.join(results_dir, fname)
        metrics = parse_k6_json(fpath)
        if metrics:
            stats = parse_stats_file(fpath.replace(".json", "_stats.jsonl"))
            by_scenario[scenario].append({"target": target, **metrics, "stats": stats})

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(root, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    scenarios_json = os.path.join(root, "config", "scenarios.json")
    with open(scenarios_json) as f:
        scenario_order = [s["name"] for s in json.load(f)]

    ts = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = ["target", "p50 (ms)", "p95 (ms)", "p99 (ms)", "requests", "errors (%)", "req/s", "peak CPU%", "peak Mem", "avg Mem"]

    report_lines = [f"# Benchmark Comparison — {ts}\n"]

    ordered = sorted(by_scenario.items(), key=lambda kv: scenario_order.index(kv[0]) if kv[0] in scenario_order else 999)
    for scenario, rows in ordered:
        rows.sort(key=lambda r: r["p95"])

        table_rows = []
        for r in rows:
            s = r.get("stats") or {}
            table_rows.append({
                "target": r["target"],
                "p50 (ms)": r["p50"],
                "p95 (ms)": r["p95"],
                "p99 (ms)": r["p99"],
                "requests": r["total_requests"],
                "errors (%)": r["error_rate"],
                "req/s": r["throughput"],
                "peak CPU%": f"{s['peak_cpu']}%" if s else "—",
                "peak Mem": f"{s['peak_mem_mb']} MB" if s else "—",
                "avg Mem": f"{s['avg_mem_mb']} MB" if s else "—",
            })

        section = f"## Scenario: {scenario}\n\n{render_table(table_rows, headers)}\n"
        report_lines.append(section)

        print(f"\n{'='*60}")
        print(f"Scenario: {scenario}  (sorted by p95 asc)")
        print(render_table(table_rows, headers))

    report_md = "\n".join(report_lines)
    out_path = os.path.join(reports_dir, f"comparison_{ts}.md")
    with open(out_path, "w") as f:
        f.write(report_md)

    print(f"\nReport saved to {out_path}")


if __name__ == "__main__":
    main()
