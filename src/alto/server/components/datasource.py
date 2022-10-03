import re
import ipaddress
import requests
import json
from service import Service

from lxml import html
from pytricia import PyTricia

from alto.common.logging import fail_with_msg
from logging import FATAL

from .db import DataBroker, data_broker_manager, ForwardingRule, Match, Action

class DBInfo:
    def __init__(self, host: str, port: int, credentials = ''):
        self.host = host
        self.port = port
        self.credentials = credentials

MISSING_FIELD_MSG = '%s field is mandatory to configure Agent %s'

class DataSourceAgent:
    """
    Base class of the data source agent.

    The base class must be configured with attributes to connect to
    the data store, and a namespace.
    """

    def __init__(self, dbinfo, agent_name, namespace):
        self.dbinfo = dbinfo
        self.agent_name = agent_name
        self.namespace = namespace
        # FIXME: use connection instead of data_broker_manager
        self.dbm = data_broker_manager

    def request_db(self, db_type: str):
        return self.dbm.get(self.namespace, db_type)

    def ensure_field(self, cfg, field):
        if field not in cfg:
            fail_with_msg(FATAL, MISSING_FIELD_MSG % (field, self.agent_name))
        return cfg[field]

    def run(self):
        raise NotImplementedError()

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

class AgentService(Service):

    def __init__(self, agent_name, pid_dir, agent_instance=None):
        super().__init__(agent_name, pid_dir)
        self.agent = agent_instance

    def run(self):
        self.agent.run()
