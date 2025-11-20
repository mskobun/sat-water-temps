#!/bin/bash

# Backfill the last 15 days of data
# Usage: ./backfill.sh

FUNCTION_NAME="eco-water-temps-initiator"
DAYS_TO_BACKFILL=15

echo "Starting backfill for the last $DAYS_TO_BACKFILL days..."

for i in $(seq 1 $DAYS_TO_BACKFILL); do
    # Calculate date (Mac/BSD compatible)
    # DATE=$(date -v-${i}d +%m-%d-%Y)
    
    # Cross-platform compatible date calculation using Python
    DATE=$(python3 -c "from datetime import datetime, timedelta; print((datetime.now() - timedelta(days=$i)).strftime('%m-%d-%Y'))")
    
    echo "Triggering for date: $DATE"
    
    PAYLOAD="{\"start_date\": \"$DATE\", \"end_date\": \"$DATE\"}"
    
    aws lambda invoke \
        --function-name $FUNCTION_NAME \
        --payload "$PAYLOAD" \
        --cli-binary-format raw-in-base64-out \
        response.json
        
    cat response.json
    echo ""
    echo "-----------------------------------"
    
    # Optional: Sleep to avoid hitting rate limits too hard
    sleep 5
done

echo "Backfill trigger complete."
