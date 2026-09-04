# tests/test_mtproto_links.py — MTProto host & links (never localhost when public).
# Author: OpenCode


def test_suggested_host_uses_railway_tcp(monkeypatch):
    monkeypatch.delenv("PUBLIC_DOMAIN", raising=False)
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    monkeypatch.setenv("RAILWAY_TCP_PROXY_DOMAIN", "tcp.proxy railway")
    monkeypatch.setenv("PORT", "8080")
    from app import domain

    domain._cache["value"] = None
    domain._cache["at"] = 0.0
    from app.mtproto import suggested_host

    assert suggested_host() == "tcp.proxy railway"


def test_suggested_host_uses_detected_domain(monkeypatch):
    monkeypatch.delenv("PUBLIC_DOMAIN", raising=False)
    monkeypatch.delenv("RAILWAY_TCP_PROXY_DOMAIN", raising=False)
    monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
    from app import domain

    domain._cache["value"] = None
    domain._cache["at"] = 0.0
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "neon.up.railway.app")
    from app.mtproto import suggested_host

    assert suggested_host() == "neon.up.railway.app"


def test_build_links_shape():
    from app.mtproto import build_links

    links = build_links("proxy.example.com", 4433, "ab" * 16)
    assert links["simple"].startswith("https://t.me/proxy?server=proxy.example.com&port=4433&secret=dd")
    assert "ee" in links["cloaked"] and "www.google.com" in links["cloaked"]
    assert "localhost" not in links["simple"]
