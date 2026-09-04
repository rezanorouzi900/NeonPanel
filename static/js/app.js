// js/app.js — router + fetch wrapper (auto JWT refresh) + 8 pages. Author: OpenCode

// ---------- tiny helpers ----------
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtGB = (b) => b >= 1024 ** 3 ? (b / 1024 ** 3).toFixed(1) + " " + t("u.gb") : (b / 1024 ** 2).toFixed(0) + " MB";
const fmtDate = (d) => d ? new Date(d).toLocaleDateString(LANG === "fa" ? "fa-IR" : "en-US") : "—";

// ---------- auth store (memory + sessionStorage, no secrets in localStorage) ----------
const Auth = {
  get access() { return sessionStorage.getItem("acc") || ""; },
  get refresh() { return sessionStorage.getItem("ref") || ""; },
  set(a, r) { sessionStorage.setItem("acc", a); sessionStorage.setItem("ref", r); if (a) localStorage.setItem("rem", "1"); },
  clear() { sessionStorage.clear(); localStorage.removeItem("rem"); },
  remembered() { return localStorage.getItem("rem") === "1" && this.refresh; },
};

// ---------- fetch wrapper: 401 → refresh → retry → login ----------
async function api(path, opts = {}, _retried = false) {
  const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  if (Auth.access) headers["Authorization"] = "Bearer " + Auth.access;
  let resp;
  try {
    resp = await fetch(path, { ...opts, headers });
  } catch {
    toast(t("err.net"), "bad");
    throw new Error("net");
  }
  if (resp.status === 401 && !_retried && Auth.refresh) {
    const r = await fetch("/api/auth/refresh", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: Auth.refresh }),
    });
    if (r.ok) {
      const j = await r.json();
      Auth.set(j.data.access, Auth.refresh);
      return api(path, opts, true);
    }
    Auth.clear();
    location.hash = "#/login";
    throw new Error("auth");
  }
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = body.detail || body;
    const msg = detail.msg_fa || detail.msg || t("err.generic");
    const e = new Error(msg);
    e.code = detail.code;
    e.status = resp.status;
    throw e;
  }
  return body.data !== undefined ? body.data : body;
}

// ---------- toast + modal ----------
function toast(msg, kind = "ok") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

function modal(html) {
  const bg = document.createElement("div");
  bg.className = "modal-bg";
  bg.innerHTML = `<div class="card modal">${html}</div>`;
  bg.addEventListener("click", e => { if (e.target === bg) bg.remove(); });
  document.body.appendChild(bg);
  return bg;
}

function errModal(e) {
  const bg = modal(`
    <h2>${esc(e.message || t("err.generic"))}</h2>
    <p style="color:var(--txt-1);font-size:13px;margin:10px 0 16px;direction:rtl;text-align:right">${esc(e.message || t("err.generic"))}</p>
    <button class="btn" onclick="this.closest('.modal-bg').remove();location.reload()">${t("err.retry")}</button>
  `);
  return bg;
}

function copy(text) {
  navigator.clipboard.writeText(text).then(() => toast(t("users.copied")), () => {});
}

// ---------- icons (inline SVG sprite) ----------
const ICONS = {
  dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3.5-6 7-6s7 2 7 6"/><path d="M16 3.5a4 4 0 0 1 0 7.4M17 15c3 .4 5 2.4 5 6"/></svg>',
  mtproto: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 4L3 11l6 2 2 6 4-6 6-2-4-5z"/></svg>',
  domain: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.5 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5c.1-.4.1-.8.1-1.2z"/></svg>',
};

// ---------- shell ----------
function shell(content) {
  const nav = [
    ["dashboard", "#/dashboard"], ["users", "#/users"], ["mtproto", "#/mtproto"],
    ["domain", "#/domain"], ["settings", "#/settings"],
  ];
  return `
  <div class="shell">
    <aside>
      <div class="brand">${t("app.title")}</div>
      <nav class="nav">
        ${nav.map(([k, h]) => `<a href="${h}" data-r="${k}">${ICONS[k]}<span>${t("nav." + k)}</span></a>`).join("")}
        <a href="#/login" id="logout">${ICONS.settings.replace("settings", "x")}<span>${t("nav.logout")}</span></a>
      </nav>
    </aside>
    <main>${content}</main>
  </div>`;
}

