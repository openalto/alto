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
# - Kai Gao <emiapwil@gmail.com>


from dataclasses import dataclass
from typing import List, Dict, Any
import json
import ipaddress
import requests
import pytricia

ALTO_CTYPE_NM = 'application/alto-networkmap+json'
ALTO_CTYPE_CM = 'application/alto-costmap+json'
ALTO_CTYPE_ECS = 'application/alto-endpointcost+json'
ALTO_CTYPE_ECS_PARAMS = 'application/alto-endpointcostparams+json'
ALTO_CTYPE_ERROR = 'application/alto-error+json'


@dataclass
class Vtag:
    resource_id: str
    tag: str

    @staticmethod
    def from_json(data):
        rid = data['resource-id']
        tag = data['tag']
        return Vtag(resource_id = rid, tag = tag)


@dataclass
class CostType:
    metric: str
    mode: str

    @staticmethod
    def from_json(data):
        metric = data['cost-metric']
        mode = data['cost-mode']
        return CostType(metric=metric, mode=mode)


class Meta(object):

    def __init__(self, data: Dict) -> None:
        self.data = data


class IRDMeta(Meta):

    def __init__(self, data: Dict) -> None:
        super().__init__(data)
        self._cost_types = data['cost-types']
        self._default_alto_network_map = data['default-alto-network-map']

    @property
    def cost_types(self):
        return self._cost_types

    @property
    def default_alto_network_map(self):
        return self._default_alto_network_map


class IRDResourceEntry(object):

    def __init__(self, data: Dict) -> None:
        self.data = data
        self._uri = data['uri']

    @property
    def uri(self):
        return self._uri


class InformationResourceDirectory(object):

    def __init__(self, data: Dict) -> None:
        self._meta = Meta(data['meta'])
        self._resources = {rid: IRDResourceEntry(res) for rid, res in data['resources'].items()}

    @property
    def meta(self):
        return self._meta

    @property
    def resources(self):
        return self._resources


class ALTOBaseResource:

    def __init__(self, ctype, url, auth=None, incre_mode=None, verify=True, **kwargs):
        self.ctype = ctype
        self.url = url
        self.auth = auth
        self.incre_mode = incre_mode
        self.verify = verify

    def get(self):
        headers = {
            'accepts': self.ctype + ',' + ALTO_CTYPE_ERROR
        }
        r = requests.get(self.url, auth=self.auth, headers=headers)
        r.raise_for_status()

        self.check_headers(r)
        self.check_contents(r)

        return r

    def check_headers(self, r):
        raise NotImplementedError

    def check_contents(self, r):
        raise NotImplementedError


class ALTONetworkMap(ALTOBaseResource):
    vtag: Vtag

    def __init__(self, url, **kwargs):
        ALTOBaseResource.__init__(self, ALTO_CTYPE_NM, url, **kwargs)

        r = self.get()
        self.__build_networkmap(r.json())
        self.__build_lookup_table()

    def check_headers(self, r):
        assert r.headers['content-type'] == ALTO_CTYPE_NM

    def check_contents(self, r):
        pass

    def __build_networkmap(self, data):
        self.vtag_ = Vtag.from_json(data['meta'].get('vtag', {}))

        self.nmap_ = data['network-map']

    def __build_lookup_table(self):
        self.plt_ = pytricia.PyTricia(128)
        for pid in self.nmap_:
            for ipv4 in self.nmap_[pid].get('ipv4', []):
                self.plt_[ipv4] = pid
            for ipv6 in self.nmap_[pid].get('ipv6', []):
                self.plt_[ipv6] = pid

    def get_pid(self, ipaddr: str or List[str]) -> List[str]:
        if isinstance(ipaddr, str):
            ipaddr = [ipaddr]
        return list(map(lambda a: self.plt_[str(a)], ipaddr))


