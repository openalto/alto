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

import logging

from alto.config import Config

_logger = logging.getLogger(__name__)


class Client:
    """
    Base ALTO client class.
    """

    def __init__(self, config=True, default_ird=None, auth_type=None,
                 username=None, password=None, **kw_args) -> None:
        """
        Constructor for the ALTO client class.
        """
        _logger.debug("Creating ALTO client instance.")
        if default_ird:
            self.default_ird = default_ird
        if auth_type:
            self.auth_type = auth_type
        if username:
            self.username = username
        if password:
            self.password = password
        if config:
            self.config = Config()

    def get_ird(self):
        """
        Return ALTO Information Resource Directory (IRD).
        """
        # TODO: query the default ird configured for this client.
        raise NotImplementedError

    def get_routing_cost(self, src_ip: str, dst_ip: str, cost_map=None, cost_type=None):
        """
        Return ALTO cost between `src_ip` and `dst_ip`.
        """
        # TODO: query cost map to get routing cost between source and destination.
        # Tips: query dependent network map to get PIDs.
        raise NotImplementedError
