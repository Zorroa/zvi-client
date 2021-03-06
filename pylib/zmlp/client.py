import base64
import binascii
import datetime
import decimal
import json
import logging
import os
import random
import sys
import time
from io import IOBase
from urllib.parse import urljoin

import jwt
import requests

from .entity.exception import ZmlpException

logger = logging.getLogger(__name__)


class ZmlpClient(object):
    """
    ZmlpClient is used to communicate to a ZMLP API server.
    """

    def __init__(self, apikey, server, **kwargs):
        """
        Create a new ZmlpClient instance.

        Args:
            apikey: An API key in any supported form. (dict, base64 string, or open file handle)
            server: The url of the server to connect to. Defaults to https://api.zmlp.zorroa.com
            project_id: An optional project UUID for API keys with access to multiple projects.
            max_retries: Maximum number of retries to make if the API server
                is down, 0 for unlimited.
        """
        self.apikey = self.__load_apikey(apikey)
        self.server = server
        self.project_id = kwargs.get('project_id')
        self.max_retries = kwargs.get('max_retries', 3)

    def stream(self, url, dst):
        """
        Stream the given URL path to local dst file path.

        Args:
            url (str): The URL to stream
            dst (str): The destination file path
        """
        try:
            with open(dst, 'wb') as handle:
                response = requests.get(self.get_url(url), verify=False,
                                        headers=self.headers(), stream=True)

                if not response.ok:
                    raise ZmlpClientException(
                        "Failed to stream asset: %s, %s" % (url, response))

                for block in response.iter_content(1024):
                    handle.write(block)
            return dst
        except requests.exceptions.ConnectionError as e:
            raise ZmlpConnectionException(e)

    def stream_text(self, url):
        """
        Stream the given URL.

        Args:
            url (str): The URL to stream

        Yields:
            generator (str): A generator of the lines making up the textual
                URL.
        """
        try:
            response = requests.get(self.get_url(url), verify=False,
                                    headers=self.headers(), stream=True)
            if not response.ok:
                raise ZmlpClientException(
                    "Failed to stream asset: %s" % response)

            for line in response.iter_lines():
                if line:
                    yield line

        except requests.exceptions.ConnectionError as e:
            raise ZmlpConnectionException(e)

    def upload_file(self, path, file, body={}, json_rsp=True):
        """
        Upload a single file and a request to the given endpoint path.

        Args:
            path (str): The URL to upload to.
            file (str): The file path to upload.
            body (dict): A request body
            json_rsp (bool): Set to true if the result returned is JSON

        Returns:
            dict: The response body of the request.
        """
        try:
            post_files = [("file", (os.path.basename(file), open(file, 'rb')))]
            if body is not None:
                post_files.append(
                    ["body", (None, to_json(body), 'application/json')])

            return self.__handle_rsp(requests.post(
                self.get_url(path), headers=self.headers(content_type=""),
                files=post_files), json_rsp)

        except requests.exceptions.ConnectionError as e:
            raise ZmlpConnectionException(e)

    def upload_files(self, path, files, body, json_rsp=True):
        """
        Upload an array of files and a reques to the given endpoint path.

        Args:
            path (str): The URL to upload to
            files (list of str): The file paths to upload
            body (dict): A request body
            json_rsp (bool): Set to true if the result returned is JSON

        Returns:
            dict: The response body of the request.
        """
        try:
            post_files = []
            for f in files:
                if isinstance(f, IOBase):
                    post_files.append(
                        ("files", (os.path.basename(f.name), f)))
                else:
                    post_files.append(
                        ("files", (os.path.basename(f), open(f, 'rb'))))

            if body is not None:
                post_files.append(
                    ("body", ("", to_json(body),
                              'application/json')))

            return self.__handle_rsp(requests.post(
                self.get_url(path), headers=self.headers(content_type=""),
                files=post_files), json_rsp)

        except requests.exceptions.ConnectionError as e:
            raise ZmlpConnectionException(e)

    def get(self, path, body=None, is_json=True):
        """
        Performs a get request.

        Args:
            path (str): An archivist URI path.
            body (dict): The request body which will be serialized to json.
            is_json (bool): Set to true to specify a JSON return value

        Returns:
            object: The http response object or an object deserialized from the
                response json if the ``json`` argument is true.

        Raises:
            Exception: An error occurred making the request or parsing the
                JSON response
        """
        return self._make_request('get', path, body, is_json)

    def post(self, path, body=None, is_json=True):
        """
        Performs a post request.

        Args:
            path (str): An archivist URI path.
            body (object): The request body which will be serialized to json.
            is_json (bool): Set to true to specify a JSON return value

        Returns:
            object: The http response object or an object deserialized from the
                response json if the ``json`` argument is true.

        Raises:
            Exception: An error occurred making the request or parsing the
                JSON response
        """
        return self._make_request('post', path, body, is_json)

    def put(self, path, body=None, is_json=True):
        """
        Performs a put request.

        Args:
            path (str): An archivist URI path.
            body (object): The request body which will be serialized to json.
            is_json (bool): Set to true to specify a JSON return value

        Returns:
            object: The http response object or an object deserialized from the
                response json if the ``json`` argument is true.

        Raises:
            Exception: An error occurred making the request or parsing the
                JSON response
        """
        return self._make_request('put', path, body, is_json)

    def delete(self, path, body=None, is_json=True):
        """
         Performs a delete request.

         Args:
             path (str): An archivist URI path.
             body (object): The request body which will be serialized to json.
             is_json (bool): Set to true to specify a JSON return value

         Returns:
             object: The http response object or an object deserialized from
             the response json if the ``json`` argument is true.

         Raises:
             Exception: An error occurred making the request or parsing the
                JSON response
         """
        return self._make_request('delete', path, body, is_json)

    def iter_paged_results(self, url, req, limit, cls):
        """
        Handles paging through the results of the standard _search
        endpoints on the backend.

        Args:
            url (str): the URL to POST a search to
            req (object): the search request body
            limit (int): the maximum items to return, None for no limit.
            cls (type): the class to wrap each result in

        Yields:
            Generator

        """
        left_to_return = limit or sys.maxsize
        page = 0
        req["page"] = {}
        while True:
            if left_to_return < 1:
                break
            page += 1
            req["page"]["size"] = min(100, left_to_return)
            req["page"]["from"] = (page - 1) * req["page"]["size"]
            rsp = self.post(url, req)
            if not rsp.get("list"):
                break
            for f in rsp["list"]:
                yield cls(f)
                left_to_return -= 1
            # Used to break before pulling new batch
            if rsp.get("break"):
                break

    def _make_request(self, method, path, body=None, is_json=True):
        request_function = getattr(requests, method)
        if body is not None:
            data = to_json(body)
        else:
            data = body

        # Making the request is wrapped in its own try/catch so it's easier
        # to catch any and all socket and http exceptions that can possibly be
        # thrown.  Once hat happens, handle_rsp is called which may throw
        # application level exceptions.
        rsp = None
        tries = 0
        url = self.get_url(path, body)
        while True:
            try:
                rsp = request_function(url, data=data, headers=self.headers(),
                                       verify=False)
                break
            except Exception as e:
                # Some form of connection error, wait until archivist comes
                # back.
                tries += 1
                if 0 < self.max_retries <= tries:
                    raise e
                wait = random.randint(1, random.randint(1, 60))
                # Switched to stderr in case no logger is setup, still want
                # to see messages.
                msg = "Communicating to ZMLP (%s) timed out %d times, " \
                      "waiting ... %d seconds, error=%s\n"
                sys.stderr.write(msg % (url, tries, wait, e))
                time.sleep(wait)

        return self.__handle_rsp(rsp, is_json)

    def __handle_rsp(self, rsp, is_json):
        if rsp.status_code != 200:
            self.__raise_exception(rsp)
        if is_json and len(rsp.content):
            rsp_val = rsp.json()
            if logger.getEffectiveLevel() == logging.DEBUG:
                logger.debug(
                    "rsp: status: %d  body: '%s'" % (rsp.status_code, rsp_val))
            return rsp_val
        return rsp

    def __raise_exception(self, rsp):
        data = {}
        try:
            data.update(rsp.json())
        except Exception as e:
            # The result is not json.
            data["message"] = "Your HTTP request was invalid '%s', response not " \
                              "JSON formatted. %s" % (rsp.status_code, e)
            data["status"] = rsp.status_code

        # If the status code can't be found, then ZmlpRequestException is returned.
        ex_class = translate_exception(rsp.status_code)
        raise ex_class(data)

    def get_url(self, path, body=None):
        """
        Returns the full URL including the configured server part.
        """
        url = urljoin(self.server, path)
        if logger.getEffectiveLevel() == logging.DEBUG:
            logger.debug("url: '%s' path: '%s' body: '%s'" % (url, path, body))
        return url

    def headers(self, content_type="application/json"):
        """
        Generate the return some request headers.

        Args:
            content_type(str):  The content-type for the request. Defaults to
                'application/json'

        Returns:
            dict: An http header struct.

        """
        header = {'Authorization': "Bearer {}".format(self.__sign_request())}

        if content_type:
            header['Content-Type'] = content_type

        if logger.getEffectiveLevel() == logging.DEBUG:
            logger.debug("headers: %s" % header)

        return header

    def __load_apikey(self, apikey):
        key_data = None
        if not apikey:
            return key_data
        elif hasattr(apikey, 'read'):
            key_data = json.load(apikey)
        elif isinstance(apikey, dict):
            key_data = apikey
        elif isinstance(apikey, (str, bytes)):
            try:
                key_data = json.loads(base64.b64decode(apikey))
            except binascii.Error:
                raise ValueError("Invalid base64 encoded API key.")

        return key_data

    def __sign_request(self):
        if not self.apikey:
            raise RuntimeError("Unable to make request, no ApiKey has been specified.")
        claims = {
            'aud': self.server,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=60),
            'accessKey': self.apikey["accessKey"],
        }

        if os.environ.get("ZMLP_TASK_ID"):
            claims['taskId'] = os.environ.get("ZMLP_TASK_ID")
            claims['jobId'] = os.environ.get("ZMLP_JOB_ID")

        if self.project_id:
            claims["projectId"] = self.project_id
        return jwt.encode(claims, self.apikey['secretKey'], algorithm='HS512').decode("utf-8")


