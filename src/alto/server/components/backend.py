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
import hashlib
import ipaddress
import json
import random
import time
from urllib.parse import urljoin

from alto.config import Config
from alto.common.constants import ALTO_CONTENT_TYPES, ALTO_PARAMETER_TYPES, get_diff_format
from alto.mock import (TEST_DYNAMIC_NM_1,
                       TEST_DYNAMIC_NM_2,
                       TEST_DYNAMIC_NM_3,
                       TEST_DYNAMIC_NM_4,
                       TEST_DYNAMIC_NM_5)

from .db import data_broker_manager


class MockService:
    """
    Mock backend algorithm for test purpose.
    """

    def __init__(self, *args, resource_id='default-networkmap',
                 resource_type='network-map', refresh_interval=-1, **kwargs):
        self.count = 0
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.refresh_interval = refresh_interval
        self.last_timestamp = -1
        self.map = dict()

    def get_random_ip_range(self, ip_prefix='192.0.2.{}'):
        first, second = sorted(random.choices(range(256), k=2))
        first_ip = ipaddress.ip_address(ip_prefix.format(first))
        second_ip = ipaddress.ip_address(ip_prefix.format(second))
        return ipaddress.summarize_address_range(first_ip, second_ip)

    def next_map(self):
        data = dict()
        if self.resource_type == 'network-map':
            data['PID0'] = { "ipv4" : [ "0.0.0.0/0" ], "ipv6" : [ "::/0" ] }
            data['PID1'] = { "ipv4": [ ip.exploded for ip in self.get_random_ip_range('192.0.2.{}') ] }
            data['PID2'] = { "ipv4": [ ip.exploded for ip in self.get_random_ip_range('198.51.100.{}') ] }
            data['PID3'] = { "ipv4": [ ip.exploded for ip in self.get_random_ip_range('203.0.113.{}') ] }
        return {
            "meta" : {
                "vtag": {
                    "resource-id": self.resource_id,
                    "tag": hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()
                }
            },
            "network-map": data
        }

    def lookup(self, *args, **kwargs):
        now = time.time()
        if self.refresh_interval < 0:
            self.map = self.next_map()
        elif self.last_timestamp < 0 or now - self.last_timestamp > self.refresh_interval:
            self.map = self.next_map()
            self.last_timestamp = now
        return self.map


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

    def lookup(self, srcs, dsts, cost_type):
        if self.autoreload:
            self.db.build_cache()

        content = dict()
        content['meta'] = dict()
        content['meta']['cost-type'] = cost_type

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
        content['endpoint-cost-map'] = costs
        return content


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


class TIPSControlService:
    """
    Backend algorithm for TIPS.
    """

    def __init__(self, namespace, tips_resource_id='', **kwargs) -> None:
        from .vcs import vcs_singleton

        self.ns = namespace
        self.vcs = vcs_singleton
        self.tips_resource_id = tips_resource_id
        self.config = Config()

    def subscribe(self, post_data, client_id='public'):
        resource_id = post_data.get('resource-id')
        request_body = post_data.get('input')
        diff_format = self.get_diff_format(resource_id)
        if diff_format is None:
            return
        print('Client ({}) subscribing {} (input={}, diff_formath={})'.format(client_id, resource_id, request_body, diff_format))
        digest = self.vcs.subscribe(resource_id, request_body=request_body,
                                    client_id=client_id, diff_format=diff_format)
        print('Client ({}) subscribed {}: {}'.format(client_id, resource_id, digest))
        tips_view = dict()
        # FIXME: the path root '/tips' SHOULD NOT be hardcoded
        tips_view['tips-view-uri'] = '/tips/{}/{}'.format(resource_id, digest)
        tips_view_summary = dict()
        updates_graph = self.vcs.get_tips_view(resource_id, digest)
        print('Got updates graph of {}/{}'.format(resource_id, digest))
        seqs = set()
        for start_seq in updates_graph:
            if start_seq != '0':
                seqs.add(int(start_seq))
            for end_seq in updates_graph[start_seq]:
                seqs.add(int(end_seq))
        tips_view_summary['updates-graph-summary'] = {
            'start-seq': min(seqs),
            'end-seq': max(seqs),
            'start-edge-rec': {
                'seq-i': 0,
                'seq-j': int(updates_graph['0'][-1])
            }
        }

        # FIXME: get `support-server-push` from capabilities of the IRD entry
        tips_view_summary['server-push'] = False
        tips_view['tips-view-summary'] = tips_view_summary
        return tips_view

    def unsubscribe(self, resource_id, digest, client_id='public'):
        return self.vcs.unsubscribe(resource_id, digest, client_id=client_id)

    def get_tips_view(self, resource_id, digest, ug_only=False, start_seq=None, end_seq=None):
        # TODO: check if the client has already subscribed the resource; if not, return Unauthorized error
        ug = self.vcs.get_tips_view(resource_id, digest)
        view = dict()
        tag = hashlib.sha1(json.dumps(ug, sort_keys=True).encode()).hexdigest()
        if not ug_only:
            view['meta'] = {'resource-id': digest, 'tag': tag}
            # TODO: support server push later
            view['push-state'] = {'server-push': False, 'next-edge': None}
        updates_graph = dict()
        if start_seq is not None and end_seq is not None:
            start_seq = str(start_seq)
            end_seq = str(end_seq)
            edge_view = self.get_tips_edge_view(resource_id, digest, start_seq, end_seq)
            if edge_view is None:
                return
            updates_graph = {start_seq: {end_seq: edge_view}}
        else:
            for start_seq in ug:
                updates_graph[start_seq] = dict()
                for end_seq in ug[start_seq]:
                    edge_view = self.get_tips_edge_view(resource_id, digest, start_seq, end_seq)
                    if edge_view is not None:
                        updates_graph[start_seq][end_seq] = edge_view

        view['updates-graph'] = updates_graph

        return view

    def get_tips_edge_view(self, resource_id, digest, start_seq, end_seq):
        data = self.vcs.get_tips_data(resource_id, digest, start_seq, end_seq)
        edge_view = None
        if data is not None:
            edge_view = {
                'media-type': self.get_media_type(resource_id, patch=(start_seq != '0')),
                'tag': hashlib.sha1(data).hexdigest(),
                'size': len(data)
            }
        return edge_view

    def get_tips_data(self, resource_id, digest, start_seq, end_seq):
        start_seq = str(start_seq)
        end_seq = str(end_seq)
        data = self.vcs.get_tips_data(resource_id, digest, start_seq, end_seq)
        if data is None:
            return None, None
        media_type = self.get_media_type(resource_id, patch=(start_seq != '0'))
        return json.loads(data), media_type

    def get_configured_resources(self):
        return self.config.get_configured_resources()

    def get_diff_format(self, resource_id, resources=None):
        media_type = self.get_diff_media_type(resource_id, resources=resources)
        return get_diff_format(media_type)

    def get_diff_media_type(self, resource_id, resources=None):
        if resources is None:
            resources = self.get_configured_resources()
        resource_config = resources.get(self.tips_resource_id)
        if resource_config is None:
            return
        capability = resource_config.get('capabilities', dict())
        diff_format_dict = capability.get('incremental-change-media-types', dict())
        return diff_format_dict.get(resource_id)

    def get_media_type(self, resource_id, patch=False):
        resources = self.get_configured_resources()
        if patch:
            return self.get_diff_media_type(resource_id, resources=resources)
        resource_config = resources.get(resource_id)
        return ALTO_CONTENT_TYPES.get(resource_config['type'])
