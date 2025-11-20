#!/bin/bash

# Reprocess an existing AppEEARS task
# Usage: ./reprocess_task.sh <TASK_ID>

if [ -z "$1" ]; then
    echo "Usage: ./reprocess_task.sh <TASK_ID>"
    exit 1
fi

TASK_ID=$1
STATE_MACHINE_ARN=$(terraform output -raw step_function_arn)

echo "Triggering reprocessing for Task ID: $TASK_ID"

aws stepfunctions start-execution \
    --state-machine-arn "$STATE_MACHINE_ARN" \
    --input "{\"task_id\": \"$TASK_ID\", \"wait_seconds\": 0}"

echo "Execution started."
