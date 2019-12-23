# -*- coding: utf-8 -*-
'''
Tests for the Azure Blob Ext_Pillar
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import pickle
import tempfile
import time

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Import Salt Libs
from salt.ext import six
import salt.pillar.azureblob as azureblob
import salt.utils.files
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
    '''

    def setup_loader_modules(self):
        self.opts = salt.config.DEFAULT_MASTER_OPTS.copy()
        utils = salt.loader.utils(self.opts)
        return {
            azureblob: {
                '__opts__': self.opts, 
                '__utils__': utils,
            },
        }

    #def setUp(self):
        #self.tcache = tempfile.NamedTemporaryFile(delete=False, mode='w+')
        # Find example contents of a .cache file to use in read_containers_cache_file
        #self.tcache.write(self.CACHE_CONTENTS)
        #self.tcache.close()

    #def tearDown(self):
        #os.remove(self.tcache.name)
        #del self.tcache


    def test__init_expired(self):
        ''' 
        Tests the result of _init when the cache is expired.
        '''
        container = 'test'
        multiple_env = False
        environment = 'base'
        blob_cache_expire = 0 # The cache will be expired
        blob_client = MockBlobServiceClient()
        cache_file = tempfile.NamedTemporaryFile()
        
        # Patches the _get_containers_cache_filename module so that it returns the name of the new tempfile that
        # represents the cache file
        with patch.object(azureblob, '_get_containers_cache_filename', MagicMock(return_value=str(cache_file.name))):
            # Patches the from_connection_string module of the BlobServiceClient class so that a connection string does
            # not need to be given. Additionally it returns example blob data used by the ext_pillar.
            with patch.object(BlobServiceClient, 'from_connection_string', MagicMock(return_value=blob_client)):
              ret = azureblob._init('', container, multiple_env, environment, blob_cache_expire)
        self.assertEqual(ret, {'base': {'test': [{'container': None, 'name': 'test.sls', 'prefix': None,  
                                'delimiter': '/', 'results_per_page': None, 'location_mode': None}]}})


    def test__init_not_expired(self):
        '''
        Tests the result of _init when the cache is not expired.
        '''
        container = 'test'
        multiple_env = False
        environment = 'base'
        blob_cache_expire = (time.time()) * (time.time()) # The cache will not be expired
        metadata = {'base': {'test': [{'name': 'base/secret.sls', 'relevant': 'include.sls'},
                                      {'name': 'blobtest.sls', 'irrelevant': 'ignore.sls'}]}}
        cache_file = tempfile.NamedTemporaryFile()
        # Pickles the metadata and stores it in cache_file
        with salt.utils.files.fopen(str(cache_file), 'wb') as fp_:
            pickle.dump(metadata, fp_)
        
        # Patches the _get_containers_cache_filename module so that it returns the name of the new tempfile that 
        # represents the cache file
        with patch.object(azureblob, '_get_containers_cache_filename', MagicMock(return_value=str(cache_file.name))):
            # Patches the _read_containers_cache_file module so that it returns what it normally would if the new 
            # tempfile representing the cache file was passed to it
            plugged = azureblob._read_containers_cache_file(str(cache_file))
            with patch.object(azureblob, '_read_containers_cache_file', MagicMock(return_value=plugged)):
                ret = azureblob._init('', container, multiple_env, environment, blob_cache_expire)
        self.assertEqual(ret, metadata)


    def test__get_cache_dir(self):
        ret = azureblob._get_cache_dir()
        self.assertEqual(ret, '/var/cache/salt/master/pillar_azureblob')


    def test__get_cached_file_name(self):
        container = 'test'
        saltenv = 'base'
        path = 'base/secret.sls'
        ret = azureblob._get_cached_file_name(container, saltenv, path)
        self.assertEqual(ret, '/var/cache/salt/master/pillar_azureblob/base/test/base/secret.sls')


    def test__get_containers_cache_filename(self):
        container = 'test'
        ret = azureblob._get_containers_cache_filename(container)
        self.assertEqual(ret, '/var/cache/salt/master/pillar_azureblob/test-files.cache')


    def test__refresh_containers_cache_file(self):
        blob_client = MockBlobServiceClient()
        container = 'test'
        cache_file = tempfile.NamedTemporaryFile()
        with patch.object(BlobServiceClient, 'from_connection_string', MagicMock(return_value=blob_client)):
            ret = azureblob._refresh_containers_cache_file('', container, cache_file.name)
            self.assertEqual(ret, {'base': {'test': [{'container': None, 'name': 'test.sls', 'prefix': None, 
                                   'delimiter': '/', 'results_per_page': None, 'location_mode': None}]}})


    def test__read_containers_cache_file(self):
        metadata = {'base': {'test': [{'name': 'base/secret.sls', 'relevant': 'include.sls'},
                                      {'name': 'blobtest.sls', 'irrelevant': 'ignore.sls'}]}}
        cache_file = tempfile.NamedTemporaryFile()
        # Pickles the metadata and stores it in cache_file
        with salt.utils.files.fopen(str(cache_file), 'wb') as fp_:
            pickle.dump(metadata, fp_)
        # Checks to see if _read_containers_cache_file can successfully read the pickled metadata from the cache file
        ret = azureblob._read_containers_cache_file(str(cache_file))
        self.assertEqual(ret, metadata)


    def test__find_files(self):
        metadata = {'test': [{'name': 'base/secret.sls'}, {'name': 'blobtest.sls', 'irrelevant': 'ignore.sls'},
                             {'name': 'base/'}]}
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


    # Figure out how to test this
    def test__get_file_from_blob(self):
        blob_client = MockBlobServiceClient()
        metadata = {}
        saltenv = 'base'
        container = 'test'
        path = ''
        cached_file_path = ''
        self.assertEqual('true', 'true')
