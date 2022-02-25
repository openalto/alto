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


class Meta(object):

    def __init__(self, data: dict) -> None:
        self.data = data


class IRDMeta(Meta):

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._cost_types = data['cost-types']
        self._default_alto_network_map = data['default-alto-network-map']

    @property
    def cost_types(self):
        return self._cost_types

    @property
    def default_alto_network_map(self):
        return self._default_alto_network_map


class IRDResourceEntry(object):

    def __init__(self, data: dict) -> None:
        self.data = data
        self._uri = data['uri']

    @property
    def uri(self):
        return self._uri


class InformationResourceDirectory(object):

    def __init__(self, data: dict) -> None:
        self._meta = Meta(data['meta'])
        self._resources = {rid: IRDResourceEntry(res) for rid, res in data['resources'].items()}

    @property
    def meta(self):
        return self._meta

    @property
    def resources(self):
        return self._resources
