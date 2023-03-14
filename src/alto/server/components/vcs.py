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

import hashlib
import json
import time
from threading import Event, Thread
from urllib.parse import urljoin

import json_merge_patch
import requests
from kazoo.client import KazooClient

from alto.config import Config
from alto.common.constants import ALTO_PARAMETER_TYPES


class VersionControl:
    """
    Version control system for ALTO information resources.
    """

    def __init__(self) -> None:
        self.config = Config()
        self.zk_host = self.config.get_vcs_zookeeper_host()
        self.zk_timeout = self.config.get_vcs_zookeeper_timeout()
        self.zk = KazooClient(hosts=self.zk_host)
        self.zk.start(timeout=self.zk_timeout)
        self.zk.ensure_path('/alto')
        self.subscribers = dict()

    
    def __del__(self):
        self.stop()

    
    def stop(self):
        """
        Stop the version control system.
        """
        for listener in self.subscribers.values():
            listener.stop()
            listener.join()
        self.subscribers.clear()
        self.zk.stop()


    def subscribe(self, resource_id, request_body=None):
        """
        Subscribe an ALTO information resource to track future updates.

        Parameters
        ----------
        resource_id : str
            Resource ID of the subscribed information resource
        request_body : dict or None
            Optional request body to request the information resource. Set to
            None if the information resource is in GET mode. (default None)

        Returns
        -------
        digest : str
            The digest token of the subscribed update listenser. If None, the
            subscription failed.
        """
        # Check if resource exists
        resources = self.config.get_configured_resources()
        resource = resources.get(resource_id)
        if resource is None:
            return None
        
        # Safely create dir for the resource
        self.zk.ensure_path('/alto/{}'.format(resource_id))
        request_body_enc = b''
        if request_body:
            request_body_enc = request_body.encode()
        digest = hashlib.md5(request_body_enc).hexdigest()

        path = '/alto/{}/{}'.format(resource_id, digest)
        resource_listener = ResourceListener(self, path, resource_id, resource,
                                             request_body=request_body)
        self.subscribers[(resource_id, digest)] = resource_listener

        success = resource_listener.initilize()
        if not success:
            return None
        resource_listener.start()

        return digest


    def unsubscribe(self, resource_id, digest):
        """
        Unsubscribe an update listener of an ALTO information resource.

        Parameters
        ----------
        resource_id : str
            Resource ID of the subscribed information resource
        digest : str
            The digest token of a subscribed update listenser.
        """
        listener = self.subscribers[(resource_id, digest)]
        listener.stop()
        listener.join()
        del self.subscribers[(resource_id, digest)]
        self.zk.delete('/alto/{}/{}'.format(resource_id, digest), recursive=True)


    def get_tips_view(self, resource_id, digest):
        """
        Get available update graph.
        """
        ug = dict()
        ug_path = '/alto/{}/{}/ug'.format(resource_id, digest)
        start_seqs = sorted(self.zk.get_children(ug_path))
        for start_seq in start_seqs:
            ug[start_seq] = sorted(self.zk.get_children('{}/{}'.format(ug_path, start_seq)))
        return ug


    def show_tips_view(self, resource_id, digest):
        ug = self.get_tips_view(resource_id, digest)
        ug_path = '/alto/{}/{}/ug'.format(resource_id, digest)
        print(ug_path)
        for start_seq in sorted(ug.keys()):
            print(' ' * len(ug_path) + '%4d' % int(start_seq))
            for end_seq in ug[start_seq]:
                print(' ' * (len(ug_path)+5) + '%4d' % int(end_seq))


    def get_tips_data(self, resource_id, digest, start_seq, end_seq):
        """
        Get update data from start_seq to end_seq in an update graph.
        """
        try:
            data, stat = self.zk.get('/alto/{}/{}/ug/{}/{}'.format(resource_id, digest, start_seq, end_seq))
        except Exception:
            return None
        return data


def get_resource(ctx: VersionControl, resource_id, resource, request_body=None):
    """
    Get ALTO response of an information resource.

    Parameters
    ----------
    ctx : VersionControl
        Context of the version control system
    resource_id : str
        Resource ID
    resource : dict
        Metadata of the information resource
    request_body : dict | None
        Request body to query the information resource

    Returns
    -------
    response : bytes or None
        The content of the query response. If None, the request failed.
    """
    base_uri = ctx.config.get_server_base_uri()
    resource_path = resource.get('path')
    url = urljoin(base_uri, '{}/{}'.format(resource_path, resource_id))
    resource_type = resource.get('type')
    kwargs = dict()

    auth = ctx.config.get_server_auth()
    kwargs['auth'] = auth

    if resource_type == 'ird':
        method = 'GET'
    elif resource_type == 'network-map':
        method = 'GET'
    elif resource_type == 'cost-map':
        method = 'GET'
    elif resource_type == 'filtered-network-map':
        method = 'POST'
    elif resource_type == 'filtered-cost-map':
        method = 'POST'
    elif resource_type == 'endpoint-cost':
        method = 'POST'
    elif resource_type == 'endpoint-prop':
        method = 'POST'
    elif resource_type == 'entity-prop':
        method = 'POST'
    elif resource_type == 'path-vector':
        method = 'POST'

    if method == 'POST':
        kwargs['json'] = request_body
        kwargs['headers'] = {
            'content-type': ALTO_PARAMETER_TYPES.get(resource_type)
        }
    res = requests.request(method, url, **kwargs)
    if res.status_code == 200:
        return res.content
    else:
        return None


class ResourceListener(Thread):

    def __init__(self, ctx: VersionControl, path, resource_id, resource,
                 request_body=None, polling_interval=5, snapshot_freq=3) -> None:
        super().__init__()
        self.ctx = ctx
        self.path = path
        self.resource_id = resource_id
        self.resource = resource
        self.request_body = request_body
        self.stop_event = Event()
        self.polling_interval = polling_interval
        self.snapshot_freq = snapshot_freq


    def initilize(self):
        raw_last_res = get_resource(self.ctx, self.resource_id, self.resource, self.request_body)
        if raw_last_res is None:
            return False
        self.ctx.zk.create(self.path, raw_last_res)
        self.ctx.zk.ensure_path('{}/ug/0'.format(self.path))
        self.ctx.zk.create('{}/ug/0/0'.format(self.path), raw_last_res)
        self.last_res = json.loads(raw_last_res)
        self.last_ver = 0
        return True

    
    def run(self):
        while not self.stop_event.is_set():
            raw_res = get_resource(self.ctx, self.resource_id, self.resource, self.request_body)
            if raw_res is None:
                continue
            res = json.loads(raw_res)
            patch = json_merge_patch.create_patch(self.last_res, res)
            if patch:
                self.last_res = res
                stat = self.ctx.zk.set(self.path, raw_res)
                self.ctx.zk.ensure_path('{}/ug/{}'.format(self.path, self.last_ver))
                self.ctx.zk.create('{}/ug/{}/{}'.format(self.path, self.last_ver, stat.version),
                                   json.dumps(patch).encode())
                self.last_ver = stat.version
                if self.last_ver % self.snapshot_freq == 0:
                    self.ctx.zk.create('{}/ug/0/{}'.format(self.path, self.last_ver), raw_res)

            time.sleep(self.polling_interval)


    def stop(self):
        self.stop_event.set()
