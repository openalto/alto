import requests
import json
import logging
import time

from alto.server.components.datasource import DBInfo, DataSourceAgent

class DelegateAgent(DataSourceAgent):

    def __init__(self, dbinfo: DBInfo, name: str, namespace='default', **cfg):
        super().__init__(dbinfo, name, namespace)
        self.refresh_interval = cfg.get('refresh_interval', None)

        self.data_source_name = self.ensure_field(cfg, 'data_source_name')
        self.data_source_config = self.ensure_field(cfg, 'data_source_config')

        logging.info("Loading databases")
        self.db = [ self.request_db(t) for t in ['delegate']]

    def update(self):
        trans = self.db[0].new_transaction()
        trans.add_data_source(self.data_source_name, **self.data_source_config)
        trans.commit()
        logging.info("Adding delegated data source: {}".format(self.data_source_name))

    def run(self):
        if self.refresh_interval is None:
            self.refresh_interval = 60
        # Not update delegate agent
        self.update()
        while True:
            time.sleep(self.refresh_interval)