function setActiveNav() {
  const cur = location.hash.split("/")[1] || "dashboard";
  document.querySelectorAll(".nav a").forEach(a => a.classList.toggle("active", a.dataset.r === cur));
}

// ---------- pages ----------
async function pageLogin() {
  $("#app").innerHTML = `
  <div class="login-wrap"><div class="card login-box">
    <div class="brand">${t("app.title")}</div>
    <h2 style="text-align:center">${t("login.title")}</h2>
    <form id="f">
      <label>${t("login.user")}</label><input id="u" autocomplete="username" required>
      <label>${t("login.pass")}</label><input id="p" type="password" autocomplete="current-password" required>
      <label style="display:flex;align-items:center;gap:8px;margin-top:14px">
        <input type="checkbox" id="rem" style="width:auto" ${Auth.remembered() ? "checked" : ""}>
        <span style="color:var(--txt-0)">${t("login.go")}</span>
      </label>
      <button class="btn" style="width:100%;margin-top:14px" type="submit">${t("login.go")}</button>
    </form>
  </div></div>`;
  $("#f").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const d = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: $("#u").value, password: $("#p").value }),
      });
      Auth.set(d.access, d.refresh);
      location.hash = "#/dashboard";
    } catch (ex) {
      toast(ex.code === "LOCKED" ? t("login.locked") : t("login.bad"), "bad");
    }
  };
}

async function pageDashboard() {
  const [health, stats, domain] = await Promise.all([
    api("/api/health"), api("/api/stats/summary"), api("/api/domain"),
  ]);
  const isLocal = domain.domain.startsWith("localhost");
  $("#app").innerHTML = shell(`
    <h1>${t("nav.dashboard")}</h1>
    ${isLocal ? `<div class="banner-warn">${t("dash.localhost_warn")}</div>` : ""}
    <div class="grid">
      <div class="card stat"><div class="num">${health.active_users ?? stats.active_users}/${stats.total_users}</div><div class="lbl">${t("dash.users_active")}</div></div>
      <div class="card stat"><div class="num">${fmtGB(stats.today_bytes)}</div><div class="lbl">${t("dash.use_today")}</div></div>
      <div class="card stat"><div class="num" style="font-size:16px;word-break:break-all">${esc(domain.domain)}</div><div class="lbl">${t("dash.domain_now")}</div></div>
    </div>
    <div class="card"><h2>${t("dash.services")}</h2>
      <div style="display:flex;gap:24px;flex-wrap:wrap;font-size:14px">
        <span><i class="light ${health.xray}"></i>Xray</span>
        <span><i class="light ${health.tunnel}"></i>Tunnel</span>
        <span><i class="light ${health.mtproto}"></i>MTProto</span>
        <span style="color:var(--txt-1)">uptime: ${Math.floor(health.uptime / 60)}m</span>
      </div>
    </div>
    <div class="card"><h2>${t("chart.month")}</h2><canvas id="chart" height="90"></canvas><div id="chart-fallback"></div></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn" onclick="location.hash='#/users'">${t("dash.quick_new")}</button>
      <button class="btn ghost" id="rx">${t("dash.quick_restart")}</button>
    </div>
  `);
  $("#rx").onclick = async () => {
    try { await api("/api/xray/reload", { method: "POST" }); toast(t("users.copied").replace("کپی شد ✅", "OK ✅")); }
    catch (e) { toast(e.message, "bad"); }
  };
  loadChart();
}

