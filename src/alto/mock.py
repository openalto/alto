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

import json

from unittest.mock import MagicMock

from alto.model.rfc7285 import ALTO_CTYPE_NM, ALTO_CTYPE_CM, ALTO_CTYPE_ECS


MOCK_GEOIP2_DB = {
    '10.1.0.2': (31.224, 121.469),
    '10.2.0.2': (41.311, -72.93)
}

class MockGeoIP2(MagicMock):

    class Location:

        def __init__(self, location) -> None:
            self.latitude = location[0]
            self.longitude = location[1]

    class GeoInfo:

        def __init__(self, location) -> None:
            self.location = MockGeoIP2.Location(location)

    class Reader:

        def __init__(self, path, preset=dict()):
            self.path = path

        def city(self, endpoint):
            return MockGeoIP2.GeoInfo(MOCK_GEOIP2_DB.get(endpoint, (0.0, 0.0)))


    class Client:

        def __init__(self, account_id, license_key, preset=dict(), **kwargs):
            self.account_id = account_id
            self.license_key = license_key
            self.preset = preset
            self.kwargs = kwargs

        def city(self, endpoint):
            return MockGeoIP2.GeoInfo(MOCK_GEOIP2_DB.get(endpoint, (0.0, 0.0)))


mockGeoIP2 = MockGeoIP2()


class MockKazoo(MagicMock):

    class KazooClient:

        def __init__(self, **kwargs):
            self.base = dict()

        def _parse_path(self, path):
            return path.split('/')[1:]

        def _get_leaf_node(self, node_path):
            parent = self.base
            for n in node_path:
                parent = parent[n]
            return parent

        def start(self, **kwargs):
            pass

        def stop(self, **kwargs):
            pass

        def ensure_path(self, path, **kwargs):
            nodes = self._parse_path(path)
            parent = self.base
            for n in nodes:
                if n not in parent:
                    parent[n] = dict()
                parent = parent[n]

        def exists(self, path, **kwargs):
            nodes = self._parse_path(path)
            parent = self.base
            for n in nodes:
                if n not in parent:
                    return None
                parent = parent[n]
            return True

        def create(self, path, data, **kwargs):
            nodes = self._parse_path(path)
            parent = self._get_leaf_node(nodes[:-1])
            parent[nodes[-1]] = data

        def get_children(self, path, **kwargs):
            nodes = self._parse_path(path)
            parent = self._get_leaf_node(nodes)
            return list(parent.keys())

        def get(self, path, **kwargs):
            nodes = self._parse_path(path)
            return self._get_leaf_node(nodes), None

        def delete(self, path, **kwargs):
            nodes = self._parse_path(path)
            parent = self._get_leaf_node(nodes[:-1])
            del parent[nodes[-1]]


mockKazoo = MockKazoo()


TEST_DEFAULT_NM = {
    "meta" : {
        "vtag": {
            "resource-id": "my-default-network-map",
            "tag": "da65eca2eb7a10ce8b059740b0b2e3f8eb1d4785"
        }
    },
    "network-map" : {
        "PID1" : {
            "ipv4" : [
                "192.0.2.0/24",
                "198.51.100.0/25"
            ]
        },
        "PID2" : {
            "ipv4" : [
                "198.51.100.128/25"
            ]
        },
        "PID0" : {
            "ipv4" : [
                "0.0.0.0/0"
            ],
            "ipv6" : [
                "::/0"
            ]
        }
    }
}

TEST_DEFAULT_CM = {
    "meta" : {
        "dependent-vtags" : [
            {"resource-id": "my-default-network-map",
             "tag": "da65eca2eb7a10ce8b059740b0b2e3f8eb1d4785"
             }
        ],
        "cost-type" : {"cost-mode"  : "numerical",
                       "cost-metric": "routingcost"
                       }
    },
    "cost-map" : {
        "PID1": { "PID1": 1,  "PID2": 5,  "PID0": 10 },
        "PID2": { "PID1": 5,  "PID2": 1,  "PID0": 15 },
        "PID0": { "PID1": 20, "PID2": 15, "PID0": 1  }
    }
}

TEST_BW_AVAIL_CM = {
  "meta" : {
    "dependent-vtags" : [
      {"resource-id": "my-default-network-map",
       "tag": "da65eca2eb7a10ce8b059740b0b2e3f8eb1d4785"
      }
    ],
    "cost-type" : {"cost-mode"  : "numerical",
                   "cost-metric": "bw-available"
                  }
  },
  "cost-map" : {
    "PID1": { "PID1": 1000000, "PID2": 1000, "PID0": 1000 },
    "PID2": { "PID1": 1000, "PID2": 1000000, "PID0": 5000 },
    "PID0": { "PID1": 1000, "PID2": 5000, "PID0": 1000000 }
  }
}

