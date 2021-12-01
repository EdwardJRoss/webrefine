# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_query.ipynb (unless otherwise specified).


from __future__ import annotations # For Python <3.9


__all__ = ['WarcFileRecord', 'get_warc_url', 'get_warc_timestamp', 'get_warc_mime', 'get_warc_status',
           'get_warc_digest', 'WarcFileQuery', 'header_and_rows_to_dict', 'mimetypes_to_regex', 'query_wayback_cdx',
           'IA_CDX_URL', 'CaptureIndexRecord', 'wayback_url', 'fetch_wayback_content', 'WaybackRecord', 'WaybackQuery',
           'get_cc_indexes', 'parse_cc_crawl_date', 'cc_index_by_time', 'jsonl_loads', 'CC_PAGE_SIZE',
           'query_cc_cdx_num_pages', 'query_cc_cdx_page', 'CC_API_FILTER_BLACKLIST', 'fetch_cc', 'CC_DATA_URL',
           'CommonCrawlRecord', 'CommonCrawlQuery']

# Cell
# Typing
#nbdev_comment from __future__ import annotations # For Python <3.9
from typing import Any, Callable, Generator, Optional, Union
from collections.abc import Iterable
from pathlib import Path
from dataclasses import dataclass

from datetime import datetime

import requests
from requests.sessions import Session
import json

from warcio.recordloader import ArcWarcRecord
import warcio

from .util import sha1_digest, URL, make_session

# Cell

@dataclass(frozen=True)
class WarcFileRecord:
    url: str
    timestamp: datetime
    mime: str
    status: int
    path: Path
    offset: int
    digest: str

    def get_content(self):
        with open(self.path, 'rb') as f:
            f.seek(self.offset)
            record = next(warcio.ArchiveIterator(f))
            return record.content_stream().read()

    @property
    def content(self):
        return self.get_content()

def get_warc_url(record: ArcWarcRecord) -> str:
    return record.rec_headers.get_header('WARC-Target-URI')

_WARC_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
def get_warc_timestamp(record: ArcWarcRecord) -> datetime:
    return datetime.strptime(record.rec_headers.get_header('WARC-Date'), _WARC_TIMESTAMP_FORMAT)

def get_warc_mime(record: ArcWarcRecord) -> str:
    return record.http_headers.get_header('Content-Type').split(';')[0]

def get_warc_status(record: ArcWarcRecord) -> int:
    return record.http_headers.get_statuscode()

def get_warc_digest(record: ArcWarcRecord) -> str:
    digest = record.rec_headers.get_header('WARC-Payload-Digest')
    prefix = 'sha1:'
    if not digest.startswith(prefix):
        raise ValueError('Expected %s to start with %s', digest, prefix)
    return digest[len(prefix):]

class WarcFileQuery:
    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def query(self) -> Generator[WarcRecord, None, None]:
        results = []
        with open(self.path, 'rb') as f:
            archive = warcio.ArchiveIterator(f)
            for record in archive:
                if record.rec_type != 'response':
                    continue
                warc_record = WarcFileRecord(url=get_warc_url(record),
                                         timestamp=get_warc_timestamp(record),
                                         mime = get_warc_mime(record),
                                         status = get_warc_status(record),
                                         digest = get_warc_digest(record),
                                         offset = archive.get_record_offset(),
                                         path = self.path)


                results.append(warc_record)
        return results

# Cell
def header_and_rows_to_dict(rows: Iterable[list[Any]]) -> list[dict[Any, Any]]:
    header = None
    data = []
    for row in rows:
        if header is None:
            header = row
        else:
            assert len(row) == len(header), "Row should be same length as header"
            data.append(dict(zip(header, row)))
    return data

# Cell
IA_CDX_URL = 'http://web.archive.org/cdx/search/cdx'

# This could be more precise
CaptureIndexRecord = dict

def mimetypes_to_regex(mime: list[str], prefix='mimetype:') -> str:
    return prefix + '|'.join('(' + s.replace('*', '.*') + ')' for s in mime)

