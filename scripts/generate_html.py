#!/usr/bin/env python3
"""
Generates a sortable HTML report from k6 result files.

Usage:
  python3 scripts/generate_html.py results/ [--timestamp TS] [--out reports/report.html]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

# ── parsing (mirrors compare_results.py) ──────────────────────────────────────

def _parse_ts(ts_str):
    ts_str = re.sub(r'(\.\d{6})\d+', r'\1', ts_str)
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def parse_k6_json(path):
    duration_values = []
    failed_count = 0
    first_ts = last_ts = None

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
    duration_seconds = (last_ts - first_ts).total_seconds() if first_ts and last_ts and last_ts > first_ts else 1.0

    def pct(p):
        return duration_values[min(int(n * p / 100), n - 1)]

    return {
        "p50": round(pct(50), 2),
        "p95": round(pct(95), 2),
        "p99": round(pct(99), 2),
        "total_requests": n,
        "failed": failed_count,
        "error_rate": round(failed_count / n * 100, 3) if n else 0,
        "throughput": round(n / duration_seconds, 1),
    }


def _parse_mem_mb(s):
    used = s.split(" / ")[0].strip()
    for suffix, factor in [("GiB", 1024), ("MiB", 1), ("kB", 1/1024), ("MB", 1), ("GB", 1024), ("B", 1/1048576)]:
        if used.endswith(suffix):
            return float(used[:-len(suffix)]) * factor
    return 0.0


def parse_stats_file(path):
    cpu_vals, mem_vals = [], []
    try:
        with open(path) as f:
            for line in f:
                brace = line.find('{')
                if brace < 0:
                    continue
                try:
                    obj = json.loads(line[brace:])
                    cpu_vals.append(float(obj.get("CPUPerc", "0%").replace("%", "")))
                    mem_vals.append(_parse_mem_mb(obj.get("MemUsage", "0B / 0B")))
                except (ValueError, KeyError, json.JSONDecodeError):
                    continue
    except FileNotFoundError:
        return {}
    if not cpu_vals:
        return {}
    return {
        "peak_cpu": round(max(cpu_vals), 1),
        "peak_mem_mb": round(max(mem_vals), 1),
        "avg_mem_mb": round(sum(mem_vals) / len(mem_vals), 1),
    }


def extract_metadata(filename):
    base = os.path.basename(filename).replace(".json", "")
    parts = base.split("_")
    if len(parts) >= 4:
        return "_".join(parts[:-3]), parts[-3]
    return base, "unknown"


# ── HTML generation ───────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f6fa; color: #222; padding: 32px 24px; }
h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: 8px; color: #111; }
.subtitle { font-size: 0.85rem; color: #666; margin-bottom: 40px; }
.scenario { background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 36px; overflow: hidden; }
.scenario-header { padding: 20px 24px 16px; border-bottom: 1px solid #eee; }
.scenario-header h2 { font-size: 1.1rem; font-weight: 700; color: #1a1a2e; margin-bottom: 4px; }
.scenario-header h2 span { font-family: monospace; background: #eef0f8; padding: 2px 8px; border-radius: 4px; font-size: 0.95rem; }
.scenario-desc { font-size: 0.82rem; color: #555; margin-top: 6px; }
.table-wrap { overflow-x: auto; padding: 0 0 4px; }
table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
thead th { padding: 10px 14px; text-align: left; font-weight: 600; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .04em; color: #555; background: #f8f9fc; border-bottom: 2px solid #e8eaf0; cursor: pointer; white-space: nowrap; user-select: none; }
thead th:hover { background: #eef0f8; color: #222; }
thead th .sort-icon { display: inline-block; width: 14px; text-align: center; margin-left: 2px; color: #bbb; font-size: 0.75rem; }
thead th.sort-asc .sort-icon, thead th.sort-desc .sort-icon { color: #4a6cf7; }
tbody tr:nth-child(even) { background: #f8f9fc; }
tbody tr:hover { background: #eef0f8; }
tbody td { padding: 9px 14px; border-bottom: 1px solid #f0f1f5; white-space: nowrap; }
tbody td:first-child { font-weight: 600; font-size: 0.82rem; }
tbody td.num { text-align: right; font-variant-numeric: tabular-nums; }
.badge-best { color: #15803d; font-weight: 700; }
"""

JS = """
function sortTable(table, colIndex, direction) {
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {
    const aCell = a.cells[colIndex];
    const bCell = b.cells[colIndex];
    const aVal = aCell.dataset.val !== undefined ? parseFloat(aCell.dataset.val) : aCell.textContent.trim();
    const bVal = bCell.dataset.val !== undefined ? parseFloat(bCell.dataset.val) : bCell.textContent.trim();
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return direction === 'asc' ? aVal - bVal : bVal - aVal;
    }
    return direction === 'asc' ? String(aVal).localeCompare(String(bVal)) : String(bVal).localeCompare(String(aVal));
  });
  rows.forEach(r => tbody.appendChild(r));
}

function updateHeaders(table, activeIdx, direction) {
  table.querySelectorAll('thead th').forEach((th, i) => {
    th.classList.remove('sort-asc', 'sort-desc');
    const icon = th.querySelector('.sort-icon');
    if (i === activeIdx) {
      th.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');
      icon.textContent = direction === 'asc' ? '↑' : '↓';
    } else {
      icon.textContent = '↕';
    }
  });
}

document.querySelectorAll('table.benchmark').forEach(table => {
  const state = { col: null, dir: null };

  // default sort: req/s desc
  const headers = Array.from(table.querySelectorAll('thead th'));
  const reqsIdx = headers.findIndex(th => th.dataset.col === 'throughput');
  if (reqsIdx >= 0) {
    state.col = reqsIdx;
    state.dir = 'desc';
    sortTable(table, reqsIdx, 'desc');
    updateHeaders(table, reqsIdx, 'desc');
  }

  headers.forEach((th, i) => {
    th.addEventListener('click', () => {
      let dir;
      if (state.col === i) {
        dir = state.dir === 'desc' ? 'asc' : 'desc';
      } else {
        dir = th.dataset.type === 'string' ? 'asc' : 'desc';
      }
      state.col = i;
      state.dir = dir;
      sortTable(table, i, dir);
      updateHeaders(table, i, dir);
    });
  });
});
"""

