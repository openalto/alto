# -*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2023 OpenALTO Community
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
# - Kai Gao <emiapwil@gmail.com>

import requests

class WrappedPerfSonarServiceV1:
    """
    Backend algorithm for ECS based on PerfSonar wrapper

    This algorithm is basically a proxy
    """

    def __init__(self, namespace, visualnet_api=None, **kwargs):
        self.namespace = namespace
        self.uri = visualnet_api

    def lookup(self, srcs, dsts, cost_type):
        headers = {
            'content-type': 'application/json'
        }
        req = {
            'cost-type': {
                'cost-metric': cost_type['cost-metric'],
                'anchor-alg': 'same-site',
                'interval': { 'last': '2d' }
            },
            'endpoints': [
                {
                    'srcs': srcs,
                    'dsts': dsts
                }
            ]
        }
        resp = requests.post(self.uri, json=req, headers=headers)
        data = resp.json()
        data['meta']['cost-type']['cost-mode'] = cost_type['cost-mode']
        return data
