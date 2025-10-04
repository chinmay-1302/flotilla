"""
Authors: Prince Modi, Roopkatha Banerjee, Yogesh Simmhan
Emails: princemodi@iisc.ac.in, roopkathab@iisc.ac.in, simmhan@iisc.ac.in
Copyright 2023 Indian Institute of Science
Licensed under the Apache License, Version 2.0, http://www.apache.org/licenses/LICENSE-2.0
"""

import json
import os
import time
from threading import Event

import paho.mqtt.client as mqtt

from client.client_file_manager import get_available_models
from client.utils.ip import get_ip_address, get_ip_address_docker
from utils.hardware_info import get_hardware_info
from utils.logger import FedLogger


class ClientMQTTManager:
    def __init__(
        self,
        id: str,
        mqtt_config: dict,
        grpc_config: dict,
        temp_dir_path: str,
        dataset_details: dict,
        client_info: dict,
        torch_device,
        dataset_paths: dict = None,
    ) -> None:
        try:
            ev = eval(os.environ["DOCKER_RUNNING"])
        except KeyError:
            ev = False

        self.ip: str = get_ip_address_docker() if ev else get_ip_address()
        self.temp_dir_path = temp_dir_path

        self.client_id: str = id
        self.client_name: str = mqtt_config["client_name"]
        self.logger: FedLogger = FedLogger(
            id=self.client_id, loggername="CLIENT_MQTT_MANAGER"
        )
        self.hw_info: dict = get_hardware_info()
        self.client_info: dict = client_info
        self.torch_device = torch_device

        self.type_: str = mqtt_config["type"]
        self.mqtt_broker: str = mqtt_config["mqtt_broker"]
        self.mqtt_broker_port: int = int(mqtt_config["mqtt_broker_port"])
        self.mqtt_heartbeat_timeout_s: float = float(mqtt_config["heartbeat_timeout_s"])
        # New topic scheme
        self.server_advertise_topic: str = "flotilla/server/advertise"
        self.client_advertise_topic: str = "flotilla/client/advertise"
        self.client_heartbeat_topic: str = f"flotilla/client/heartbeat/{id}"

        self.grpc_port: str = str(grpc_config["sync_port"])
        self.grpc_workers: int = grpc_config["workers"]
        self.grpc_ep: str = f"{self.ip}:{self.grpc_port}"
        self.dataset_details: dict = dataset_details
        self.dataset_paths: dict = dataset_paths if dataset_paths is not None else {}
        self.session_id = None

        self.heard_from_server_event = Event()

    def mqtt_sub(self, event_flag):
        def on_connect(client, userdata, flags, rc):
            self.logger.info("MQTT.client.connect", f"MQTT connection status,{rc}")

        def on_subscribe(client, userdata, mid, granted_qos):
            self.logger.info(
                "MQTT.client.subscribe", f"subscribe tracking variable:,{mid}"
            )

        def on_publish(client, userdata, mid):
            self.logger.info("MQTT.client.publish", f"publish tracking variable:,{mid}")

        def message_ad_response(client, userdata, message):
            info = json.loads(str(message.payload.decode()))
            self.mqtt_heartbeat_timeout_s = info["heartbeat_interval"]
            self.logger.info("MQTT.client.advertise.response", info)
            payload = json.dumps(
                {
                    self.client_id: {
                        "payload": {
                            "type": self.type_,
                            "timestamp": time.time(),
                            # grpc_ep omitted in MQTT-only mode
                            "cluster_id": 0,
                            "hw_info": self.hw_info,
                            "datasets": self.dataset_details,
                            "models": get_available_models(self.temp_dir_path),
                            "benchmark_info": self.client_info["benchmark_info"],
                            "name": self.client_name,
                        }
                    }
                }
            )
            client.publish(self.client_advertise_topic, payload, qos=1)
            userdata.set()
            self.logger.info(
                "MQTT.client.advert",
                f"Payload published on topic ,{self.client_advertise_topic}",
            )
            self.logger.debug(
                "MQTT.client.advert.payload",
                f"Payload to server:, {self.client_id}, {payload}",
            )

        client_userdata = self.heard_from_server_event
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            f"FedML_client_{self.client_id}",
            userdata=client_userdata,
        )
        client.user_data_set(self.heard_from_server_event)

        client.on_connect = on_connect
        client.on_subscribe = on_subscribe
        client.on_publish = on_publish

        client.connect(self.mqtt_broker, self.mqtt_broker_port, keepalive=60)
        self.logger.info(
            "MQTT.client.broker.connect",
            f"Connected to MQTT Broker at ,{self.mqtt_broker},{self.mqtt_broker_port}",
        )

        client.message_callback_add(self.server_advertise_topic, message_ad_response)
        client.loop_start()
        client.subscribe(self.server_advertise_topic, qos=1)
        self.logger.info(
            "MQTT.client.subscribed",
            f"Subscribed to topics:,{self.server_advertise_topic}",
        )

        self.heard_from_server_event.wait()

        # After initial handshake, subscribe to command and model topics for this client
        def on_model_global(client, userdata, message):
            # Cache latest global weights (base64)
            try:
                body = json.loads(str(message.payload.decode()))
                self.latest_global_model = body
                self.logger.info(
                    "MQTT.client.model.global", f"round,{body.get('round_id')}"
                )
            except Exception as e:
                self.logger.error("MQTT.client.model.global.error", str(e))

        def on_model_artifact(client, userdata, message):
            # Save and extract artifact tarball
            try:
                import base64, tarfile, io, os

                body = json.loads(str(message.payload.decode()))
                artifact_b64 = body["artifact_b64"]
                data = base64.b64decode(artifact_b64)
                with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                    tf.extractall(
                        path=os.path.join(
                            self.temp_dir_path, "model_cache", body["model_id"]
                        )
                    )
                self.logger.info(
                    "MQTT.client.model.artifact", f"model_id,{body['model_id']}"
                )
            except Exception as e:
                self.logger.error("MQTT.client.model.artifact.error", str(e))

        def on_command(client, userdata, message):
            # Dispatch tasks and publish results/status
            try:
                import base64, pickle
                from client.client import Client as FloClient

                body = json.loads(str(message.payload.decode()))
                task = body["task"]
                params = body.get("params", {})
                task_id = body.get("task_id")
                round_id = body.get("round_id")
                session_id = body.get("session_id")

                # Helper to publish status/result
                def pub(topic, payload):
                    client.publish(topic, json.dumps(payload), qos=1)

                status_topic = f"flotilla/client/status/{self.client_id}"
                result_prefix = f"flotilla/client/result"

                # Instantiate client per command
                flo = FloClient(
                    client_id=self.client_id,
                    torch_device=str(self.torch_device),
                    temp_dir_path=self.temp_dir_path,
                    dataset_paths=self.dataset_paths,
                    client_info=self.client_info,
                )

                if task == "BENCHMARK":
                    pub(
                        status_topic,
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "status": "BENCHMARK_STARTED",
                            "timestamp": time.time(),
                        },
                    )
                    res = flo.Benchmark(
                        model_id=params["model_id"],
                        model_class=params["model_class"],
                        model_config=params.get("model_config"),
                        dataset_id=params["dataset_id"],
                        batch_size=params["batch_size"],
                        learning_rate=params["learning_rate"],
                        loss_function=None,
                        optimizer=None,
                        timeout_duration_s=params.get("timeout_duration_s"),
                        max_mini_batches=params.get("bench_minibatch_count"),
                    )
                    pub(
                        f"{result_prefix}/benchmark/{self.client_id}",
                        {
                            "session_id": session_id,
                            "task_id": task_id,
                            "model_id": params["model_id"],
                            "hash": res.get("model_hash", ""),
                            "bench_duration_s": res.get("time_taken_s"),
                            "num_mini_batches": res.get("total_mini_batches"),
                            "timestamp": time.time(),
                        },
                    )
                    pub(
                        status_topic,
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "status": "BENCHMARK_COMPLETED",
                            "timestamp": time.time(),
                        },
                    )

                elif task == "TRAIN":
                    pub(
                        status_topic,
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "status": "TRAINING_STARTED",
                            "timestamp": time.time(),
                        },
                    )
                    # Use latest global weights if supplied
                    model_wts = None
                    if self.latest_global_model and self.latest_global_model.get(
                        "weights_b64"
                    ):
                        model_wts = base64.b64decode(
                            self.latest_global_model["weights_b64"]
                        )  # pickled OrderedDict
                    try:
                        res, new_wts = flo.Train(
                            model_id=params["model_id"],
                            model_class=params["model_class"],
                            model_config=params.get("model_config"),
                            dataset_id=params["dataset_id"],
                            model_wts=model_wts,
                            batch_size=params["batch_size"],
                            learning_rate=params["learning_rate"],
                            num_epochs=params["num_epochs"],
                            loss_function=None,
                            optimizer=None,
                            timeout_duration_s=params.get("timeout_duration_s"),
                            max_epochs=params.get("max_epochs"),
                            max_mini_batches=params.get("max_mini_batches"),
                        )
                    except Exception as ex:
                        # Signal artifact request if model files missing
                        client.publish(
                            status_topic,
                            json.dumps(
                                {
                                    "session_id": session_id,
                                    "round_id": round_id,
                                    "task_id": task_id,
                                    "status": "ERROR",
                                    "timestamp": time.time(),
                                    "message": f"artifact missing: {str(ex)}",
                                }
                            ),
                            qos=1,
                        )
                        return
                    pub(
                        f"{result_prefix}/train/{self.client_id}",
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "metrics": res,
                            "weights_b64": base64.b64encode(
                                pickle.dumps(new_wts)
                            ).decode("utf-8"),
                            "timestamp": time.time(),
                        },
                    )
                    pub(
                        status_topic,
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "status": "TRAINING_COMPLETED",
                            "timestamp": time.time(),
                        },
                    )

                elif task == "TEST":
                    pub(
                        status_topic,
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "status": "TEST_STARTED",
                            "timestamp": time.time(),
                        },
                    )
                    model_wts = None
                    if self.latest_global_model and self.latest_global_model.get(
                        "weights_b64"
                    ):
                        model_wts = base64.b64decode(
                            self.latest_global_model["weights_b64"]
                        )  # pickled OrderedDict
                    res = flo.Validate(
                        model_id=params["model_id"],
                        model_class=params["model_class"],
                        model_config=params.get("model_config"),
                        dataset_id=params["dataset_id"],
                        model_wts=model_wts,
                        batch_size=params["batch_size"],
                        loss_function=None,
                        optimizer=None,
                    )
                    pub(
                        f"{result_prefix}/test/{self.client_id}",
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "metrics": res,
                            "timestamp": time.time(),
                        },
                    )
                    pub(
                        status_topic,
                        {
                            "session_id": session_id,
                            "round_id": round_id,
                            "task_id": task_id,
                            "status": "TEST_COMPLETED",
                            "timestamp": time.time(),
                        },
                    )
            except Exception as e:
                self.logger.error("MQTT.client.command.error", str(e))
                client.publish(
                    f"flotilla/client/status/{self.client_id}",
                    json.dumps(
                        {
                            "task_id": (
                                body.get("task_id") if "body" in locals() else None
                            ),
                            "status": "ERROR",
                            "timestamp": time.time(),
                            "message": str(e),
                        }
                    ),
                    qos=1,
                )

        # Subscriptions for operation
        client.message_callback_add("flotilla/server/model/global", on_model_global)
        client.subscribe("flotilla/server/model/global", qos=1)
        client.message_callback_add(
            "flotilla/server/model/artifact/+", on_model_artifact
        )
        client.subscribe("flotilla/server/model/artifact/+", qos=1)
        client.message_callback_add(
            f"flotilla/server/command/{self.client_id}", on_command
        )
        client.subscribe(f"flotilla/server/command/{self.client_id}", qos=1)

        while not event_flag.is_set():
            payload = json.dumps({"id": self.client_id, "timestamp": time.time()})
            client.publish(self.client_heartbeat_topic, payload, qos=1)
            payload = json.loads(payload)
            self.logger.debug(
                "MQTT.client.heartbeat.payload",
                f"Heartbeat sent client_id and timestamp:, {payload['id']},{payload['timestamp']}",
            )
            event_flag.wait(self.mqtt_heartbeat_timeout_s)

        client.loop_stop()
