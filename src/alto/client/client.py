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

import logging

from typing import List, Dict

from alto.config import Config
from alto.model import ALTONetworkMap, ALTOCostMap, ALTOPathVector

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

    def get_resource(self, url=None, resource_type='cost-map', **kwargs):
        """
        """
        if resource_type == 'cost-map':
            return self.get_cost_map(url=url, **kwargs)
        elif resource_type == 'endpoint-cost':
            return self.get_endpoint_cost(url=url, **kwargs)
        elif resource_type == 'path-vector':
            return self.get_path_vector(url=url, **kwargs)
        else:
            return None

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
        nm = self.get_network_map(url=kwargs.pop('dependent_network_map', None))
        return ALTOCostMap(url, auth=auth, dependent_network_map=nm, **kwargs)

    def get_path_vector(self, url, **kwargs):
        """
        Low-level API: get raw path vector query object.

        Parameters
        ----------
        url : (optional) str
            URI to access the path vector query object.

        Returns
        -------
        ALTOPathVector
            ALTO Path Vector query object.
        """
        auth = self.config.get_server_auth()
        if self.auth:
            auth = self.auth
        # TODO: move ssl_verify config to configuration file
        return ALTOPathVector(url, auth=auth, verify=False, **kwargs)

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

    def get_multiple_costs(self, src_ips: List[str], dst_ips: List[str],
                           metrics=[], where=None):
        """
        Return multiple ALTO costs between `src_ips` and `dst_ips`

        Parameters
        ----------
        src_ips : list[str]
            List of source IP addresses
        dst_ips : list[str]
            List of destination IP addresses
        metrics : list[str]
            A list of metrics defined in the configuration file
        where : list[str]
            A list of constraints to filter (src_ip, dst_ip) pairs
        """
        costs = dict()
        mcosts = dict()
        for metric in metrics:
            resource_spec = self.config.get_resource_spec_by_metric(metric)
            if not resource_spec:
                continue
            cm = self.get_resource(**resource_spec)
            if not cm:
                continue
            mcosts[metric] = cm.get_endpoint_costs(src_ips, dst_ips)
        for s in src_ips:
            costs[s] = dict()
            for d in dst_ips:
                costs[s][d] = {m: mcosts[m][s][d] for m in metrics}
        # TODO: use `where` to filter costs
        return costs

    def get_routing_costs(self, src_ips: List[str], dst_ips: List[str],
                          cost_map=None, cost_type=None,
                          use_pv=None) -> Dict[str, Dict[str, int or float]]:
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
        use_pv : (optional) str
            Resource id of path vector service

        Returns
        -------
        dict[str, dict[str, int or float]]
            Mapping of routing costs
        """
        if use_pv:
            pv_uri = self.config.get_static_resource_uri(use_pv)
            _pv = self.get_path_vector(pv_uri)
            ane_paths, ane_props = _pv.get_costs(src_ips, dst_ips, prop_names=['next_hop', 'as_path'])
            costs = dict()
            for s in ane_paths:
                costs[s] = dict()
                for d in ane_paths[s]:
                    path = ane_paths[s][d]
                    c = dict()
                    c['hopcount'] = 0
                    for ane in path:
                        prop = ane_props.get(ane, dict())
                        if 'next_hop' in prop:
                            c['hopcount'] += 1
                            c['next_hop'] = prop['next_hop']
                        if 'as_path' in prop:
                            c['as_path'] = prop['as_path'].split(' ')
                            c['hopcount'] += len(c['as_path'])
                    costs[s][d] = c
            return costs
        else:
            if cost_map is not None:
                # TODO: read IRD to get cost map object using the resource id.
                # read static IRD to get cost map uri.
                cost_map = self.config.get_static_resource_uri(cost_map)

            if cost_type is not None:
                # TODO: user-specified cost type for filtered cost map
                raise NotImplementedError

            _nm = self.get_network_map()
            spids = _nm.get_pid(src_ips)
            spidmap = dict(zip(src_ips, spids))
            dpids = _nm.get_pid(dst_ips)
            dpidmap = dict(zip(dst_ips, dpids))

            _cm = self.get_cost_map(cost_map)
            costs = _cm.get_costs(spids, dpids)
            return {
                sip: {
                    dip: costs[spidmap[sip]][dpidmap[dip]]
                    for dip in dst_ips
                } for sip in src_ips
            }