def query_wayback_cdx(url: str, start: Optional[str], end: Optional[str],
                      status_ok: bool = True,
                      mime: Optional[Union[str, Iterable[str]]] = None,
                      limit: Optional[int] = None, offset: Optional[int] = None,
                      session: Optional[Session] = None) -> list[CaptureIndexRecord]:
    """Get references to Wayback Machine Captures for url.

    Queries the Internet Archive Capture Index (CDX) for url.

    Arguments:
      * start: Minimum date in format YYYYmmddHHMMSS (or any substring) inclusive
      * end: Maximum date in format YYYYmmddHHMMSS (or any substring) inclusive
      * status_ok: Only return those with a HTTP status 200
      * mime: Filter on mimetypes, '*' is a wildcard (e.g. 'image/*')
      * limit: Only return first limit records
      * offset: Skip the first offset records, combine with limit
      * session: Session to use when making requests
    Filters results between start and end inclusive, in format YYYYmmddHHMMSS or any substring
    (e.g. start="202001", end="202001" will get all captures in January 2020)
    """
    if session is None:
        session = requests

    params = {'url': url,
              'output': 'json',
              'from': start,
              'to': end,
              'limit': limit,
              'offset': offset}

    filter = []
    if status_ok:
        filter.append('statuscode:200')
    if mime:
        # Turn our list of mimetypes into a regex
        if isinstance(mime, str):
            mime = [mime]
        filter.append(mimetypes_to_regex(mime))
    params['filter'] = filter

    params = {k:v for k,v in params.items() if v}
    response = session.get(IA_CDX_URL, params=params)
    response.raise_for_status()
    return header_and_rows_to_dict(response.json())

# Cell
def wayback_url(timestamp: str, url: str, wayback: bool = False) -> str:
    postfix = '' if wayback else 'id_'
    return f'http://web.archive.org/web/{timestamp}{postfix}/{url}'

def fetch_wayback_content(timestamp: str, url: str,
                          session: Optional[Session] = None) -> Optional[bytes]:
    if session is None:
        session = requests

    url = wayback_url(timestamp, url)
    response = session.get(url)
    # Sometimes Internet Archive deletes records
    if response.status_code == 404:
        logging.warning(f'Missing {url}')
        return None
    response.raise_for_status()
    return response.content

# Cell

@dataclass(frozen=True)
class WaybackRecord:
    url: str
    timestamp: datetime
    mime: str
    status: Optional[int]
    digest: str

    def preview(self) -> URL:
        return URL(wayback_url(self.timestamp_str, self.url, wayback=True))

    @property
    def timestamp_str(self) -> str:
        return self.timestamp.strftime(_WAYBACK_TIMESTAMP_FORMAT)

    def get_content(self, session=None) -> Optional[bytes]:
        return fetch_wayback_content(self.timestamp_str, self.url, session=None)

    @property
    def content(self):
        return self.get_content()

    @classmethod
    def from_dict(cls, record: dict):
        return _wayback_cdx_to_record(record)

_WAYBACK_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'
def _wayback_cdx_to_record(record: dict) -> WaybackRecord:
    return WaybackRecord(url = record['original'],
                         timestamp = datetime.strptime(record['timestamp'], _WAYBACK_TIMESTAMP_FORMAT),
                         mime = record['mimetype'],
                         status = None if record['statuscode'] == '-' else int(record['statuscode']),
                         digest = record['digest'])

# Cell
@dataclass
class WaybackQuery:
    url: str
    start: Optional[str]
    end: Optional[str]
    status_ok: bool = True
    mime: Optional[Union[str, Iterable[str]]] = None

    def query(self,
              limit: Optional[int] = None,
              session: Optional[Session] = None) -> Generator[WaybackRecord, None, None]:
        for r in query_wayback_cdx(self.url, self.start, self.end, self.status_ok, self.mime, limit, session=session):
            yield _wayback_cdx_to_record(r)

