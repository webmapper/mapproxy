# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement
import os
import shutil
import stat
import tempfile

from mapproxy.client.http import HTTPClientError
from mapproxy.client.cgi import CGIClient, split_http_response
from mapproxy.source import SourceError

from nose.tools import eq_

class TestSplitHTTPResponse(object):
    def test_n(self):
        eq_(split_http_response('header1: foo\nheader2: bar\n\ncontent\n\ncontent'),
            ({'Header1':'foo', 'Header2': 'bar'}, 'content\n\ncontent'))
    def test_rn(self):
        eq_(split_http_response('header1\r\nheader2\r\n\r\ncontent\r\n\r\ncontent'),
            ({'Header1': None, 'Header2': None}, 'content\r\n\r\ncontent'))
    def test_mixed(self):
        eq_(split_http_response('header1: bar:foo\r\nheader2\n\r\ncontent\r\n\r\ncontent'),
            ({'Header1': 'bar:foo', 'Header2': None}, 'content\r\n\r\ncontent'))
        eq_(split_http_response('header1\r\nheader2\n\ncontent\r\n\r\ncontent'),
            ({'Header1': None, 'Header2': None}, 'content\r\n\r\ncontent'))
        eq_(split_http_response('header1\nheader2\r\n\r\ncontent\r\n\r\ncontent'),
            ({'Header1': None, 'Header2': None}, 'content\r\n\r\ncontent'))
    def test_no_header(self):
        eq_(split_http_response('content\r\ncontent'),
            ({}, 'content\r\ncontent'))


TEST_CGI_SCRIPT = r"""#! /usr/bin/env python
import sys
import os
w = sys.stdout.write
w("Content-type: text/plain\r\n")
w("\r\n")
w(os.environ['QUERY_STRING'])
"""

TEST_CGI_SCRIPT_FAIL = TEST_CGI_SCRIPT + '\nexit(1)'

TEST_CGI_SCRIPT_CWD = TEST_CGI_SCRIPT + r"""
if not os.path.exists('testfile'):
    exit(2)
"""

class TestCGIClient(object):
    def setup(self):
        self.script_dir = tempfile.mkdtemp()
    
    def teardown(self):
        shutil.rmtree(self.script_dir)
    
    def create_script(self, script=TEST_CGI_SCRIPT, executable=True):
        script_file = os.path.join(self.script_dir, 'cgi.py')
        with open(script_file, 'w') as f:
            f.write(script)
        if executable:
            os.chmod(script_file, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
        return script_file
    
    def test_missing_script(self):
        client = CGIClient('/tmp/doesnotexist')
        try:
            client.open('http://example.org/service?hello=bar')
        except SourceError:
            pass
        else:
            assert False, 'expected SourceError'
    
    def test_script_not_executable(self):
        script = self.create_script(executable=False)
        client = CGIClient(script)
        try:
            client.open('http://example.org/service?hello=bar')
        except SourceError:
            pass
        else:
            assert False, 'expected SourceError'
    
    def test_call(self):
        script = self.create_script()
        client = CGIClient(script)
        resp = client.open('http://example.org/service?hello=bar')
        eq_(resp.headers['Content-type'], 'text/plain')
        eq_(resp.read(), 'hello=bar')
    
    def test_failed_call(self):
        script = self.create_script(TEST_CGI_SCRIPT_FAIL)
        client = CGIClient(script)
        try:
            client.open('http://example.org/service?hello=bar')
        except HTTPClientError:
            pass
        else:
            assert False, 'expected HTTPClientError'
    
    def test_working_directory(self):
        tmp_work_dir = os.path.join(self.script_dir, 'tmp')
        os.mkdir(tmp_work_dir)
        tmp_file = os.path.join(tmp_work_dir, 'testfile')
        open(tmp_file, 'w')
        
        # start script in default directory
        script = self.create_script(TEST_CGI_SCRIPT_CWD)
        client = CGIClient(script)
        try:
            client.open('http://example.org/service?hello=bar')
        except HTTPClientError:
            pass
        else:
            assert False, 'expected HTTPClientError'

        # start in tmp_work_dir
        client = CGIClient(script, working_directory=tmp_work_dir)
        client.open('http://example.org/service?hello=bar')
        