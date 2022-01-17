import json
from typing import Union
from typing import List


class FujiNetPlatform:
    def __init__(self, name: str, url: str, description: str = "", build: str = ""):
        self.name = name
        self.url = url
        self.description = description
        self.build = build


def as_platform(dct: dict):
    # print("as_platform", str(dct))
    p = None
    try:
        if 'name' in dct and 'url' in dct:  # mandatory keys
            p = FujiNetPlatform(
                str(dct['name']),
                str(dct['url']),
                str(dct.get('description', "")),
                str(dct.get('build', "").upper()),
            )
        else:
            print("Missing mandatory key(s) for platform entry, platform entry skipped.")
    except Exception as e:
        print("Unexpected error: {}".format(e))
        p = None
    return p


def loads(data: bytes) -> List[FujiNetPlatform]:
    platforms = []
    try:
        # parse json
        platforms_lst = json.loads(data).get('platforms', [])
        # build platforms: List[FujiNetPlatform]
        # skip None - invalid object from as_platform()
        platforms = [
            p for p in [as_platform(dct) for dct in platforms_lst] if p is not None
        ]
    except json.JSONDecodeError as e:
        print("JSON error: {}".format(e))
    except Exception as e:
        print("Unexpected error: {}".format(e))
    return platforms
