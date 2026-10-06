#!/usr/bin/env bash

# MQTT Temperature Sensor
# Publishes temperature to MQTT broker for 120 seconds

BROKER="10.0.0.100"
TOPIC="factory/temp"

DURATION=120
INTERVAL=2

MIN_TEMP=20
MAX_TEMP=31   # Set to 30 if you do not want it to go above 30

temp=$MIN_TEMP
direction="up"

start_time=$(date +%s)
end_time=$((start_time + DURATION))

echo "Starting MQTT temperature sensor..."
echo "Broker: $BROKER"
echo "Topic:  $TOPIC"
echo "Duration: $DURATION seconds"
echo ""

while true; do
    now=$(date +%s)

    if [ "$now" -ge "$end_time" ]; then
        echo ""
        echo "Sensor finished after $DURATION seconds."
        break
    fi

    mosquitto_pub -h "$BROKER" -t "$TOPIC" -m "$temp"

    echo "$(date '+%H:%M:%S') Sensor sent: ${temp}C"

    sleep "$INTERVAL"

    if [ "$direction" = "up" ]; then
        temp=$((temp + 1))

        if [ "$temp" -ge "$MAX_TEMP" ]; then
            direction="down"
        fi
    else
        temp=$((temp - 1))

        if [ "$temp" -le "$MIN_TEMP" ]; then
            direction="up"
        fi
    fi
done
