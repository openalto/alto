import requests
import ipaddress
import logging
import re
import time

from lxml import html
from pytricia import PyTricia

from alto.server.components.datasource import AgentService, DBInfo, DataSourceAgent
from alto.server.components.db import data_broker_manager, ForwardingRule, Match, Action

class LookingGlassAgent(DataSourceAgent):
    """
    Class of data source agent for looking glass server.
    """

    def __init__(self, dbinfo: DBInfo, name: str, namespace='default', **cfg):
        super().__init__(dbinfo, name, namespace)

        self.uri = self.ensure_field(cfg, 'uri')
        self.router = cfg.get('default_router', None)
        self.proxies = cfg.get('proxies', None)
        self.refresh_interval = cfg.get('refresh_interval', None)
        self.listened_routers = cfg.get('listened_routers', set())
        self.default_router = cfg.get('default_router', None)

        logging.info("Loading databases")
        self.db = [ self.request_db(t) for t in ['forwarding', 'endpoint']]

        if self.default_router:
            if len(self.listened_routers) == 0:
                self.listened_routers |= { self.default_router }

            eb_trans = self.db[1].new_transaction()
            default_sw = {'dpid': self.default_router, 'in_port': '0'}
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
        logging.info('Loading IPv4 routes on %s' % (router))
        route_str = self._do_query(query='routes4', router=router)
        logging.info('Parsing IPv4 routes on %s' % (router))
        routes = self._parse_all_routes(route_str, route_dict=dict())
        logging.info('Loading IPv6 routes on %s' % (router))
        route_str = self._do_query(query='routes6', router=router)
        logging.info('Parsing IPv6 routes on %s' % (router))
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

    def run(self):
        if self.refresh_interval is None:
            self.refresh_interval = 60
        while True:
            self.update()
            time.sleep(self.refresh_interval)

import alto.server.django_server.django_server.settings as conf_settings
from alto.server.components.db import data_broker_manager, ForwardingDB, EndpointDB

for ns, ns_config in conf_settings.DB_CONFIG.items():
    for db_type, db_config in ns_config.items():
        if db_type == 'forwarding':
            db = ForwardingDB(namespace=ns, **db_config)
        elif db_type == 'endpoint':
            db = EndpointDB(namespace=ns, **db_config)
        else:
            db = None
        if db:
            data_broker_manager.register(ns, db_type, db)

if __name__ == '__main__':
    import argparse
    import json

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='LHCONE LookingGlass Agent')
    subparsers = parser.add_subparsers(title='actions', dest='action')

    start_parser = subparsers.add_parser('start')
    stop_parser = subparsers.add_parser('stop')

    start_parser.add_argument('-c', '--config', dest='config',
                              help='path to the config file')
    start_parser.add_argument('-H', '--host', dest='host',
                              default=None,
                              help='host name of the data store')
    start_parser.add_argument('-p', '--port', dest='port', action='store_const',
                              default=None, const=int,
                              help='port of the data store')
    start_parser.add_argument('-n', '--namespace', dest='namespace',
                              default=None,
                              help='namespace of the agent')
    start_parser.add_argument('-d', '--daemonize', dest='daemonized',
                              action='store_true',
                              default=False,
                              help='daemonize the agent')
    parser.add_argument('--pid', dest='pid_dir', default=None,
                        help='specify the PID path to be used')

    parser.add_argument('agent_name', metavar='N')

    args = parser.parse_args()

    pid_dir = '/var/log/openalto/'
    pid_dir = args.pid_dir if args.pid_dir is not None else pid_dir

    if args.action == 'start':
        with open(args.config, 'r') as f:
            cfg = json.load(f)

        host = cfg.pop('host', 'localhost')
        if args.host is not None:
            host = args.host

        port = int(cfg.pop('port', 6793))
        if args.port is not None:
            port = int(args.port)

        namespace = cfg.pop('namespace', 'default')
        if args.namespace is not None:
            namespace = args.namespace

        dbinfo = DBInfo(host, port)
        logging.info('Initializing CERN LookingGlass Agent...')
        agent = LookingGlassAgent(dbinfo, args.agent_name, namespace, **cfg)
        logging.info('Starting CERN LookingGlass Agent...')
        service = AgentService(args.agent_name, pid_dir, agent)

        if args.daemonized:
            service.start()
        else:
            agent.run()
    else:
        logging.info('Stopping CERN LookingGlass Agent...')
        service = AgentService(args.agent_name, pid_dir)

        service.stop()
