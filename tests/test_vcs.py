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
import json
import time
from unittest import TestCase, mock

import pytest
import json_merge_patch
import jsonpatch

from alto.config import Config
from alto.common.constants import Diff
from alto.mock import mocked_requests_request, mockKazoo
from alto.utils import setup_debug_db

__author__ = "OpenALTO"
__copyright__ = "OpenALTO"
__license__ = "MIT"


class ALTOVersionControlTest(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault('ALTO_CONFIG', os.path.join(os.path.dirname(__file__), '../etc/alto.conf.test'))
        cls.config = Config()
        setup_debug_db(cls.config)
        mock.patch.dict('sys.modules', {'kazoo.client': mockKazoo}).start()
        mock.patch('requests.request', side_effect=mocked_requests_request).start()
        return super().setUpClass()
    
    def setUp(self) -> None:
        from alto.server.components.vcs import VersionControl
        self.vcs = VersionControl()
        return super().setUp()

    def tearDown(self) -> None:
        self.vcs.stop()
        return super().tearDown()

    def test_vcs(self):
        resource_id = 'dynamic-networkmap'
        digest = self.vcs.subscribe(resource_id, client_id='client1')
        self.assertIn((resource_id, digest), self.vcs.subscribers, 'Listener MUST be added once subscribe()')

        digest3 = self.vcs.subscribe(resource_id, client_id='client3', diff_format=Diff.JSON_PATCH)
        self.assertNotEqual(digest, digest3, 'Different diff patch formats MUST have different digests')

        time.sleep(5)

        # Full Replacement Test
        self.vcs.show_tips_view(resource_id, digest)
        update_graph = self.vcs.get_tips_view(resource_id, digest)
        full_versions = update_graph['0']
        full_ver_0 = full_versions[0]
        full_repl_str_0 = self.vcs.get_tips_data(resource_id, digest, '0', full_ver_0)
        full_repl_0 = json.loads(full_repl_str_0)
        self.assertIn('network-map', full_repl_0, 'Full replacement 0 MUST be a netowrk-map response')

        full_ver_1 = full_versions[1]
        full_repl_str_1 = self.vcs.get_tips_data(resource_id, digest, '0', full_ver_1)
        full_repl_1 = json.loads(full_repl_str_1)
        self.assertIn('network-map', full_repl_1, 'Full replacement 1 MUST be a netowrk-map response')

        # JSON Merge Patch Test
        for patch_ver in range(int(full_ver_0), int(full_ver_1)):
            patch_str = self.vcs.get_tips_data(resource_id, digest, patch_ver, patch_ver+1)
            patch = json.loads(patch_str)
            full_repl_0 = json_merge_patch.merge(full_repl_0, patch)
        self.assertDictEqual(full_repl_0, full_repl_1, 'JSON merge patch is not correct')

        # Get Full Replacement for JSON Patch
        self.vcs.show_tips_view(resource_id, digest3)
        update_graph2 = self.vcs.get_tips_view(resource_id, digest3)
        full_versions2 = update_graph2['0']
        full_ver_2 = full_versions2[0]
        full_repl_str_2 = self.vcs.get_tips_data(resource_id, digest3, '0', full_ver_2)
        full_repl_2 = json.loads(full_repl_str_2)
        full_ver_3 = full_versions2[1]
        full_repl_str_3 = self.vcs.get_tips_data(resource_id, digest3, '0', full_ver_3)
        full_repl_3 = json.loads(full_repl_str_3)

        # JSON Patch Test
        for patch_ver in range(int(full_ver_2), int(full_ver_3)):
            patch_str = self.vcs.get_tips_data(resource_id, digest3, patch_ver, patch_ver+1)
            patch = jsonpatch.JsonPatch.from_string(patch_str)
            full_repl_2 = jsonpatch.apply_patch(full_repl_2, patch)
        self.assertDictEqual(full_repl_2, full_repl_3, 'JSON patch is not correct')

        # Resubscribe Test
        digest2 = self.vcs.subscribe(resource_id, client_id='client2')
        assert digest == digest2
        self.assertEqual(digest, digest2, 'Same subscription MUST return the same digest')

        # Unsubscribe Test
        self.vcs.unsubscribe(resource_id, digest, client_id='client2')
        self.assertIn((resource_id, digest), self.vcs.subscribers, 'Listener SHOULD NOT be removed if there are still active client')

        self.vcs.unsubscribe(resource_id, digest, client_id='client1')
        self.assertNotIn((resource_id, digest), self.vcs.subscribers, 'Listener MUST be removed if no active client')

        # Stop Test
        self.vcs.stop()
        self.assertDictEqual(self.vcs.subscribers, dict(), 'stop() MUST clean up all the active subscription')
