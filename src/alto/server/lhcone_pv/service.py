import re
import json
import ipaddress
import requests
import socket

from lxml import html
from pytricia import PyTricia

class CRIC(object):

    def __init__(self, filepath) -> None:
        self.filepath = filepath
        self.netroute_map = dict()
        self.load()

    def load(self):
        self.cric_dict = dict()
        if self.filepath.startswith('http'):
            data = requests.get(self.filepath, verify=False)
            self.cric_dict = json.loads(data.content)
        else:
            with open(self.filepath, 'r') as f_cric:
                self.cric_dict = json.load(f_cric)

        for rcsite_name, rcsite_obj in self.cric_dict.items():
            netroutes = rcsite_obj.get('netroutes', dict())
            for _, netroute in netroutes.items():
                for _, ipprefixes in netroute['networks'].items():
                    for ipprefix in ipprefixes:
                        self.netroute_map[ipprefix] = {
                            'rcsite': rcsite_name,
                            'netroute': netroute
                        }
        print('CRIC database loaded.')

    def find_netroute(self, ipaddr):
        ipnetwork = ipaddress.ip_network(ipaddr)
        for ipprefix in self.netroute_map.keys():
            ipprefix_obj = ipaddress.ip_network(ipprefix)
            if ipprefix_obj.version == ipnetwork.version and ipnetwork.subnet_of(ipprefix_obj):
                return ipprefix, self.netroute_map[ipprefix]
        return None, None

    def find_netroute_by_asn(self, asn):
        return sum([[n for n in rc.get('netroutes', dict()).values() if n.get('asn') == asn] for rc in self.cric_dict.values()], start=[])

    def find_subnet_by_asn(self, asn):
        netroutes = self.find_netroute_by_asn(asn)
        subnets = PyTricia(128)
        for n in netroutes:
            for p in n['networks'].get('ipv4', []):
                subnets[p] = dict()
            for p in n['networks'].get('ipv6', []):
                subnets[p] = dict()
        return subnets

    def find_asn(self, ipaddr):
        _, netroute = self.find_netroute(ipaddr)
        if netroute:
            return netroute['rcsite'], netroute['netroute']['asn']
        return None, None

    def find_services(self, rcsite_name, service_type='PerfSonar'):
        rcsite = self.cric_dict.get(rcsite_name)
        if rcsite is None:
            return []
        return [s for s in rcsite.get('services', []) if s['type'] == service_type]

    def find_closest_service(self, ipaddr, rcsite_name=None, service_type='PerfSonar'):
        if rcsite_name is None:
            _, netroute = self.find_netroute(ipaddr)
            if netroute is None:
                return None
            rcsite_name = netroute['rcsite']
        services = self.find_services(rcsite_name, service_type)
        ip = ipaddress.ip_address(ipaddr)
        closest_service = None
        min_diff = 0xffffffff
        for service in services:
            service_ip = ipaddress.ip_address(socket.gethostbyname(service['endpoint']))
            diff = eval('0x'+ip.packed.hex()) ^ eval('0x'+service_ip.packed.hex())
            if diff < min_diff:
                closest_service = service['endpoint']
                diff = min_diff
        return closest_service


def traceroute_query(src_testpoint, dst_testpoint):
    from esmond.api.client.perfsonar.query import ApiConnect, ApiFilters
    filters = ApiFilters()
    filters.tool_name = 'pscheduler/traceroute'
    filters.timeout = 5
    filters.input_source = src_testpoint
    filters.input_destination = dst_testpoint
    filters.source = socket.gethostbyname(src_testpoint)
    filters.ssl_verify = False
    conn = ApiConnect('https://' + src_testpoint, filters)
    md = next(conn.get_metadata())
    et = md.get_event_type('packet-trace')
    dpay = et.get_data()
    latest_dp = next(dpay)
    return latest_dp.val


