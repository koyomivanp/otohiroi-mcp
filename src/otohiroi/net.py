"""HTTPS client limited to the hosts Otohiroi has a documented reason to talk to."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from otohiroi import __version__

ALLOWED_HOSTS = {"api.openverse.org", "freesound.org", "cdn.freesound.org", "upload.wikimedia.org"}
USER_AGENT = f"otohiroi-mcp/{__version__} (+https://github.com/koyomivanp/otohiroi-mcp)"
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
TIMEOUT_S = 30


class NetError(Exception):
    pass


def check_url(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise NetError(f"Refusing to connect to {url!r}: only https to {sorted(ALLOWED_HOSTS)} is allowed.")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        # Credentials are for the host they were issued to, never for a redirect target.
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            redirected.remove_header("Authorization")
        return redirected


_opener = urllib.request.build_opener(_CheckedRedirects)


def _open(url: str, headers: dict | None):
    check_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        return _opener.open(request, timeout=TIMEOUT_S)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise NetError("The source is rate limiting this machine. Wait a minute and try again.") from error
        raise NetError(f"{urllib.parse.urlsplit(url).hostname} answered HTTP {error.code}.") from error
    except OSError as error:
        raise NetError(f"Could not reach {urllib.parse.urlsplit(url).hostname}: {error}") from error


def get_json(url: str, headers: dict | None = None):
    with _open(url, headers) as response:
        return json.load(response)


def get_bytes(url: str, headers: dict | None = None) -> bytes:
    with _open(url, headers) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise NetError("The file is larger than the 200 MB limit.")
    return data
