import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import json
import urllib.request
import uuid, time
import os, socket, sys

run_id = str(uuid.uuid4())
series_ids = {} # key => series_id
run_serial_num = 0
mqtcc = None
db_access_server_url = "http://h1:8000/api/add-row"

def save_run_dets(*, category):
    global mqttc
    mqttc = mqtt.Client(CallbackAPIVersion.VERSION2)
    #mqttc.on_connect = on_connect
    #mqttc.on_message = on_message
    mqttc.connect("h1", 1883, 60)
    mqttc.loop_start()
    
    global run_id
    host = socket.gethostname()
    pid = os.getpid()
    #print(f"process {pid}@{host} starting with run_id {run_id}")
    run_label = os.environ.get("RUN_LABEL")
    if run_label is None:
        run_label = os.environ.get("RL")        

    rec = {"table__": "runs", "run_id": run_id, "category": category, "created_ts": time.time(), "host": host, "pid": pid, "argv0": sys.executable, "args": " ".join(sys.argv), "run_label": run_label}
    rec_js = json.dumps(rec)
    try:
        req = urllib.request.Request(db_access_server_url, data=rec_js.encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req) as response:
            result = response.read().decode("utf-8")
            print("save_run_dets:", response)
    except urllib.error.HTTPError as e:
        # If FastAPI still rejects it with a 422, this prints out the exact reason why
        print(f"HTTP Error: {e.code}")
        error_details = e.read().decode("utf-8")
        print(f"Validation details from FastAPI: {error_details}")
    except urllib.error.URLError as e:
        print(f"Failed to reach the server. Reason: {e.reason}")

def save_series_dets(series_id, run_id, key):
    global mqttc
    rec = {"table__": "series", "series_id": series_id, "run_id": run_id, "key": key}
    rec_js = json.dumps(rec)
    req = urllib.request.Request(db_access_server_url, data=rec_js.encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")   
    with urllib.request.urlopen(req) as response:
        result = response.read().decode("utf-8")
        print("save_series_dets:", response)
    
def get_series_id(key:str) -> tuple[bool, str]:
    if key in series_ids:
        return False, series_ids.get(key)    
    global run_id
    new_series_id = run_id + "---" + str(hash(key))
    series_ids[key] = new_series_id
    return True, new_series_id

def add_serial_point(key, value):
    add_ts_point(key, -1.0, value)

def add_ts_point(key, ts, value):
    is_new_key, series_id = get_series_id(key)
    if is_new_key:
        save_series_dets(series_id, run_id, key)
    global run_serial_num
    run_serial_num += 1
    global mqttc
    rec = [{"table__": "series_points", "series_id": series_id, "timestamp": ts, "value": float(value), "run_serial_num": run_serial_num}]
    rec_js = json.dumps(rec)
    mqttc.publish(f"telemetry/series/{series_id}", rec_js)
