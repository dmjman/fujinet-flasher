import json
from typing import Union
from typing import List


class FujiNetRelease:
    def __init__(self, version: str, url: str, sha256: str,
                 platform_build: str = "", platform_name: str = "",
                 version_date: str = "", build_date: str = "", description: str = ""):
        self.version = version
        self.url = url
        self.sha256 = sha256
        self.platform_build = platform_build
        self.platform_name = platform_name
        self.version_date = version_date
        self.build_date = build_date
        self.description = description

    @property
    def named_version(self):
        return "{} - {}".format(self.platform_name, self.version)

    @property
    def info_text(self):
        return "Platform: {}\nVersion: {}\nVersion Date/Time: {}\nBuild Date/Time: {}\nDescription: {}\n".format(
            self.platform_name, self.version,
            self.version_date, self.build_date, self.description
        )


def as_release(dct: dict, platform_build: str = "", platform_name: str = ""):
    r = None
    try:
        if 'version' in dct and 'url' in dct and 'sha256' in dct:
            r = FujiNetRelease(
                str(dct['version']),
                str(dct['url']),
                str(dct['sha256']),
                platform_build,
                platform_name,
                str(dct.get('version_date', "")),
                str(dct.get('build_date', "")),
                str(dct.get('description', "")),
            )
    except Exception as e:
        print("Unexpected error: {}".format(e))
        r = None
    return r


def loads(data: bytes, platform_build: str = "", platform_name: str = "") -> List[FujiNetRelease]:
    releases = []
    try:
        # parse json
        releases_lst = json.loads(data).get('releases', [])
        # build releases: List[FujiNetRelease]
        # skip None - invalid object from as_release()
        releases = [
            r for r in [as_release(dct, platform_build, platform_name) for dct in releases_lst] if r is not None
        ]
    except json.JSONDecodeError as e:
        print("JSON error: {}".format(e))
    except Exception as e:
        print("Unexpected error: {}".format(e))
    return releases
