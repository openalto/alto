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


from dataclasses import dataclass, field
from typing import List, Dict, Optional
import requests
import pytricia
from dataclasses_json import dataclass_json, LetterCase, config

ALTO_CTYPE_NM = 'application/alto-networkmap+json'
ALTO_CTYPE_CM = 'application/alto-costmap+json'
ALTO_CTYPE_ECS = 'application/alto-endpointcost+json'
ALTO_CTYPE_ECS_PARAM = 'application/alto-endpointcostparams+json'
ALTO_CTYPE_ERROR = 'application/alto-error+json'


@dataclass_json(letter_case=LetterCase.KEBAB)
@dataclass
class Vtag:
    resource_id: str
    tag: str

@dataclass_json(letter_case=LetterCase.KEBAB)
@dataclass
class CostType:
    cost_metric: str
    cost_mode: str

@dataclass_json(letter_case=LetterCase.KEBAB)
@dataclass
class EndpointFilter:
    srcs: List[str]
    dsts: List[str]

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

    def __init__(self, ctype, url, auth=None, incre_mode=None):
        self.ctype = ctype
        self.url = url
        self.auth = auth
        self.incre_mode = incre_mode

    def get(self):
        headers = {
            'accepts': self.ctype + ',' + ALTO_CTYPE_ERROR
        }
        r = requests.get(self.url, auth=self.auth, headers=headers)
        r.raise_for_status()

        self.check_headers(r)
        self.check_contents(r)

        return r

    def post(self, ptype, params):
        self.check_params(params)

        headers = {
            'accepts': self.ctype + ',' + ALTO_CTYPE_ERROR,
            'Content-type': ptype
        }
        r = requests.get(self.url, auth=self.auth, headers=headers)
        r.raise_for_status()

        self.check_headers(r)
        self.check_contents(r)

    def check_headers(self, r):
        raise NotImplementedError

    def check_contents(self, r):
        raise NotImplementedError

    def check_params(self, params):
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

    def check_params(self, params):
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

    def check_headers(self, r):
        assert r.headers['content-type'] == ALTO_CTYPE_CM

    def check_contents(self, r):
        pass

    def check_params(self, params):
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

@dataclass_json(letter_case=LetterCase.KEBAB)
@dataclass
class ALTOEndpointCostParam:
    cost_type: CostType
    endpoint_flows: Optional[list[EndpointFilter]] = field(default=None, metadata=config(exclude=lambda x: x is None))
    endpoints: Optional[EndpointFilter] = field(default=None, metadata=config(exclude=lambda x: x is None))

class ALTOEndpointCostService(ALTOBaseResource):

    def __init__(self, param, url, **kwargs):
        ALTOBaseResource.__init__(self, ALTO_CTYPE_ECS, url, **kwargs)

        r = self.post(ALTO_CTYPE_ECS_PARAM, param)
