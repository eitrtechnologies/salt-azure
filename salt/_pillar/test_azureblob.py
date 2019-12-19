# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import tempfile

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

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

__opts__ = salt.config.minion_config('/etc/salt/minion')

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

@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not azureblob.HAS_LIBS, 'Azure modules not available')
class AzureblobTestCase(TestCase):
    # Params: connection_string, container, cache_file, multiple_env=False, environment='base'
    def test__refresh_containers_cache_file(self):
        blob_client = MockBlobServiceClient()
        container = 'test'
        cache_file = tempfile.NamedTemporaryFile()
        with patch.object(BlobServiceClient, 'from_connection_string', MagicMock(return_value=blob_client)):
            ret = azureblob._refresh_containers_cache_file('', container, cache_file.name)
            self.assertEqual(ret, {'base': {'test': [{'container': None, 'name': 'test.sls', 'prefix': None, 
                                   'delimiter': '/', 'results_per_page': None, 'location_mode': None}]}})
    
    # Params: connection_string, metadata, saltenv, container, path, cached_file_path)
    def test__get_file_from_blob(self):
        blob_client = MockBlobServiceClient()
        '''
        # Metadata
        # Saltenv 
        # Container
        # Path
        # Cached_file_path
        with patch.object(BlobServiceClient, 'from_connection_string', MagicMock(return_value=blob_client)):
            ret = azureblob._get_file_from_blob('', container, cache_file.name)
            self.assertEqual(ret, {'base': {'test': [{'container': None, 'name': 'test.sls', 'prefix': None,
                                   'delimiter': '/', 'results_per_page': None, 'location_mode': None}]}})

        '''
        pass


    def test__get_cache_dir(self):
        ret = azureblob._get_cache_dir()
        self.assertEqual(ret, '/var/cache/salt/master/pillar_azureblob')


    def test__get_cached_file_name(self):
        ret = azureblob._get_cached_file_name('test', 'base', 'base/secret.sls')
        self.assertEqual(ret, '/var/cache/salt/master/pillar_azureblob/base/test/base/secret.sls')


    def test__get_containers_cache_filename(self):
        ret = azureblob._get_containers_cache_filename('test')
        self.assertEqual(ret, '/var/cache/salt/master/pillar_azureblob/test-files.cache')


    def test__read_containers_cache_fle(self):
        #ret = azureblob._read_containers_cache_file()
        #self.assertEqual(ret, 'RIGHT THIS VALUE STILL')
        pass

    def test__find_files(self):
        metadata = {'test': [{'name': 'base/secret.sls'}, {'name': 'blobtest.sls'}]}
        ret = azureblob._find_files(metadata)
        self.assertEqual(ret, {'test': ['base/secret.sls', 'blobtest.sls']})
