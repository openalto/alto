# -*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2022 OpenALTO Community
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
# - Kai Gao <emiapwil@gmail.com>

from dataclasses import dataclass
from typing import List, Dict, Any
import json
import requests
import ipaddress

from alto.model.rfc7285 import ALTOEndpointCost, ALTO_CTYPE_ECS, ALTO_CTYPE_ERROR


ALTO_CTYPE_PV = 'multipart/related;type=' + ALTO_CTYPE_ECS
ALTO_CTYPE_PM = 'application/alto-propmap+json'


class MultiPart:

    def __init__(self, raw_data, boundary):
        self.raw_data = raw_data
        self.boundary = boundary
        self.parts = []
        self._parse()

    def _parse(self):
        for line in self.raw_data.splitlines():
            if line == '--' + self.boundary:
                part = dict()
                part['headers'] = dict()
                is_body = False
                self.parts.append(part)
            elif line == '--' + self.boundary + '--':
                break
            elif is_body:
                if 'body' in part:
                    part['body'] += '\n' + line
                else:
                    part['body'] = line
            elif not line:
                is_body = True
                continue
            else:
                pairs = line.split(':')
                header_key = pairs[0].strip().lower()
                header_val = ':'.join(pairs[1:]).strip()
                part['headers'][header_key] = header_val


class ALTOPathVector(ALTOEndpointCost):

    def __init__(self, url, **kwargs):
        ALTOEndpointCost.__init__(self, url, 'array', 'ane-path', **kwargs)
        self.ctype = ALTO_CTYPE_PV
        self.boundary = ''
        self.charset = None

    def check_headers(self, r):
        self.boundary = ''
        self.charset = None
        ctype_params = r.headers['content-type'].split(';')
        assert ctype_params[0].strip() == 'multipart/related'
        for p in ctype_params[1:]:
            kv = p.strip().split('=')
            if len(kv) > 1:
                if kv[0] == 'type':
                    assert kv[1] == ALTO_CTYPE_ECS
                elif kv[0] == 'boundary':
                    self.boundary = kv[1]
                elif kv[0] == 'charset':
                    self.charset = kv[1]

    def from_payload(self, payload):
        multipart = MultiPart(payload, self.boundary)
        for part in multipart.parts:
            if part['headers'].get('content-type') == ALTO_CTYPE_ECS:
                data = json.loads(part.get('body'))
                self._build_endpointcost(data)
            elif part['headers'].get('content-type') == ALTO_CTYPE_PM:
                data = json.loads(part.get('body'))
                self._build_propmap(data)

    def _build_propmap(self, data):
        self.anepm_ = data['property-map']

    def __build_query(self, sips, dips, prop_names=[]):
        sips = ['ipv{}:{}'.format(ipaddress.ip_address(s).version, s) for s in sips]
        dips = ['ipv{}:{}'.format(ipaddress.ip_address(d).version, d) for d in dips]

        data = dict()
        data['cost-type'] = dict()
        data['cost-type']['cost-mode'] = self.cost_mode
        data['cost-type']['cost-metric'] = self.cost_metric
        data['endpoint-flows'] = []
        flow = dict()
        flow['srcs'] = sips
        flow['dsts'] = dips
        data['endpoint-flows'].append(flow)
        data['ane-property-names'] = prop_names
        return data

    def get_costs(self, sips: List[str], dips: List[str],
                  prop_names: List[str]) -> Dict[str, Dict[str, Any]]:
        data = self.__build_query(sips, dips, prop_names)
        r = self.post(data)
        if self.charset:
            r.encoding = self.charset
        self.from_payload(r.text)

        ane_paths = {}
        for s in set(sips):
            if s not in self.ecmap_:
                continue
            ane_paths.update({s: {d: self.ecmap_[s][d] for d in set(dips) if d in self.ecmap_[s]}})
        ane_props = {}
        for ane in self.anepm_:
            if ane.startswith('.ane:'):
                ane_props[ane[5:]] = self.anepm_[ane]
        return ane_paths, ane_props