class SearchResult(object):
    """
    A utility class for wrapping various search result formats
    that come back from the ZMLP servers.
    """

    def __init__(self, data, clazz):
        """
        Create a new SearchResult instance.

        Note that its possible to both iterate and index a SearchResult
        as a list. For example

        Args:
            data (dict): A search response body from the ZMLP servers.
            clazz (mixed): A class to wrap each item in the response body.
        """
        self.items = [clazz(item) for item in data["list"]]
        self.offset = data["page"]["from"]
        self.size = len(data["list"])
        self.total = data["page"]["totalCount"]

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, idx):
        return self.items[idx]


def to_json(obj, indent=None):
    """
    Convert the given object to a JSON string using
    the ZmlpJsonEncoder.

    Args:
        obj (mixed): any json serializable python object.
        indent (int): The indentation level for the json, or None for compact.
    Returns:
        str: The serialized object

    """
    val = json.dumps(obj, cls=ZmlpJsonEncoder, indent=indent)
    if logger.getEffectiveLevel() == logging.DEBUG:
        logger.debug("json: %s" % val)
    return val


class ZmlpJsonEncoder(json.JSONEncoder):
    """
    JSON encoder for with ZMLP specific serialization defaults.
    """

    def default(self, obj):
        if hasattr(obj, 'for_json'):
            return obj.for_json()
        elif isinstance(obj, (set, frozenset)):
            return list(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, datetime.time):
            return obj.isoformat()
        elif isinstance(obj, decimal.Decimal):
            return float(obj)

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class ZmlpClientException(ZmlpException):
    """The base exception class for all ZmlpClient related Exceptions."""
    pass