COLS = [
    ("target",    "target",    "string",  False),
    ("p50 (ms)",  "p50",       "number",  True),
    ("p95 (ms)",  "p95",       "number",  True),
    ("p99 (ms)",  "p99",       "number",  True),
    ("requests",  "requests",  "number",  True),
    ("errors (%)", "errors",   "number",  True),
    ("req/s",     "throughput","number",  True),
    ("peak CPU%", "peak_cpu",  "number",  True),
    ("peak Mem",  "peak_mem",  "number",  True),
    ("avg Mem",   "avg_mem",   "number",  True),
]


def render_table(rows):
    thead_cells = ""
    for label, col_id, col_type, _ in COLS:
        thead_cells += f'<th data-col="{col_id}" data-type="{col_type}">{label}<span class="sort-icon">↕</span></th>'

    tbody_rows = ""
    for r in rows:
        s = r.get("stats") or {}
        cells = {
            "target":     (r["target"],              r["target"],                   False),
            "p50":        (r["p50"],                  r["p50"],                      True),
            "p95":        (r["p95"],                  r["p95"],                      True),
            "p99":        (r["p99"],                  r["p99"],                      True),
            "requests":   (r["total_requests"],       f'{r["total_requests"]:,}',    True),
            "errors":     (r["error_rate"],           r["error_rate"],               True),
            "throughput": (r["throughput"],           r["throughput"],               True),
            "peak_cpu":   (s.get("peak_cpu", 0),      f'{s["peak_cpu"]}%' if s else "—", True),
            "peak_mem":   (s.get("peak_mem_mb", 0),   f'{s["peak_mem_mb"]} MB' if s else "—", True),
            "avg_mem":    (s.get("avg_mem_mb", 0),    f'{s["avg_mem_mb"]} MB' if s else "—", True),
        }
        tds = ""
        for _, col_id, _, _ in COLS:
            raw, display, is_num = cells[col_id]
            css = ' class="num"' if is_num else ""
            data = f' data-val="{raw}"' if is_num else ""
            tds += f"<td{css}{data}>{display}</td>"
        tbody_rows += f"<tr>{tds}</tr>"

    return f'<table class="benchmark"><thead><tr>{thead_cells}</tr></thead><tbody>{tbody_rows}</tbody></table>'


def generate_html(by_scenario, scenario_meta, ts):
    sections = ""
    for name, rows in by_scenario:
        desc = scenario_meta.get(name, {}).get("description", "")
        table_html = render_table(rows)
        sections += f"""
  <section class="scenario">
    <div class="scenario-header">
      <h2><span>{name}</span></h2>
      <p class="scenario-desc">{desc}</p>
    </div>
    <div class="table-wrap">{table_html}</div>
  </section>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Benchmark — {ts}</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>Benchmark Comparison</h1>
  <p class="subtitle">Run: {ts} &nbsp;·&nbsp; Click en cualquier columna para ordenar</p>
{sections}
  <script>{JS}</script>
</body>
</html>"""


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir")
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if not os.path.isdir(args.results_dir):
        print(f"ERROR: {args.results_dir} is not a directory")
        sys.exit(1)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    scenarios_json = os.path.join(root, "config", "scenarios.json")
    with open(scenarios_json) as f:
        scenarios_cfg = json.load(f)
    scenario_order = [s["name"] for s in scenarios_cfg]
    scenario_meta  = {s["name"]: s for s in scenarios_cfg}

    files = sorted(f for f in os.listdir(args.results_dir) if f.endswith(".json") and "_stats" not in f)
    if args.timestamp:
        files = [f for f in files if args.timestamp in f]

    if not files:
        # auto-pick latest timestamp
        all_ts = sorted({re.search(r'(\d{8}_\d{6})', f).group(1) for f in os.listdir(args.results_dir) if re.search(r'(\d{8}_\d{6})', f)})
        if not all_ts:
            print("No result files found.")
            sys.exit(0)
        latest = all_ts[-1]
        files = sorted(f for f in os.listdir(args.results_dir) if f.endswith(".json") and "_stats" not in f and latest in f)
        ts = latest
    else:
        ts = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")

    by_scenario = defaultdict(list)
    for fname in files:
        target, scenario = extract_metadata(fname)
        fpath = os.path.join(args.results_dir, fname)
        metrics = parse_k6_json(fpath)
        if metrics:
            stats = parse_stats_file(fpath.replace(".json", "_stats.jsonl"))
            by_scenario[scenario].append({"target": target, **metrics, "stats": stats})

    ordered = sorted(by_scenario.items(), key=lambda kv: scenario_order.index(kv[0]) if kv[0] in scenario_order else 999)

    html = generate_html(ordered, scenario_meta, ts)

    reports_dir = os.path.join(root, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    out_path = args.out or os.path.join(reports_dir, f"comparison_{ts}.html")
    with open(out_path, "w") as f:
        f.write(html)
    print(f"HTML report saved to {out_path}")

    # Always keep docs/index.html in sync (served by GitHub Pages)
    docs_dir = os.path.join(root, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    docs_path = os.path.join(docs_dir, "index.html")
    with open(docs_path, "w") as f:
        f.write(html)
    print(f"GitHub Pages updated → {docs_path}")


if __name__ == "__main__":
    main()