class ALTOCostMap(ALTOBaseResource):
    dependent_vtags = List[Vtag]

    def __init__(self, url, **kwargs):
        ALTOBaseResource.__init__(self, ALTO_CTYPE_CM, url, **kwargs)

        r = self.get()
        self.__build_costmap(r.json())
        self.nm = kwargs.get('dependent_network_map')

    def check_headers(self, r):
        assert r.headers['content-type'] == ALTO_CTYPE_CM

    def check_contents(self, r):
        pass

    def __build_costmap(self, data):
        self.dependent_vtags = [Vtag.from_json(dv)
                                for dv in data['meta'].get('dependent_vtags', [])]
        self.cost_type = CostType.from_json(data['meta'].get('cost-type', {}))

        self.cmap_ = data['cost-map']

    def get_costs(self, spid: List[str],
                  dpid: List[str]) -> Dict[str, Dict[str, int or float]]:
        result = {}
        for s in set(spid):
            if s not in self.cmap_:
                continue
            result.update({s: {d: self.cmap_[s][d] for d in set(dpid) if d in self.cmap_[s]}})
        return result

    def get_endpoint_costs(self, src_ips: List[str], dst_ips: List[str]):
        spids = self.nm.get_pid(src_ips)
        spidmap = dict(zip(src_ips, spids))
        dpids = self.nm.get_pid(dst_ips)
        dpidmap = dict(zip(dst_ips, dpids))

        costs = self.get_costs(spids, dpids)
        return {
            sip: {
                dip: costs[spidmap[sip]][dpidmap[dip]]
                for dip in dst_ips
            } for sip in src_ips
        }


class ALTOEndpointCost(ALTOBaseResource):
    vtag: Vtag

    def __init__(self, url, cost_mode, cost_metric, **kwargs):
        self.cost_mode = cost_mode
        self.cost_metric = cost_metric
        ALTOBaseResource.__init__(self, ALTO_CTYPE_ECS, url, **kwargs)

    def check_headers(self, r):
        assert r.headers['content-type'] == ALTO_CTYPE_ECS

    def check_contents(self, r):
        pass

    def from_payload(self, payload):
        data = json.loads(payload)
        self._build_endpointcost(data)

    def post(self, data):
        headers = {
            'content-type': ALTO_CTYPE_ECS_PARAMS,
            'accepts': self.ctype + ',' + ALTO_CTYPE_ERROR
        }
        r = requests.post(self.url, json=data, auth=self.auth, headers=headers, verify=self.verify)
        r.raise_for_status()

        self.check_headers(r)
        self.check_contents(r)

        return r

    def _build_endpointcost(self, data):
        self.vtag_ = Vtag.from_json(data['meta'].get('vtag', {}))
        self.ecmap_ = data['endpoint-cost-map']

    def __build_query(self, sips, dips):
        data = dict()
        data['cost-type'] = dict()
        data['cost-type']['cost-mode'] = self.cost_mode
        data['cost-type']['cost-metric'] = self.cost_metric
        data['endpoints'] = dict()
        data['endpoints']['srcs'] = sips
        data['endpoints']['dsts'] = dips
        return data

    def get_costs(self, sips: List[str],
                  dips: List[str]) -> Dict[str, Dict[str, Any]]:
        sips = {s: 'ipv{}:{}'.format(ipaddress.ip_address(s).version, s) for s in sips}
        dips = {d: 'ipv{}:{}'.format(ipaddress.ip_address(d).version, d) for d in dips}
        data = self.__build_query(list(sips.values()), list(dips.values()))
        r = self.post(data)
        self.from_payload(r.text)

        result = {}
        for s in sips.keys():
            if sips[s] not in self.ecmap_:
                continue
            result.update({s: {d: self.ecmap_[sips[s]][dips[d]] for d in dips.keys() if dips[d] in self.ecmap_[sips[s]]}})
        return result

    def get_endpoint_costs(self, sips: List[str],
                           dips: List[str]) -> Dict[str, Dict[str, Any]]:
        return self.get_costs(sips, dips)
