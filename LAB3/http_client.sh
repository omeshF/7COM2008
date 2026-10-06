#!/bin/bash
echo "Polling HTTP REST API every 2 seconds..."
for i in {1..60}; do
  echo -n "$(date '+%H:%M:%S') Server returned: "
  curl -s http://10.0.0.100:8080/temp | python3 -c 'import sys, json; print(json.loads(sys.stdin.read())["temperature"], "C")'
  sleep 2
done
