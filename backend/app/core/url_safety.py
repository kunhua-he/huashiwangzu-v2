"""URL safety — SSRF protection for outbound HTTP requests.

Rejects requests to private/internal/loopback/link-local/multicast/reserved
addresses.  Based on Hermes url_safety.py logic but rewritten for V2 patterns.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

from app.core.exceptions import ValidationError

logger = logging.getLogger("v2.url_safety")

_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.goog",
    "169.254.169.254",
})

_ALWAYS_BLOCKED_IPS = frozenset(
    ipaddress.ip_address(addr)
    for addr in [
        "169.254.169.254",
        "169.254.170.2",
        "169.254.169.253",
        "fd00:ec2::254",
        "100.100.100.200",
        "::ffff:169.254.169.254",
        "::ffff:169.254.170.2",
        "::ffff:169.254.169.253",
        "::ffff:100.100.100.200",
    ]
)

_ALWAYS_BLOCKED_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::ffff:169.254.0.0/112"),
]

_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        embedded = ip.ipv4_mapped
        return (
            embedded.is_private or embedded.is_loopback or
            embedded.is_link_local or embedded.is_reserved or
            embedded.is_multicast or embedded.is_unspecified or
            embedded in _CGNAT_NETWORK
        )
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    if ip in _CGNAT_NETWORK:
        return True
    return False


def validate_safe_url(url: str) -> str:
    """Validate URL for SSRF safety.  Returns normalized URL or raises ValidationError.

    Checks:
    - Only http/https schemes
    - No userinfo (user:pass@host)
    - No localhost/loopback/private/link-local/multicast/reserved
    - DNS resolution checked (fail-closed on resolution failure)
    - Cloud metadata IPs/hostnames always blocked
    """
    if not isinstance(url, str) or not url.strip():
        raise ValidationError("URL is required")

    url = url.strip()

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValidationError(f"Invalid URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValidationError("Only http/https URLs are allowed")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise ValidationError("URL has no hostname")

    # Reject URLs with userinfo
    if parsed.username or parsed.password:
        raise ValidationError("URL with embedded credentials is not allowed")

    # Block known internal hostnames
    if hostname in _BLOCKED_HOSTNAMES:
        logger.warning("Blocked request to internal hostname: %s", hostname)
        raise ValidationError("URL targets a blocked internal address")

    # Literal IP check
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None

    if ip is not None:
        if ip in _ALWAYS_BLOCKED_IPS or any(
            ip in net for net in _ALWAYS_BLOCKED_NETWORKS
        ):
            raise ValidationError("URL targets a blocked internal address")
        if _is_blocked_ip(ip):
            raise ValidationError("URL targets a private/internal address")
        return url

    # Resolve hostname and check all addresses
    try:
        addr_info = socket.getaddrinfo(
            hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ValidationError(f"DNS resolution failed for: {hostname}")

    for _family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        if "%" in ip_str:
            ip_str = ip_str.split("%")[0]
        try:
            resolved = ipaddress.ip_address(ip_str)
        except ValueError:
            raise ValidationError(f"Unparseable IP for hostname {hostname}")

        if resolved in _ALWAYS_BLOCKED_IPS or any(
            resolved in net for net in _ALWAYS_BLOCKED_NETWORKS
        ):
            raise ValidationError("URL resolves to a blocked internal address")
        if _is_blocked_ip(resolved):
            raise ValidationError("URL resolves to a private/internal address")

    return url
