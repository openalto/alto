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

import os
import sys
import json

try:
    # Compatible with Python 2
    import ConfigParser
except ImportError:
    import configparser as ConfigParser


CONFIG_FILE = 'alto.conf'


def get_ordered_config_dirs():
    """
    Return ordered list of directories to search for configuration files:

    - $HOME/.alto/
    - $XDG_CONFIG_HOME/alto/
    - $ALTO_HOME/etc/
    - /opt/alto/etc/
    """
    config_dirs = []
    if 'HOME' in os.environ:
        config_dirs.append(os.path.join(os.environ['HOME'], '.alto'))
    if 'XDG_CONFIG_HOME' in os.environ:
        config_dirs.append(os.path.join(os.environ['XDG_CONFIG_HOME'], 'alto'))
    if 'ALTO_HOME' in os.environ:
        config_dirs.append(os.path.join(os.environ['ALTO_HOME'], 'etc'))
    config_dirs.append('/opt/alto/etc/')
    return config_dirs


class Config:
    """
    Top configuration class.
    """
    def __init__(self) -> None:
        if sys.version_info < (3, 2):
            self.parser = ConfigParser.SafeConfigParser()
        else:
            self.parser = ConfigParser.ConfigParser()
        if 'ALTO_CONFIG' in os.environ:
            self.location = os.environ['ALTO_CONFIG']
        else:
            config_paths = [os.path.join(d, CONFIG_FILE) for d in get_ordered_config_dirs()]
            self.location = next(iter(filter(os.path.exists, config_paths)), None)

    ####################
    # ALTO client config
    ####################
    def get_server_auth(self):
        self.parser.read(self.location)
        auth_type = self.parser.get('client', 'auth_type', fallback=None)
        auth = None
        if auth_type == 'userpass':
            auth = (
                self.parser.get('client', 'username'),
                self.parser.get('client', 'password')
                )
        return auth


    def get_default_ird_uri(self):
        self.parser.read(self.location)
        uri = self.parser.get('client', 'default_ird', fallback=None)
        return uri


    def get_default_networkmap_uri(self):
        self.parser.read(self.location)
        uri = self.parser.get('client', 'default_networkmap', fallback=None)
        return uri


    def get_default_costmap_uri(self):
        self.parser.read(self.location)
        uri = self.parser.get('client', 'default_costmap', fallback=None)
        return uri


    def get_resource_uri(self, resource_id):
        uri = self.get_static_resource_uri(resource_id)
        if not uri:
            # TODO: try to get resource from IRD
            pass
        return uri


    def get_static_resource_uri(self, resource_id):
        self.parser.read(self.location)
        static_ird = json.loads(self.parser.get('client', 'static_ird', fallback='{}').strip())
        return static_ird.get(resource_id)


    def get_resource_spec_by_metric(self, metric):
        self.parser.read(self.location)
        metric_resources = json.loads(self.parser.get('client', 'metrics', fallback='{}').strip())
        return metric_resources.get(metric)


    ####################
    # ALTO server config
    ####################
    def get_db_config(self):
        self.parser.read(self.location)
        db_config = json.loads(self.parser.get('server', 'db_config', fallback='{}').strip())
        return db_config


    def get_configured_resources(self):
        self.parser.read(self.location)
        resources = json.loads(self.parser.get('server', 'resources', fallback='{}').strip())
        return resources


    def get_default_namespace(self):
        self.parser.read(self.location)
        return self.parser.get('server', 'default_namespace', fallback='default')


    def get_server_base_uri(self):
        self.parser.read(self.location)
        return self.parser.get('server', 'base_uri', fallback=None)


    def get_server_cost_types(self):
        self.parser.read(self.location)
        cost_types_json = self.parser.get('server', 'cost_types', fallback=None)
        if cost_types_json:
            return json.loads(cost_types_json.strip())


    def get_vcs_zookeeper_host(self):
        self.parser.read(self.location)
        return self.parser.get('server.vcs', 'zookeeper_host', fallback=None)


    def get_vcs_zookeeper_timeout(self):
        self.parser.read(self.location)
        return int(self.parser.get('server.vcs', 'zookeeper_timeout', fallback=15))
