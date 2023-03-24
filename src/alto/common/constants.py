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

from enum import Enum


ALTO_CONTENT_TYPE_IRD = 'application/alto-directory+json'
ALTO_CONTENT_TYPE_NM = 'application/alto-networkmap+json'
ALTO_CONTENT_TYPE_CM = 'application/alto-costmap+json'
ALTO_CONTENT_TYPE_ECS = 'application/alto-endpointcost+json'
ALTO_CONTENT_TYPE_EPS = 'application/alto-endpointprop+json'
ALTO_CONTENT_TYPE_PROPMAP = 'application/alto-propmap+json'
ALTO_CONTENT_TYPE_CM_PV = 'multipart/related;type={}'.format(ALTO_CONTENT_TYPE_CM)
ALTO_CONTENT_TYPE_ECS_PV = 'multipart/related;type={}'.format(ALTO_CONTENT_TYPE_ECS)

ALTO_PARAMETER_TYPE_FNM = 'application/alto-networkmapfilter+json'
ALTO_PARAMETER_TYPE_FCM = 'application/alto-costmapfilter+json'
ALTO_PARAMETER_TYPE_ECS = 'application/alto-endpointcostparams+json'
ALTO_PARAMETER_TYPE_EPS = 'application/alto-endpointpropparams+json'
ALTO_PARAMETER_TYPE_PROPMAP = 'application/alto-propmapparams+json'

ALTO_CONTENT_TYPES = {
    "ird": ALTO_CONTENT_TYPE_IRD,
    "network-map": ALTO_CONTENT_TYPE_NM,
    "cost-map": ALTO_CONTENT_TYPE_CM,
    "endpoint-cost": ALTO_CONTENT_TYPE_ECS,
    "endpoint-prop": ALTO_CONTENT_TYPE_EPS,
    "path-vector": ALTO_CONTENT_TYPE_ECS_PV,
    "cost-map-pv": ALTO_CONTENT_TYPE_CM_PV,
    "entity-prop": ALTO_CONTENT_TYPE_PROPMAP
}

ALTO_PARAMETER_TYPES = {
    "filtered-network-map": ALTO_PARAMETER_TYPE_FNM,
    "filtered-cost-map": ALTO_PARAMETER_TYPE_FCM,
    "endpoint-cost": ALTO_PARAMETER_TYPE_ECS,
    "path-vector": ALTO_PARAMETER_TYPE_ECS,
    "entity-prop": ALTO_PARAMETER_TYPE_PROPMAP
}


class Diff(Enum):
    JSON_PATCH = 1
    JSON_MERGE_PATCH = 2
