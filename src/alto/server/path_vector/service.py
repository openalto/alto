
class PathVectorService():
    def __init__(self, mininet_host):
        self.mininet_host = mininet_host

    def lookup(self, pairs, property_names):
        paths = {}
        link_map = { 'L2': { 'bandwidth': 100, 'latency': 5} }
        for src, dst in pairs:
            if src not in paths:
                paths[src] = {}
            paths[src][dst] = ['L2']
        return paths, link_map
