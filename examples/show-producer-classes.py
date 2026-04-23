from rdflib import Graph, RDF, URIRef, Literal
import jupiterli, os.path

# =========================================================
# Namespaces
# =========================================================
SH = URIRef("http://www.w3.org/ns/shacl#")
XSD = "http://www.w3.org/2001/XMLSchema#"


# =========================================================
# TYPE CONVERTERS (GLOBAL REGISTRY)
# =========================================================
TYPE_CONVERTERS = {
    XSD + "string": str,
    XSD + "integer": int,
    XSD + "float": float,
    XSD + "boolean": lambda x: str(x).lower() == "true",
}

def coerce(value):
    if isinstance(value, Literal) and value.datatype:
        fn = TYPE_CONVERTERS.get(str(value.datatype))
        if fn:
            return fn(value)
    return value


# =========================================================
# UTILITIES
# =========================================================
def local_name(uri):
    s = str(uri)
    return s.split("#")[-1] if "#" in s else s.split("/")[-1]

def build_prefix_map(graph):
    return {p: str(u) for p, u in graph.namespace_manager.namespaces()}

def resolve_curie(curie, prefix_map):
    if curie.startswith("http"):
        return curie
    if not curie.startswith(":"):
        raise ValueError(f"CURIE must start with ':' (default prefix): {curie!r}")
    return prefix_map[""] + curie[1:]

# =========================================================
# CLASS FACTORY (RUNTIME + SOURCE GENERATION)
# =========================================================
def make_class(name, props, class_prefix="jli__"):
    """
    props: list of tuples (path, datatype, class_uri, min_count, max_count)
    maxCount == 1 → scalar member; anything else → list member
    """

    def map_type(datatype, class_uri, is_list):
        if datatype:
            dt = str(datatype)
            if dt.endswith("string"):
                base = "str"
            elif dt.endswith("integer"):
                base = "int"
            elif dt.endswith("float"):
                base = "float"
            elif dt.endswith("boolean"):
                base = "bool"
            else:
                base = "Any"
        elif class_uri:
            base = class_prefix + local_name(class_uri)
        else:
            base = "Any"
        return f"list[{base}]" if is_list else base

    annotations = {}
    for path, datatype, class_uri, min_count, max_count in props:
        is_list = max_count is None or int(max_count) != 1
        annotations[local_name(path)] = map_type(datatype, class_uri, is_list)

    # runtime class behavior
    def __init__(self, _ctx=None, _uri=None, **kwargs):
        self._ctx = _ctx
        self._uri = _uri
        self._data = kwargs

    def __getattr__(self, item):
        if item in self._data:
            val = self._data[item]
            if isinstance(val, list):
                if self._ctx:
                    val = [self._ctx.get(v) if isinstance(v, URIRef) else v for v in val]
            elif isinstance(val, URIRef) and self._ctx:
                val = self._ctx.get(val)
            setattr(self, item, val)
            return val
        raise AttributeError(f"{name}.{item}")

    def __repr__(self):
        return f"{name}({self._uri})"

    cls = type(name, (), {
        "__init__": __init__,
        "__getattr__": __getattr__,
        "__repr__": __repr__,
        "__annotations__": annotations,
    })

    # generate Python source code
    lines = [f"class {name}:"]
    lines.append("    def __init__(self, **kwargs):")

    if not annotations:
        lines.append("        pass")
    else:
        for attr, typ in annotations.items():
            default = "[]" if typ.startswith("list[") else "None"
            lines.append(f"        self.{attr}: {typ} = kwargs.get('{attr}', {default})")

    source_code = "\n".join(lines)

    return cls, source_code


