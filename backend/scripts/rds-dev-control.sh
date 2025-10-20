#!/usr/bin/env bash
set -euo pipefail

# Simple helper to start/stop a dev RDS instance.
# Usage:
#   ./rds-dev-control.sh stop <db-instance-identifier> [--profile prof] [--region us-east-1]
#   ./rds-dev-control.sh start <db-instance-identifier> [--profile prof] [--region us-east-1]

ACTION=${1:-}
INSTANCE_ID=${2:-}
shift 2 || true

AWS_ARGS=("$@")

if [[ -z "$ACTION" || -z "$INSTANCE_ID" ]]; then
  echo "Usage: $0 <start|stop> <db-instance-identifier> [aws args]"
  exit 1
fi

case "$ACTION" in
  stop)
    echo "Stopping RDS instance: $INSTANCE_ID"
    aws rds stop-db-instance --db-instance-identifier "$INSTANCE_ID" "${AWS_ARGS[@]}"
    ;;
  start)
    echo "Starting RDS instance: $INSTANCE_ID"
    aws rds start-db-instance --db-instance-identifier "$INSTANCE_ID" "${AWS_ARGS[@]}"
    ;;
  *)
    echo "Unknown action: $ACTION (use start|stop)"
    exit 1
    ;;
esac


