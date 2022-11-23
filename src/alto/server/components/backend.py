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

import math
from urllib.parse import urljoin

from alto.config import Config
from alto.common.constants import ALTO_CONTENT_TYPES, ALTO_PARAMETER_TYPES

from .db import data_broker_manager


class IRDService:
    """
    Backend algorithm for IRD generation.
    """

    def __init__(self, namespace, namespaces=None, **kwargs):
        self.ns = namespace
        self.namespaces = namespaces
        self.config = Config()

    def list_resources(self, self_resource_id, default_base_uri='https://localhost/'):
        resources = self.config.get_configured_resources()
        base_uri = self.config.get_server_base_uri() or default_base_uri
        directory = dict()

        directory['meta'] = dict()
        cost_types = self.config.get_server_cost_types()
        if cost_types:
            directory['meta']['cost-types'] = cost_types

        directory['resources'] = dict()
        for rid in resources.keys():
            if rid == self_resource_id:
                continue
            resource_config = resources[rid]
            if self.namespaces and resource_config['namespace'] not in self.namespaces:
                continue

            resource_entry = dict()
            resource_path = resource_config['path']
            resource_entry['uri'] = urljoin(base_uri, '{}/{}'.format(resource_path, rid))
            media_type = ALTO_CONTENT_TYPES.get(resource_config['type'])
            if not media_type:
                continue
            resource_entry['media-type'] = media_type
            accepts = ALTO_PARAMETER_TYPES.get(resource_config['type'])
            if accepts:
                resource_entry['accepts'] = accepts
            capabilities = resource_config.get('capabilities')
            if capabilities:
                resource_entry['capabilities'] = capabilities
            uses = resource_config.get('uses')
            if uses:
                resource_entry['uses'] = uses

            directory['resources'][rid] = resource_entry
        return directory


class EndpointPropertyService:
    """
    Backend algorithm for EPS.
    """

    def __init__(self, namespace, autoreload=True, **kwargs):
        self.ns = namespace
        self.autoreload = autoreload
        self.eb = data_broker_manager.get(self.ns, db_type='endpoint')

    def lookup(self, endpoints, prop_names):
        property_map = dict()
        if self.autoreload:
            self.eb.build_cache()
        for endpoint in endpoints:
            property_map[endpoint] = self.eb.lookup(endpoint, prop_names)
        return property_map


class GeoIPPropertyService:
    """
    Backend algorithm for entity property using GeoIP database.
    """

    def __init__(self, namespace, data_source=None, autoreload=True, **kwargs):
        self.ns = namespace
        self.autoreload = autoreload
        self.db = data_broker_manager.get(self.ns, db_type='delegate')
        self.data_source = data_source

    def get_geomap(self, entities):
        eidmap = dict()
        for e in entities:
            domain, entityid = e.split(':', 1)
            if domain not in ['ipv4', 'ipv6']:
                continue
            eidmap[e] = entityid
        geomap = self.db.lookup(self.data_source, list(eidmap.values()))
        return {e: geomap[eid] for e, eid in eidmap.items()}

    def lookup(self, entities):
        if self.autoreload:
            self.db.build_cache()

        geomap = self.get_geomap(entities)
        property_map = dict()
        for e in geomap.keys():
            geoinfo = geomap[e]
            if not geoinfo:
                continue
            property_map[e] = {
                'geolocation': {'lat': geoinfo[0], 'lng': geoinfo[1]}
            }
        return property_map


class GeoDistanceService(GeoIPPropertyService):
    """
    Backend algorithm for geo-distance based endpoint cost service.
    """

    def get_geo_distance(self, src_loc, dst_loc):
        lat1, lng1 = map(math.radians, src_loc)
        lat2, lng2 = map(math.radians, dst_loc)
        d_lat = lat1 - lat2
        d_lng = lng1 - lng2
        d_geo = 6378 * 2 * math.asin(math.sqrt(math.sin(d_lat/2)**2 +
                                               math.cos(lat1)*math.cos(lat2)*math.sin(d_lng/2)**2))
        return d_geo

    def lookup(self, srcs, dsts):
        if self.autoreload:
            self.db.build_cache()

        costs = dict()
        endpoints = set(srcs).union(set(dsts))
        geomap = self.get_geomap(endpoints)
        for s in srcs:
            src_loc = geomap.get(s)
            if not src_loc:
                continue
            costs[s] = dict()
            for d in dsts:
                dst_loc = geomap.get(d)
                if not dst_loc:
                    continue
                costs[s][d] = self.get_geo_distance(src_loc, dst_loc)
        return costs