# =========================================================
# CONTEXT (IDENTITY MAP + DOT ACCESS)
# =========================================================
class Context:
    def __init__(self):
        self.instances = {}
        self.classes = {}
        self.prefix_map = {}

    def bind_prefixes(self, prefix_map):
        self.prefix_map = prefix_map

    def register_class(self, uri, cls):
        self.classes[uri] = cls

    def get(self, uri):
        return self.instances.get(uri)

    def resolve(self, uri, g, shapes):
        if uri in self.instances:
            return self.instances[uri]

        rdf_type = g.value(uri, RDF.type)
        cls = self.classes.get(rdf_type)
        if not cls:
            return None

        kwargs = {}
        for p, datatype, class_uri, min_count, max_count in shapes.get(rdf_type, []):
            is_list = max_count is None or int(max_count) != 1
            if is_list:
                kwargs[local_name(p)] = [coerce(v) for v in g.objects(uri, p)]
            else:
                val = g.value(uri, p)
                if val:
                    kwargs[local_name(p)] = coerce(val)

        obj = cls(_ctx=self, _uri=uri, **kwargs)
        self.instances[uri] = obj
        return obj

    def __getattr__(self, name):
        # default ":" prefix
        base = self.prefix_map.get("")
        if base:
            uri = URIRef(base + name)
            return self.instances.get(uri)
        raise AttributeError(name)


# =========================================================
# SHACL EXTRACTION
# =========================================================
def extract_shapes(g):
    shapes = {}

    for shape in g.subjects(RDF.type, SH + "NodeShape"):
        target = shape # g.value(shape, SH + "targetClass")
        if not target:
            continue

        props = []
        for p in g.objects(shape, SH + "property"):
            path = g.value(p, SH + "path")
            datatype = g.value(p, SH + "datatype")
            cls = g.value(p, SH + "class")
            min_count = g.value(p, SH + "minCount")
            max_count = g.value(p, SH + "maxCount")

            if path and path != RDF.type:
                props.append((path, datatype, cls, min_count, max_count))

        shapes[target] = props

    return shapes


# =========================================================
# BUILD RUNTIME
# =========================================================
def build_runtime(g, class_prefix="jli__"):
    ctx = Context()

    prefix_map = build_prefix_map(g)
    ctx.bind_prefixes(prefix_map)

    shapes = extract_shapes(g)

    class_sources = {}

    for cls_uri, props in shapes.items():
        name = class_prefix + local_name(cls_uri)

        cls, src = make_class(name, props, class_prefix=class_prefix)

        ctx.register_class(cls_uri, cls)
        class_sources[name] = src

    return ctx, shapes, class_sources


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":

    g = Graph()
    jli_shacl_ttl_path = os.path.join(jupiterli.__path__[0], "ttl/jli-shacl.ttl")
    g.parse(jli_shacl_ttl_path, format = "turtle")
    g.parse("producer.ttl", format="turtle")

    ctx, shapes, class_sources = build_runtime(g)

    # build identity map
    for s in g.subjects(RDF.type, None):
        ctx.resolve(s, g, shapes)

    if 0:
        # usage
        market = ctx.fig1
        mq = ctx.fig1_c1
        
        print(market.title)
        print(mq.on_plot.title)
        
        # identity check
        print(mq.on_plot is market)

        for c in market.curves:
            print("curves title:", c.title)
    
    # =====================================================
    # TEST OUTPUT
    # =====================================================
    if 0:
        fig1_uri = URIRef(resolve_curie(":fig1", ctx.prefix_map))
        print("fig1_uri:", fig1_uri)
        fig1 = ctx.get(URIRef(resolve_curie(":fig1", ctx.prefix_map)))
        fig1_c1 = ctx.get(URIRef("http://example.com/scratch#fig1_c1"))

        print(fig1.title)
        print(fig1_c1.on_plot.title)

        # DOT ACCESS API
        print("ctx dot access")
        print(ctx.fig1.title)
        print(ctx.fig1_c2.title, ctx.fig1_c2.on_plot.title)

        print(ctx.fig3_c1.title)

        
    # show generated classes
    print("\n--- Generated Classes ---\n")
    for name, src in class_sources.items():
        print(src)
        print()