TEST_DELAY_OW_CM = {
  "meta" : {
    "dependent-vtags" : [
      {"resource-id": "my-default-network-map",
       "tag": "da65eca2eb7a10ce8b059740b0b2e3f8eb1d4785"
      }
    ],
    "cost-type" : {"cost-mode"  : "numerical",
                   "cost-metric": "delay-ow"
                  }
  },
  "cost-map" : {
    "PID1": { "PID1": 0,   "PID2": 50, "PID0": 100 },
    "PID2": { "PID1": 50,  "PID2": 0,  "PID0": 50 },
    "PID0": { "PID1": 100, "PID2": 50, "PID0": 0 }
  }
}

TEST_ECS = {
    "meta": {
        "vtag": {"resource-id": "ecs",
                 "tag": "e0a457d947cf4e7db6e1ec08f2de0946"},
        "cost-type": {"cost-metric": "numerical",
                      "cost-mode": "array"
                      }
    },
    "endpoint-cost-map": {
        "ipv4:192.0.2.100": {"ipv4:198.51.100.2": 1,
                             "ipv4:198.51.100.254": 5}
    }
}

TEST_ECS_PV = """--d41d8cd98f00b204e9800998ecf8427e
Content-Type: application/alto-endpointcost+json
Content-ID: <ecs@localhost>

{"meta": {"vtag": {"resource-id": "cern-pv.ecs", "tag": "e0a457d947cf4e7db6e1ec08f2de0946"}, "cost-type": {"cost-metric": "ane-path", "cost-mode": "array"}}, "endpoint-cost-map": { "ipv4:198.51.100.2": {"ipv4:192.0.2.100": ["autolink_1", "autopath_1"]}, "ipv4:198.51.100.254": {"ipv4:192.0.2.100": ["autolink_2", "autopath_2"]}}}
--d41d8cd98f00b204e9800998ecf8427e
Content-Type: application/alto-propmap+json
Content-ID: <propmap@localhost>

{"meta": {"dependent-vtags": [{"resource-id": "cern-pv.ecs", "tag": "e0a457d947cf4e7db6e1ec08f2de0946"}]}, "property-map": {".ane:autolink_1": {"next_hop": "192.65.183.46"}, ".ane:autopath_1": {"as_path": "513"}, ".ane:autolink_2": {"next_hop": "192.65.184.145"}, ".ane:autopath_2": {"as_path": "20965 2091 789"}}}
--d41d8cd98f00b204e9800998ecf8427e--
"""

TEST_DYNAMIC_NM_1 = {
    "meta" : {
        "vtag": {
            "resource-id": "dynamic-networkmap",
            "tag": "da65eca2eb7a10ce8b059740b0b2e3f8eb1d4785"
        }
    },
    "network-map" : {
        "PID1" : {
            "ipv4" : [ "192.0.2.0/24", "198.51.100.0/25" ]
        },
        "PID2" : {
            "ipv4" : [ "198.51.100.128/25" ]
        },
        "PID0" : {
            "ipv4" : [ "0.0.0.0/0" ],
            "ipv6" : [ "::/0" ]
        }
    }
}

TEST_DYNAMIC_NM_2 = {
    "meta" : {
        "vtag": {
            "resource-id": "dynamic-networkmap",
            "tag": "8124fa5960796ba5d9295d1bb094563fe77fff03"
        }
    },
    "network-map" : {
        "PID1" : {
            "ipv4" : [ "192.0.2.0/24", "198.51.100.0/25" ]
        },
        "PID2" : {
            "ipv4" : [ "198.51.100.128/25" ]
        },
        "PID3" : {
            "ipv4" : [ "192.0.3.0/24" ]
        },
        "PID0" : {
            "ipv4" : [ "0.0.0.0/0" ],
            "ipv6" : [ "::/0" ]
        }
    }
}

TEST_DYNAMIC_NM_3 = {
    "meta" : {
        "vtag": {
            "resource-id": "dynamic-networkmap",
            "tag": "dafb9c1b9a78d00ab6896c09b8e350f727fd966c"
        }
    },
    "network-map" : {
        "PID1" : {
            "ipv4" : [ "192.0.2.0/24", "198.51.100.0/24" ]
        },
        "PID3" : {
            "ipv4" : [ "192.0.3.0/24" ]
        },
        "PID0" : {
            "ipv4" : [ "0.0.0.0/0" ],
            "ipv6" : [ "::/0" ]
        }
    }
}