async function loadChart() {
  const el = $("#chart");
  const fallback = $("#chart-fallback");
  try {
    // lazy-load Chart.js from CDN only on dashboard
    if (!window.Chart) {
      await new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js";
        s.onload = res; s.onerror = rej;
        document.head.appendChild(s);
        setTimeout(rej, 4000);
      });
    }
    const stats = await api("/api/stats/summary");
    const days = stats.daily || [];
    new Chart(el, {
      type: "line",
      data: {
        labels: days.map(d => d.day),
        datasets: [{ data: days.map(d => +(d.bytes / 1024 ** 3).toFixed(2)), borderColor: "#22d3ee", fill: true, backgroundColor: "rgba(34,211,238,.15)", tension: .35 }],
      },
      options: { plugins: { legend: { display: false } }, scales: { y: { grid: { color: "#1e293b" } }, x: { grid: { display: false } } } },
    });
  } catch {
    el.remove();
    if (fallback) fallback.innerHTML = `<div class="empty">${t("chart.nodata")}</div>`;
  }
}

async function pageUsers() {
  const q = new URLSearchParams(location.hash.split("?")[1] || "").get("q") || "";
  const data = await api("/api/users?" + new URLSearchParams({ page: 1, per: 100, q }));
  const rows = (data.items || []).map(u => {
    const pct = u.quota_gb > 0 ? Math.min(100, u.used_bytes / (u.quota_gb * 1024 ** 3) * 100) : 0;
    const badge = !u.enabled ? ["off", "users.off"] : (u.expires_at && new Date(u.expires_at) < new Date()) ? ["warn", "users.expired"] : ["on", "users.on"];
    return `<tr>
      <td data-l="${t("users.name")}"><a href="#/users/${u.id}" style="font-weight:700">${esc(u.name)}</a></td>
      <td data-l="${t("users.status")}"><span class="badge ${badge[0]}">${t(badge[1])}</span></td>
      <td data-l="${t("users.quota")}"><div class="bar"><i style="width:${pct}%"></i></div><small style="color:var(--txt-1)">${fmtGB(u.used_bytes)} / ${u.quota_gb || t("u.unlimited")}</small></td>
      <td data-l="${t("users.expire")}">${fmtDate(u.expires_at)}</td>
      <td data-l="${t("users.actions")}" style="display:flex;gap:6px;flex-wrap:wrap;border:0">
        <button class="btn small ghost" data-copy="${u.id}">${t("users.copy_link")}</button>
        <button class="btn small ghost" data-sub="${u.id}">${t("users.sub")}</button>
        <button class="btn small ${u.enabled ? "ghost" : ""}" data-tg="${u.id}" data-v="${u.enabled}">${u.enabled ? t("users.off") : t("users.on")}</button>
        <button class="btn small bad" data-del="${u.id}">${t("users.delete")}</button>
      </td>
    </tr>`;
  }).join("");
  $("#app").innerHTML = shell(`
    <h1>${t("nav.users")}</h1>
    <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap">
      <input id="q" placeholder="${t("users.search")}" style="max-width:280px" value="${esc(q)}">
      <button class="btn" id="new">${t("users.new")}</button>
    </div>
    <div class="card" style="padding:6px 12px">
      ${data.items.length ? `<table><thead><tr>
        <th>${t("users.name")}</th><th>${t("users.status")}</th><th>${t("users.quota")}</th><th>${t("users.expire")}</th><th>${t("users.actions")}</th>
      </tr></thead><tbody>${rows}</tbody></table>`
      : `<div class="empty"><div class="big">👤</div>${t("users.empty")}<br><br><button class="btn" id="new2">${t("users.empty_cta")}</button></div>`}
    </div>
  `);
  $("#q").oninput = debounce(() => { location.hash = "#/users?q=" + encodeURIComponent($("#q").value); render(true); }, 350);
  $("#new")?.addEventListener("click", () => userModal());
  $("#new2")?.addEventListener("click", () => userModal());
  document.querySelectorAll("[data-copy]").forEach(b => b.onclick = () => copyLink(b.dataset.copy));
  document.querySelectorAll("[data-sub]").forEach(b => b.onclick = () => showSub(b.dataset.sub));
  document.querySelectorAll("[data-tg]").forEach(b => b.onclick = () => toggleUser(b.dataset.tg, b.dataset.v));
  document.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
    if (!confirm(t("users.delete_ask"))) return;
    try { await api("/api/users/" + b.dataset.del, { method: "DELETE" }); toast("✅"); render(true); }
    catch (e) { toast(e.message, "bad"); }
  });
}

