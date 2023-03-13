import threading
import requests

try:
    # For MacOS so it finds the certificates
    import os
    import sys
    os.environ['SSL_CERT_FILE'] = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
except:
    pass

from typing import Union, Dict
# import time  # TODO remove, used for tests with time.sleep
import hashlib

import wx


class RemoteFileCache:
    """Very simple cache for RemoteFile's url:data"""

    def __init__(self):
        self.entries: Dict[str, bytes] = {}
        self.lock = threading.Lock()

    def flush(self):
        with self.lock:
            self.entries.clear()

    def set(self, url: str, data: bytes):
        with self.lock:
            self.entries[url] = data

    def get(self, url):
        with self.lock:
            return self.entries.get(url)


cache = RemoteFileCache()


def flush_cache():
    cache.flush()
    # print("cache flushed")


class RemoteFileEvent(wx.PyEvent):
    event_type = wx.NewEventType()

    def __init__(self, remote_file: 'RemoteFile', event_id: int = 0):
        wx.PyEvent.__init__(self, event_id, RemoteFileEvent.event_type)
        self.remote_file = remote_file


class RemoteFile:
    STATUS_UNKNOWN = -1
    STATUS_OK = 0
    STATUS_ERROR = 1
    STATUS_ABORT = 2

    def __init__(self, url: str, window: wx.Window, event_id: int = 0):
        self.status: int = RemoteFile.STATUS_UNKNOWN
        self.window: wx.Window = window
        self.event_id: int = event_id
        self.url: str = url
        self.use_cache = False
        self.data: Union[None, bytes] = None
        self.thread: Union[None, RemoteFileThread] = None

    def get(self, use_cache=False):
        data = None
        if use_cache:
            self.use_cache = True
            data = cache.get(self.url)
            if data is not None:
                # print("cache hit")
                self.data = data
                self.status = RemoteFile.STATUS_OK
                wx.PostEvent(self.window, RemoteFileEvent(self, self.event_id))
            else:
                pass
                # print("cache miss")
        if data is None:
            self.cancel()
            self.thread = RemoteFileThread(self)
            self.thread.start()

    def cancel(self):
        if self.thread and self.thread.is_alive():
            self.thread.cancel()

    @property
    def sha256(self):
        return hashlib.sha256(self.data).hexdigest() if self.data is not None else ""


class RemoteFileThread(threading.Thread):
    def __init__(self, remote_file: RemoteFile):
        threading.Thread.__init__(self)
        self.daemon = True
        self.remote_file = remote_file
        self.cancel_pending = threading.Event()

    def run(self):
        data = bytes()

        # # TODO remove, simulates busy work
        # print("Sleeping...")
        # for s in range(6):
        #     time.sleep(.5)
        #     if self.cancel_pending.is_set():
        #         print("Aborted")
        #         self.remote_file.status = RemoteFile.STATUS_ABORT
        #         return

        # real work
        print("Downloading {}".format(self.remote_file.url))
        try:
            req = requests.get(self.remote_file.url, stream=True, timeout=10.0)
            for chunk in req.iter_content(chunk_size=1024):
                if self.cancel_pending.is_set():
                    print("Download aborted")
                    req.close()
                    self.remote_file.status = RemoteFile.STATUS_ABORT
                    return
                if chunk:
                    data += chunk
            self.remote_file.data = data
            req.raise_for_status()
            self.remote_file.status = RemoteFile.STATUS_OK
        except requests.HTTPError as e:
            self.remote_file.status = RemoteFile.STATUS_ERROR
            print("HTTP error: {}".format(e))
        except requests.Timeout as e:
            self.remote_file.status = RemoteFile.STATUS_ERROR
            print("Timeout while downloading file: {}".format(e))
        except Exception as e:
            self.remote_file.status = RemoteFile.STATUS_ERROR
            print("Unexpected error: {}".format(e))
        else:
            # print("Download completed({})".format(self.remote_file.status))
            if self.remote_file.use_cache:
                # print("cache update")
                cache.set(self.remote_file.url, self.remote_file.data)
            wx.PostEvent(self.remote_file.window,
                         RemoteFileEvent(self.remote_file, self.remote_file.event_id))

    def cancel(self):
        self.cancel_pending.set()
