import asyncio, uuid
from nicegui import ui
from pyobserve.redis_utils import RedisLoop
from pyobserve.plots import Plot


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


def setup_page():
    rl = RedisLoop()
    pl = PlotterLoop(rl)

    if 1:
        fig1 = Plot(pl, "fig1")
        fig1.add_timeseries_scatter("data1")
        fig1.add_timeseries_scatter("data2")

    fig2 = Plot(pl, "fig2")
    fig2.add_histogram("data1")

    fig3 = Plot(pl, "fig3")
    fig3.add_scatter("data1")

    loop = asyncio.get_event_loop()
    loop.create_task(pl.loop())

    redis_task = loop.create_task(rl.loop())
    redis_task.set_name(f"redis-task--{uuid.uuid4().hex[:8]}")
    ui.context.client.on_disconnect(redis_task.cancel)


def main():
    ui.page('/')(setup_page)
    ui.run(reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
