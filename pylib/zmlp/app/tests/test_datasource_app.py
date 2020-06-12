import logging
import unittest
from unittest.mock import patch

from zmlp import ZmlpClient, ZmlpApp, DataSource

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ZmlpDataSourceAppTests(unittest.TestCase):

    def setUp(self):
        # This is not a valid key
        self.key_dict = {
            'projectId': 'A5BAFAAA-42FD-45BE-9FA2-92670AB4DA80',
            'keyId': 'A5BAFAAA-42FD-45BE-9FA2-92670AB4DA80',
            'sharedKey': 'test123test135'
        }
        self.app = ZmlpApp(self.key_dict)

    @patch.object(ZmlpClient, 'post')
    def test_create_datasource(self, post_patch):
        value = {
            'id': 'A5BAFAAA-42FD-45BE-9FA2-92670AB4DA80',
            'name': 'test',
            'uri': 'gs://test/test',
            'file_types': ['jpg'],
            'modules': ['google-ocr']
        }
        post_patch.return_value = value
        ds = self.app.datasource.create_datasource('test', 'gs://test/test')
        assert value['id'] == ds.id
        assert value['name'] == ds.name
        assert value['uri'] == ds.uri
        assert ds.file_types == ['jpg']
        assert ds.modules == ['google-ocr']

    @patch.object(ZmlpClient, 'post')
    def test_get_datasource(self, post_patch):
        value = {
            'id': 'A5BAFAAA-42FD-45BE-9FA2-92670AB4DA80',
            'name': 'test',
            'uri': 'gs://test/test'
        }
        post_patch.return_value = value
        ds = self.app.datasource.get_datasource('test')
        assert value['id'] == ds.id
        assert value['name'] == ds.name
        assert value['uri'] == ds.uri

    @patch.object(ZmlpClient, 'post')
    def test_import_files(self, post_patch):
        value = {
            'id': 'A5BAFAAA-42FD-45BE-9FA2-92670AB4DA80',
            'name': 'Import DataSource'
        }
        post_patch.return_value = value
        job = self.app.datasource.import_files(DataSource({'id': '123'}))
        assert value['id'] == job.id
        assert value['name'] == job.name
