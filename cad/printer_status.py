"""Connection test for the Bambu printer on the LAN.

Authenticates over MQTT (TLS, port 8883), requests a full status push and
prints the interesting fields. Credentials come from .env.

Run with:  uv run printer_status.py
"""

import json
import os
import ssl
import sys
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

IP = os.environ["BAMBU_PRINTER_IP"]
SERIAL = os.environ["BAMBU_PRINTER_SERIAL"]
ACCESS_CODE = os.environ["BAMBU_ACCESS_CODE"]

reports: list[dict] = []


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        print(f"MQTT connection refused: {reason_code}")
        sys.exit(1)
    print(f"Connected to printer at {IP}")
    client.subscribe(f"device/{SERIAL}/report")
    # Ask the printer to push its complete state
    client.publish(
        f"device/{SERIAL}/request",
        json.dumps({"pushing": {"sequence_id": "1", "command": "pushall"}}),
    )
    client.publish(
        f"device/{SERIAL}/request",
        json.dumps({"info": {"sequence_id": "2", "command": "get_version"}}),
    )


def on_message(client, userdata, msg):
    reports.append(json.loads(msg.payload))


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set("bblp", ACCESS_CODE)
client.tls_set(cert_reqs=ssl.CERT_NONE)  # printer uses a self-signed cert
client.tls_insecure_set(True)
client.on_connect = on_connect
client.on_message = on_message

client.connect(IP, 8883, keepalive=30)
client.loop_start()

deadline = time.time() + 12
while time.time() < deadline:
    time.sleep(0.5)

client.loop_stop()
client.disconnect()

if not reports:
    print("Connected but received no reports — check access code / LAN mode")
    sys.exit(1)

print(f"\nReceived {len(reports)} report(s)\n")

for r in reports:
    if "info" in r and "module" in r.get("info", {}):
        print("== Device info ==")
        for m in r["info"]["module"]:
            name = m.get("name", "?")
            print(f"  {name}: sw {m.get('sw_ver', '?')}  hw {m.get('hw_ver', '?')}")
    if "print" in r:
        p = r["print"]
        interesting = {
            "gcode_state": "State",
            "mc_percent": "Progress %",
            "mc_remaining_time": "Remaining (min)",
            "nozzle_temper": "Nozzle temp",
            "bed_temper": "Bed temp",
            "chamber_temper": "Chamber temp",
            "wifi_signal": "WiFi",
            "subtask_name": "Job",
            "total_layer_num": "Total layers",
            "layer_num": "Current layer",
        }
        shown = {v: p[k] for k, v in interesting.items() if k in p}
        if shown:
            print("== Printer status ==")
            for k, v in shown.items():
                print(f"  {k}: {v}")
