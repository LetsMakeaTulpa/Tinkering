"""Decides whether a URL may be fetched. Runs before every request and on every redirect hop.

Always blocked: non-http(s) schemes, and hosts that resolve to private, loopback, link-local or
reserved addresses (stops the fetcher being used to reach your own server, cloud metadata, LAN).
.onion: only via the Tor proxy, and only when the project allows Tor.
Scoped projects: only hosts in project.allowed_domains (and their subdomains).
"""

import ipaddress
import socket
from urllib.parse import urlsplit


class Blocked(Exception):
    pass


def host_in(host: str, domains: list[str]) -> bool:
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in (x.lower().strip(".") for x in domains))


def is_onion(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower().endswith(".onion")


def check_url(url: str, *, mode: str = "standard", allowed_domains: list[str] | None = None,
              allow_tor: bool = False, tor_proxy: str = "", resolve=None) -> str:
    """Return "direct" or "tor" for how to fetch, or raise Blocked."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise Blocked(f"scheme {parts.scheme!r} not allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise Blocked("no host")
    if mode == "scoped" and not host_in(host, allowed_domains or []):
        raise Blocked(f"{host} is outside this project's allowed domains")
    if host.endswith(".onion"):
        if not (allow_tor and tor_proxy):
            raise Blocked("onion address: enable Tor for this project and set TOR_PROXY")
        return "tor"
    try:
        infos = (resolve or socket.getaddrinfo)(host, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise Blocked(f"cannot resolve {host}: {e}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise Blocked(f"{host} resolves to non-public address {ip}")
    return "direct"
