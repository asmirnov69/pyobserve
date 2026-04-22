import asyncio, uuid
from nicegui import ui
from pyobserve.redis_utils import RedisLoop
from pyobserve.plots import Plot
from pyobserve.plotter_loop import PlotterLoop


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
