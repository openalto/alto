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
import re
import json
from unittest import mock
import pytest

from typing import List
from django.core import mail
from django.test import TestCase
from django.urls import URLResolver, resolve, Resolver404, get_resolver

from alto.server.components.db import (data_broker_manager,
                                       Match,
                                       Action,
                                       ForwardingRule)
from alto.config import Config
from alto.model.rfc9275 import ALTOPathVector
from alto.utils import setup_debug_db, load_class
from alto.common.constants import (ALTO_CONTENT_TYPE_IRD,
                                   ALTO_CONTENT_TYPE_ECS,
                                   ALTO_CONTENT_TYPE_ECS_PV,
                                   ALTO_CONTENT_TYPE_PROPMAP,
                                   ALTO_PARAMETER_TYPE_ECS,
                                   ALTO_PARAMETER_TYPE_PROPMAP)
from alto.mock import mockGeoIP2, mockKazoo

__author__ = "OpenALTO"
__copyright__ = "OpenALTO"
__license__ = "MIT"


# Manually empty the test outbox
# See more details: https://docs.djangoproject.com/en/4.1/topics/testing/tools/#django.core.mail.django.core.mail.outbox
mail.outbox = []

TEST_ROUTES = [
    {
        'path': '/directory/directory',
        'view': 'alto.server.northbound.alto.views.IRDView'
    },
    {
        'path': '/pathvector/pv',
        'view': 'alto.server.northbound.alto.views.PathVectorView'
    },
    {
        'path': '/entityprop/geoip',
        'view': 'alto.server.northbound.alto.views.EntityPropertyView'
    },
    {
        'path': '/errortest/404',
        'error': 404
    }
]


def show_urls(urllist: List[URLResolver], depth=0):
    urls = []
    for entry in urllist:
        urls.append(entry.pattern)
        if hasattr(entry, 'url_patterns'):
            urls += show_urls(entry.url_patterns, depth + 1)
    return urls


def perform_route_test(route):
    path = route.get('path')
    if path is None:
        return
    if route.get('error') == 404:
        with pytest.raises(Resolver404):
            view = resolve(path)
    else:
        view = resolve(path)
        assert view.func.cls is load_class(route.get('view'))


class ALTONorthboundTest(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault('ALTO_CONFIG', os.path.join(os.path.dirname(__file__), '../etc/alto.conf.test'))
        cls.config = Config()
        setup_debug_db(cls.config)
        return super().setUpClass()

    @classmethod
    def setUpTestData(cls) -> None:
        # Topology:
        #                            AS10000
        # h1 (10.1.0.2) - s1 (10.0.0.1) - (10.0.0.2) s2 - AS10086 - AS10010 - h2 (10.2.0.2)
        mock.patch.dict('sys.modules', {'geoip2.database': mockGeoIP2,
                                        'geoip2.webservice': mockGeoIP2,
                                        'kazoo.client': mockKazoo}).start()

        fib = data_broker_manager.get('default', db_type='forwarding')
        eb = data_broker_manager.get('default', db_type='endpoint')
        db = data_broker_manager.get('default', db_type='delegate')

        fib_trans = fib.new_transaction()
        _pkt_match = Match('10.2.0.0/24')
        _s1_action = Action('10.0.0.2')
        _s1_rule = ForwardingRule(_pkt_match, _s1_action)
        fib_trans.add_rule('s1', _s1_rule)
        _s2_action = Action('10.2.0.1', as_path='10086 10010')
        _s2_rule = ForwardingRule(_pkt_match, _s2_action)
        fib_trans.add_rule('s2', _s2_rule)
        fib_trans.commit()

        eb_trans = eb.new_transaction()
        eb_trans.add_property('10.1.0.0/24', {'is_local': True, 'dpid': 's1'})
        eb_trans.add_property('10.0.0.2', {'dpid': 's2'})
        eb_trans.commit()

        db_trans = db.new_transaction()
        data_source_config = {
            "data_source_cls": "alto.agent.geoip.GeoipAgent",
            "db_path": "/opt/test.mmdb"
        }
        db_trans.add_data_source('geoip', **data_source_config)
        db_trans.commit()


    def test_northbound_routes(self):
        resources = self.config.get_configured_resources()

        urls = show_urls(get_resolver().url_patterns)
        assert len(urls) == len(resources) + 1

        for route in TEST_ROUTES:
            perform_route_test(route)


    def test_view_ird(self):
        response = self.client.get('/directory/directory',
                                   accepts=ALTO_CONTENT_TYPE_IRD)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.has_header('Content-Type'), True)
        self.assertEqual(response.get('Content-Type'), ALTO_CONTENT_TYPE_IRD)

        ird = response.json()
        resources = self.config.get_configured_resources()
        self.assertEqual(len(ird['resources']), len(resources) - 1)


    def test_view_pv(self):
        response = self.client.post('/pathvector/pv',
                                    data=json.dumps({
                                        'cost-type': {
                                            'cost-mode': 'array',
                                            'cost-metric': 'ane-path'
                                        },
                                        'endpoint-flows': [
                                            {
                                                'srcs': ['ipv4:10.1.0.2'],
                                                'dsts': ['ipv4:10.2.0.2']
                                                }
                                        ]
                                    }),
                                    content_type=ALTO_PARAMETER_TYPE_ECS,
                                    accepts=ALTO_CONTENT_TYPE_ECS_PV)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.has_header('Content-Type'), True)
        content_type_slice = re.split('; *', response.get('Content-Type'))
        content_type_slice.reverse()
        content_type = content_type_slice.pop()
        self.assertEqual(content_type, 'multipart/related')
        content_type_params = dict([p.split('=', 1) for p in content_type_slice])
        self.assertEqual(content_type_params.get('type'), ALTO_CONTENT_TYPE_ECS)
        self.assertTrue('boundary' in content_type_params)

        pv = ALTOPathVector('')
        pv.boundary = content_type_params.get('boundary')
        if 'charset' in content_type_params:
            pv.charset = content_type_params.get('charset')
        pv.from_payload(response.content.decode())

        self.assertTrue('10.1.0.2' in pv.ecmap_)
        self.assertTrue(len(pv.anepm_) > 0)


    def test_view_geoip(self):
        response = self.client.post('/entityprop/geoip',
                                    data=json.dumps({
                                        'entities': [
                                            'ipv4:10.1.0.2',
                                            'ipv4:10.2.0.2',
                                            'ipv4:10.3.0.2'
                                        ]
                                    }),
                                    content_type=ALTO_PARAMETER_TYPE_PROPMAP,
                                    accepts=ALTO_CONTENT_TYPE_PROPMAP)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.has_header('Content-Type'), True)
        self.assertEqual(response.get('Content-Type'), ALTO_CONTENT_TYPE_PROPMAP)


    def test_view_geodist(self):
        response = self.client.post('/endpointcost/geodist',
                                    data=json.dumps({
                                        'cost-type': {
                                            'cost-mode': 'numerical',
                                            'cost-metric': 'routingcost'
                                        },
                                        'endpoints': {
                                            'srcs': ['ipv4:10.1.0.2'],
                                            'dsts': ['ipv4:10.2.0.2', 'ipv4:10.3.0.2']
                                        }
                                    }),
                                    content_type=ALTO_PARAMETER_TYPE_ECS,
                                    accepts=ALTO_CONTENT_TYPE_ECS)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.has_header('Content-Type'), True)
        self.assertEqual(response.get('Content-Type'), ALTO_CONTENT_TYPE_ECS)