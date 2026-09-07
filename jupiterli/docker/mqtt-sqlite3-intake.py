import sys
import time
import json
import sqlite3
from datetime import datetime

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

TELEMETRY_SUBJ = "telemetry"

BATCH_SIZE = 1000
BLOCK_MS = 1000
FLUSH_INTERVAL_SEC = 2.0

def get_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + ":"

def create_all_tables(ch):
    qs = []
    qs.append("""
    CREATE TABLE IF NOT EXISTS runs (
    run_id varchar, run_category varchar,
    created_ts real, host varchar, pid integer,
    argv0 varcharg, args varchar, run_label varchar
    )
    """)

    qs.append("""
    create table if not exists series (
    series_id varchar,
    run_id varchar,
    key varchar
    )
    """)

    qs.append("""
    create table if not exists series_points (
    series_id varchar,
    run_serial_num integer,
    timestamp real,
    value real
    )
    """)

    qs.append("""
    CREATE INDEX IF NOT EXISTS idx_series_points_sid_serial
    ON series_points(series_id, run_serial_num)
    """)

    print(get_ts(), "start of intake server")
    for q in qs:
        print(q)
        ch.execute(q)

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected with result code {reason_code}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("telemetry/series/+")
    
    ## intake server ignore telemetry-admin messages since they corresponds to two-way calls
    ## such two-way calls (insert new run etc) are handled by db-access-server
    #client.subscribe("telemetry-admin") 

class StreamToSqlite3:
    def __init__(self, sqlite3_db_fn):
        self.mqttc = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.mqttc.on_connect = on_connect
        self.mqttc.on_message = self.on_message
        self.mqttc.connect("127.0.0.1", 1883, 60)

        self.prev_flush_ts = time.time()
        self.buffer = []
        self.ch = sqlite3.connect(sqlite3_db_fn)
        self.ch.execute("PRAGMA journal_mode=WAL")
        self.ch.execute("PRAGMA synchronous=NORMAL")
        self.ch.commit()
        create_all_tables(self.ch)
        if 1: # verify WAL settings
            mode = self.ch.execute("PRAGMA journal_mode").fetchone()[0]
            sync = self.ch.execute("PRAGMA synchronous").fetchone()[0]
            print("journal_mode =", mode)
            print("synchronous =", sync)

    # The callback for when a PUBLISH message is received from the server.
    def on_message(self, client, userdata, msg):
        #print(msg.topic, str(msg.payload))
        if msg.topic.startswith("telemetry/series/"):
            self.process_message(msg.payload)
        else:
            print("unknown subject:", msg.topic)

    def process_message(self, msg):
        self.buffer.append(msg)
        ts = time.time()
        if len(self.buffer) > BATCH_SIZE or ts - self.prev_flush_ts > FLUSH_INTERVAL_SEC:
            self.prev_flush_ts = ts
            self.flush()

    def flush(self):
        if len(self.buffer) == 0:
            return

        print(get_ts(), f"flush: {len(self.buffer)} msgs")

        rows = []
        cols = []
        for msg in self.buffer:            
            try:
                msg_ja = json.loads(msg)
                for msg_j in msg_ja:
                    tn = msg_j.pop('table__', "")
                    if tn != "series_points":
                        print("mqtt-sqlite3-intake.py: unknown table__ field value:", tn)
                        continue
                    rows.append(list(msg_j.values()))
                    cols = list(msg_j.keys())
            except Exception as e:
                print("exception parsing", msg, ":", e)

        self.buffer.clear()

        # 1. Insert into sqlite3
        if len(rows) > 0:
            try:
                cols_str = ",".join(cols)
                placeholders = ",".join("?" * len(cols))
                insert_q = f"insert into series_points({cols_str}) values ({placeholders})"
                print("mqtt-sqlite3-intake.py: insert query:", insert_q)
                print(rows[0])
                self.ch.executemany(f"insert into series_points({cols_str}) values ({placeholders})", rows)
                self.ch.commit()
            except Exception as e:
                # Drop the batch instead of crash-looping on it forever. With
                # no consumer group PEL, a crash here would just replay the
                # same bad batch again from the checkpoint after restart.
                print("exception inserting batch, dropping", len(rows), "rows:", e)
                self.ch.rollback()

    def run(self):
        while True:
            self.mqttc.loop(timeout = 1.0)
            self.flush()

if __name__ == "__main__":
    sqlite3_db_fn = sys.argv[1]
    print(get_ts(), "db file:", sqlite3_db_fn)
    worker = StreamToSqlite3(sqlite3_db_fn)
    worker.run()
