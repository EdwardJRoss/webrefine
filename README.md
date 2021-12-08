# webrefine
> A workflow for refining web pages into useful datasets.


Read the [full documentation](https://edwardjross.github.io/webrefine/)

## Install

`pip install webrefine`

## How to use

We'll go through an example of getting some titles from my blog at [skeptric.com](https://skeptric.com).

The process consists of:

* Defining Queries
* Defining Extraction and Filters
* Running the process

### Querying data

To start we'll need some captures of my blog, and so we'll get them from the Internet Archive's Wayback Machine.

```python
from webrefine.query import WaybackQuery
```

We could get some HTML pages:

```python
skeptric_wb = WaybackQuery('skeptric.com/*', start='2020', end='2020', mime='text/html')
sample = list(skeptric_wb.query(limit=20))
```

We can get some sample records

```python
sample[0]
```




    WaybackRecord(url='https://skeptric.com/', timestamp=datetime.datetime(2020, 11, 26, 6, 41, 2), mime='text/html', status=200, digest='WDYU3RU7ZMFFSZPAPE56PC4L3EK4FE3D')



```python
sample[1]
```




    WaybackRecord(url='https://skeptric.com/casper-2-to-3/', timestamp=datetime.datetime(2020, 11, 26, 7, 52, 8), mime='text/html', status=200, digest='3XDBGHY77ZEA2Z7IVBARXEQT6UDLYAL7')



And view them on the Wayback Machine to work out how to get the information we want

```python
sample[1].preview()
```




<a href="http://web.archive.org/web/20201126075208/https://skeptric.com/casper-2-to-3/">http://web.archive.org/web/20201126075208/https://skeptric.com/casper-2-to-3/</a>



We could also query CommonCrawl similarly with a `CommonCrawlQuery`.
This has more captures but takes a bit longer to run.

```python
from webrefine.query import CommonCrawlQuery
skeptric_cc = CommonCrawlQuery('skeptric.com/*')
```

Another option is to add local Warc Files (e.g. produced using [`warcio`](https://github.com/webrecorder/warcio) or `wget` with `warc` parameters)

```python
from webrefine.query import WarcFileQuery
test_data = '../resources/test/skeptric.warc.gz'

skeptric_file_query = WarcFileQuery(test_data)
```

```python
[r.url for r in skeptric_file_query.query()]
```




    ['https://skeptric.com/pagination-wayback-cdx/',
     'https://skeptric.com/robots.txt',
     'https://skeptric.com/style.main.min.5ea2f07be7e07e221a7112a3095b89d049b96c48b831f16f1015bf2d95d914e5.css',
     'https://skeptric.com/',
     'https://skeptric.com/about/',
     'https://skeptric.com/tags/data',
     'https://skeptric.com/tags/data/',
     'https://skeptric.com/images/wayback_empty_returns.png',
     'https://skeptric.com/searching-100b-pages-cdx',
     'https://skeptric.com/searching-100b-pages-cdx/',
     'https://skeptric.com/fast-web-data-workflow/',
     'https://skeptric.com/key-web-captures/',
     'https://skeptric.com/emacs-tempfile-hugo/']



### Filtering and Extracting the Data

From Inspecting some web results we can see that the titles are written like:

```html
<h1 class="post-full-title">{TITLE}</h1>
```

In a real example we'd parse the HTML, but for simplicity we'll extract it with a regular expression

```python
import re
def skeptric_extract(content, record):
    html = content.decode('utf-8')
    title = next(re.finditer('<h1 class="post-full-title">([^<]+)</h1>', html)).group(1)
    return {
        'title': title,
        'url': record.url,
        'timestamp': record.timestamp
    }
```

We can then test it on some content we fetch from the Wayback Machine

```python
skeptric_extract(sample[1].content, sample[1])
```




    {'title': 'Hugo Casper 2 to 3',
     'url': 'https://skeptric.com/casper-2-to-3/',
     'timestamp': datetime.datetime(2020, 11, 26, 7, 52, 8)}



Some pages don't have it so we filter them out, and we remove duplicates

```python
def skeptric_filter(records):
    last_url = None
    for record in records:
        # Only use ok HTML captures
        if record.mime != 'text/html' or record.status != 200:
            continue
        # Pages that are not articles (and so do not have a title)
        if record.url == 'https://skeptric.com/' or '/tags/' in record.url:
            continue
        # Duplicates (using the fact that here the posts come in order)
        if record.url == last_url:
            continue
        last_url = record.url
        yield record
```

```python
[r.url for r in skeptric_filter(sample)]
```




    ['https://skeptric.com/casper-2-to-3/',
     'https://skeptric.com/common-crawl-index-athena/',
     'https://skeptric.com/common-crawl-job-ads/',
     'https://skeptric.com/considering-vscode/',
     'https://skeptric.com/decorating-pandas-tables/',
     'https://skeptric.com/drive-metrics/',
     'https://skeptric.com/emacs-buffering/',
     'https://skeptric.com/ngram-python/',
     'https://skeptric.com/portable-custom-config/',
     'https://skeptric.com/searching-100b-pages-cdx/',
     'https://skeptric.com/text-meta-data-commoncrawl/']



## Running the process

Now we've written all the logic we need, we can collect it all in a process to run

```python
from webrefine.runners import Process
```

```python
skeptric_process = Process(
    queries=[skeptric_file_query,
             # commented out to make faster
             #skeptric_wb,
             #skeptric_cc,
          ],
    filter=skeptric_filter,
    steps = [skeptric_extract])
```

We can wrap it in a runner and run it all with `.run`.

```python
%%time
from webrefine.runners import RunnerMemory
data = list(RunnerMemory(skeptric_process).run())
data
```

    CPU times: user 290 ms, sys: 14.8 ms, total: 305 ms
    Wall time: 304 ms





    [{'title': 'Pagination in Internet Archive&#39;s Wayback Machine with CDX',
      'url': 'https://skeptric.com/pagination-wayback-cdx/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 34)},
     {'title': 'About Skeptric',
      'url': 'https://skeptric.com/about/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 37)},
     {'title': 'Searching 100 Billion Webpages Pages With Capture Index',
      'url': 'https://skeptric.com/searching-100b-pages-cdx/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 39)},
     {'title': 'Fast Web Dataset Extraction Worfklow',
      'url': 'https://skeptric.com/fast-web-data-workflow/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 39)},
     {'title': 'Unique Key for Web Captures',
      'url': 'https://skeptric.com/key-web-captures/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 40)},
     {'title': 'Hugo Readdir Error with Emacs',
      'url': 'https://skeptric.com/emacs-tempfile-hugo/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 40)}]



For larger jobs `RunnerFile` is better which caches intermediate results to a file

```python
%%time
from webrefine.runners import RunnerCached

cache_path = './test_cache.sqlite'

data = list(RunnerCached(skeptric_process, path=cache_path).run())
data
```

    CPU times: user 252 ms, sys: 10.7 ms, total: 263 ms
    Wall time: 286 ms





    [{'title': 'Pagination in Internet Archive&#39;s Wayback Machine with CDX',
      'url': 'https://skeptric.com/pagination-wayback-cdx/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 34)},
     {'title': 'About Skeptric',
      'url': 'https://skeptric.com/about/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 37)},
     {'title': 'Searching 100 Billion Webpages Pages With Capture Index',
      'url': 'https://skeptric.com/searching-100b-pages-cdx/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 39)},
     {'title': 'Fast Web Dataset Extraction Worfklow',
      'url': 'https://skeptric.com/fast-web-data-workflow/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 39)},
     {'title': 'Unique Key for Web Captures',
      'url': 'https://skeptric.com/key-web-captures/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 40)},
     {'title': 'Hugo Readdir Error with Emacs',
      'url': 'https://skeptric.com/emacs-tempfile-hugo/',
      'timestamp': datetime.datetime(2021, 11, 26, 11, 28, 40)}]



```python
import os
os.unlink(cache_path)
```

Note that in the case of errors in the steps the process keeps going, and logs the errors

```python
skeptric_error_process = Process(
    queries=[skeptric_file_query,
             # commented out to make faster
             #skeptric_wb,
             #skeptric_cc,
          ],
    filter=lambda x: x,
    steps = [skeptric_extract])
```

```python
data = list(RunnerMemory(skeptric_error_process).run())
```

    ERROR:root:Error processing WarcFileRecord(url='https://skeptric.com/robots.txt', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 34), mime='text/html', status=404, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=5804, digest='QRNGXIUXE4LAI3XR5RVATIUX5GTB33HX') at step skeptric_extract: 
    ERROR:root:Error processing WarcFileRecord(url='https://skeptric.com/style.main.min.5ea2f07be7e07e221a7112a3095b89d049b96c48b831f16f1015bf2d95d914e5.css', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 35), mime='text/css', status=200, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=7197, digest='LINCDTSPQGAQGZZ6LY2XFXZHG2X476H6') at step skeptric_extract: 
    ERROR:root:Error processing WarcFileRecord(url='https://skeptric.com/', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 36), mime='text/html', status=200, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=17122, digest='JJVB3MQERHRZJCHOJNKS5VDOODXPZAV2') at step skeptric_extract: 
    ERROR:root:Error processing WarcFileRecord(url='https://skeptric.com/tags/data', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 37), mime='text/html', status=302, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=129093, digest='ZZZXDZTTV2KTABRO64ESHVWFPNKB4I5H') at step skeptric_extract: 
    ERROR:root:Error processing WarcFileRecord(url='https://skeptric.com/tags/data/', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 38), mime='text/html', status=200, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=130269, digest='R7CLAACFU5L7T5LKI5G53RZSMCNUNV6F') at step skeptric_extract: 
    ERROR:root:Error processing WarcFileRecord(url='https://skeptric.com/images/wayback_empty_returns.png', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 38), mime='image/png', status=200, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=160971, digest='SU7JRTHNW6KFCJQFL5PMMKV33U2VLV7T') at step skeptric_extract: 'utf-8' codec can't decode byte 0x89 in position 0: invalid start byte
    ERROR:root:Error processing WarcFileRecord(url='https://skeptric.com/searching-100b-pages-cdx', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 39), mime='text/html', status=302, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=173368, digest='AYVHQLVFIVGZGUYPEHX46CHMZ5NUDDBF') at step skeptric_extract: 


We could then investigate them to see what happened

```python
import datetime
from pathlib import PosixPath
from webrefine.query import WarcFileRecord

record = WarcFileRecord(url='https://skeptric.com/tags/data/', timestamp=datetime.datetime(2021, 11, 26, 11, 28, 38), mime='text/html', status=200, path=PosixPath('../resources/test/skeptric.warc.gz'), offset=130269, digest='R7CLAACFU5L7T5LKI5G53RZSMCNUNV6F')
```
