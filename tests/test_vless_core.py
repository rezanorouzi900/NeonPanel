# tests/test_vless_core.py â€” header parse/build roundtrips + all error branches.
# Author: OpenCode
import pytest

from app.vless import ERR_BAD, ERR_CMD, ERR_USER, build_header, parse_header

IDS = {"11111111-2222-3333-4444-555555555555"}


def test_roundtrip_domain():
    h = build_header("11111111-2222-3333-4444-555555555555", "example.com", 443)
    uid, addr, port, hlen = parse_header(h + b"PAYLOAD", IDS)
    assert uid == "11111111-2222-3333-4444-555555555555"
    assert addr == "example.com"
    assert port == 443
    raw = h + b"PAYLOAD"
    assert raw[hlen:] == b"PAYLOAD"


def test_roundtrip_ipv4():
    h = build_header("11111111-2222-3333-4444-555555555555", "93.184.216.34", 80)
    _, addr, port, _ = parse_header(h, IDS)
    assert addr == "93.184.216.34" and port == 80


def test_roundtrip_ipv6():
    h = build_header("11111111-2222-3333-4444-555555555555", "2606:2800:220:1:248:1893:25c8:1946", 443)
    _, addr, _, _ = parse_header(h, IDS)
    assert addr == "2606:2800:220:1:248:1893:25c8:1946"


def test_roundtrip_udp_command():
    h = build_header("11111111-2222-3333-4444-555555555555", "1.1.1.1", 53, tcp=False)
    _, addr, port, _ = parse_header(h, IDS)
    assert addr == "1.1.1.1" and port == 53


def test_reject_unknown_user():
    h = build_header("99999999-9999-9999-9999-999999999999", "x.com", 80)
    with pytest.raises(ValueError) as e:
        parse_header(h, IDS)
    assert str(e.value) == ERR_USER


def test_reject_short_buffer():
    with pytest.raises(ValueError) as e:
        parse_header(b"\x00" * 10, IDS)
    assert str(e.value) == ERR_BAD


def test_reject_bad_version():
    h = b"\x01" + build_header("11111111-2222-3333-4444-555555555555", "x.com", 80)[1:]
    with pytest.raises(ValueError) as e:
        parse_header(h, IDS)
    assert str(e.value) == ERR_BAD


def test_reject_bad_command():
    h = bytearray(build_header("11111111-2222-3333-4444-555555555555", "x.com", 80))
    h[18] = 0x03  # mux â€” unsupported
    with pytest.raises(ValueError) as e:
        parse_header(bytes(h), IDS)
    assert str(e.value) == ERR_CMD


def test_addons_skipped():
    import struct
    import uuid

    uid = uuid.UUID("11111111-2222-3333-4444-555555555555").bytes
    addons = b"secert"  # 6 bytes of addons
    dom = b"x.com"
    domain = bytes([len(dom)]) + dom
    h = b"\x00" + uid + bytes([len(addons)]) + addons + b"\x01" + struct.pack(">H", 80) + b"\x02" + domain
    got_uid, addr, port, hlen = parse_header(h + b"REST", IDS)
    assert got_uid in IDS and addr == "x.com" and port == 80
    raw = h + b"REST"
    assert raw[hlen:] == b"REST"


