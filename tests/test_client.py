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

import os
import pytest
from unittest import mock

from alto.client import Client
from alto.model.rfc7285 import ALTO_CTYPE_NM, ALTO_CTYPE_CM

__author__ = "OpenALTO"
__copyright__ = "OpenALTO"
__license__ = "MIT"


TEST_DEFAULT_NM = {
    "meta" : {
        "vtag": {
            "resource-id": "my-default-network-map",
            "tag": "da65eca2eb7a10ce8b059740b0b2e3f8eb1d4785"
        }
    },
    "network-map" : {
        "PID1" : {
            "ipv4" : [
                "192.0.2.0/24",
                "198.51.100.0/25"
            ]
        },
        "PID2" : {
            "ipv4" : [
                "198.51.100.128/25"
            ]
        },
        "PID3" : {
            "ipv4" : [
                "0.0.0.0/0"
            ],
            "ipv6" : [
                "::/0"
            ]
        }
    }
}

TEST_DEFAULT_CM = {
    "meta" : {
        "dependent-vtags" : [
            {"resource-id": "my-default-network-map",
             "tag": "3ee2cb7e8d63d9fab71b9b34cbf764436315542e"
             }
        ],
        "cost-type" : {"cost-mode"  : "numerical",
                       "cost-metric": "routingcost"
                       }
    },
    "cost-map" : {
        "PID1": { "PID1": 1,  "PID2": 5,  "PID3": 10 },
        "PID2": { "PID1": 5,  "PID2": 1,  "PID3": 15 },
        "PID3": { "PID1": 20, "PID2": 15  }
    }
}

MOCK = [
    {
        'uri': 'http://localhost:8181/alto/networkmap/default-networkmap',
        'headers': {'content-type': ALTO_CTYPE_NM},
        'json': TEST_DEFAULT_NM,
        'status_code': 200
    },
    {
        'uri': 'http://localhost:8181/alto/costmap/default-costmap',
        'headers': {'content-type': ALTO_CTYPE_CM},
        'json': TEST_DEFAULT_CM,
        'status_code': 200
    }
]

def test_client_noimpl():
    """ALTO Client Tests"""
    ac = Client(config=False, default_ird="http://mockird", auth=('admin', 'admin'))
    with pytest.raises(NotImplementedError):
        ac.get_ird()


def mocked_requests_get(uri, *args, **kwars):
    class MockResponse:
        def __init__(self, headers=dict(), json_data=None, status_code=200):
            self.headers = headers
            self.json_data = json_data
            self.status_code = status_code

        def raise_for_status(self):
            pass

        def json(self):
            return self.json_data

    for mock_item in MOCK:
        if uri == mock_item.get('uri'):
            return MockResponse(headers=mock_item.get('headers'),
                                json_data=mock_item.get('json'),
                                status_code=mock_item.get('status_code'))


@mock.patch('requests.get', side_effect=mocked_requests_get)
def test_client_config(*args):
    os.environ['ALTO_CONFIG'] = os.path.join(os.path.dirname(__file__), '../etc/alto.conf.template')
    ac = Client()

    nm = ac.get_network_map()

    pid = nm.get_pid("192.0.2.100")
    assert len(pid) == 1
    assert pid[0] == 'PID1'

    pids = nm.get_pid(["198.51.100.2", "198.51.100.254"])
    assert len(pids) == 2
    assert pids[0] == 'PID1'
    assert pids[1] == 'PID2'

    cm = ac.get_cost_map()
    costs = cm.get_costs(['PID1'], ['PID2'])
    assert 'PID1' in costs
    dst_costs = costs['PID1']
    assert 'PID2' in dst_costs
    assert dst_costs['PID2'] == 5

    costs2 = ac.get_routing_costs(['192.0.2.100'], ['198.51.100.2', '198.51.100.254'])
    assert '192.0.2.100' in costs2
    dst_costs2 = costs2['192.0.2.100']
    assert '198.51.100.2' in dst_costs2 and '198.51.100.254' in dst_costs2
    assert dst_costs2['198.51.100.2'] == 1 and dst_costs2['198.51.100.254'] == 5

