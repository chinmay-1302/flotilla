#!/bin/bash

# Simple test script for MQTT mode
echo "Starting Flotilla MQTT Test..."

# Check if mosquitto is running
if ! pgrep -x "mosquitto" > /dev/null; then
    echo "Starting mosquitto broker..."
    mosquitto -d
    sleep 2
fi

# Create necessary directories
mkdir -p ./temp ./scratch ./checkpoints ./data

echo "Starting server..."
source venv/bin/activate
python3 src/flo_server.py &
SERVER_PID=$!

# Wait for server to start
sleep 3

echo "Starting clients..."
export FLOTILLA_PROTOCOL=mqtt

# Start first client
source src/client/client_venv/bin/activate
python3 src/flo_client.py &
CLIENT1_PID=$!

# Start second client  
python3 src/flo_client.py &
CLIENT2_PID=$!

# Wait for clients to connect
sleep 5

echo "Starting training session..."
source venv/bin/activate
python3 helper/mqtt_test_runner.py --config config/flotilla_quicksetup_config.yaml --timeout 60

echo "Cleaning up..."
kill $SERVER_PID $CLIENT1_PID $CLIENT2_PID 2>/dev/null
wait
