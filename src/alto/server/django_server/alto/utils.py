import socket

import requests
from requests.exceptions import Timeout, ConnectionError

IP_URLS = ["http://whatismyip.akamai.com/", "http://wgetip.com/"]


def _verify_address(addr):
    try:
        socket.inet_aton(addr)
        return True
    except (socket.error, UnicodeEncodeError, TypeError):
        return False


def fetch_ip():
    """
    fetch ip from Internet
    """
    for url in IP_URLS:
        try:
            req = requests.get(url, timeout=5)
            if req.status_code == 200:
                data = req.text.strip()
                if data is None or not _verify_address(data):
                    continue
                else:
                    return data
            else:
                raise ConnectionError
        except (Timeout, ConnectionError):
            print('Could not fetch public ip from %s', url)
    return None


def get_content(post_data, path_vector, host_name):
    """
    post_data:
    path_vector:
    host_name:  ip of server
    """
    return [
        {
            'content-type': 'application/alto-endpointcost+json',
            "content-id": ' <endpointcost@10.0.0.249>',
            'data': {
                "meta": {
                    "vtag": {
                        "resource-id": "pv.ecs",
                        "tag": "ec137bb78118468c853d5b622ac003f1"
                    },
                    "cost-type": {
                        "cost-metric": "ane-path",
                        "cost-mode": "array"
                    }
                },
                "endpoint-cost-map": {
                    "ipv4:10.0.0.252": {
                        "ipv4:10.0.0.251": ["L1", "L2", "L3", "L4"],
                        "ipv4:10.0.0.253": ["L1", "L2", "L5"]
                    },
                    "ipv4:10.0.0.251": {
                        "ipv4:10.0.0.253": ["L6", "L7", "L5"]
                    }
                }
            }
        },
        {
            'content-type': 'application/alto-propmap+json',
            'content-id': ' <propmap@10.0.0.249>',
            'data': {
                "meta": {
                    "dependent-vtags": [
                        {
                            "resource-id": "pv.ecs",
                            "tag": "ec137bb78118468c853d5b622ac003f1"
                        }
                    ]
                },
                "property-map": {
                    ".ane:L1": {
                        "bandwidth": 100000000,
                        "latency": 5
                    },
                    ".ane:L2": {
                    },
                    ".ane:L7": {

                    }
                }
            }

        }
    ]
