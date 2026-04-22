import datetime
from nicegui import ui
import plotly.graph_objects as go


def make_plot__(title):
    fig = go.Figure()
    fig.update_layout(title=title, autosize=True, uirevision='constant')
    return fig


class Histogram:
    def __init__(self, plot, data_idx):
        self.plot = plot
        self.data_idx = data_idx
        self.xs = []
        self.plot.fig.figure.add_histogram(x=[])

    def append_curve(self, stream_messages):
        self.xs.extend(float(it['value']) for it in stream_messages)
        self.plot.fig.figure.data[self.data_idx].x = self.xs


class Scatter:
    def __init__(self, plot, data_idx):
        self.plot = plot
        self.data_idx = data_idx
        self.xs = []
        self.ys = []
        self.plot.fig.figure.add_scatter(x=[], y=[], mode='lines+markers')

    def append_curve(self, stream_messages):
        self.ys.extend(float(it['value']) for it in stream_messages)
        self.xs = list(range(len(self.ys)))
        trace = self.plot.fig.figure.data[self.data_idx]
        trace.x = self.xs
        trace.y = self.ys


class TimeseriesScatter:
    def __init__(self, plot, data_idx):
        self.plot = plot
        self.data_idx = data_idx
        self.xs = []
        self.ys = []
        self.plot.fig.figure.add_scatter(x=[], y=[], mode='lines+markers')

    def append_curve(self, stream_messages):
        self.xs.extend(datetime.datetime.fromtimestamp(float(it['timestamp'])) for it in stream_messages)
        self.ys.extend(float(it['value']) for it in stream_messages)
        trace = self.plot.fig.figure.data[self.data_idx]
        trace.x = self.xs
        trace.y = self.ys


class Plot:
    def __init__(self, pl, title):
        self.pl = pl
        self.pl.plots.add(self)
        self.fig = ui.plotly(make_plot__(title=title)).style('width: 100%; height: 100%;')

    def add_scatter(self, redis_key):
        new_scatter = Scatter(self, data_idx=len(self.fig.figure.data))
        self.pl.rl.subscribe(redis_key, self.pl.handle_messages)
        self.pl.scatters.setdefault(redis_key, []).append(new_scatter)

    def add_timeseries_scatter(self, redis_key):
        new_scatter = TimeseriesScatter(self, data_idx=len(self.fig.figure.data))
        self.pl.rl.subscribe(redis_key, self.pl.handle_messages)
        self.pl.scatters.setdefault(redis_key, []).append(new_scatter)

    def add_histogram(self, redis_key):
        new_hist = Histogram(self, data_idx=len(self.fig.figure.data))
        self.pl.rl.subscribe(redis_key, self.pl.handle_messages)
        self.pl.histograms.setdefault(redis_key, []).append(new_hist)
