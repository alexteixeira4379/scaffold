#!/usr/bin/env bash
# Local-only tests: isolated fixtures, no production migration or browser submission.
set -u
project_root=$(cd "$(dirname "$0")/../.." && pwd)
test_log_dir=$(mktemp -d /tmp/jobito-post-payment-tests.XXXXXX)
export PYTHONPATH="$project_root/scaffold/src"
result=0
pids=()
repos=(candidate-api billing-worker billing-api application-worker resume-api job-match-worker job-eligibility-worker linkedin-ingestion-worker linkedin-application-worker ingestion-controller-worker notification-router-worker resume-worker tracking-worker)
for repo in "${repos[@]}"; do
    (cd "$project_root/$repo" && timeout 60 .venv/bin/python -m pytest tests/unit -q --tb=short --disable-warnings > "$test_log_dir/$repo.log" 2>&1) &
    pids+=("$!")
done
for i in "${!pids[@]}"; do
    if ! wait "${pids[$i]}"; then result=1; fi
    printf '\n%s\n' "${repos[$i]}"
    tail -n 12 "$test_log_dir/${repos[$i]}.log"
done
(cd "$project_root/scaffold" && timeout 60 .venv/bin/python -m pytest tests/post_payment tests/test_messaging_rabbitmq.py tests/test_messaging_memory.py tests/test_messaging_topology_jobs.py -q --tb=short --disable-warnings) || result=1
(cd "$project_root/login-bridge" && NOVNC_DIR=tests timeout 60 ../scaffold/.venv/bin/python -m pytest tests/test_api.py -q --tb=short --disable-warnings) || result=1
(cd "$project_root/dashboard" && ./node_modules/.bin/tsc --noEmit) || result=1
printf '\nLogs: %s\n' "$test_log_dir"
exit "$result"
