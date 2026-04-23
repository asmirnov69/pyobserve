# JupiterLI

JupiterLI - named after small Jupiter moon [Jupiter LI](https://en.wikipedia.org/wiki/Jupiter_LI)

Real-time data visualization dashboard powered by Redis Streams and NiceGUI. Data producers publish to Redis Streams; the browser dashboard updates live as new data arrives.

## Install Redis

**Ubuntu/Debian:**
```bash
sudo apt install redis
sudo systemctl start redis
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Docker:**
```bash
docker run -p 6379:6379 redis
```

## Install JupiterLI

```bash
pip install -e .
```

## Run the example

In one terminal, start the data producer (publishes random values to Redis every 2.5s):
```bash
python examples/producer.py
```

In another terminal, start the dashboard:
```bash
pyobserve
```

Then open http://localhost:8080 in your browser.
