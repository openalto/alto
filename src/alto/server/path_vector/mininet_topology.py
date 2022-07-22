from pprint import pprint
from .ofrule import Switch
import requests
import networkx
import matplotlib.pyplot as plt

MININET_URL = "http://%s/mininet-topology.json"

META_LINK_FIELDS = ['src', 'dst', 'type']

def get_topology(url):
    json_topo = requests.get(url).json()
    g = networkx.Graph()
    for host in json_topo['host']:
        g.add_node(host['name'], **host)
    for switch in json_topo['switch']:
        g.add_node(switch['name'], **switch)
    for link in json_topo['link']:
        print('link: ', link)
        # move topology information as meta
        meta_link = {}
        meta_link['intfs'] = { link['src'], link['dst'] }
        meta_link['src'] = link['src'].split('-')[0]
        meta_link['dst'] = link['dst'].split('-')[0]
        meta_link['type'] = link['type']
        meta_link['attributes'] = { k: link[k] for k in link.keys() if k not in META_LINK_FIELDS }
        g.add_edge(meta_link['src'], meta_link['dst'], **meta_link)
    return g


class MininetTopology:
    def __init__(self, graph):
        self.graph = graph
        self.nodes = graph.nodes()
        self.hosts = [n for n in self.nodes if 1 == networkx.degree(graph, n)]
        self.switches = [Switch(**self.nodes[n]) for n in self.nodes if 1 != networkx.degree(graph, n)]
        self.edges = graph.edges()

    def get_hostname_by_ip(self, ip):
        for h in self.hosts:
            if self.graph.nodes[h]['ip'] == ip:
                return self.graph.nodes[h]['name']
        return None

    def get_switch_by_name(self, name):
        for s in self.switches:
            if s.name == name:
                return s
        return None

    # get one link from topology according to either 1 or 2 interface name(s)
    def get_link_by_intf(self, intf1, intf2=None):
        if intf2 is None:
            for e in self.edges:
                if intf1 in self.edges[e]['intfs']:
                    return self.edges[e]
        else:
            for e in self.edges:
                if {intf1, intf2} == self.edges[e]['intfs']:
                    return self.edges[e]
        return None

    def draw(self):
        plt.plot()
        networkx.draw(self.graph, with_labels=True, font_weight='bold')
        plt.show()

    def find_path(self, sip, dip):
        src = self.get_hostname_by_ip(sip)
        dst = self.get_hostname_by_ip(dip)
        assert sip is not None and dip is not None and sip != dip
        links = []

        # depth first search
        def search(switch, ingress):
            if switch not in self.hosts:
                egresses = self.get_switch_by_name(switch).find_matching_rule(ingress, sip, dip)
                if len(egresses) != 0:
                    for intf in egresses:
                        link = self.get_link_by_intf(intf)
                        links.append(link)
                        next_intf = list(link['intfs'] - {intf}).pop()
                        next_hop = next_intf.split('-')[0]
                        search(next_hop, next_intf)
                else:
                    return
            else:
                return

        # start from all neighbor switches of src
        src_intf = self.graph.nodes[src]['ports'][0]['name']
        first_link = self.get_link_by_intf(src_intf)
        next_intf = list(first_link['intfs'] - {src_intf}).pop()
        next_switch = next_intf.split('-')[0]
        links.append(first_link)
        search(next_switch, next_intf)
        return links


if __name__ == '__main__':
    graph = get_topology(MININET_URL % ('127.0.0.1:8000'))
    mt = MininetTopology(graph)
    mt.draw()

    # rucio to xrd2
    paths = mt.find_path('10.0.0.250', '10.0.0.252')
    pprint(paths)