function debounce(fn, ms) { let t_; return (...a) => { clearTimeout(t_); t_ = setTimeout(() => fn(...a), ms); }; }

async function copyLink(id) {
  try {
    const u = await api("/api/users/" + id);
    copy(u.links.vless);
  } catch (e) { toast(e.message, "bad"); }
}

async function showSub(id) {
  const u = await api("/api/users/" + id);
  modal(`<h2>${t("users.sub")}</h2><p style="color:var(--txt-1);font-size:13px;margin:8px 0">${t("sub.how")}</p>
    <div class="linkbox"><code>${esc(u.sub_url)}</code><button class="btn small" id="cs">${t("sub.copy")}</button></div>`);
  $("#cs").onclick = () => copy(u.sub_url);
}

async function toggleUser(id, v) {
  try { await api("/api/users/" + id, { method: "PATCH", body: JSON.stringify({ enabled: v !== "true" }) }); render(true); }
  catch (e) { toast(e.message, "bad"); }
}

function userModal() {
  modal(`
    <h2>${t("users.new")}</h2>
    <form id="uf">
      <label>${t("users.new_name")}</label><input id="n" required>
      <label>${t("users.new_quota")}</label><input id="q" type="number" min="0" max="10000" value="0">
      <label>${t("users.new_days")}</label><input id="d" type="number" min="0" max="3650" value="30">
      <button class="btn" style="width:100%;margin-top:14px">${t("users.create")}</button>
    </form>`);
  $("#uf").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/api/users", { method: "POST", body: JSON.stringify({ name: $("#n").value, quota_gb: +$("#q").value, expires_days: +$("#d").value, enabled: true }) });
      document.querySelector(".modal-bg")?.remove();
      toast("✅");
      render(true);
    } catch (ex) { toast(ex.message, "bad"); }
  };
}

async function pageUserDetail(id) {
  const u = await api("/api/users/" + id);
  const protos = Object.keys(u.links);
  const deeplinks = {
    vless: `v2rayng://install-sub?url=${encodeURIComponent(u.sub_url)}`,
    vmess: `hiddify://import/${encodeURIComponent(u.sub_url)}`,
    trojan: `sing-box://import-remote-profile?url=${encodeURIComponent(u.sub_url)}`,
  };
  $("#app").innerHTML = shell(`
    <h1>${esc(u.name)}</h1>
    <div class="card">
      <div class="tabs" id="pt">${protos.map((p, i) => `<button class="${i === 0 ? "active" : ""}" data-p="${p}">${p.toUpperCase()}</button>`).join("")}</div>
      <div id="linkarea"></div>
      <div class="tabs" style="margin-top:16px" id="dq">
        <button data-d="vless">V2RayNG</button><button data-d="hiddify">Hiddify</button><button data-d="singbox">Streisand/NekoBox</button>
      </div>
      <p style="color:var(--txt-1);font-size:12px">${t("users.open_client")} — ${t("users.client_missing")}</p>
    </div>
    <div class="card"><h2>${t("users.sub")}</h2>
      <div class="linkbox"><code>${esc(u.sub_url)}</code><button class="btn small" id="cs">${t("sub.copy")}</button></div>
    </div>
    <div class="card"><h2>${t("users.traffic")}</h2><div id="tr">…</div></div>
  `);
  const renderLink = (p) => {
    const link = u.links[p];
    const qr = (u.qr || [])[protos.indexOf(p)] || "";
    $("#linkarea").innerHTML = `
      <div class="linkbox"><code>${esc(link)}</code>
        <button class="btn small" data-c>${t("users.copy_link")}</button></div>
      <div class="qr-wrap">${qr ? `<img src="${qr}" alt="QR">` : `<img src="/api/users/${id}/qr?proto=${p}" alt="QR">`}</div>`;
    $("#linkarea [data-c]").onclick = () => copy(link);
  };
  renderLink(protos[0]);
  $("#pt").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $("#pt").querySelectorAll("button").forEach(x => x.classList.toggle("active", x === b));
    renderLink(b.dataset.p);
  };
  $("#dq").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const map = { vless: "v2rayng://", hiddify: "hiddify://", singbox: "sing-box://" };
    location.href = map[b.dataset.d] + "import/" + encodeURIComponent(u.sub_url);
  };
  $("#cs").onclick = () => copy(u.sub_url);
}

