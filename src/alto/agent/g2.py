from urllib.parse import urljoin
import requests
import ipaddress
import logging
import re
import time
import json

from alto.server.components.datasource import DBInfo, DataSourceAgent
from alto.server.components.db import ForwardingRule, Match, Action


LOGIN_API = 'auth/login'
TSRANGE_API = 'tsrange/-1/0'
SNAPSHOT_API = 'snapshot?id={:.0f}'


class ECRule:
    """
    Class of rule to generate an Equivelant Class (EC).
    """

    def __init__(self, **rule):
        self.dst_prefix_pattern = rule.pop('dst_prefix', None)
        self.in_port = rule.pop('in_port', None)
        self.src_prefix_pattern = rule.get('src_prefix', None)
        self.optional_attr = rule

    def gen(self, **flow_info):
        dst_prefix = None
        if self.dst_prefix_pattern and 'dst_ip' in flow_info:
            dst_prefix = self.dst_prefix_pattern.format(flow_info['dst_ip'])
            dst_prefix = ipaddress.ip_network(dst_prefix, strict=False).compressed
        in_port = self.in_port
        src_prefix = None
        if self.src_prefix_pattern and 'src_ip' in flow_info:
            src_prefix = self.src_prefix_pattern.format(flow_info['src_ip'])
            src_prefix = ipaddress.ip_network(src_prefix, strict=False).compressed
        return Match(dst_prefix, in_port, src_prefix, **self.optional_attr)


class G2Agent(DataSourceAgent):
    """
    Class of data source agent for G2.
    """

    def __init__(self, dbinfo: DBInfo, name: str, namespace='default', **cfg):
        super().__init__(dbinfo, name, namespace)
        self.base_uri = self.ensure_field(cfg, 'base_uri')
        self.username = self.ensure_field(cfg, 'username')
        self.password = self.ensure_field(cfg, 'password')
        self.auth = {
            'username': self.username,
            'password': self.password
        }
        self.refresh_interval = cfg.get('refresh_interval', None)
        self.token = None
        self.ec_rule_location = cfg.get('ec_rule')
        self.ec_rules = []
        self.snapshot = dict()
        self.latest_ts = -1

        logging.info("Loading databases")
        self.db = [ self.request_db(t) for t in ['forwarding', 'endpoint']]

    def _login(self):
        data = requests.post(urljoin(self.base_uri, LOGIN_API),
                             headers={'content-type': 'application/json'},
                             json=self.auth)
        self.token = data.json().get('token')

    def _do_query(self, retry=3):
        if not self.token:
            self._login()
        latest_ts = self.latest_ts
        try:
            tsrange = requests.get(urljoin(self.base_uri, TSRANGE_API),
                                   headers={'authorization': 'Bearer {token}'.format(token=self.token)})
            if not tsrange.ok:
                self.token = None
                logging.debug(tsrange.content)
                raise requests.HTTPError("Fail to get timestamp range.")
            latest_ts, latest_id = tsrange.json()[-1]
            snapshot = requests.get(urljoin(self.base_uri, SNAPSHOT_API.format(latest_id)),
                                    headers={'authorization': 'Bearer {token}'.format(token=self.token)})
            if not snapshot.ok:
                self.token = None
                logging.debug(snapshot.content)
                raise requests.HTTPError("Fail to get latest snapshot.")
            self.snapshot = snapshot.json().get('data', {}).get('snapshots')[0]
        except Exception as e:
            if retry > 0:
                logging.debug('Fail to fetch the latest snapshot')
                logging.debug(e)
                logging.debug('Retry the query ({})'.format(retry))
                return self._do_query(retry=retry-1)
        return latest_ts, self.snapshot

    def _load_ec_rule(self):
        with open(self.ec_rule_location) as _file:
            ec_rules = json.load(_file)
            self.ec_rules = []
            for rule in ec_rules:
                self.ec_rules.append(ECRule(**rule))

    def _get_ec(self, **flow_info):
        """
        Get an equivalent class of a given flow.

        Parameters
        ----------
        flow_info : dict
            A flow attribute object.

        Returns
        -------
        ec : Match
            A Match object representing the equivalent class including the given
            flow.
        """
        for ec_rule in self.ec_rules:
            ec = ec_rule.gen(**flow_info)
            if ec.match(**flow_info):
                return ec
        dst_prefix = flow_info.pop('dst_ip', None)
        in_port = flow_info.pop('in_port', None)
        src_prefix = flow_info.pop('src_ip', None)
        return Match(dst_prefix, in_port, src_prefix, **flow_info)

    def _parse_routes(self, snapshot):
        """
        Parse forwarding rules from a G2 snapshot.

        Parameters
        ----------
        snapshot : dict
            A G2 format snapshot object.

        Returns
        -------
        routes : list
            A list of (dpid: str, fwd_rule: ForwardingRule) pairs.
        """
        routes = []
        flows = snapshot.get('flows', {}).get('flowgroups', [])
        links = dict()
        for link in snapshot.get('topo', {}).get('topology', {}).get('links', []):
            link_info = link['info']
            if type(link_info) is str:
                link_info = eval(link_info)
            if link_info is None:
                continue
            link.update(link_info)
            links[link['id']] = link
        for f in flows:
            flow_info = f['info']
            if type(flow_info) is str:
                flow_info = eval(flow_info)
            pkt_match = self._get_ec(**flow_info)
            flow_links = f['links']
            for l in flow_links:
                if l['id'] in links:
                    linfo = links[l['id']]
                    dpid = linfo.get('src_sw')
                    next_hop = linfo.get('dst_swip')
                    if dpid is None:
                        continue
                    action = Action(next_hop)
                    fwd_rule = ForwardingRule(pkt_match, action)
                    routes.append((dpid, fwd_rule))
        return routes

    def update(self):
        logging.info('Polling latest snapshot from G2...')
        ts, snapshot = self._do_query()
        if ts <= self.latest_ts:
            logging.info('No updated snapshot')
            return
        self.latest_ts = ts

        fib_trans = self.db[0].new_transaction()
        routes = self._parse_routes(snapshot)
        logging.info('Writing routes to backend db...')
        for route in routes:
            dpid = route[0]
            rule = route[1]
            fib_trans.add_rule(dpid, rule)
        fib_trans.commit()
        logging.info('Backend db is updated')

    def run(self):
        if self.refresh_interval is None:
            self.refresh_interval = 60
        while True:
            self.update()
            time.sleep(self.refresh_interval)
