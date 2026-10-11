#!/usr/bin/env bash
# Hands-off build loop: implementer -> tester -> reviewer for every unchecked task in tasks.md.
# Resumable (state lives in the tasks.md checkboxes) and quota-aware (retry with backoff, then stop cleanly).
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f agents.env ] && source agents.env

: "${MODEL_STRONG:=}" "${MODEL_FAST:=}" "${MODEL_LITE:=}"
: "${MAX_ROUNDS:=4}"
: "${MAX_RETRIES:=4}"
: "${BACKOFF_BASE:=60}"
: "${CALL_GAP:=10}"
: "${CONTINUE_ON_BLOCK:=1}"
: "${FALLBACK_MODELS:=}"   # space-separated models tried when one runs out of daily quota
LAST_MODEL=default
declare -A EXHAUSTED=()
TASKS_FILE="${TASKS_FILE:-$(ls specs/*/tasks.md 2>/dev/null | head -1)}"
LOG_DIR=.agent-logs
PROGRESS=PROGRESS.md
mkdir -p "$LOG_DIR"
touch .gitignore
for p in .agent-logs/ .env; do grep -qxF "$p" .gitignore || echo "$p" >> .gitignore; done
[ -f "$PROGRESS" ] || echo "# Progress log (written by scripts/run-loop.sh)" > "$PROGRESS"

say() { echo "$(date '+%F %T') $*" | tee -a "$PROGRESS"; }

# call_agent AGENT MODEL LOGFILE PROMPT -> 0 ok, 2 every model failed or is out of quota.
# Tries MODEL first, then each of FALLBACK_MODELS. A model whose DAILY quota is gone ("retry in 6h...")
# is skipped for the rest of the run instead of being retried pointlessly.
call_agent() {
  local agent=$1 primary=$2 log=$3 prompt=$4 model attempt rc wait
  local models=("$primary") extra=()
  read -ra extra <<<"$FALLBACK_MODELS"
  models+=("${extra[@]}")
  for model in "${models[@]}"; do
    if [ -n "$model" ] && [ -n "${EXHAUSTED[$model]:-}" ]; then continue; fi
    local args=(--agent "$agent")
    [ -n "$model" ] && args+=(--model "$model")
    attempt=0
    while [ "$attempt" -lt "$MAX_RETRIES" ]; do
      attempt=$((attempt + 1))
      opencode run "${args[@]}" "$prompt" >"$log" 2>&1
      rc=$?
      # failure = non-zero exit, or a very short reply that looks like a rate-limit error
      if [ "$rc" -eq 0 ] && ! { [ "$(wc -c <"$log")" -lt 3000 ] && grep -qiE '429|rate.?limit|quota|resource.?exhausted' "$log"; }; then
        LAST_MODEL=${model:-default}
        sleep "$CALL_GAP"
        return 0
      fi
      if grep -qiE 'retry in [0-9]+h|per ?day|perday' "$log"; then
        say "  WARN $agent: daily quota exhausted for ${model:-default model}; trying next model"
        [ -n "$model" ] && EXHAUSTED[$model]=1
        break
      fi
      wait=$((BACKOFF_BASE * (2 ** (attempt - 1))))
      say "  WARN $agent (${model:-default}) failed (rc=$rc, attempt $attempt/$MAX_RETRIES); waiting ${wait}s"
      sleep "$wait"
    done
  done
  return 2
}

commit_or_warn() {
  git add -A
  git diff --cached --quiet && return 0
  git commit -q -m "$1" || say "  WARN git commit failed - set git user.name / user.email, or later reviews will see mixed changes"
}

last_line() { grep -E "^$2" "$1" | tail -1; }
stop_quota() { say "STOP: every configured model failed or is out of quota ($1). Progress is saved. Add models to FALLBACK_MODELS or re-run after the daily reset."; exit 2; }

[ -n "$TASKS_FILE" ] && [ -f "$TASKS_FILE" ] || { echo "No tasks.md found - run the planner first."; exit 1; }
say "RUN START (tasks: $TASKS_FILE)"

while true; do
  line=$(grep -n -m1 '^- \[ \]' "$TASKS_FILE") || { say "ALL TASKS PROCESSED"; break; }
  num=${line%%:*}
  text=${line#*:}
  id=$(printf '%s' "$text" | grep -oE 'T[0-9]+' | head -1)
  id=${id:-L$num}
  say "START $id: ${text:0:110}"
  feedback=""
  ok=0

  for round in $(seq 1 "$MAX_ROUNDS"); do
    ilog="$LOG_DIR/$id-r$round-1impl.log"; tlog="$LOG_DIR/$id-r$round-2test.log"; rlog="$LOG_DIR/$id-r$round-3review.log"

    t0=$SECONDS
    call_agent implementer "$MODEL_FAST" "$ilog" \
      "Implement this task from $TASKS_FILE (line $num): $text${feedback:+

Fix these issues first:
$feedback}" || stop_quota implementer
    say "  $id r$round implementer [$LAST_MODEL] ($((SECONDS - t0))s) $(last_line "$ilog" 'STATUS:')"

    t0=$SECONDS
    call_agent tester "${MODEL_LITE:-$MODEL_FAST}" "$tlog" \
      "Test the work for this task: $text" || stop_quota tester
    tv=$(last_line "$tlog" 'TESTS:')
    say "  $id r$round tester [$LAST_MODEL] ($((SECONDS - t0))s) ${tv:-TESTS: (no verdict line)}"
    if [[ "$tv" != "TESTS: PASS"* ]]; then
      feedback="Tests failed. Tester output:
$(tail -n 40 "$tlog")"
      continue
    fi

    t0=$SECONDS
    call_agent reviewer "$MODEL_STRONG" "$rlog" \
      "Review the uncommitted changes for this task: $text" || stop_quota reviewer
    rv=$(last_line "$rlog" 'VERDICT:')
    say "  $id r$round reviewer [$LAST_MODEL] ($((SECONDS - t0))s) ${rv:-VERDICT: (none)}"
    if [[ "$rv" == "VERDICT: APPROVE"* ]]; then ok=1; break; fi
    feedback="Reviewer requested changes:
$(tail -n 40 "$rlog")"
  done

  if [ "$ok" -eq 1 ]; then
    sed -i "${num}s/^- \[ \]/- [x]/" "$TASKS_FILE"
    desc=$(printf '%s' "${text:6}" | sed -E "s/^$id //"); commit_or_warn "$id: ${desc:0:70}"
    say "DONE $id (round $round)"
  else
    sed -i "${num}s/^- \[ \]/- [!]/" "$TASKS_FILE"
    commit_or_warn "wip: $id blocked"
    say "BLOCKED $id after $MAX_ROUNDS rounds - see $LOG_DIR/$id-*"
    [ "$CONTINUE_ON_BLOCK" = 1 ] || exit 3
  fi
done

say "SUMMARY: done=$(grep -c '^- \[x\]' "$TASKS_FILE") blocked=$(grep -c '^- \[!\]' "$TASKS_FILE")"