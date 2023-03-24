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
from alto.mock import mocked_requests_get

__author__ = "OpenALTO"
__copyright__ = "OpenALTO"
__license__ = "MIT"


def test_client_noimpl():
    """ALTO Client Tests"""
    ac = Client(config=False, default_ird="http://mockird", auth=('admin', 'admin'))
    with pytest.raises(NotImplementedError):
        # FIXME: once implement get_ird() method, remove this test
        ac.get_ird()


@mock.patch('requests.get', side_effect=mocked_requests_get)
@mock.patch('requests.post', side_effect=mocked_requests_get)
def test_client_config(*args):
    os.environ.setdefault('ALTO_CONFIG', os.path.join(os.path.dirname(__file__), '../etc/alto.conf.test'))
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

    cm_bw = ac.get_resource('costmap-bw-available')
    costs_bw = cm_bw.get_costs(['PID1'], ['PID2'])
    assert 'PID1' in costs_bw
    dst_costs_bw = costs_bw['PID1']
    assert 'PID2' in dst_costs_bw
    assert dst_costs_bw['PID2'] == 1000

    cm_delay = ac.get_resource('costmap-delay-ow')
    costs_delay = cm_delay.get_costs(['PID1'], ['PID2'])
    assert 'PID1' in costs_delay
    dst_costs_delay = costs_delay['PID1']
    assert 'PID2' in dst_costs_delay
    assert dst_costs_delay['PID2'] == 50

    ecs = ac.get_resource('ecs', resource_type='endpoint-cost')
    ecosts_rc = ecs.get_endpoint_costs(['192.0.2.100'], ['198.51.100.2', '198.51.100.254'])
    assert '192.0.2.100' in ecosts_rc
    dst_ecosts_rc = ecosts_rc['192.0.2.100']
    assert '198.51.100.2' in dst_ecosts_rc and '198.51.100.254' in dst_ecosts_rc
    assert dst_ecosts_rc['198.51.100.2'] == 1 and dst_ecosts_rc['198.51.100.254'] == 5

    pv = ac.get_resource('ecs-pv', resource_type='path-vector', reverse=True)
    ecosts_pv = pv.get_endpoint_costs(['192.0.2.100'], ['198.51.100.2', '198.51.100.254'])
    assert '192.0.2.100' in ecosts_pv
    dst_ecosts_pv = ecosts_pv['192.0.2.100']
    assert '198.51.100.2' in dst_ecosts_pv and '198.51.100.254' in dst_ecosts_pv
    assert dst_ecosts_pv['198.51.100.2'] == 2 and dst_ecosts_pv['198.51.100.254'] == 4

    mcosts = ac.get_multiple_costs(['192.0.2.100'], ['198.51.100.2', '198.51.100.254'],
                                   metrics=['as-path-length', 'delay-ow', 'bw-available', 'routing-cost'])
    assert '192.0.2.100' in mcosts
    dst_mcosts = mcosts['192.0.2.100']
    assert '198.51.100.2' in dst_mcosts and '198.51.100.254' in dst_mcosts
    assert len(dst_mcosts['198.51.100.2']) == 4 and len(dst_mcosts['198.51.100.254']) == 4

    routing_costs = ac.get_routing_costs(['192.0.2.100'], ['198.51.100.2', '198.51.100.254'],
                                         cost_map='costmap-delay-ow')
    assert '192.0.2.100' in routing_costs
    dst_routing_costs = routing_costs['192.0.2.100']
    assert '198.51.100.2' in dst_routing_costs and '198.51.100.254' in dst_routing_costs

    pv_routing_costs = ac.get_routing_costs(['198.51.100.2', '198.51.100.254'], ['192.0.2.100'],
                                            use_pv='ecs-pv')
    assert '198.51.100.2' in pv_routing_costs and '198.51.100.254' in pv_routing_costs
    assert '192.0.2.100' in pv_routing_costs['198.51.100.2']
    assert '192.0.2.100' in pv_routing_costs['198.51.100.254']