# Cell
from functools import lru_cache
@lru_cache(maxsize=None)
def get_cc_indexes() -> List[Dict[str, str]]:
    response = requests.get("https://index.commoncrawl.org/collinfo.json")
    response.raise_for_status()
    return response.json()

# Cell
import re
def parse_cc_crawl_date(crawl_id: str) -> datetime:
    year_week = re.match(r'^CC-MAIN-(\d{4}-\d{2})$', crawl_id)
    year = re.match(r'^CC-MAIN-(?:\d{4}-)?(\d{4})', crawl_id)
    if year_week:
        return datetime.strptime(year_week.group(1)  + '-0', '%Y-%W-%w')
    elif year:
        return datetime.strptime(year.group(1)  + '-12-01', '%Y-%m-%d')
    else:
        raise ValueError(f'Unexpected id: {crawl_id}')

# Cell
def cc_index_by_time(start:Optional[datetime]=None, end:Optional[datetime]=None, indexes:Optional[list[str]]=None) -> list[str]:
    """Gets all indexes that may contain entries between start and end

    Generally errs on the side of giving an additional index"""
    if indexes is None:
        indexes = [i['id'] for i in get_cc_indexes()]

    if start and end and end < start:
        raise ValueError(f"Expect start >= end: start={start}, end={end}")


    dates = [parse_cc_crawl_date(i) for i in indexes]
    if start:
        previous_date = max((ts for ts in dates if ts < start), default=min(dates))
    else:
        previous_date = min(dates)

    if end:
        next_date = min((ts for ts in dates if ts > end), default=max(dates))
    else:
        next_date = max(dates)

    return [i for i in indexes if previous_date <= parse_cc_crawl_date(i) <= next_date]

# Cell
import json

def jsonl_loads(jsonl):
    return [json.loads(line) for line in jsonl.splitlines()]

# Cell

# Default page size for queries (the underlying default is 5)
CC_PAGE_SIZE = 5

# Cell

def query_cc_cdx_num_pages(api: str,  url: str, page_size: int = CC_PAGE_SIZE,
                           session: Optional[Session] = None) -> int:
    if session is None:
        session = requests

    response = session.get(api, params=dict(url=url, output='json',
                                            showNumPages=True, pageSize=page_size))

    response.raise_for_status()
    data = response.json()
    return data["pages"]

def query_cc_cdx_page(
                 api: str, url: str, page: int,
                 start: Optional[str] = None, end: Optional[str] = None,
                 status_ok: bool = True, mime: Optional[Union[str, Iterable[str]]] = None,
                 limit: Optional[int] = None, offset: Optional[int] = None,
                 page_size: int = CC_PAGE_SIZE,
                 session: Optional[Session] = None) -> List[CaptureIndexRecord]:
    """Get references to Common Crawl Captures for url.

    Queries the Common Crawl Capture Index (CDX) for url.

    Filters:
      * api: API endpoint to use (e.g. 'https://index.commoncrawl.org/CC-MAIN-2021-43-index')
      * start: Minimum date in format YYYYmmddHHMMSS (or any substring) inclusive
      * end: Maximum date in format YYYYmmddHHMMSS (or any substring) inclusive
      * status_ok: Only return those with a HTTP status 200
      * mime: Filter on mimetypes, '*' is a wildcard (e.g. 'image/*')
      * limit: Only return first limit records
      * offset: Skip the first offset records, combine with limit
      * session: Session to use when making requests
    Filters results between start and end inclusive, in format YYYYmmddHHMMSS or any substring
    (e.g. start="202001", end="202001" will get all captures in January 2020)
    """
    if session is None:
        session = requests

    params = {'url': url,
              'page': page,
              'output': 'json',
              'page': page,
              'from': start,
              'to': end,
              'pageSize': page_size,
              'limit': limit,
              'offset': offset}

    filter = []
    if status_ok:
        # N.B. Different to IA
        filter.append('=status:200')
    if mime:
        if isinstance(mime, str):
            mime = [mime]
        # N.B. Different to IA
        filter.append(mimetypes_to_regex(mime, prefix='~mime:'))
    params['filter'] = filter

    params = {k:v for k,v in params.items() if v}
    response = session.get(api, params=params)
    response.raise_for_status()
    return jsonl_loads(response.content)

