import argparse
import json
import os
import threading
import time
from collections import defaultdict

import paho.mqtt.client as mqtt
import requests
import yaml


class MQTTTestRunner:
    def __init__(
        self, config_path: str, mqtt_host: str = "localhost", mqtt_port: int = 1883
    ):
        with open(config_path, "r") as f:
            self.cfg = yaml.safe_load(f)

        self.session_id = self.cfg["session_config"]["session_id"]
        self.rest_host = self.cfg.get("server_training_config", {}).get(
            "rest_host", "127.0.0.1"
        )
        self.rest_port = self.cfg.get("server_training_config", {}).get(
            "rest_port", 5000
        )

        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port

        self.events = defaultdict(list)
        self.metrics = defaultdict(lambda: defaultdict(dict))
        self.lock = threading.Lock()

    def on_connect(self, client, userdata, flags, rc):
        print(f"[mqtt] connected rc={rc}")
        client.subscribe("flotilla/#", qos=1)

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            body = json.loads(msg.payload.decode())
        except Exception:
            body = {}
        with self.lock:
            self.events[topic].append(body)
        # Simple aggregation of results
        if topic.startswith("flotilla/client/result/train/"):
            client_id = topic.split("/")[-1]
            round_id = body.get("round_id", -1)
            self.metrics[client_id][round_id]["train"] = True
        if topic.startswith("flotilla/client/result/test/"):
            client_id = topic.split("/")[-1]
            round_id = body.get("round_id", -1)
            self.metrics[client_id][round_id]["test"] = True
        if topic.startswith("flotilla/client/result/benchmark/"):
            client_id = topic.split("/")[-1]
            self.metrics[client_id][-1]["benchmark"] = True

    def start_session(self):
        url = f"http://{self.rest_host}:{self.rest_port}/execute_command"
        payload = {
            "federated_learning_config": self.cfg,
            "session_id": self.session_id,
            "restore": False,
            "revive": False,
            "file": False,
        }
        r = requests.post(url, json=payload, timeout=10)
        print(f"[rest] {r.status_code} {r.text}")

    def run(self, timeout_s: int = 120):
        client = mqtt.Client(client_id=f"test_runner_{int(time.time())}")
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        client.loop_start()

        print("[runner] starting session via REST...")
        self.start_session()

        print("[runner] listening for MQTT events...")
        deadline = time.time() + timeout_s
        try:
            while time.time() < deadline:
                time.sleep(1)
        finally:
            client.loop_stop()

        # Summary
        print("\n===== MQTT Test Summary =====")
        with self.lock:
            for client_id, rounds in self.metrics.items():
                for round_id, flags in sorted(rounds.items()):
                    label = "benchmark" if round_id == -1 else f"round {round_id}"
                    print(
                        f"client={client_id} {label}: train={flags.get('train', False)} test={flags.get('test', False)} benchmark={flags.get('benchmark', False)}"
                    )


def main():
    parser = argparse.ArgumentParser(description="Flotilla MQTT test runner")
    parser.add_argument("--config", default="config/flotilla_quicksetup_config.yaml")
    parser.add_argument("--mqtt-host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument(
        "--mqtt-port", type=int, default=int(os.getenv("MQTT_PORT", "1883"))
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    runner = MQTTTestRunner(args.config, args.mqtt_host, args.mqtt_port)
    runner.run(timeout_s=args.timeout)


if __name__ == "__main__":
    main()
