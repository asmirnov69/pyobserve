# JupiterLI

JupiterLI - named after small Jupiter moon [Jupiter LI](https://en.wikipedia.org/wiki/Jupiter_LI)

Real-time telemetry data visualization dashboard. Data to be shown can be produced by any python code, see examples/producer.py. Resulting timeseries will be observable via JupiterLI-browser webapp.

Python package JupiterLI provides API to allow reporting values to remote application to provide measurements. 

The way how API implemented is Redis stream which is populated by API call of client library. The data intake server (redis-clickhouse-intake.py) inserts data from Redis stream listening end into clickhouse database.
JUpiterLI-browser is web-based application. Python Flask backend has access to both Redis streams and clieckhouse database. Typescript frontend provides time-series view of collected telemetry data.

JupiterLI python package provides CLI to create and manage podman container where three components are configured and running: Redis server, clickhouse database server and JupiterLI-browser backend. JupiterLI-browser frontend webapp can be used via browser.

## Install JupiterLI

First make sure podman is installed on your system

```bash
% apt install podman
```

pip install JupiterLI from github repo:

```bash
% python3 -m venv jupiterli-venv
% source jupiterli-venv
(jupiterli-venv) % pip install git+https://github.com/asmirnov69/JupiterLI
```

## Run JupiterLI

```bash
% source jupiterli-venv/bin/activate
(jupiterli-venv) % jupiterli verify # should print version of podman
(jupiterli-venv) % jupiterli init --data-dir <local dir for jupiterli podman container>
(jupiterli-venv) % jupiterli start
(jupiterli-venv) % jupiterli status
```

JupipterLI is now ready to accept telemetry information. It should be observable using JupiterLI-viewer app which connects to JupiterLI server.

# How to install and run JupiterLI-viewer?

TBC

## Run example

In one terminal, start the data producer (publishes random values to mqtt every 2.5s):
```bash
% source jupipterli-venv
(jupiterli-venv) % python examples/producer.py
```

# podman reset

Usual command to reset podman:
```
% podman system reset -f
```

In the case of errors this command sequence should help to fix errors.
```
% systemctl --user stop podman.socket
% systemctl --user stop podman.service

% sudo rm -rf ~/.local/share/containers
% rm -rf ~/.config/containers
% rm -rf ~/.cache/containers

% podman system reset -f
```
