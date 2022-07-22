from .mininet_topology import MININET_URL, get_topology, MininetTopology

class PathVectorService():
    def __init__(self, mininet_host):
        self.mininet_host = mininet_host
        graph = get_topology(MININET_URL % (mininet_host))
        self.topology = MininetTopology(graph)

    def lookup(self, pairs, property_names):
        print(pairs)
        paths = {}
        link_map = {}
        link_id_map = {}
        link_id = 0
        for src, dst in pairs:
            if src not in paths:
                paths[src] = {}
            links = self.topology.find_path(src, dst)
            path = []
            for l in links:
                intfs = (l['src'], l['dst'])
                if intfs not in link_id_map:
                    link_id += 1
                    link_id_map[intfs] = link_id
                ane_name = 'L%d' % (link_id_map[intfs])
                if ane_name not in link_map:
                    link_map[ane_name] = l['attributes']
                path += [ane_name]
            paths[src][dst] = path
        return paths, link_map
