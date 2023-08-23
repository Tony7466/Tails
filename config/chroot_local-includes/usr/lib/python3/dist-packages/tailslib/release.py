"""
This module is meant to provide informations about Tails release data
(ie: /etc/os-release).
"""

import datetime

def version_data() -> Dict[str, str]:
    """dict of information in /etc/os-release"""
    ret = dict()
    try:
        with open("/etc/os-release") as f:
            data = f.read()
        for i in data.splitlines():
            name, value = i.split("=")
            ret[name.strip()] = value.strip('"')

    except OSError:
        pass

    return ret


def get_release_date() -> datetime.datetime:
    source_dt = datetime.datetime.fromtimestamp(
            int(VERSION_DATA["TAILS_SOURCE_DATE_EPOCH"])
    )
    source_dt = source_dt.replace(tzinfo=datetime.timezone.utc)
    return source_dt

VERSION_DATA = version_data()
