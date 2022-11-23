# -*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2021 OpenALTO Community
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Authors:
# - Jensen Zhang <jingxuan.n.zhang@gmail.com>

import pytest

from unittest import mock

from alto.server.components.db import (DataBrokerManager,
                                       EndpointDB,
                                       ForwardingDB,
                                       DelegateDB,
                                       Match,
                                       Action,
                                       ForwardingRule)
from alto.common.error import NotSupportedError
from alto.mock import mockGeoIP2, MOCK_GEOIP2_DB

__author__ = "OpenALTO"
__copyright__ = "OpenALTO"
__license__ = "MIT"


@mock.patch.dict('sys.modules', {'geoip2.database': mockGeoIP2,
                                 'geoip2.webservice': mockGeoIP2})
def test_databroker():
    dbm = DataBrokerManager()

    _fib = ForwardingDB(backend='local')
    fib = dbm.get('default', 'forwarding')
    assert fib is _fib

    _eb = EndpointDB(backend='local')
    eb = dbm.get('default', 'endpoint')
    assert eb is _eb

    _db = DelegateDB(backend='local')
    db = dbm.get('default', 'delegate')
    assert db is _db

    with pytest.raises(NotSupportedError):
        _ = ForwardingDB(backend='not-supported')

    # Topology:
    # h1 (10.1.0.2) - s1 (10.0.0.1) - (10.0.0.2) s2 - h2 (10.2.0.2)

    fib_trans = fib.new_transaction()
    _pkt_match = Match('10.2.0.0/24')
    _s1_action = Action('10.0.0.2')
    _s1_rule = ForwardingRule(_pkt_match, _s1_action)
    fib_trans.add_rule('s1', _s1_rule)
    _s2_action = Action('10.2.0.1')
    _s2_rule = ForwardingRule(_pkt_match, _s2_action)
    fib_trans.add_rule('s2', _s2_rule)
    fib_trans.commit()

    fib.build_cache()
    s1_action = fib.lookup('s1', '10.2.0.2')
    assert s1_action.to_dict() == _s1_action.to_dict()
    s2_action = fib.lookup('s2', '10.2.0.2')
    assert s2_action.to_dict() == _s2_action.to_dict()

    eb_trans = eb.new_transaction()
    eb_trans.add_property('10.1.0.0/24', {'is_local': True, 'dpid': 's1'})
    eb_trans.add_property('10.0.0.2', {'dpid': 's2'})
    eb_trans.commit()

    eb.build_cache()
    h1_props = eb.lookup('10.1.0.2', ['is_local', 'dpid'])
    assert h1_props.get('is_local')
    assert h1_props.get('dpid') == 's1'
    s2_props = eb.lookup('10.0.0.2', ['dpid'])
    assert s2_props.get('dpid') == 's2'

    # Test invalid delegated data source agent
    db_trans = db.new_transaction()
    data_source_config = {
        "data_source_cls": "alto.agent.geoip.GeoipAgent"
    }
    db_trans.add_data_source('invalid_geoip_agent', **data_source_config)
    db_trans.commit()

    db.build_cache()
    with pytest.raises(NotSupportedError):
        _ = db.lookup('invalid_geoip_agent')

    # Test geoip2 data source agent using local db
    db_trans = db.new_transaction()
    data_source_config = {
        "data_source_cls": "alto.agent.geoip.GeoipAgent",
        "db_path": "/opt/test.mmdb"
    }
    db_trans.add_data_source('local_db_geoip_agent', **data_source_config)
    db_trans.commit()

    db.build_cache()
    endpoints = ["10.1.0.2", "10.2.0.2", "10.3.0.2"]
    geomap = db.lookup('local_db_geoip_agent', endpoints)
    for endpoint in endpoints:
        assert geomap[endpoint] == MOCK_GEOIP2_DB.get(endpoint, (0.0, 0.0))

    # Test geoip2 data source agent using local db
    db_trans = db.new_transaction()
    data_source_config = {
        "data_source_cls": "alto.agent.geoip.GeoipAgent",
        "account_id": "test",
        "license_key": "secret"
    }
    db_trans.add_data_source('webservice_geoip_agent', **data_source_config)
    db_trans.commit()

    db.build_cache()
    endpoints = ["10.1.0.2", "10.2.0.2", "10.3.0.2"]
    geomap = db.lookup('webservice_geoip_agent', endpoints)
    for endpoint in endpoints:
        assert geomap[endpoint] == MOCK_GEOIP2_DB.get(endpoint, (0.0, 0.0))
