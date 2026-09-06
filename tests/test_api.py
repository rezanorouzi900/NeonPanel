# tests/test_api.py â€” v3 API: login, CRUD, groups, sub formats, QR.
# Author: OpenCode
import base64


def _login(client, pw="test-pass-123"):
    r = client.post("/api/login", json={"password": pw})
    assert r.status_code == 200, r.text
    return r


def test_login_ok_and_bad(client):
    _login(client)
    r = client.post("/api/login", json={"password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "BAD_CRED"


def test_login_lockout(client):
    for _ in range(6):
        client.post("/api/login", json={"password": "x"})
    r = client.post("/api/login", json={"password": "test-pass-123"})
    assert r.status_code == 429


def test_health_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["version"] == __import__("app").__version__


def test_crud_requires_auth(client):
    r = client.get("/api/configs")
    assert r.status_code == 401


def test_config_crud_flow(auth_client):
    r = auth_client.post("/api/configs", json={"name": "reza", "quota_gb": 10, "expires_days": 30})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["uuid"] and d["link"].startswith("vless://")
    assert "type=ws" in d["link"] and "ed=2560" in d["link"]
    assert d["qr"].startswith("data:image/png;base64,")

    # duplicate
    r2 = auth_client.post("/api/configs", json={"name": "reza"})
    assert r2.status_code == 409

    # bad name
    r3 = auth_client.post("/api/configs", json={"name": "x"})
    assert r3.status_code == 400

    # patch enable off
    cid = d["id"]
    r4 = auth_client.patch(f"/api/configs/{cid}", json={"enabled": False})
    assert r4.json()["data"]["enabled"] is False

    # reset
    r5 = auth_client.post(f"/api/configs/{cid}/reset?new_uuid=true")
    assert r5.json()["data"]["used_bytes"] == 0

    # delete
    r6 = auth_client.delete(f"/api/configs/{cid}")
    assert r6.status_code == 200


def test_config_link_uses_public_host(auth_client):
    r = auth_client.post("/api/configs", json={"name": "host-test"})
    link = r.json()["data"]["link"]
    # testclient sends host=testserver â†’ non-TLS â†’ port must appear
    assert "testserver" in link


def test_sub_raw_base64(auth_client):
    r = auth_client.post("/api/configs", json={"name": "sub-user"})
    uid = r.json()["data"]["uuid"]
    s = auth_client.get(f"/sub/{uid}", headers={"user-agent": "okhttp/4.12"})
    assert s.status_code == 200
    decoded = base64.b64decode(s.text).decode()
    assert decoded.startswith("vless://")
    assert "subscription-userinfo" in {k.lower() for k in s.headers}


def test_sub_html_for_browser(auth_client):
    r = auth_client.post("/api/configs", json={"name": "page-user"})
    uid = r.json()["data"]["uuid"]
    s = auth_client.get(f"/sub/{uid}", headers={
        "user-agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/120"})
    assert "text/html" in s.headers["content-type"]
    assert "vless://" in s.text
    assert "مصرف" in s.text


def test_sub_singbox(auth_client):
    r = auth_client.post("/api/configs", json={"name": "sb-user"})
    uid = r.json()["data"]["uuid"]
    s = auth_client.get(f"/sub/{uid}?fmt=singbox")
    doc = s.json()
    ob = doc["outbounds"][0]
    assert ob["type"] == "vless"
    assert ob["transport"]["early_data_header_name"] == "Sec-WebSocket-Protocol"
    assert ob["transport"]["max_early_data"] == 2560


def test_sub_clash(auth_client):
    r = auth_client.post("/api/configs", json={"name": "cl-user"})
    uid = r.json()["data"]["uuid"]
    s = auth_client.get(f"/sub/{uid}?fmt=clash")
    assert "type: vless" in s.text
    assert "url-test" in s.text


def test_disabled_config_sub_404(auth_client):
    r = auth_client.post("/api/configs", json={"name": "off-sub"})
    d = r.json()["data"]
    auth_client.patch(f"/api/configs/{d['id']}", json={"enabled": False})
    s = auth_client.get(f"/sub/{d['uuid']}")
    assert s.status_code == 404


def test_groups_flow(auth_client):
    r = auth_client.post("/api/configs", json={"name": "g-member1"})
    m1 = r.json()["data"]["id"]
    r = auth_client.post("/api/configs", json={"name": "g-member2"})
    m2 = r.json()["data"]["id"]

    g = auth_client.post("/api/groups", json={"name": "family", "members": [m1, m2]})
    assert g.status_code == 200, g.text
    gd = g.json()["data"]
    assert gd["sub_path"]

    # list + url
    lst = auth_client.get("/api/groups").json()["data"]
    assert any(x["url"].endswith(gd["sub_path"]) for x in lst)

    # public group sub (raw)
    s = auth_client.get(f"/g/{gd['sub_path']}", headers={"user-agent": "okhttp/1"})
    assert s.status_code == 200
    assert base64.b64decode(s.text).decode().count("vless://") == 2

    # password-protected
    auth_client.patch(f"/api/groups/{gd['id']}", json={"password": "secret"})
    s2 = auth_client.get(f"/g/{gd['sub_path']}")
    assert s2.status_code == 401
    s3 = auth_client.get(f"/g/{gd['sub_path']}?pw=secret", headers={"user-agent": "okhttp/1"})
    assert s3.status_code == 200


def test_stats_and_live(auth_client):
    auth_client.post("/api/configs", json={"name": "st-user"})
    st = auth_client.get("/api/stats").json()["data"]
    assert st["configs"] >= 1 and st["active"] >= 1
    lv = auth_client.get("/api/live").json()["data"]
    assert isinstance(lv, list)

