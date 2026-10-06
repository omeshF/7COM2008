#!/usr/bin/env bash

# MQTT Temperature Server
# Subscribes to temperature topic and prints warnings if temperature is above 30C

BROKER="10.0.0.100"
TOPIC="factory/temp"
THRESHOLD=30

echo "Starting MQTT temperature server..."
echo "Listening on broker: $BROKER"
echo "Topic: $TOPIC"
echo "Warning threshold: above ${THRESHOLD}C"
echo ""
echo "Press Ctrl+C to stop."
echo ""

mosquitto_sub -h "$BROKER" -t "$TOPIC" | while read -r payload; do

    # Remove any non-numeric characters except dot and minus
    temp=$(echo "$payload" | sed 's/[^0-9.-]//g')

    if [ -z "$temp" ]; then
        echo "$(date '+%H:%M:%S') Received non-numeric payload: $payload"
        continue
    fi

    # Compare temperature numerically
    if awk -v t="$temp" -v th="$THRESHOLD" 'BEGIN { exit !(t > th) }'; then
        echo "$(date '+%H:%M:%S') TEMPERATURE: ${temp}C  *** WARNING: TEMPERATURE ABOVE ${THRESHOLD}C ***"
    else
        echo "$(date '+%H:%M:%S') TEMPERATURE: ${temp}C  OK"
    fi

done
