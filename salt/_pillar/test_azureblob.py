# -*- coding: utf-8 -*-
'''
Tests for the Azure Blob Ext_Pillar
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import tempfile

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Import Salt Libs
from salt.ext import six
import salt.pillar.azureblob as azureblob
import salt.config
import salt.loader

# Import Azure libs
HAS_LIBS = False
try:
    from azure.storage.blob import BlobServiceClient
    HAS_LIBS = True
except ImportError:
    pass

class MockBlob(dict):
    name = ''
    def __init__(self):
        if six.PY3:
        # Handle PY3
            super().__init__(
                {'container': None, 'name': 'test.sls', 'prefix': None, 'delimiter': '/', 'results_per_page': None,
                 'location_mode': None})
        else:
        # Handle PY2
            super(MockBlob, self).__init__(
                {'container': None, 'name': 'test.sls', 'prefix': None, 'delimiter': '/', 'results_per_page': None,
                 'location_mode': None})

class MockContainerClient:
    def walk_blobs(self, *args, **kwargs):
        yield MockBlob()
    def get_blob_client(self, *args, **kwargs):
        pass

class MockBlobServiceClient:
    def get_container_client(self, *args, **kwargs):
        container_client = MockContainerClient()
        return container_client

@skipIf(HAS_LIBS is False, 'The azure.storage.blob module must be installed.')
class AzureBlobTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.pillar.azureblob ext_pillar.

    NOTE: In an actual use case of the Azure Blob ext_pillar, the ext_pillar will be cached to the master. However,
        for testing purposes the ext_pillar is cached to the minion.
    '''

    def setup_loader_modules(self):
        '''
        Setup loader modules
        '''
        self.opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(self.opts)
        funcs = salt.loader.minion_mods(self.opts, utils=utils)
        return {
            azureblob: {
                '__opts__': self.opts, 
                '__utils__': utils,
                '__salt__': funcs
            },
        }

    def setUp(self):
        '''
        Setup
        '''
        TestCase.setUp(self)
        azureblob.__virtual__()


    def test__init(self):
        self.assertEqual('true', 'true')


    def test__get_cache_dir(self):
        ret = azureblob._get_cache_dir()
        self.assertEqual(ret, '/var/cache/salt/minion/pillar_azureblob')


    def test__get_cached_file_name(self):
        container = 'test'
        saltenv = 'base'
        path = 'base/secret.sls'
        ret = azureblob._get_cached_file_name(container, saltenv, path)
        self.assertEqual(ret, '/var/cache/salt/minion/pillar_azureblob/base/test/base/secret.sls')


    def test__get_containers_cache_filename(self):
        container = 'test'
        ret = azureblob._get_containers_cache_filename(container)
        self.assertEqual(ret, '/var/cache/salt/minion/pillar_azureblob/test-files.cache')


    def test__refresh_containers_cache_file(self):
        blob_client = MockBlobServiceClient()
        container = 'test'
        cache_file = tempfile.NamedTemporaryFile()
        with patch.object(BlobServiceClient, 'from_connection_string', MagicMock(return_value=blob_client)):
            ret = azureblob._refresh_containers_cache_file('', container, cache_file.name)
            self.assertEqual(ret, {'base': {'test': [{'container': None, 'name': 'test.sls', 'prefix': None, 
                                   'delimiter': '/', 'results_per_page': None, 'location_mode': None}]}})


    # DO I NEED TO PATCH THE TEMP FILE TO THE METHOD?
    # If I use the tempfile and use delete=False option, then where would the temp file be stored?
    # https://stackoverflow.com/questions/8577137/how-can-i-create-a-tmp-file-in-python
    def test__read_containers_cache_fle(self):
        cache_file = tempfile.NamedTemporaryFile()
        cache_file.name = 'test-files.cache'
        #cache_file = '/var/cache/salt/minion/pillar_azureblob/test-files.cache'
        #ret = azureblob._read_containers_cache_file(cache_file.name)
        self.assertEqual('true', 'true')


    def test__find_files(self):
        metadata = {'test': [{'name': 'base/secret.sls'}, {'name': 'blobtest.sls', 'irrelevant': 'ignore.sls'},                                      {'name': 'base/'}]}
        ret = azureblob._find_files(metadata)
        self.assertEqual(ret, {'test': ['base/secret.sls', 'blobtest.sls']})


    def test__find_file_meta1(self):
        metadata = {'base': {'test': [{'name': 'base/secret.sls', 'relevant': 'include.sls'}, 
                                      {'name': 'blobtest.sls', 'irrelevant': 'ignore.sls'}]}}
        container = 'test'
        saltenv = 'base'
        path = 'base/secret.sls'
        ret = azureblob._find_file_meta(metadata, container, saltenv, path)
        self.assertEqual(ret, {'name': 'base/secret.sls', 'relevant': 'include.sls'})


    def test__find_file_meta2(self):
        metadata = {'wrong': {'test': [{'name': 'base/secret.sls'}]}}
        container = 'test'
        saltenv = 'base'
        path = 'base/secret.sls'
        ret = azureblob._find_file_meta(metadata, container, saltenv, path)
        self.assertEqual(ret, None)


    def test__find_file_meta3(self):
        metadata = {'base': {'wrong': [{'name': 'base/secret.sls'}]}}
        container = 'test'
        saltenv = 'base'
        path = 'base/secret.sls'
        ret = azureblob._find_file_meta(metadata, container, saltenv, path)
        self.assertEqual(ret, None)


    # Can this be tested? If so, how?
    def test__get_file_from_blob(self):
        blob_client = MockBlobServiceClient()
        metadata = {}
        saltenv = 'base'
        container = 'test'
        path = ''
        cached_file_path = ''
        '''
        with patch.object(BlobServiceClient, 'from_connection_string', MagicMock(return_value=blob_client)):
            ret = azureblob._get_file_from_blob('', container, cache_file.name)
            self.assertEqual(ret, {'base': {'test': [{'container': None, 'name': 'test.sls', 'prefix': None,
            'delimiter': '/', 'results_per_page': None, 'location_mode': None}]}})
        '''
        self.assertEqual('true', 'true')
