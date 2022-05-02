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
# - Jacob Dunefsky <jacob.dunefsky@yale.edu>

import logging

from typing import List, Dict

import requests

from alto.config import Config
from alto.model import ALTONetworkMap, ALTOCostMap

_logger = logging.getLogger(__name__)


class Client:
    """
    Base ALTO client class.
    """

    def __init__(self, config=True, default_ird=None, auth=None, **kwargs) -> None:
        """
        Constructor for the ALTO client class.
        """
        _logger.debug("Creating ALTO client instance.")
        self.default_ird = default_ird if default_ird else None
        self.auth = auth if auth else None
        if config:
            self.config = Config()

    def get_network_map(self, url=None, **kwargs):
        """
        Low-level API: get raw network map object.

        Parameters
        ----------
        url : (optional) str
            URI to access the network map

        Returns
        -------
        ALTONetworkMap
            ALTO Network Map object.
        """
        if url is None:
            url = self.config.get_default_networkmap_uri()
        auth = self.config.get_server_auth()
        if self.auth:
            auth = self.auth
        return ALTONetworkMap(url, auth=auth, **kwargs)

    def get_cost_map(self, url=None, **kwargs):
        """
        Low-level API: get raw cost map object.

        Parameters
        ----------
        url : (optional) str
            URI to access the cost map

        Returns
        -------
        ALTOCostMap
            ALTO Cost Map object.
        """
        if url is None:
            url = self.config.get_default_costmap_uri()
        auth = self.config.get_server_auth()
        if self.auth:
            auth = self.auth
        return ALTOCostMap(url, auth=auth, **kwargs)

    def get_ird(self):
        """
        Return ALTO Information Resource Directory (IRD).

        Returns
        -------
        InformationResourceDirectory
            ALTO Information Resource Directory (IRD) object.
        """
        # TODO: query the default ird configured for this client.
        raise NotImplementedError

    def get_routing_costs(self, src_ips: List[str], dst_ips: List[str],
                          cost_map=None, cost_type=None) -> Dict[str, Dict[str, int or float]]:
        """
        Return ALTO routing costs between `src_ips` and `dst_ips`.

        This method will query cost map and network map to get coarse-grained costs.

        Parameters
        ----------
        src_ips : list[str]
            List of source IP addresses
        dst_ips : list[str]
            List of destination IP addresses
        cost_map : (optional) str
            Resource id of the requested cost map
        cost_type : (optional) str
            Requested cost type

        Returns
        -------
        dict[str, dict[str, int or float]]
            Mapping of routing costs
        """
        if cost_map is not None:
            # TODO: read IRD to get cost map object using the resource id.
            raise NotImplementedError

        if cost_type is not None:
            # TODO: user-specified cost type for filtered cost map
            raise NotImplementedError

        _nm = self.get_network_map()
        spids = _nm.get_pid(src_ips)
        spidmap = dict(zip(src_ips, spids))
        dpids = _nm.get_pid(dst_ips)
        dpidmap = dict(zip(dst_ips, dpids))

        _cm = self.get_cost_map()
        costs = _cm.get_costs(spids, dpids)
        return {
            sip: {
                dip: costs[spidmap[sip]][dpidmap[dip]]
                for dip in dst_ips
            } for sip in src_ips
        }
    
    def get_throughput(self, input_dict: str, url=None) -> str:
        """Obtains ALTO throughput data for an input list representing flows
            of interest.

        Args:
            input_dict (list): A list of dicts, representing a list of flows.
                The list should be of the form
                [{"srcs": [src1, src2, src3, ...], "dsts": [dst1, dst2, dst3, ...]},
                {"srcs": [src4, src5, src6, ...], "dsts": [dst4, dst5, dst6, ...]},
                ...]
            
            url : (optional) str
                URI to access the cost map
            
        Returns:
            A JSON string representing the throughput for each flow
        """

        query_json = {
            "cost-type": {"cost-mode" : "numerical",
                          "cost-metric" : "tput"},
            "endpoint-flows" : input_dict
        }
        query_str = json.dumps(query_json)
        query_headers = {
            "Content-Type": "application/alto-endpointcostparams+json",
            "Accept": "application/alto-endpointcost+json,application/alto-error+json"
        }
        if url=None: url = self.config.get_costmap_uri()
        alto_r = requests.post(url,
            headers=query_headers,
            data=query_str
        )

        alto_json_resp = alto_r.json()
        return json.dumps(alto_json_resp)
