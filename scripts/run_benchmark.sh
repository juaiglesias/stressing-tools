#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$ROOT/results"
SCENARIOS_DIR="$ROOT/scenarios"
TARGETS_JSON="$ROOT/config/targets.json"
SCENARIOS_JSON="$ROOT/config/scenarios.json"

mkdir -p "$RESULTS_DIR"

# ---------- resource stats collection ----------
STATS_PID=""

stop_stats() {
  if [[ -n "$STATS_PID" ]]; then
    kill -9 "$STATS_PID" 2>/dev/null || true
    STATS_PID=""
  fi
}
trap stop_stats EXIT

# ---------- argument parsing ----------
SELECTED_TARGETS=""
SELECTED_SCENARIOS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --targets)   SELECTED_TARGETS="$2";   shift 2 ;;
    --scenarios) SELECTED_SCENARIOS="$2"; shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ---------- load enabled targets ----------
mapfile -t ALL_TARGETS < <(jq -r '.[] | select(.enabled == true) | .name' "$TARGETS_JSON")

if [[ -n "$SELECTED_TARGETS" ]]; then
  IFS=',' read -ra FILTER_TARGETS <<< "$SELECTED_TARGETS"
  TARGETS=()
  for t in "${FILTER_TARGETS[@]}"; do
    # accept short name (e.g. "express") or full name (e.g. "node-express")
    for candidate in "${ALL_TARGETS[@]}"; do
      if [[ "$candidate" == "$t" || "$candidate" == *"-$t" ]]; then
        TARGETS+=("$candidate")
      fi
    done
  done
else
  TARGETS=("${ALL_TARGETS[@]}")
fi

# ---------- load enabled scenarios ----------
mapfile -t ALL_SCENARIOS < <(jq -r '.[] | select(.enabled == true) | .name' "$SCENARIOS_JSON")

if [[ -n "$SELECTED_SCENARIOS" ]]; then
  IFS=',' read -ra SCENARIOS <<< "$SELECTED_SCENARIOS"
else
  SCENARIOS=("${ALL_SCENARIOS[@]}")
fi

# ---------- validate k6 ----------
if ! command -v k6 &>/dev/null; then
  echo "ERROR: k6 not found. Install it from https://k6.io/docs/get-started/installation/"
  exit 1
fi

echo "=== Targets  : ${TARGETS[*]}"
echo "=== Scenarios: ${SCENARIOS[*]}"
echo ""

# ---------- bring up containers ----------
SERVICE_LIST="${TARGETS[*]}"
echo ">>> docker compose up -d --build $SERVICE_LIST"
# shellcheck disable=SC2086
docker compose -f "$ROOT/docker-compose.yml" up -d --build $SERVICE_LIST

# ---------- wait for healthy ----------
TIMEOUT=90
wait_healthy() {
  local name="$1"
  local elapsed=0
  echo -n "    Waiting for $name to be healthy..."
  while true; do
    status=$(docker inspect --format '{{.State.Health.Status}}' "$name" 2>/dev/null || echo "missing")
    if [[ "$status" == "healthy" ]]; then
      echo " OK"
      return 0
    fi
    if [[ $elapsed -ge $TIMEOUT ]]; then
      echo " TIMEOUT"
      echo "ERROR: $name did not become healthy within ${TIMEOUT}s"
      docker logs "$name" --tail 20 || true
      return 1
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
}

echo ">>> Waiting for targets to be healthy..."
for target in "${TARGETS[@]}"; do
  # container name = service name (docker compose default)
  container_name=$(docker compose -f "$ROOT/docker-compose.yml" ps -q "$target" 2>/dev/null | head -1)
  if [[ -z "$container_name" ]]; then
    # fallback: use service name directly as container name
    container_name="$target"
  fi
  wait_healthy "$container_name" || exit 1
done

# ---------- run benchmarks ----------
TS=$(date +%Y%m%d_%H%M%S)

for target in "${TARGETS[@]}"; do
  port=$(jq -r --arg n "$target" '.[] | select(.name == $n) | .port' "$TARGETS_JSON")

  for scenario in "${SCENARIOS[@]}"; do
    scenario_file=$(jq -r --arg s "$scenario" '.[] | select(.name == $s) | .file' "$SCENARIOS_JSON")
    method=$(jq -r --arg n "$target" --arg s "$scenario" \
      '.[] | select(.name == $n) | .tests[$s].method' "$TARGETS_JSON")
    path=$(jq -r --arg n "$target" --arg s "$scenario" \
      '.[] | select(.name == $n) | .tests[$s].path' "$TARGETS_JSON")

    if [[ "$method" == "null" || "$path" == "null" ]]; then
      echo "SKIP: $target has no test config for scenario '$scenario'"
      continue
    fi

    out_file="$RESULTS_DIR/${target}_${scenario}_${TS}.json"
    stats_file="$RESULTS_DIR/${target}_${scenario}_${TS}_stats.jsonl"

    echo ""
    echo ">>> k6: $target / $scenario → $out_file"

    CONTAINER_ID=$(docker compose -f "$ROOT/docker-compose.yml" ps -q "$target" 2>/dev/null | head -1)
    if [[ -n "$CONTAINER_ID" ]]; then
      docker stats "$CONTAINER_ID" --format '{{json .}}' --no-trunc >> "$stats_file" &
      STATS_PID=$!
    fi

    k6 run \
      --out "json=$out_file" \
      -e TARGET_URL="http://localhost:${port}" \
      -e TEST_METHOD="$method" \
      -e TEST_PATH="$path" \
      -e TARGET_NAME="$target" \
      "$ROOT/$scenario_file" || true

    stop_stats
  done
done

# ---------- compare ----------
echo ""
echo ">>> Generating comparison report..."
python3 "$ROOT/scripts/compare_results.py" "$RESULTS_DIR" --timestamp "$TS"
