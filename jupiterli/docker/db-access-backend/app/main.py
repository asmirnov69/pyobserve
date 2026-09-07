import json
import logging

from fastapi import FastAPI
from pydantic import BaseModel
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from contextlib import asynccontextmanager

from .config import settings
from .db import SQLiteClient

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup initialization
    print("Initializing db-access-backend")

    print("Connect to mqtt")
    app.mqttc = mqtt.Client(CallbackAPIVersion.VERSION2)
    #app.mqttc.on_connect = on_connect
    #app.mqttc.on_message = on_message
    app.mqttc.connect(settings.mqtt_host, settings.mqtt_port, 60)
    app.mqttc.loop_start()
    print("done")
    print("connect to db")
    app.db = SQLiteClient(settings.sqlite3_db_fn)
    print("done")
    
    print("Initialization complete")
    print(flush = True) # without this nothing shows in log

    yield

    # Shutdown cleanup
    print("Shutting down...")
    print("=====================")
    print(flush = True) # without this nothing shows in log

app = FastAPI(title="db-access-server", lifespan = lifespan)

class Run(BaseModel):
    table__: str
    run_id: str
    run_category: str
    created_ts: float
    host: str
    pid: int
    argv0: str
    args: str
    run_label: str | None

class Series(BaseModel):
    table__: str
    series_id: str
    key: str
    run_id: str

class SeriesPoint(BaseModel):
    table__: str
    series_id: str
    timestamp: float
    value: float
    run_serial_num: int

@app.get("/api/health")
def health() -> dict:
    app.db.query("SELECT 1")
    return {"ok": True}

@app.get("/api/runs", response_model=list[Run])
def list_runs() -> list[Run]:
    result = app.db.query(
        "SELECT * FROM runs ORDER BY created_ts DESC"
    )
    return [Run(table__ = 'runs', run_id=row[0], run_category = row[1], created_ts = row[1+1], host = row[2+1], pid = row[3+1], argv0 = row[4+1], args = row[5+1], run_label=row[6+1]) for row in result.result_rows]

@app.get("/api/runs/{run_id}/series", response_model=list[Series])
def list_series(run_id: str) -> list[Series]:
    result = app.db.query(
        "SELECT series_id, key FROM series WHERE run_id = %(run_id)s ORDER BY key",
        parameters={"run_id": run_id},
    )
    return [Series(table__ = "series", series_id=row[0], key=row[1], run_id = run_id) for row in result.result_rows]

@app.get("/api/series/{series_id}/history", response_model=list[SeriesPoint])
def series_history(series_id: str, max_serial: int | None = None) -> list[SeriesPoint]:
    """One-shot ClickHouse backfill. With max_serial set, returns rows with
    run_serial_num < max_serial (the active-run path: everything older than
    the first live Redis observation). Without it, returns the full series —
    used as a fallback for runs that no longer produce live data."""
    if max_serial is None:
        result = app.db.query(
            """SELECT timestamp, value, run_serial_num
               FROM series_points
               WHERE series_id = %(series_id)s
               ORDER BY run_serial_num""",
            parameters={"series_id": series_id},
        )
    else:
        result = app.db.query(
            """SELECT timestamp, value, run_serial_num
               FROM series_points
               WHERE series_id = %(series_id)s AND run_serial_num < %(max_serial)s
               ORDER BY run_serial_num""",
            parameters={"series_id": series_id, "max_serial": max_serial},
        )

    return [SeriesPoint(table__ = "series_points",
                        series_id = series_id,
                        timestamp=float(r[0]),
                        value=float(r[1]),
                        run_serial_num=int(r[2])) for r in result.result_rows]

@app.post("/api/add-row", status_code = 201)
def add_row(rec: dict):
    print("add_row:", rec)
    rec_js = json.dumps(rec)
    table_name = rec.pop('table__', None)

    if table_name is None:
        print("db-access-server::add_rec: missing 'table__' field in rec")
        return {"status": "NOT-OK" }
    
    if not table_name in ['runs', 'series']:
        print("db-access-server::add_rec: unknown table:", table_name)
        return {"status": "NOT-OK"}
    
    app.db.insert_rec(table_name, rec)
    print("to publish to telemetry-admin:", rec_js)
    app.mqttc.publish("telemetry-admin", rec_js)

    return {"status": "OK"}