class ZmlpRequestException(ZmlpClientException):
    """
    The base exception class for all exceptions thrown from zmlp.
    """
    def __init__(self, data):
        super(ZmlpClientException, self).__init__(
            data.get("message", "Unknown request exception"))
        self.__data = data

    @property
    def type(self):
        return self.__data["exception"]

    @property
    def cause(self):
        return self.__data["cause"]

    @property
    def endpoint(self):
        return self.__data["path"]

    @property
    def status(self):
        return self.__data["status"]

    def __str__(self):
        return "<ZmlpRequestException msg=%s>" % self.__data["message"]


class ZmlpConnectionException(ZmlpClientException):
    """
    This exception is thrown if the client encounters a connectivity issue
    with the Zmlp API servers..
    """
    pass


class ZmlpWriteException(ZmlpRequestException):
    """
    This exception is thrown the Zmlp fails a write operation.
    """

    def __init__(self, data):
        super(ZmlpWriteException, self).__init__(data)


class ZmlpSecurityException(ZmlpRequestException):
    """
    This exception is thrown if Zmlp fails a security check on the request.
    """

    def __init__(self, data):
        super(ZmlpSecurityException, self).__init__(data)


class ZmlpNotFoundException(ZmlpRequestException):
    """
    This exception is thrown if the Zmlp fails a read operation because
    a piece of named data cannot be found.
    """

    def __init__(self, data):
        super(ZmlpNotFoundException, self).__init__(data)


class ZmlpDuplicateException(ZmlpWriteException):
    """
    This exception is thrown if the Zmlp fails a write operation because
    the newly created element would be a duplicate.
    """

    def __init__(self, data):
        super(ZmlpDuplicateException, self).__init__(data)


class ZmlpInvalidRequestException(ZmlpRequestException):
    """
    This exception is thrown if the request sent to Zmlp is invalid in
    some way, similar to an IllegalArgumentException.
    """

    def __init__(self, data):
        super(ZmlpInvalidRequestException, self).__init__(data)


"""
A map of HTTP response codes to local exception types.
"""
EXCEPTION_MAP = {
    404: ZmlpNotFoundException,
    409: ZmlpDuplicateException,
    500: ZmlpInvalidRequestException,
    400: ZmlpInvalidRequestException,
    401: ZmlpSecurityException,
    403: ZmlpSecurityException
}


def translate_exception(status_code):
    """
    Translate the HTTP status code into one of the exceptions.

    Args:
        status_code (int): the HTTP status code

    Returns:
        Exception: the exception to throw for the given status code
    """
    return EXCEPTION_MAP.get(status_code, ZmlpRequestException)
