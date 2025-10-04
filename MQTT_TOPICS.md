## Flotilla MQTT Topics (MQTT-only mode)

### Conventions

- QoS: 1 for all topics unless noted.
- Retain: only for `flotilla/server/model/global`.
- All envelopes are JSON. Binary blobs (model weights, artifacts) are base64-encoded.
- Common fields where applicable: `session_id` (string), `round_id` (number), `task_id` (string UUID), `client_id` (string), `timestamp` (unix seconds).

---

### Server → Clients

1) flotilla/server/advertise

- Purpose: Server announces runtime parameters (e.g., heartbeat interval).
- QoS: 1, Retained: true
- Payload (JSON):
  { "type": "server", "timestamp": number, "heartbeat_interval": number }

2) flotilla/server/model/global

- Purpose: Publish full global model weights each round.
- QoS: 1, Retained: true
- Payload (JSON):
  { "session_id": string, "round_id": number, "model_id": string, "model_class": string, "hash": string, "timestamp": number, "weights_b64": string }

3) flotilla/server/model/artifact/{model_id}

- Purpose: One-time model code/config tarball for cache miss.
- QoS: 1, Retained: false
- Topic param: model_id
- Payload (JSON):
  { "model_id": string, "model_class": string, "hash": string, "timestamp": number, "artifact_b64": string, "filename": string }

4) flotilla/server/command/{client_id}

- Purpose: Instruct a client to BENCHMARK, TRAIN, or TEST.
- QoS: 1, Retained: false
- Topic param: client_id
- Payload (JSON):
  { "task": "BENCHMARK" | "TRAIN" | "TEST", "task_id": string, "session_id": string, "round_id": number, "timestamp": number, "params": { "model_id": string, "model_class": string, "dataset_id": string, "batch_size": number, "learning_rate": number, "num_epochs"?: number, "timeout_duration_s"?: number } }

---

### Clients → Server

1) flotilla/client/advertise

- Purpose: Client metadata on join (no gRPC address in MQTT mode).
- QoS: 1, Retained: false
- Payload (JSON):
  { "{client_id}": { "payload": { "type": "client", "timestamp": number, "cluster_id": number, "hw_info": object, "datasets": object, "models": object, "benchmark_info": object, "name": string } } }

2) flotilla/client/heartbeat/{client_id}

- Purpose: Periodic liveness.
- QoS: 1, Retained: false
- Topic param: client_id
- Payload (JSON):
  { "id": string, "timestamp": number }

3) flotilla/client/status/{client_id}

- Purpose: Async progress updates.
- QoS: 1, Retained: false
- Topic param: client_id
- Payload (JSON):
  { "session_id": string, "round_id": number, "task_id": string, "status": "TRAINING_STARTED" | "TRAINING_COMPLETED" | "UPLOAD_COMPLETE" | "BENCHMARK_STARTED" | "BENCHMARK_COMPLETED" | "TEST_STARTED" | "TEST_COMPLETED" | "ERROR", "timestamp": number, "message"?: string }

4) flotilla/client/result/benchmark/{client_id}

- Purpose: Benchmark results.
- QoS: 1, Retained: false
- Topic param: client_id
- Payload (JSON):
  { "session_id": string, "task_id": string, "model_id": string, "hash": string, "bench_duration_s": number, "num_mini_batches": number, "timestamp": number }

5) flotilla/client/result/train/{client_id}

- Purpose: Local model update and metrics after training.
- QoS: 1, Retained: false
- Topic param: client_id
- Payload (JSON):
  { "session_id": string, "round_id": number, "task_id": string, "metrics": object, "weights_b64": string, "timestamp": number }

6) flotilla/client/result/test/{client_id}

- Purpose: Evaluation metrics.
- QoS: 1, Retained: false
- Topic param: client_id
- Payload (JSON):
  { "session_id": string, "round_id": number, "task_id": string, "metrics": object, "timestamp": number }

7) (Optional) flotilla/client/error/{client_id}

- Purpose: Structured error reports.
- QoS: 1, Retained: false
- Topic param: client_id
- Payload (JSON):
  { "session_id": string, "round_id"?: number, "task_id"?: string, "error": string, "details"?: object, "timestamp": number }

---

### Subscriptions

- Server subscribes: `flotilla/client/advertise`, `flotilla/client/heartbeat/+`, `flotilla/client/status/+`, `flotilla/client/result/benchmark/+`, `flotilla/client/result/train/+`, `flotilla/client/result/test/+`, (optional) `flotilla/client/error/+`.
- Client subscribes: `flotilla/server/advertise`, `flotilla/server/model/global`, `flotilla/server/model/artifact/+`, `flotilla/server/command/{client_id}`.

### Notes

- Use `task_id` and `round_id` for deduplication and correlation. Handlers should be idempotent.
- Model weights are serialized (e.g., pickle of `OrderedDict`) and base64-encoded into `weights_b64`.
- Artifacts are tarballs of model directory, base64-encoded into `artifact_b64`.