class LookingGlass(object):

    def __init__(self, uri, default_router=None, proxies=None) -> None:
        self.uri = uri
        self.router = default_router
        self.proxies = proxies

    def _parse_route(self, route_str):
        routes = list()
        entry = dict()
        for rline in route_str.splitlines():
            line = rline.strip()
            if not line and entry:
                routes.append(entry)
                entry = dict()
            if line.startswith('BGP') or line.startswith('*BGP'):
                if entry:
                    routes.append(entry)
                entry = dict()
                if line.startswith('*'):
                    entry['selected'] = True
                line = line[4:].strip()
            # Parse line to BGP route attributes
            if line.startswith('Peer AS:'):
                asn = int(line[8:].strip())
                entry['asn'] = asn
            elif line.startswith('AS path:'):
                as_path = [asn for asn in line[8:].strip().split(' ')]
                entry['as_path'] = as_path
            elif line.startswith('Communities:'):
                communities = line[12:].strip().split(' ')
                entry['communities'] = communities
            elif line.startswith('Next hop:') and line.endswith(', selected'):
                next_hop_entry = line[10:-10].split(' via ')
                entry['next_hop'] = next_hop_entry[0]
                if len(next_hop_entry) > 1:
                    entry['outgoing_interface'] = next_hop_entry[1]
        return routes

    def _do_query(self, query='route', router=None, args=None):
        data = requests.post(self.uri,
                             data={
                                'query': query,
                                'args': args,
                                'router': router or self.router,
                                'submit': 'Submit'
                             }, proxies=self.proxies)
        doctree = html.fromstring(data.content)
        query_result = doctree.xpath('//pre[1]')
        return ''.join([r for r in query_result[0].itertext()])

    def _parse_all_routes(self, route_str, width=19, route_dict=PyTricia(128)):
        routes = list()
        route = dict()
        entry_found = False
        for line in route_str.splitlines():
            prefix = None
            try:
                match_prefix = re.match('^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])(\\.|(\\/(([12]?[0-9])|(3[0-2]))$))){4}', line)
                if match_prefix:
                    prefix = match_prefix.group()
                else:
                    prefix = ipaddress.ip_network(line[:width].strip()).exploded
            except ValueError:
                pass
            if prefix:
                routes = list()
                route_dict[prefix] = routes
                entry_found = True
            if not entry_found:
                continue
            line = line[width:].strip()
            match_bgp = re.match('^(.?)\[BGP.*\].*, localpref (.*), from (.*)$', line)
            if match_bgp:
                route = dict()
                routes.append(route)
                selected, localpref, peer = match_bgp.groups()
                if selected == '*' or selected == '+':
                    route['selected'] = True
                route['preference'] = int(localpref)
                route['peer'] = peer
            match_aspath = re.match('^AS path: (.*), validation-state: .*$', line)
            if match_aspath:
                as_path = match_aspath.groups()[0]
                route['as_path'] = [asn for asn in as_path.split(' ')]
            match_nh = re.match('> to (.*) via (.*)', line)
            if match_nh:
                next_hop, out_int = match_nh.groups()
                route['next_hop'] = next_hop
                route['outgoing_interface'] = out_int
        return route_dict

    def get_route(self, ipprefix, router=None, selected=False):
        route_str = self._do_query(query='route', router=router, args=ipprefix)
        routes = self._parse_route(route_str)
        if selected:
            routes = [r for r in routes if r.get('selected')]
        return routes

    def get_all_routes(self, router=None, selected=False):
        route_str = self._do_query(query='routes4', router=router)
        routes = self._parse_all_routes(route_str)
        route_str = self._do_query(query='routes6', router=router)
        routes = self._parse_all_routes(route_str, route_dict=routes)
        if selected:
            for p in routes:
                routes[p] = [r for r in routes[p] if r.get('selected')]
        return routes



class CERNLookingGlass(LookingGlass):

    def _parse_route(self, route_str):
        routes = list()
        entry = dict()
        header_found = False
        dest_prefix = ''
        for line in route_str.splitlines():
            if line.startswith('A V Destination'):
                header_found = True
                continue
            if not header_found:
                continue
            if not line and entry:
                routes.append(entry)
                entry = dict()
                continue
            if len(line) > 2 and line[2] == '?':
                if entry:
                    routes.append(entry)
                entry = dict()
                if line.startswith('+') or line.startswith('*'):
                    entry['selected'] = True
                dest_prefix = line[4:23].strip() or dest_prefix
                entry['dest_prefix'] = dest_prefix
                entry['protocol'] = line[23].strip()
                entry['preference'] = line[25:31].strip()
                entry['metric1'] = line[31:39].strip()
                entry['metric2'] = line[42:50].strip()
            if len(line) > 51:
                next_hop = line[51:68].strip()
                if next_hop.startswith('>'):
                    entry['next_hop'] = next_hop[1:]
                as_path = line[68:].strip()
                if as_path:
                    entry['as_path'] = [asn for asn in as_path.split(' ')]
        if entry:
            routes.append(entry)
        return routes



