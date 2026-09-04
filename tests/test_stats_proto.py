# tests/test_stats_proto.py — hand-rolled protobuf encode/decode roundtrip.
# Author: OpenCode
import struct

from app.stats import decode_stats, encode_query


def test_encode_query_shape():
    raw = encode_query("user>>>", reset=False)
    # field 1 (pattern, wire 2)
    assert raw[0] == (1 << 3) | 2
    ln = raw[1]
    assert raw[2:2 + ln] == b"user>>>"
    # field 2 (reset=false, wire 0)
    assert raw[2 + ln] == (2 << 3) | 0
    assert raw[2 + ln + 1] == 0


def _mk_stat(name: bytes, value: int) -> bytes:
    def varint(n):
        out = b""
        while True:
            b = n & 0x7F
            n >>= 7
            out += bytes([b | (0x80 if n else 0)])
            if not n:
                return out

    inner = bytes([1 << 3 | 2]) + varint(len(name)) + name
    inner += bytes([2 << 3 | 0]) + varint(value)
    return bytes([1 << 3 | 2]) + varint(len(inner)) + inner


def test_decode_stats_parses_counters():
    body = _mk_stat(b"user>>>reza>>>traffic>>>uplink", 100) + \
        _mk_stat(b"user>>>reza>>>traffic>>>downlink", 900) + \
        _mk_stat(b"user>>>mina>>>traffic>>>downlink", 50)
    stats = decode_stats(body)
    d = dict(stats)
    assert d["user>>>reza>>>traffic>>>uplink"] == 100
    assert d["user>>>reza>>>traffic>>>downlink"] == 900
    assert d["user>>>mina>>>traffic>>>downlink"] == 50


def test_grpc_frame_roundtrip():
    body = encode_query("user>>>", True)
    frame = b"\x00" + struct.pack(">I", len(body)) + body
    assert frame[0] == 0
    assert struct.unpack(">I", frame[1:5])[0] == len(body)


def test_decode_empty_and_garbage():
    assert decode_stats(b"") == []
    assert decode_stats(b"\x08\x01") == []  # unknown field, wire 0 — skipped safely