TEST_DYNAMIC_NM_4 = {
    "meta" : {
        "vtag": {
            "resource-id": "dynamic-networkmap",
            "tag": "dafb9c1b9a78d00ab6896c09b8e350f727fd966c"
        }
    },
    "network-map" : {
        "PID1" : {
            "ipv4" : [ "192.0.2.0/24", "198.51.100.0/24" ]
        },
        "PID2" : {
            "ipv4" : [ "198.51.101.0/25" ]
        },
        "PID3" : {
            "ipv4" : [ "192.0.3.0/24", "198.51.101.128/25" ]
        },
        "PID0" : {
            "ipv4" : [ "0.0.0.0/0" ],
            "ipv6" : [ "::/0" ]
        }
    }
}

TEST_DYNAMIC_NM_5 = {
    "meta" : {
        "vtag": {
            "resource-id": "dynamic-networkmap",
            "tag": "dafb9c1b9a78d00ab6896c09b8e350f727fd966c"
        }
    },
    "network-map" : {
        "PID1" : {
            "ipv4" : [ "192.0.2.0/24", "198.51.100.0/24" ]
        },
        "PID2" : {
            "ipv4" : [ "198.51.101.0/24" ]
        },
        "PID3" : {
            "ipv4" : [ "192.0.3.0/24" ]
        },
        "PID0" : {
            "ipv4" : [ "0.0.0.0/0" ],
            "ipv6" : [ "::/0" ]
        }
    }
}

MOCK = [
    {
        'uri': 'http://localhost:8181/alto/networkmap/default-networkmap',
        'headers': {'content-type': ALTO_CTYPE_NM},
        'json': TEST_DEFAULT_NM,
        'status_code': 200
    },
    {
        'uri': 'http://localhost:8000/networkmap/dynamic-networkmap',
        'headers': {'content-type': ALTO_CTYPE_NM},
        'json_alt': [TEST_DYNAMIC_NM_1, TEST_DYNAMIC_NM_2, TEST_DYNAMIC_NM_3,
                     TEST_DYNAMIC_NM_4, TEST_DYNAMIC_NM_5],
        'index': 0,
        'status_code': 200
    },
    {
        'uri': 'http://localhost:8181/alto/costmap/default-costmap',
        'headers': {'content-type': ALTO_CTYPE_CM},
        'json': TEST_DEFAULT_CM,
        'status_code': 200
    },
    {
        'uri': 'http://localhost:8181/alto/costmap/bw-available',
        'headers': {'content-type': ALTO_CTYPE_CM},
        'json': TEST_BW_AVAIL_CM,
        'status_code': 200
    },
    {
        'uri': 'http://localhost:8181/alto/costmap/delay-ow',
        'headers': {'content-type': ALTO_CTYPE_CM},
        'json': TEST_DELAY_OW_CM,
        'status_code': 200
    },
    {
        'uri': 'http://localhost:8181/alto/ecs/routingcost',
        'headers': {'content-type': ALTO_CTYPE_ECS},
        'json': TEST_ECS,
        'status_code': 200
    },
    {
        'uri': 'http://localhost:8181/alto/pathvector/pv',
        'headers': {'content-type': 'multipart/related; boundary=d41d8cd98f00b204e9800998ecf8427e; type=application/alto-endpointcost+json; charset=utf-8'},
        'text': TEST_ECS_PV,
        'status_code': 200
    }
]


def mocked_requests_get(uri, *args, **kwars):
    class MockResponse:
        def __init__(self, headers=dict(), json_data=None, text_data=None, status_code=200):
            self.headers = headers
            self.json_data = json_data
            self.status_code = status_code
            self.text = text_data or json.dumps(self.json())
            self.content = self.text.encode()

        def raise_for_status(self):
            pass

        def json(self):
            return self.json_data

    for mock_item in MOCK:
        if uri == mock_item.get('uri'):
            json_data = mock_item.get('json')
            if 'json_alt' in mock_item:
                json_alt = mock_item.get('json_alt')
                if 'index' not in mock_item:
                    mock_item['index'] = 0
                json_idx = mock_item['index'] % len(json_alt)
                json_data = json_alt[json_idx]
                mock_item['index'] = json_idx + 1
            return MockResponse(headers=mock_item.get('headers'),
                                json_data=json_data,
                                text_data=mock_item.get('text'),
                                status_code=mock_item.get('status_code'))


def mocked_requests_request(method, uri, *args, **kwargs):
    return mocked_requests_get(uri)

