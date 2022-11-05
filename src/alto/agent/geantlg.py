import requests
import json
import logging
import time
import xmltodict

from pytricia import PyTricia

from alto.server.components.datasource import DBInfo, DataSourceAgent
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
        self.prefixes = cfg.get('prefixes', set())

        logging.info("Loading databases")
        self.db = [ self.request_db(t) for t in ['forwarding', 'endpoint']]

        if self.default_router:
            if len(self.listened_routers) == 0:
                self.listened_routers |= { self.default_router }

            eb_trans = self.db[1].new_transaction()
            default_sw = {'dpid': self.default_router, 'in_port': '0'}
            eb_trans.add_property('0.0.0.0/0', default_sw)
            eb_trans.commit()

    def _parse_routes(self, results_dict, width=19, route_dict=PyTricia(128)):
        route_dict = dict()
        for prefix in results_dict:
            route_info = []
            for entry in results_dict[prefix]["rt"]["rt-entry"]:
                attribute_dict = dict()
                attribute_dict["selected"] = entry["active-tag"] == "*"
                attribute_dict["preference"] = int(entry.get("preference", None))
                attribute_dict["peer"] = entry.get("learned-from", None)
                attribute_dict["as_path"] = entry.get("as-path", None)

                if isinstance(entry.get("nh", None), list):
                    for hop in entry.get("nh", []):
                        if hop.get("selected-next-hop", True) is None:
                            attribute_dict["next_hop"] = hop.get("to", None)
                            attribute_dict["outgoing"] = hop.get("via", None)
                elif isinstance(entry.get("nh", None), set):
                    hop = entry.get("nh")
                    if hop.get("selected-next-hop", True) is None:
                        attribute_dict["next_hop"] = hop.get("to", None)
                        attribute_dict["outgoing"] = hop.get("via", None)

                route_info.append(attribute_dict)
            route_dict[prefix] = route_info
        return route_dict

    def _do_query(self, router=None, args=None):
        results = dict()
        for prefix in args:
            try:
                data = requests.post(self.uri,
                                    json={
                                        'selectedRouters': [{"name": router}],
                                        'selectedCommand': {
                                            'value': f'show route {prefix} | display xml'
                                        },
                                    },
                                    headers={
                                        'Content-Type': 'application/json'
                                    },
                                    proxies=self.proxies, timeout=5)
                doctree = data.json()['output'][router]['commandResult']
                query_result = json.loads(json.dumps(xmltodict.parse(doctree)))
                for table in query_result["rpc-reply"]["route-information"]["route-table"]:
                    if table["table-name"] == "lhcone-l3vpn.inet.0":
                        results.update({prefix : table})
            except:
                logging.warn(f"Error fetching prefix {prefix} on router {router}; skipping")
        return results

    def get_routes(self, ipprefix=None, router=None, selected=False):
        """
        Get a route entries.

        Parameters
        ----------
        ipprefix : str
            Destination IP prefix to lookup. If None, `prefixes` will be used.
        router : str
            Name of the looking glass router. If None, `default_router` will be
            used.

        Returns
        -------
        routes : list
            All the route entries for the given destination IP prefix.
        """
        logging.info('Loading routes on %s' % (router))
        args = ipprefix if ipprefix else self.prefixes
        results_dict = self._do_query(router=router, args=args)
        logging.info('Parsing routes on %s' % (router))
        routes = self._parse_routes(results_dict)
        if selected:
            for p in routes:
                routes[p] = [r for r in routes[p] if r.get('selected')]
        return routes

    def update(self):
        fib_trans = self.db[0].new_transaction()
        for _router in self.listened_routers:
            routes = self.get_routes(router=_router, selected=True)
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
