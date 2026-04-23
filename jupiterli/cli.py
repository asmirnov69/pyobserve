import asyncio, os, pathlib, sys, uuid
from nicegui import ui, app
from jupiterli.redis_utils import RedisLoop
from jupiterli.plotter_loop import PlotterLoop
from jupiterli.config import load_config
from rdflib import Graph, URIRef, Namespace
from importlib import resources

TTL_PATH = sys.argv[1] # "examples/producer.ttl"
PKG_DIR = pathlib.Path(__file__).parent

class NiceGUIApplication:
    def __init__(self):
        self.g = None

    def verify_prefixes(self, g:Graph):
        known_prefixes = {
            "rdf": URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
            "jli": URIRef("http://example.com/jupiterli#")
        }
        
        any_errors = False
        for prefix, namespace in g.namespaces():
            if prefix in known_prefixes:
                print(prefix, namespace)
                print(type(prefix), type(namespace))
                if known_prefixes.get(prefix) != namespace:
                    any_errors = True

        if any_errors:
            print("prefix verification failed")
            sys.exit(2)
        
    def load_config_graph(self):
        try:
            shapes_g = Graph()
            jli_shacl_ttl_path = resources.files("jupiterli").joinpath("ttl/jli-shacl.ttl")
            print("parsing", jli_shacl_ttl_path)
            shapes_g.parse(jli_shacl_ttl_path, format = "turtle")
            self.verify_prefixes(shapes_g)
        except Exception as e:
            print(f">>> exception during parse of {jli_shacl_ttl_path}")
            print(e)
            sys.exit(2)

        try:
            print("parsing", TTL_PATH)
            data_g = Graph()
            data_g.parse(TTL_PATH, format="turtle")
            self.verify_prefixes(data_g)
        except Exception as e:
            print(f">>> exception during parse of {TTL_PATH}")
            print(e)
            sys.exit(2)

        # this way of merged graph construction retain order of triples, maybe broken in future
        self.g = Graph()
        self.g.parse(jli_shacl_ttl_path, format = "turtle")
        self.g.parse(TTL_PATH, format = "turtle")
            
        
    def launch(self):
        rl = RedisLoop()
        pl = PlotterLoop(rl)
        
        load_config(self.g, pl)
        
        loop = asyncio.get_event_loop()
        loop.create_task(pl.loop())
        
        redis_task = loop.create_task(rl.loop())
        redis_task.set_name(f"redis-task--{uuid.uuid4().hex[:8]}")
        ui.context.client.on_disconnect(redis_task.cancel)
        

def _watched_mtimes():
    paths = [TTL_PATH, *(str(p) for p in PKG_DIR.rglob("*.py"))]
    out = {}
    for path in paths:
        try:
            out[path] = os.stat(path).st_mtime
        except FileNotFoundError:
            pass
    return out


async def _watch_files():
    last = _watched_mtimes()
    while True:
        await asyncio.sleep(1.0)
        current = _watched_mtimes()
        for path, mtime in current.items():
            if path in last and mtime != last[path]:
                print(f"{path} changed, restarting...", flush=True)
                os.execv(sys.executable, [sys.executable, *sys.argv])
        last = current


def main():
    nicegui_app = NiceGUIApplication()
    nicegui_app.load_config_graph()
    ui.page('/')(nicegui_app.launch)
    app.on_startup(_watch_files)
    ui.run(reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
