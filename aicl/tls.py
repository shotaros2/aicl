"""HTTPS for the specialists and links: the system's trust store, plus certifi's when it is installed.

Python on Windows trusts only the roots already in the Windows store, and Windows adds a new root
to that store only when a Windows program first needs it. A PC that never visited a site through
Edge can therefore lack a newer root: measured on the home PC (2026-11-05), ja.wikipedia.org
(Let's Encrypt YE2) failed with "certificate has expired" while Discord, Open-Meteo and Google
worked, and the library and reader were blind all night. certifi carries Mozilla's current roots;
loading it next to the system store fixes that without touching the system. It stays optional:
without it, behaviour is the plain standard library's.
"""
from __future__ import annotations

import socket
import ssl
import urllib.request
from typing import Optional

_context: Optional[ssl.SSLContext] = None


def context() -> ssl.SSLContext:
    global _context
    if _context is None:
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx.load_verify_locations(certifi.where())
        except (ImportError, OSError):
            pass
        _context = ctx
    return _context


def urlopen(req, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
    return urllib.request.urlopen(req, timeout=timeout, context=context())