class PathVectorService:
    """
    Backend algorithm for ECS with path vector extension
    """

    def __init__(self, namespace, autoreload=True, **kwargs) -> None:
        self.ns = namespace
        self.autoreload = autoreload
        self.fib = data_broker_manager.get(self.ns, db_type='forwarding')
        self.eb = data_broker_manager.get(self.ns, db_type='endpoint')

    def parse_flow(self, flow):
        """
        Extract attributes of a flow object.

        Parameters
        ----------
        flow : object

        Return
        ------
        A tuple of attributes.
        """
        return flow[0], flow[0], flow[1]

    def iterate_next_hops(self, ingress, dst, ane_dict, property_map, ane_path):
        ingress_prop = self.eb.lookup(ingress, ['dpid', 'in_port'])
        dpid = ingress_prop.get('dpid')
        if not dpid:
            return None, ane_path
        in_port = ingress_prop.get('in_port')
        if not in_port:
            in_port = '0'

        action = self.fib.lookup(dpid, dst, in_port=in_port)
        nh = action.next_hop
        if not nh:
            # last hop, exit
            return action, ane_path
        outgoing_link = action.actions.get('outgoing_link')
        if outgoing_link:
            ane_name = outgoing_link
            if ane_name not in property_map:
                nh_props = self.eb.lookup(nh, property_names=['incoming_links'])
                incoming_links = nh_props.get('incoming_links', dict())
                property_map[ane_name] = incoming_links.get(ane_name, dict())
        else:
            nh_ane = (dpid, nh)
            if nh_ane not in ane_dict:
                ane_idx = len(ane_dict) + 1
                ane_name = 'autolink_{}'.format(ane_idx)
                ane_dict[nh_ane] = ane_name
            ane_name = ane_dict[nh_ane]
            if ane_name not in property_map:
                property_map[ane_name] = dict()
        property_map[ane_name]['next_hop'] = nh
        if ane_name in ane_path:
            # find loop, exit
            return action, ane_path
        ane_path.append(ane_name)
        return self.iterate_next_hops(nh, dst, ane_dict, property_map, ane_path)

    def lookup(self, flows, property_names):
        """
        Parameters
        ----------
        flows : list
            A list of flow objects.

        Returns
        -------
        paths : list
            A list of ane paths.
        propery_map : dict
            Mapping from ane to properties.
        """
        if self.autoreload:
            self.fib.build_cache()
            self.eb.build_cache()

        paths = dict()
        property_map = dict()

        ane_dict = dict()
        as_path_dict = dict()

        for flow in flows:
            ingress, src, dst = self.parse_flow(flow)
            src_prop = self.eb.lookup(src)
            if src_prop is None:
                continue
            if not src_prop.get('is_local'):
                continue

            if src not in paths:
                paths[src] = dict()

            ane_path = list()
            last_action, ane_path = self.iterate_next_hops(ingress, dst, ane_dict, property_map, ane_path)

            as_path = ''
            if last_action:
                as_path = ' '.join(last_action.actions.get('as_path', [])[:-1])
            if len(as_path) > 0:
                if as_path not in as_path_dict:
                    as_path_idx = len(as_path_dict) + 1
                    as_path_ane = 'autopath_{}'.format(as_path_idx)
                    as_path_dict[as_path] = as_path_ane
                    property_map[as_path_ane] = dict()
                    if property_names is not None and 'as_path' in property_names:
                        property_map[as_path_ane]['as_path'] = as_path
                as_path_ane = as_path_dict[as_path]
                ane_path.append(as_path_ane)

            paths[src][dst] = ane_path

        property_map = {ane: {pname: pval
                              for pname, pval in props.items() if pname in property_names}
                        for ane, props in property_map.items()}

        return paths, property_map

