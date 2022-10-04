import requests
import json
import logging

from alto.server.components.datasource import DBInfo, DataSourceAgent

class CRICAgent(DataSourceAgent):

    def __init__(self, dbinfo: DBInfo, name: str, namespace='default', **cfg):
        super().__init__(dbinfo, name, namespace)

        self.uri = self.ensure_field(cfg, 'uri')
        self.local_asn = cfg.get('local_asn', None)
        self.refresh_interval = cfg.get('refresh_interval', None)
        self.netroute_map = dict()

        logging.info("Loading databases")
        self.db = [ self.request_db(t) for t in ['endpoint']]

    def update(self):
        eb_trans = self.db[0].new_transaction()
        cric_dict = dict()
        if self.uri.startswith('http'):
            data = requests.get(self.uri, verify=False)
            cric_dict = json.loads(data.content)
        else:
            with open(self.uri, 'r') as f_cric:
                cric_dict = json.load(f_cric)

        for _, rcsite_obj in cric_dict.items():
            netroutes = rcsite_obj.get('netroutes', dict())
            for _, netroute in netroutes.items():
                for _, ipprefixes in netroute['networks'].items():
                    for ipprefix in ipprefixes:
                        asn = netroute.get('asn')
                        if asn == self.local_asn:
                            eb_trans.add_property(ipprefix, {'is_local': True})
        eb_trans.commit()

    def run(self):
        if self.refresh_interval is None:
            self.refresh_interval = 60
        while True:
            self.update()
            time.sleep(self.refresh_interval)