async function pageMtproto() {
  const st = await api("/api/mtproto");
  $("#app").innerHTML = shell(`
    <h1>${t("nav.mtproto")}</h1>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
        <h2 style="margin:0"><i class="light ${st.enabled ? "up" : "off"}"></i>${st.enabled ? t("mt.on") : t("mt.off")}</h2>
        <button class="btn ${st.enabled ? "bad" : ""}" id="tg">${t("mt.toggle")}</button>
      </div>
      <p style="color:var(--txt-1);margin-top:8px;font-size:13px">${t("mt.port")}: <b>${st.port}</b> — ${t("mt.host")}: <b>${esc((st.links.simple || "").split("server=")[1]?.split("&")[0] || "—")}</b></p>
    </div>
    ${st.enabled ? `
    <div class="card"><h2>${t("mt.links")}</h2>
      <p style="color:var(--txt-1);font-size:13px">${t("mt.simple")}</p>
      <div class="linkbox"><code>${esc(st.links.simple)}</code><button class="btn small" data-l="${esc(st.links.simple)}">${t("users.copy_link")}</button></div>
      <p style="color:var(--txt-1);font-size:13px;margin-top:10px">${t("mt.cloaked")}</p>
      <div class="linkbox"><code>${esc(st.links.cloaked)}</code><button class="btn small" data-l="${esc(st.links.cloaked)}">${t("users.copy_link")}</button></div>
    </div>
    <div class="card"><h2>${t("mt.how1")} → ${t("mt.how2")} → ${t("mt.how3")}</h2></div>` : ""}
  `);
  $("#tg").onclick = async () => {
    try { await api("/api/mtproto/toggle", { method: "POST", body: JSON.stringify({ on: !st.enabled }) }); render(true); }
    catch (e) { toast(e.message, "bad"); }
  };
  document.querySelectorAll("[data-l]").forEach(b => b.onclick = () => copy(b.dataset.l));
}

async function pageDomain() {
  const [d, tun] = await Promise.all([api("/api/domain"), api("/api/tunnel")]);
  $("#app").innerHTML = shell(`
    <h1>${t("nav.domain")}</h1>
    <div class="card">
      <h2>${t("domain.now")}</h2>
      <div style="font-size:18px;font-weight:700;color:var(--neon-1);word-break:break-all">${esc(d.domain)}</div>
      <p style="color:var(--txt-1);font-size:13px;margin-top:8px">${t("domain.source")}: ${esc(d.source)}</p>
    </div>
    <div class="card"><h2>${t("domain.override")}</h2>
      <form id="df" style="display:flex;gap:10px;flex-wrap:wrap">
        <input id="nd" placeholder="example.com" style="flex:1;min-width:180px">
        <button class="btn">${t("domain.set")}</button>
        <button class="btn ghost" type="button" id="clr">${t("domain.clear")}</button>
      </form>
    </div>
    <div class="card"><h2>${t("tunnel.state")}</h2>
      <p><i class="light ${tun.up ? "up" : "off"}"></i>${tun.mode !== "off" ? (tun.up ? t("mt.on") : t("mt.off")) : t("tunnel.none")}</p>
      ${tun.url ? `<p style="margin-top:8px">${t("tunnel.url")}: <code style="color:var(--neon-1)">${esc(tun.url)}</code></p>` : ""}
    </div>
  `);
  $("#df").onsubmit = async (e) => {
    e.preventDefault();
    try { await api("/api/domain/override", { method: "POST", body: JSON.stringify({ domain: $("#nd").value }) }); toast("✅"); render(true); }
    catch (ex) { toast(ex.message, "bad"); }
  };
  $("#clr").onclick = async () => {
    try { await api("/api/domain/override", { method: "POST", body: JSON.stringify({ domain: null }) }); toast("✅"); render(true); }
    catch (e) { toast(e.message, "bad"); }
  };
}

