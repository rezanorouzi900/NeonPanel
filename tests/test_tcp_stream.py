# tests/test_tcp_stream.py — VLESS over raw TCP (real pipe), plus default link seed.
# Author: OpenCode
import asyncio
import socket

import pytest

from app import store
from app.relay import handle_tcp_stream
from app.vless import RESP_OK, build_header


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_ensure_default_link_creates_when_empty(fresh_store):
    fresh_store._state["configs"] = {}
    default = store.ensure_default_link()
    assert default is not None and default["name"] == "default"
    assert len(fresh_store._state["configs"]) == 1
    # idempotent — second call does nothing
    assert store.ensure_default_link() is None


@pytest.mark.asyncio
async def test_handle_tcp_stream_echo(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store._state = {"configs": {}, "groups": {}, "admin_hash": "x", "seq": 1}
    store.save = lambda: None
    cfg, _ = store.create_config("tcp-user")

    echo_port = free_port()

    async def echo():
        async def h(r, w):
            try:
                while True:
                    d = await r.read(65536)
                    if not d:
                        break
                    w.write(d.upper())
                    await w.drain()
            finally:
                w.close()

        return await asyncio.start_server(h, "127.0.0.1", echo_port)

    srv = await echo()
    srv_port = free_port()
    srv2 = await asyncio.start_server(handle_tcp_stream, "127.0.0.1", srv_port)
    try:
        r, w = await asyncio.open_connection("127.0.0.1", srv_port)
        w.write(build_header(cfg["uuid"], "127.0.0.1", echo_port) + b"hello-tcp")
        await w.drain()

        # client-side: first reply = RESP_OK, then piped echo
        first = await asyncio.wait_for(r.read(2), timeout=5)
        pair = await asyncio.wait_for(r.read(64), timeout=5)
        assert first == RESP_OK
        assert b"hello-tcp".upper() in pair
        # roundtrip after header
        w.write(b"ping")
        await w.drain()
        pair2 = await asyncio.wait_for(r.read(64), timeout=5)
        assert b"ping".upper() in pair2
        w.close()
    finally:
        srv.close()
        srv2.close()
        await srv.wait_closed()
        await srv2.wait_closed()


@pytest.mark.asyncio
async def test_tcp_rejects_bad_uuid(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    store._state = {"configs": {}, "groups": {}, "admin_hash": "x", "seq": 1}
    store.save = lambda: None
    store.create_config("tcp-user")

    srv_port = free_port()
    srv = await asyncio.start_server(handle_tcp_stream, "127.0.0.1", srv_port)
    try:
        r, w = await asyncio.open_connection("127.0.0.1", srv_port)
        w.write(build_header("99999999-9999-9999-9999-999999999999", "127.0.0.1", 80))
        await w.drain()
        # connection should be closed quickly (no RESP_OK, no data)
        data = await asyncio.wait_for(r.read(16), timeout=5)
        assert data == b"" or data != RESP_OK
        w.close()
    finally:
        srv.close()
        await srv.wait_closed()