# Cell
CC_API_FILTER_BLACKLIST = ['CC-MAIN-2015-11', 'CC-MAIN-2015-06']

# Cell
from warcio import ArchiveIterator
from io import BytesIO

CC_DATA_URL = "https://commoncrawl.s3.amazonaws.com/"
def fetch_cc(filename: str, offset: int, length: int, session: Optional[Session] = None) -> bytes:
    if session is None:
        session = requests
    data_url = CC_DATA_URL + filename
    start_byte = int(offset)
    end_byte = start_byte + int(length)
    headers = {"Range": f"bytes={start_byte}-{end_byte}"}
    r = session.get(data_url, headers=headers)
    r.raise_for_status()

    # Decord WARC
    response_content = r.content
    archive = ArchiveIterator(BytesIO(response_content))
    record = next(archive)
    content = record.content_stream().read()

    # Archive should have just 1 record
    assert not any(True for _ in archive), "Expected 1 result in archive"

    return content

# Cell
_CC_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'
from IPython.display import FileLink

@dataclass(frozen=True)
class CommonCrawlRecord:
    url: str
    timestamp: datetime
    filename: str
    offset: int
    length: int
    mime: Optional[str]
    status: Optional[int]
    digest: Optional[str]

    def preview(self, filename):
        with open(filename, 'wb') as f:
            f.write(self.content)
        return FileLink(filename)

    @property
    def timestamp_str(self) -> str:
        return self.timestamp.strftime(_CC_TIMESTAMP_FORMAT)

    def get_content(self, session=None) -> Optional[bytes]:
        return fetch_cc(self.filename, self.offset, self.length, session=session)

    @property
    def content(self):
        return self.get_content()

    @classmethod
    def from_dict(cls, record: dict):
        return _cc_cdx_to_record(record)

_WAYBACK_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'
def _cc_cdx_to_record(record: dict) -> WaybackRecord:
    return CommonCrawlRecord(url = record['url'],
                         timestamp = datetime.strptime(record['timestamp'], _WAYBACK_TIMESTAMP_FORMAT),
                             filename=record['filename'],
                             offset=record['offset'],
                             length=record['length'],
                         mime = record.get('mime'),
                         status = None if record.get('status', '-') == '-' else int(record['status']),
                         digest = record.get('digest'))

# Cell
import logging



@dataclass
class CommonCrawlQuery:
    url: str
    start: Optional[str] = None
    end: Optional[str] = None
    apis: Optional[list[str]] = None
    status_ok: bool = True
    mime: Optional[Union[str, Iterable[str]]] = None

    @property
    def cdx_apis(self) -> Dict[str, str]:
        all_apis = get_cc_indexes()
        if self.apis is None:
            apis = cc_index_by_time(self.start, self.end)
        else:
            apis = self.apis

        return {x['id']: x['cdx-api'] for x in all_apis if x['id'] in apis}

    def query(self, page_size=CC_PAGE_SIZE, session=None) -> Generator[CommonCrawlRecord, None, None]:
        for api_id, api in self.cdx_apis.items():
            num_pages = query_cc_cdx_num_pages(api, self.url, page_size=page_size, session=session)

            for page in range(num_pages):
                if api_id not in CC_API_FILTER_BLACKLIST:
                    results_page = query_cc_cdx_page(api, self.url, page, page_size=page_size, status_ok=self.status_ok, mime=self.mime, session=session)
                else:
                    # Deal with missing Status OK and Mime
                    results_page = query_cc_cdx_page(api, self.url, page, page_size=page_size, status_ok=False, mime=None, session=session)

                for result in results_page:
                    yield _cc_cdx_to_record(result)