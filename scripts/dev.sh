#!/usr/bin/env bash
# Both halves of the app, started together and - the point of this file - shut
# down together.
#
# Ctrl+C reaches every process in the group, so the servers do stop. What made
# it feel otherwise is that `wait` gives up the instant the signal lands: bash
# exited, the prompt came back, and uvicorn's reloader was still printing its
# shutdown a moment later, on top of the new prompt. The obvious read is that
# it did not work, so you press it again.
#
# Here the trap stops the children and then waits for them, so the prompt
# returns last - once both ports are actually free.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

pids=()

shutdown() {
  trap - INT TERM EXIT
  # macOS ships bash 3.2, where an empty array under `set -u` is an error.
  if [ ${#pids[@]} -gt 0 ]; then
    kill "${pids[@]}" 2>/dev/null
    wait "${pids[@]}" 2>/dev/null
  fi
  echo "dreamwalker: stopped"
}
# Ctrl+C is how this is meant to end, so it is not a failure: exit 0 rather
# than 130, which bun would otherwise report as `script "dev" exited with
# code 130`. A server dying on its own still falls through to the EXIT trap
# and keeps its own status.
trap 'shutdown; exit 0' INT TERM
trap shutdown EXIT

(cd backend && exec uv run uvicorn app.main:app --reload --port 8000) &
pids+=($!)
(cd web && exec bun run dev) &
pids+=($!)

# Interrupted by the trap above; the real waiting happens in `shutdown`.
wait