async function pageSettings() {
  const health = await api("/api/health");
  $("#app").innerHTML = shell(`
    <h1>${t("nav.settings")}</h1>
    <div class="card"><h2>${t("set.lang")}</h2>
      <select id="lang" style="max-width:200px">
        <option value="fa" ${LANG === "fa" ? "selected" : ""}>فارسی</option>
        <option value="en" ${LANG === "en" ? "selected" : ""}>English</option>
      </select>
    </div>
    <div class="card"><h2>${t("set.chpass")}</h2>
      <form id="pf">
        <label>${t("set.old")}</label><input id="o" type="password" required>
        <label>${t("set.new")}</label><input id="n2" type="password" minlength="8" required>
        <button class="btn" style="margin-top:14px">${t("set.chpass")}</button>
      </form>
    </div>
    <div class="card"><h2>${t("set.backup")}</h2>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn ghost" id="bk">${t("set.backup")}</button>
        <label class="btn ghost" style="display:inline-block">${t("set.restore")}
          <input type="file" id="rs" accept=".zip" hidden></label>
      </div>
    </div>
    <div class="card"><h2>${t("set.version")}</h2><p style="color:var(--neon-1);font-weight:700">${esc(health.version)}</p></div>
  `);
  $("#lang").onchange = () => setLang($("#lang").value);
  $("#pf").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/api/auth/change-pass", { method: "POST", body: JSON.stringify({ old: $("#o").value, new: $("#n2").value }) });
      toast("✅");
    } catch (ex) { toast(ex.message, "bad"); }
  };
  $("#bk").onclick = () => { window.open("/api/backup", "_self"); };
  $("#rs").onchange = async (e) => {
    if (!confirm(t("set.restore_ask"))) { e.target.value = ""; return; }
    const fd = new FormData();
    fd.append("file", e.target.files[0]);
    try {
      const r = await fetch("/api/restore", { method: "POST", headers: { Authorization: "Bearer " + Auth.access }, body: fd });
      if (!r.ok) throw new Error((await r.json()).detail?.msg_fa || "restore failed");
      toast("✅"); render(true);
    } catch (ex) { toast(ex.message, "bad"); }
  };
}

// ---------- router ----------
const routes = {
  "": pageDashboard, "login": pageLogin, "dashboard": pageDashboard,
  "users": pageUsers, "mtproto": pageMtproto, "domain": pageDomain, "settings": pageSettings,
};

async function render(keepScroll = false) {
  const raw = location.hash.replace(/^#\/?/, "") || "dashboard";
  const [path] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  const page = parts[0] || "dashboard";
  try {
    if (page === "users" && parts[1]) {
      if (!Auth.access && !Auth.remembered()) return (location.hash = "#/login");
      await pageUserDetail(parts[1]);
    } else if (routes[page]) {
      const needAuth = page !== "login";
      if (needAuth && !Auth.access && !Auth.remembered()) return (location.hash = "#/login");
      await routes[page]();
    } else {
      location.hash = "#/dashboard";
    }
    setActiveNav();
  } catch (e) {
    if (e.message !== "auth" && e.message !== "net") errModal(e);
  }
}

window.addEventListener("hashchange", () => render());
$("#logout")?.addEventListener("click", () => { Auth.clear(); });

document.addEventListener("click", (e) => {
  if (e.target.closest("#logout")) { Auth.clear(); location.hash = "#/login"; }
});

document.documentElement.lang = LANG;
document.documentElement.dir = LANG === "fa" ? "rtl" : "ltr";
render();
