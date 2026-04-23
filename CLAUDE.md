# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**JupiterLI** is a real-time data visualization framework that combines Redis Streams (data transport) with NiceGUI + Plotly (web dashboard). Data producers publish to Redis Streams; the UI polls for new messages and updates live charts in the browser.

## Installation and Running

```bash
# Install the package (from the repo root)
pip install -e .

# Start a Redis instance (required before running anything)
redis-server

# In one terminal — run the test data producer (publishes to Redis every 0.25s)
python examples/producer.py

# In another terminal — run the dashboard (serves on http://localhost:8080)
jupiterli
```

There are no tests and no linter config.

## Architecture

The package lives in `jupiterli/`:

### `jupiterli/redis_utils.py` — Stream Consumption
`RedisLoop` polls Redis Streams every 0.5s using `xread()`. Callers register stream keys with handlers via `subscribe(key, handler)`. After each polling cycle all handlers are called with their buffered messages (a list of Redis field-value dicts), the buffer is cleared, then `batch_is_done` (`asyncio.Event`) is set to signal the UI layer. `KeySubscriber` is a small dataclass bundling a buffer and its handler.

### `jupiterli/plots.py` — Plot Types
`Plot` wraps a NiceGUI `ui.plotly` element and owns a list of curve objects. It exposes `add_scatter`, `add_timeseries_scatter`, and `add_histogram` methods, each of which creates the corresponding curve object, registers a Redis subscription, and tracks the curve in `PlotterLoop`'s `scatters` / `histograms` dicts.

Curve classes `Histogram`, `Scatter`, `TimeseriesScatter` each hold an internal `_pending_*` buffer. `append_curve(stream_messages)` accumulates new points into the pending buffer; `flush()` sends them to the browser via `_extend_traces`.

`_extend_traces` bypasses NiceGUI's `fig.update()` / `Plotly.react()` by calling `Plotly.extendTraces` directly on the mounted Vue element via `client.run_javascript()`. This streams only the new delta to the client and avoids disrupting an in-progress pan or zoom gesture.

### `jupiterli/config.py` — TTL Config Loader
`load_config(pl, ttl_path)` parses a Turtle/RDF file with `rdflib` and builds the dashboard from it: each `jli:Plot` subject becomes a `Plot` (titled via `:title`), and each `jli:Scatter` / `jli:TimeseriesScatter` / `jli:Histogram` subject becomes a curve on its referenced `:on_plot`, subscribed to its `:redis_key`. The `jli:` and `:` (scratch) namespaces are hardcoded to `http://example.com/jupiterli#` and `http://example.com/scratch#`.

### `jupiterli/cli.py` — UI Wiring (entry point: `jupiterli`)
`setup_page` is registered as the NiceGUI page handler for `/`. Each browser connection gets its own `RedisLoop` and `PlotterLoop`, then calls `load_config(pl, TTL_PATH)` (module-level constant, default `"examples/producer.ttl"`) to instantiate plots/curves from the TTL config. On disconnect the Redis polling task is cancelled.

`_watch_files` is an auto-restart watcher registered via `app.on_startup`. It polls `st_mtime` on `TTL_PATH` plus every `*.py` under `PKG_DIR` (the `jupiterli/` package dir) every 1s; on any change it `os.execv`s the current interpreter with the original `sys.argv`, replacing the process in place. NiceGUI's own `reload=True` is not used because it does not work with console-script entry points (it re-imports the module under its dotted name, never hitting the `__main__`/`__mp_main__` guard).

`PlotterLoop.loop()` waits on `batch_is_done`, resets the event, and calls `plot.flush()` on every `Plot`. The one `fig.update()` call at the top of `loop()` (before the while loop) is an initial render trigger only.

### `examples/producer.py` — Synthetic Data Source
Publishes random integer values plus a `timestamp` field to Redis Streams `data1` and `data2` every ~0.25s using `xadd`. Streams are capped at 10,000 entries via `maxlen`. Run directly with `python examples/producer.py`.

### `examples/producer.ttl` — Dashboard Config
Turtle/RDF file declaring the plots and curves for `setup_page` to render. Contains SHACL shapes (`sh:NodeShape`) for `jli:Plot`, `jli:Scatter`, `jli:TimeseriesScatter`, `jli:Histogram` followed by instances (`:fig1`, `:fig2`, `:fig3` and their curves). The SHACL shapes are documentation/validation only — `load_config` reads the instance triples, not the shapes. Validate with `pyshacl -i rdfs examples/producer.ttl -f human`.

## Key Design Decisions

- **Batch signal**: `RedisLoop` fires one `asyncio.Event` after processing all streams per cycle, so the UI updates once per polling interval rather than once per message.
- **Incremental reads**: `RedisLoop` tracks `last_id` per stream to fetch only new messages on each `xread` call.
- **Per-client isolation**: `setup_page` creates a fresh `RedisLoop` + `PlotterLoop` per browser connection; disconnect cancels the Redis task.
- **extendTraces over react**: Live updates use `Plotly.extendTraces` via raw JavaScript rather than `Plotly.react`, so pan/zoom state is preserved during streaming updates.
- **Redis URL**: Hardcoded as `"redis://localhost"` in both `producer.py` and `redis_utils.py` — change both if using a remote Redis instance.
- **Stream message schema**: Each Redis message must contain at minimum a `"value"` field (float string). `TimeseriesScatter` additionally requires a `"timestamp"` field (Unix epoch float string).
- **TTL-driven dashboard**: Plots and curves are declared in a Turtle file (`examples/producer.ttl`) rather than hardcoded in `cli.py`. Adding or reconfiguring a chart means editing the TTL, not the Python. The config path is the module-level `TTL_PATH` constant in `cli.py` — change it there to point at a different file.
- **In-process restart-on-change**: `cli.py` polls mtimes of the TTL file and all package `*.py` files and `os.execv`s on any change, instead of using NiceGUI's `reload=True` (which is incompatible with the console-script entry point).
