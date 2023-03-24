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
# - Jensen Zhang <jingxuan.n.zhang@gmail.com>

import os
import pytest
from unittest import mock

from alto.config import Config, get_ordered_config_dirs

__author__ = "OpenALTO"
__copyright__ = "OpenALTO"
__license__ = "MIT"


def test_alto_config(*args):
    if 'ALTO_CONFIG' in os.environ:
        del os.environ['ALTO_CONFIG']
    if 'HOME' in os.environ:
        del os.environ['HOME']
    if 'XDG_CONFIG_HOME' in os.environ:
        del os.environ['XDG_CONFIG_HOME']
    if 'ALTO_HOME' in os.environ:
        del os.environ['ALTO_HOME']
    
    config = Config()
    assert config.location is None or os.path.dirname(config.location) == os.path.normpath('/opt/alto/etc')
    
    if 'HOME' not in os.environ:
        os.environ.setdefault('HOME', os.path.dirname(__file__))
    if 'XDG_CONFIG_HOME' not in os.environ:
        os.environ.setdefault('XDG_CONFIG_HOME', os.path.dirname(__file__))
    if 'ALTO_HOME' not in os.environ:
        os.environ.setdefault('ALTO_HOME', os.path.dirname(__file__))

    config = Config()
    config_dirs = get_ordered_config_dirs()

    assert config.location is None or os.path.dirname(config.location) in config_dirs

    os.environ.setdefault('ALTO_CONFIG', os.path.join(os.path.dirname(__file__), '../etc/alto.conf.test'))
    config = Config()

    db_config = config.get_db_config()
    assert 'default' in db_config

    configured_resources = config.get_configured_resources()
    assert 'directory' in configured_resources
    assert configured_resources['directory']['type'] == 'ird'

    default_namespace = config.get_default_namespace()
    assert default_namespace == 'default'

    base_uri = config.get_server_base_uri()
    assert base_uri == 'https://alto.example.com/'

    cost_types = config.get_server_cost_types()
    assert 'num-rc' in cost_types
    assert cost_types['num-rc']['cost-mode'] == 'numerical'
    assert cost_types['num-rc']['cost-metric'] == 'routingcost'

    zookeeper_host = config.get_vcs_zookeeper_host()
    assert zookeeper_host == 'zoo1'

    zookeeper_timeout = config.get_vcs_zookeeper_timeout()
    assert zookeeper_timeout == 15

    polling_interval = config.get_vcs_polling_interval()
    assert polling_interval == 1

    snapshot_freq = config.get_vcs_snapshot_freq()
    assert snapshot_freq == 3

    init_version = config.get_vcs_init_version()
    assert init_version == 100
