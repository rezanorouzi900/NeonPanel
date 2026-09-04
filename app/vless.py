# app/vless.py
# Pure-Python VLESS protocol core: header parse/build (spec-compliant).
# Author: OpenCode
from __future__ import annotations

import struct
import uuid

RESP_OK = b"\x00\x00"  # version(0) + addon-len(0) — standard VLESS response

ERR_BAD = "bad_header"
ERR_USER = "bad_user"
ERR_CMD = "bad_command"


def parse_header(buf: bytes, valid_ids: set[str]) -> tuple[str, str, int, int]:
    """Parse a VLESS request header.

    Layout: ver(1) uuid(16) addons_len(1) addons(N) cmd(1) port(2)
            atyp(1) addr(var) [+ padding for UDP]
    Returns (uuid, addr, port, header_len) — raises ValueError(ERR_*) on bad input.
    """
    if len(buf) < 24:
        raise ValueError(ERR_BAD)
    if buf[0] != 0:
        raise ValueError(ERR_BAD)
    uid = str(uuid.UUID(bytes=bytes(buf[1:17])))
    if uid not in valid_ids:
        raise ValueError(ERR_USER)
    pos = 17
    addons_len = buf[pos]
    pos += 1 + addons_len
    if len(buf) < pos + 4:
        raise ValueError(ERR_BAD)
    cmd = buf[pos]
    pos += 1
    if cmd not in (0x01, 0x02):  # TCP / UDP
        raise ValueError(ERR_CMD)
    port = struct.unpack(">H", buf[pos:pos + 2])[0]
    pos += 2
    atyp = buf[pos]
    pos += 1
    if atyp == 0x01:  # IPv4
        if len(buf) < pos + 4:
            raise ValueError(ERR_BAD)
        addr = ".".join(str(b) for b in buf[pos:pos + 4])
        pos += 4
    elif atyp == 0x02:  # domain
        if len(buf) < pos + 1:
            raise ValueError(ERR_BAD)
        dlen = buf[pos]
        pos += 1
        if len(buf) < pos + dlen:
            raise ValueError(ERR_BAD)
        addr = buf[pos:pos + dlen].decode("utf-8", "replace")
        pos += dlen
    elif atyp == 0x03:  # IPv6
        if len(buf) < pos + 16:
            raise ValueError(ERR_BAD)
        addr = _fmt_ipv6(buf[pos:pos + 16])
        pos += 16
    else:
        raise ValueError(ERR_BAD)
    return uid, addr, port, pos


def _fmt_ipv6(raw: bytes) -> str:
    import ipaddress

    return str(ipaddress.IPv6Address(raw))


def build_header(uid: str, addr: str, port: int, tcp: bool = True) -> bytes:
    """Build a VLESS request header (mirror of parse — used by e2e tests)."""
    out = b"\x00" + uuid.UUID(uid).bytes + b"\x00" + (b"\x01" if tcp else b"\x02")
    out += struct.pack(">H", port)
    try:
        import ipaddress

        ip = ipaddress.ip_address(addr)
        if ip.version == 4:
            out += b"\x01" + ip.packed
        else:
            out += b"\x03" + ip.packed
    except ValueError:
        d = addr.encode("idna") if addr.isascii() else addr.encode()
        out += b"\x02" + bytes([len(d)]) + d
    return out
