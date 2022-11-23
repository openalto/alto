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


def get_content(alg, flows, prop_names, cost_type, resource_id, host_name):
    """
    Call path vector algorithm to compute path vectors and properties.

    Parameters
    ----------
    alg : class
        A class provide `lookup()` method for path vector lookup for a given set
        of `flows` and a given list of `property_names`.
    flows : list
        List of `(src, dst)` pairs.
    prop_names : list
        List of property names.
    service_name : str
        Resource id.
    host_name : str
        Host name of the ALTO server.

    Returns
    -------
    ecs_part : dict
        Dictionary for the `endpoint-cost-map` response.
    prop_part : dict
        Dictionary for the `property-map` response.
    """
    paths, link_map = alg.lookup(flows, prop_names)

    # prepare the ECS part
    ecs_part = {}
    ecs_part[HEADER_CTYPE] = ALTO_CONTENT_TYPE_ECS
    ecs_part[HEADER_ID] = "<ecs@%s>" % (host_name)
    ecs_rid = '%s.ecs' % resource_id

    tag = uuid.uuid4().hex
    vtag = { 'resource-id': ecs_rid, 'tag': tag }
    data = {}
    data['meta'] = { 'vtag': vtag, 'cost-type': cost_type }
    data['endpoint-cost-map'] = paths
    ecs_part['data'] = data

    # prepare the property map part
    prop_part = {}
    prop_part[HEADER_CTYPE] = ALTO_CONTENT_TYPE_PROPMAP
    prop_part[HEADER_ID] = "<propmap@%s>" % (host_name)
    prop_rid = '%s.propmap' % resource_id

    data = {}
    data['meta'] = {'dependent-vtags': [ vtag ]}
    property_map = {}
    for ane in link_map:
        ane_name = '.ane:%s' % (ane)
        ane_props = link_map[ane]
        props = prop_names if len(prop_names) > 0 else ane_props.keys()
        print(props)
        property_map[ane_name] = {pn: ane_props[pn] for pn in props if ane_props.get(pn) is not None}
    data['property-map'] = property_map

    prop_part['data'] = data

    return [ ecs_part, prop_part ]

