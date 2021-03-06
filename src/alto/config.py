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


    def get_server_auth(self):
        self.parser.read(self.location)
        auth_type = self.parser.get('client', 'auth_type')
        auth = None
        if auth_type == 'userpass':
            auth = (
                self.parser.get('client', 'username'),
                self.parser.get('client', 'password')
                )
        return auth


    def get_default_ird_uri(self):
        self.parser.read(self.location)
        uri = self.parser.get('client', 'default_ird')
        return uri


    def get_default_networkmap_uri(self):
        self.parser.read(self.location)
        uri = self.parser.get('client', 'default_networkmap')
        return uri


    def get_default_costmap_uri(self):
        self.parser.read(self.location)
        uri = self.parser.get('client', 'default_costmap')
        return uri

    def get_static_resource_uri(self, resource_id):
        self.parser.read(self.location)
        static_ird = json.loads(self.parser.get('client', 'static_ird').strip())
        return static_ird.get(resource_id)

