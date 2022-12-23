import logging
import pandas as pd
from pybatfish.client.session import Session
from pybatfish.datamodel import *
from pybatfish.datamodel.answer import *
from pybatfish.datamodel.flow import *
import time

from alto.server.components.datasource import DBInfo, DataSourceAgent
from alto.server.components.db import ForwardingRule, Match, Action

class BatfishAgent(DataSourceAgent):
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

        self.bf = Session(host="alto-batfish-server")

        # TODO: initialize snapshot
        SNAPSHOT_DIR = '../../networks/example'
        self.bf.init_snapshot(SNAPSHOT_DIR, name='snapshot-2020-01-01', overwrite=True)
        self.bf.set_network('example_dc')
        self.bf.set_snapshot('snapshot-2020-01-01')
        self.bf.q.initIssues().answer()

    def update(self):
        fib_trans = self.db[0].new_transaction()
        results = self.bf.q.routes().answer().frame()
        for row in results:
            pkt_match = Match("network")
            action = Action("next_hop")
            rule = ForwardingRule(pkt_match, action)
            fib_trans.add_rule(row["node"], rule)
        fib_trans.commit()

    def run(self):
        if self.refresh_interval is None:
            self.refresh_interval = 60
        while True:
            self.update()
            time.sleep(self.refresh_interval)
