import logging
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

        self.refresh_interval = cfg.get('refresh_interval', None)

        logging.info("Loading databases")
        self.db = [ self.request_db(t) for t in ['forwarding', 'endpoint']]

        self.bf = Session(host="localhost")

        self.bf.init_snapshot('/data/live', name='live', overwrite=True)
        self.bf.q.initIssues().answer()

    def update(self):
        fib_trans = self.db[0].new_transaction()
        results = self.bf.q.routes().answer().frame()
        logging.info("RESULTS*****************************************" + str(results))
        for index in results.index:
            pkt_match = Match(results["Network"][index])
            action = Action(results["Next_Hop_IP"][index])
            rule = ForwardingRule(pkt_match, action)
            fib_trans.add_rule(results["Node"][index], rule)
        fib_trans.commit()

    def run(self):
        if self.refresh_interval is None:
            self.refresh_interval = 60
        while True:
            self.update()
            time.sleep(self.refresh_interval)
