import asyncio
from pyobserve.redis_utils import RedisLoop


class PlotterLoop:
    def __init__(self, rl: RedisLoop):
        self.rl = rl
        self.plots = set()
        self.scatters = {}   # key -> list[Scatter]
        self.histograms = {} # key -> list[Histogram]

    def handle_messages(self, key, messages):
        curves = self.scatters.get(key, []) + self.histograms.get(key, [])
        for sct in curves:
            sct.append_curve(messages)

    async def loop(self):
        for plot in self.plots:
            plot.fig.update()

        while True:
            await self.rl.batch_is_done.wait()
            self.rl.batch_is_done = asyncio.Event()
            for plot in self.plots:
                plot.flush()
