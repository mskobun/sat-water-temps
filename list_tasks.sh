#!/bin/bash

# List the last 20 task_ids from Step Function executions
# Usage: ./list_tasks.sh

# Ensure we get the ARN correctly
if [ -d "terraform" ]; then
    cd terraform
    STATE_MACHINE_ARN=$(terraform output -raw step_function_arn)
    cd ..
else
    # Assume we are in terraform dir or it works
    STATE_MACHINE_ARN=$(terraform output -raw step_function_arn)
fi

echo "Fetching last 20 executions for: $STATE_MACHINE_ARN"

# Get execution ARNs
EXEC_ARNS=$(aws stepfunctions list-executions \
    --state-machine-arn "$STATE_MACHINE_ARN" \
    --max-results 20 \
    --query 'executions[*].executionArn' \
    --output text)

echo "---------------------------------------------------"
echo "DATE                 | STATUS    | TASK_ID"
echo "---------------------------------------------------"

for arn in $EXEC_ARNS; do
    # Describe execution to get input and details
    DESC=$(aws stepfunctions describe-execution --execution-arn "$arn" --query '{input:input, startDate:startDate, status:status}' --output json)
    
    # Parse JSON safely using stdin
    echo "$DESC" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    input_data = json.loads(data['input'])
    task_id = input_data.get('task_id', 'N/A')
    status = data['status']
    # Format date
    ts = data['startDate']
    print(f'{ts} | {status:<9} | {task_id}')
except Exception as e:
    print(f'Error parsing: {e}')
"
done
