# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**pyobserve** is a real-time data visualization framework that combines Redis Streams (data transport) with NiceGUI + Plotly (web dashboard). Data producers publish to Redis Streams; the UI polls for new messages and updates live charts in the browser.

## Installation and Running

```bash
# Install the package (from the repo root)
pip install -e .

# Start a Redis instance (required before running anything)
redis-server

# In one terminal — run the test data producer (publishes to Redis every 0.25s)
python examples/producer.py

# In another terminal — run the dashboard (serves on http://localhost:8080)
pyobserve
```

There are no tests and no linter config.

## Architecture

The package lives in `pyobserve/` with three modules:

### `pyobserve/redis_utils.py` — Stream Consumption
`RedisLoop` polls Redis Streams every 0.5s using `xread()`. Callers register stream keys with handlers via `subscribe(key, handler)`. After each polling cycle all handlers are called with their buffered messages (a list of Redis field-value dicts), the buffer is cleared, then `batch_is_done` (`asyncio.Event`) is set to signal the UI layer. `KeySubscriber` is a small dataclass bundling a buffer and its handler.

### `pyobserve/plots.py` — Plot Types
`Plot` wraps a NiceGUI `ui.plotly` element and owns a list of curve objects. It exposes `add_scatter`, `add_timeseries_scatter`, and `add_histogram` methods, each of which creates the corresponding curve object, registers a Redis subscription, and tracks the curve in `PlotterLoop`'s `scatters` / `histograms` dicts.

Curve classes `Histogram`, `Scatter`, `TimeseriesScatter` each hold an internal `_pending_*` buffer. `append_curve(stream_messages)` accumulates new points into the pending buffer; `flush()` sends them to the browser via `_extend_traces`.

`_extend_traces` bypasses NiceGUI's `fig.update()` / `Plotly.react()` by calling `Plotly.extendTraces` directly on the mounted Vue element via `client.run_javascript()`. This streams only the new delta to the client and avoids disrupting an in-progress pan or zoom gesture.

### `pyobserve/cli.py` — UI Wiring (entry point: `pyobserve`)
`setup_page` is registered as the NiceGUI page handler for `/`. Each browser connection gets its own `RedisLoop` and `PlotterLoop`. On disconnect the Redis polling task is cancelled.

`PlotterLoop.loop()` waits on `batch_is_done`, resets the event, and calls `plot.flush()` on every `Plot`. The one `fig.update()` call at the top of `loop()` (before the while loop) is an initial render trigger only.

### `examples/producer.py` — Synthetic Data Source
Publishes random integer values plus a `timestamp` field to Redis Streams `data1` and `data2` every ~0.25s using `xadd`. Streams are capped at 10,000 entries via `maxlen`. Run directly with `python examples/producer.py`.

## Key Design Decisions

- **Batch signal**: `RedisLoop` fires one `asyncio.Event` after processing all streams per cycle, so the UI updates once per polling interval rather than once per message.
- **Incremental reads**: `RedisLoop` tracks `last_id` per stream to fetch only new messages on each `xread` call.
- **Per-client isolation**: `setup_page` creates a fresh `RedisLoop` + `PlotterLoop` per browser connection; disconnect cancels the Redis task.
- **extendTraces over react**: Live updates use `Plotly.extendTraces` via raw JavaScript rather than `Plotly.react`, so pan/zoom state is preserved during streaming updates.
- **Redis URL**: Hardcoded as `"redis://localhost"` in both `producer.py` and `redis_utils.py` — change both if using a remote Redis instance.
- **Stream message schema**: Each Redis message must contain at minimum a `"value"` field (float string). `TimeseriesScatter` additionally requires a `"timestamp"` field (Unix epoch float string).
