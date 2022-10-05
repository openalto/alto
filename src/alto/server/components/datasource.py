import re
import ipaddress
import requests
import json

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

    def __init__(self, dbinfo, agent_name, namespace, **cfg):
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
