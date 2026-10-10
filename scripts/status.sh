#!/usr/bin/env bash
# One-screen health check: task counts, recent log lines, commits, token usage per model.
cd "$(dirname "$0")/.." || exit 1
T=$(ls specs/*/tasks.md 2>/dev/null | head -1)
if [ -n "$T" ]; then
  echo "Tasks: done=$(grep -c '^- \[x\]' "$T")  blocked=$(grep -c '^- \[!\]' "$T")  todo=$(grep -c '^- \[ \]' "$T")"
fi
echo; echo "--- last progress lines"; tail -n 15 PROGRESS.md 2>/dev/null
echo; echo "--- last commits"; git log --oneline 2>/dev/null | head -10
echo; echo "--- token usage by model"; opencode stats --models 2>/dev/null | head -30
