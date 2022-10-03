import re
import ipaddress
import requests
import json

from lxml import html
from pytricia import PyTricia

from .db import data_broker_manager, ForwardingRule, Match, Action


class DataSourceAgent:
    """
    Base class of the data source agent.
    """

    def __init__(self, namespace='default', db_types=[], **kwargs):
        self.db = [data_broker_manager.get(namespace, t) for t in db_types]

    def update(self):
        """
        This method should be called by a centralized scheduler.
        """
        raise NotImplementedError


class LookingGlassAgent(DataSourceAgent):
    """
    Class of data source agent for looking glass server.
    """

    def __init__(self, uri, namespace='default', listened_routers=set(),
                 default_router=None, refresh_interval=None, proxies=None, **kwargs):
        super().__init__(namespace, db_types=['forwarding', 'endpoint'])
        self.uri = uri
        self.router = default_router
        self.proxies = proxies
        self.refresh_interval = refresh_interval
        self.listened_routers = set(listened_routers)
        if not self.listened_routers:
            self.listened_routers.add(default_router)
        if default_router:
            eb_trans = self.db[1].new_transaction()
            default_sw = {'dpid': default_router, 'in_port': '0'}
            eb_trans.add_property('0.0.0.0/0', default_sw)
            eb_trans.commit()

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
        """
        Get a single route entry.

        Parameters
        ----------
        ipprefix : str
            Destination IP prefix to lookup.
        router : str
            Name of the looking glass router. If None, `default_router` will be
            used.
        selected : bool
            Whether only return the selected route or not.

        Returns
        -------
        routes : list
            All the route entries for the given destination IP prefix.
        """
        route_str = self._do_query(query='route', router=router, args=ipprefix)
        routes = self._parse_route(route_str)
        if selected:
            routes = [r for r in routes if r.get('selected')]
        return routes

    def get_all_routes(self, router=None, selected=False):
        """
        Get routes for all reachable prefixes.

        Parameters
        ----------
        router : str
            Name of the looking glass router. If None, `default_router` will be
            used.
        selected : bool
            Whether only return selected routes or not.

        Returns
        -------
        routes : dict
            A dictionary mapping each reachable prefix to a list of route
            entries.
        """
        route_str = self._do_query(query='routes4', router=router)
        routes = self._parse_all_routes(route_str, route_dict=dict())
        route_str = self._do_query(query='routes6', router=router)
        routes = self._parse_all_routes(route_str, route_dict=routes)
        if selected:
            for p in routes:
                routes[p] = [r for r in routes[p] if r.get('selected')]
        return routes

    def update(self):
        fib_trans = self.db[0].new_transaction()
        for _router in self.listened_routers:
            routes = self.get_all_routes(_router, selected=True)
            for dst_prefix, route in routes.items():
                if route:
                    route = route[0]
                else:
                    continue
                pkt_match = Match(dst_prefix)
                action = Action(**route)
                rule = ForwardingRule(pkt_match, action)
                fib_trans.add_rule(_router, rule)
        fib_trans.commit()


class CRICAgent(DataSourceAgent):

    def __init__(self, uri, namespace='default', local_asn=None,
                 refresh_interval=None, proxies=None, **kwargs):
        super().__init__(namespace, db_types=['endpoint'])
        self.uri = uri
        self.netroute_map = dict()
        self.local_asn = local_asn

    def update(self):
        eb_trans = self.db[0].new_transaction()
        cric_dict = dict()
        if self.uri.startswith('http'):
            data = requests.get(self.uri, verify=False)
            cric_dict = json.loads(data.content)
        else:
            with open(self.uri, 'r') as f_cric:
                cric_dict = json.load(f_cric)

        for rcsite_name, rcsite_obj in cric_dict.items():
            netroutes = rcsite_obj.get('netroutes', dict())
            for _, netroute in netroutes.items():
                for _, ipprefixes in netroute['networks'].items():
                    for ipprefix in ipprefixes:
                        asn = netroute.get('asn')
                        if asn == self.local_asn:
                            eb_trans.add_property(ipprefix, {'is_local': True})
        eb_trans.commit()
