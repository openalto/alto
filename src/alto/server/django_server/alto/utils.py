import socket
import uuid

import requests
from requests.exceptions import Timeout, ConnectionError

IP_URLS = ["http://whatismyip.akamai.com/", "http://wgetip.com/"]

HEADER_CTYPE = 'Content-Type'
HEADER_ID = 'Content-ID'
ALTO_CONTENT_TYPE_ECS = 'application/alto-endpointcost+json'
ALTO_CONTENT_TYPE_PROPMAP = 'application/alto-propmap+json'
PREFIX_INET4 = "ipv4:"

def get_content(pv, post_data, service_name, host_name):
    """
    post_data:
    service_name: resource id of the service
    host_name:  ip of server
    """
    print(post_data)
    if 'endpoints' in post_data:
        srcs = post_data['endpoints']['srcs']
        dsts = post_data['endpoints']['dsts']
        pairs = {(src.lstrip(PREFIX_INET4), dst.lstrip(PREFIX_INET4)) for src in srcs for dst in dsts}
    elif 'endpoint-flows' in post_data:
        pairs = set()
        for spec in post_data['endpoint-flows']:
            srcs, dsts = spec['srcs'], spec['dsts']
            pairs |= {(src.lstrip(PREFIX_INET4), dst.lstrip(PREFIX_INET4)) for src in srcs for dst in dsts}

    assert 'cost-type' in post_data
    cost_type = post_data['cost-type']
    assert cost_type['cost-mode'] == 'array'
    assert cost_type['cost-metric'] == 'ane-path'

    if 'ane-property-names' in post_data:
        properties = post_data['ane-property-names']
    else:
        properties = []

    paths, link_map = pv.lookup(pairs, properties)

    # prepare the ECS part
    ecs_part = {}
    ecs_part[HEADER_CTYPE] = ALTO_CONTENT_TYPE_ECS
    ecs_part[HEADER_ID] = "<ecs@%s>" % (host_name)
    ecs_rid = '%s.ecs' % (service_name)

    tag = uuid.uuid4().hex
    vtag = { 'resource-id': ecs_rid, 'tag': tag }
    data = {}
    data['meta'] = { 'vtag': vtag, 'cost-type': cost_type }
    data['endponit-cost-map'] = paths
    ecs_part['data'] = data

    # prepare the property map part
    prop_part = {}
    prop_part[HEADER_CTYPE] = ALTO_CONTENT_TYPE_PROPMAP
    prop_part[HEADER_ID] = "<propmap@%s>" % (host_name)
    prop_rid = '%s.propmap' % (service_name)

    data = {}
    data['meta'] = {'dependent-vtags': [ vtag ]}
    property_map = {}
    for ane in link_map:
        ane_name = '.ane:%s' % (ane)
        ane_props = link_map[ane]
        props = properties if len(properties) > 0 else ane_props.keys()
        print(props)
        property_map[ane_name] = {pn: ane_props[pn] for pn in props if ane_props.get(pn) is not None}
    data['property-map'] = property_map

    prop_part['data'] = data

    return [ ecs_part, prop_part ]
