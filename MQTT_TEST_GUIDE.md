# MQTT Mode Test Guide

## Prerequisites

1. Install mosquitto broker:

   ```bash
   # macOS
   brew install mosquitto
   brew services start mosquitto
   
   # Or run manually
   mosquitto -d
   ```

2. Create directories:

   ```bash
   mkdir -p ./temp ./scratch ./checkpoints ./data
   ```

## Step-by-Step Test

### 1. Start Server

```bash
# Terminal 1
cd /path/to/flotilla
source venv/bin/activate
python3 src/flo_server.py
```

Server should start and show "Starting FLo_Server" and REST endpoint.

### 2. Start First Client

```bash
# Terminal 2
cd /path/to/flotilla
source src/client/client_venv/bin/activate
export FLOTILLA_PROTOCOL=mqtt
python3 src/flo_client.py
```

Should show client ID and connect to MQTT broker.

### 3. Start Second Client

```bash
# Terminal 3
cd /path/to/flotilla
source src/client/client_venv/bin/activate
export FLOTILLA_PROTOCOL=mqtt
python3 src/flo_client.py
```

### 4. Monitor MQTT Traffic (Optional)

```bash
# Terminal 4
mosquitto_sub -h localhost -t 'flotilla/#' -v
```

### 5. Start Training Session

```bash
# Terminal 5
cd /path/to/flotilla
source venv/bin/activate
python3 helper/mqtt_test_runner.py --config config/flotilla_quicksetup_config.yaml --timeout 120
```

## Expected Behavior

- Server publishes `flotilla/server/advertise` (retained)
- Clients publish `flotilla/client/advertise` and `flotilla/client/heartbeat/{client_id}`
- Server detects clients and shows "active clients"
- Training session starts and publishes:
  - `flotilla/server/model/global` (retained, per round)
  - `flotilla/server/command/{client_id}` (per client task)
- Clients respond with:
  - `flotilla/client/result/train/{client_id}`
  - `flotilla/client/result/test/{client_id}`
  - `flotilla/client/status/{client_id}`

## Troubleshooting

- If clients don't connect: check mosquitto is running (`ps aux | grep mosquitto`)
- If IP detection fails: client will use 127.0.0.1 (fixed in code)
- If config errors: ensure `config/flotilla_quicksetup_config.yaml` has `communication_protocol: mqtt`