class LhconeALTOService:

    def __init__(self, cric: CRIC, lg: LookingGlass, local_asn: int, refresh_time=None) -> None:
        """
        """
        self.cric = cric
        self.lg = lg
        self.asn = local_asn
        self.fetch_routes()
        self.fetch_scope()
        self.fetch_capacity()
        # TODO: async update

    def lookup(self, pairs, property_names):
        """
        Example:
        "endpoint-cost-map": {
            "ipv4:10.0.0.1": {
                "ipv4:192.51.0.101": ["ane:CERN", "ane:peerlink1", "ane:path1", "ane:Caltech"]
            }
        }

        "property-map": {
            "ane:CERN": {
                ".asn": 513
            },
            "ane:path1": {
                "as_path": [293, 20965],
                "next_hop": "192.168.1.1"
            },
            "ane:Caltech: {
                ".asn": xxx
            }
        }
        """
        print(pairs)
        paths = dict()
        as_path_dict = dict()
        as_path_idx = 0
        nh_dict = dict()
        nh_idx = 0
        property_map = dict()
        print(self.scope.keys())
        for src, dst in pairs:
            if src not in self.scope:
                print(src)
                continue
            if src not in paths:
                paths[src] = dict()
            path = list()
            _, src_netroute = self.cric.find_netroute(src)
            if src_netroute is None:
                continue
            _, dst_netroute = self.cric.find_netroute(dst)
            if dst_netroute is None:
                continue
            route = self.routes[dst]
            if route:
                route = route[0]
            else:
                continue

            src_site = src_netroute['netroute']['netsite']
            src_ane = 'ane:S_%s' % src_site
            path.append(src_ane)

            if src_ane not in property_map:
                property_map[src_ane] = dict()
                property_map[src_ane]['asn'] = src_netroute['netroute']['asn']

            nh = route['next_hop']
            if nh not in nh_dict:
                nh_ane = 'ane:L_%d' % nh_idx
                nh_idx += 1
                nh_dict[nh] = nh_ane
                property_map[nh_ane] = dict()
                property_map[nh_ane]['next_hop'] = nh
                property_map[nh_ane]['bandwidth'] = self.capacity.get(nh)
            nh_ane = nh_dict[nh]
            path.append(nh_ane)

            as_path = ' '.join(route['as_path'][:-1])
            if as_path not in as_path_dict:
                as_path_ane = 'ane:P_%d' % as_path_idx
                as_path_idx += 1
                as_path_dict[as_path] = as_path_ane
                property_map[as_path_ane] = dict()
                property_map[as_path_ane]['as_path'] = as_path
            as_path_ane = as_path_dict[as_path]
            path.append(as_path_ane)

            dst_site = dst_netroute['netroute']['netsite']
            dst_ane = 'ane:S_%s' % dst_site
            path.append(dst_ane)

            if dst_ane not in property_map:
                property_map[dst_ane] = dict()
                property_map[dst_ane]['asn'] = dst_netroute['netroute']['asn']

            paths[src][dst] = path
        return paths, property_map


    def fetch_routes(self):
        self.routes = self.lg.get_all_routes(selected=True)
        print('Looking glass routing table loaded.')

    def fetch_scope(self):
        self.scope = self.cric.find_subnet_by_asn(self.asn)

    def fetch_capacity(self):
        self.capacity = dict()
        # TODO: read capacity of peer link from configuration file

    def find_path(self, src_ip, dst_ip):
        src_prefix, src_netroute = self.cric.find_netroute(src_ip)
        if src_prefix is None:
            return
        src_asn = src_netroute['netroute']['asn']
        src_rcsite = src_netroute['rcsite']
        src_testpoint = self.cric.find_closest_service(src_ip, src_rcsite)

        dst_prefix, dst_netroute = self.cric.find_netroute(dst_ip)
        if dst_prefix is None:
            return
        dst_asn = dst_netroute['netroute']['asn']
        dst_rcsite = dst_netroute['rcsite']
        dst_testpoint = self.cric.find_closest_service(dst_ip, dst_rcsite)

        tr = traceroute_query(src_testpoint, dst_testpoint)
        # TODO: if no trace route, use asn to query looking glass for as path
        return tr

    def find_as_path(self, src_ip, dst_ip):
        pass
