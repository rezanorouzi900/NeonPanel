// js/app.js — NeonPanel, clean minimal UI. Author: OpenCode
const $=(s,r=document)=>r.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const gb=b=>b>=1024**3?(b/1024**3).toFixed(2)+' GB':(b/1024**2).toFixed(0)+' MB';
const fmtT=s=>s?new Date(s*1000).toLocaleDateString('fa-IR'):'—';

const LOGO=`<svg class="logo" viewBox="0 0 64 64" aria-hidden="true">
  <path d="M37 8 17 36h9l-4 20 21-28H34z" fill="currentColor"/>
</svg>`;

const IC={
  dash:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/></svg>',
  cfgs:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4 14h6l-1 8 9-12h-6z"/></svg>',
  groups:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3.5-6 7-6s7 2 7 6"/><circle cx="17" cy="9" r="3"/><path d="M22 21c0-3-2-5-4.5-5"/></svg>',
  set:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.5 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5c.1-.4.1-.8.1-1.2z"/></svg>',
};

const I={
  login:'ورود مدیر',pass:'رمز عبور',go:'ورود',bad:'رمز اشتباه است',
  dash:'داشبورد',cfgs:'لینک‌ها',groups:'گروه‌ها',set:'تنظیمات',out:'خروج',
  total:'کل لینک‌ها',active:'لینک فعال',online:'اتصال زنده',used:'مصرف کل',
  newc:'＋ لینک جدید',search:'جست‌وجو…',empty:'هنوز لینکی نساختی',
  name:'نام',status:'وضعیت',quota:'سقف',usedb:'مصرف',expire:'انقضا',acts:'عملیات',
  on:'فعال',off:'قطع',noexp:'نامحدود',copy:'کپی',copied:'کپی شد ✅',del:'حذف',reset:'ریست',
  askdel:'مطمئنی حذف شود؟',links:'جزئیات',sub:'ساب',
  nname:'نام لینک',nq:'سقف حجم (GB)',nd:'روزهای اعتبار',nsp:'سرعت (Mbps)',nip:'حد IP هم‌زمان',
  mk:'بساز',gname:'نام گروه',gmk:'بساز',gempty:'هنوز گروهی نساختی',gpass:'رمز (اختیاری)',
  chp:'تغییر رمز',old:'رمز فعلی',new:'رمز جدید',save:'ذخیره',
  err:'مشکلی پیش آمد',locked:'تلاش زیاد — ۱۵ دقیقه صبر کن',
};

const api=async(p,o={})=>{
  const r=await fetch(p,{...o,headers:{'Content-Type':'application/json',...(o.headers||{})}});
  const b=await r.json().catch(()=>({}));
  if(!r.ok){const e=new Error(b?.detail?.msg_fa||I.err);e.code=b?.detail?.code;throw e}
  return b.data??b;
};
const toast=(m,k='ok')=>{const e=document.createElement('div');e.className='toast '+k;e.textContent=m;document.body.appendChild(e);setTimeout(()=>e.remove(),2200)};
const modal=h=>{const b=document.createElement('div');b.className='modal-bg';b.innerHTML=`<div class="modal">${h}</div>`;b.onclick=e=>{if(e.target===b)b.remove()};document.body.appendChild(b);return b};
const copy=t=>navigator.clipboard.writeText(t).then(()=>toast(I.copied));

function shell(c){
  return `<div class="shell"><aside>
  <div class="brand">${LOGO}<b>NeonPanel</b></div>
  <nav class="nav">
    <a href="#/" data-r="dash">${IC.dash}<span>${I.dash}</span></a>
    <a href="#/cfgs" data-r="cfgs">${IC.cfgs}<span>${I.cfgs}</span></a>
    <a href="#/groups" data-r="groups">${IC.groups}<span>${I.groups}</span></a>
    <a href="#/set" data-r="set">${IC.set}<span>${I.set}</span></a>
    <a href="#/x" id="lo">${IC.set}<span>${I.out}</span></a>
  </nav><div class="foot">v3.2</div></aside><main>${c}</main></div>`;
}
const nav=()=>{const c=(location.hash.split('/')[1]||'');document.querySelectorAll('.nav a').forEach(a=>a.classList.toggle('on',a.dataset.r===c))};

// ---------- pages ----------
async function pLogin(){
  $('#app').innerHTML=`<div class="login-wrap"><div class="login-box card">
  ${LOGO}<h2>${I.login}</h2>
  <form id="f"><label>${I.pass}</label><input id="p" type="password" autofocus required>
  <button class="btn" style="width:100%;margin-top:16px">${I.go}</button></form></div></div>`;
  $('#f').onsubmit=async e=>{e.preventDefault();
    try{await api('/api/login',{method:'POST',body:JSON.stringify({password:$('#p').value})});location.hash='#/'}
    catch(ex){toast(ex.code==='LOCKED'?I.locked:I.bad,'bad')}};
}

async function pDash(){
  const [st,live,cfgs]=await Promise.all([api('/api/stats'),api('/api/live'),api('/api/configs')]);
  $('#app').innerHTML=shell(`<h1>${I.dash}</h1>
  <div class="grid">
    <div class="card stat"><div class="n">${st.active}/${st.configs}</div><div class="l">${I.total}</div></div>
    <div class="card stat"><div class="n">${st.online}</div><div class="l">${I.online}</div></div>
    <div class="card stat"><div class="n">${gb(st.total_used)}</div><div class="l">${I.used}</div></div>
    <div class="card stat"><div class="n" style="font-size:15px;word-break:break-all">${esc(cfgs.domain)}</div><div class="l">دامنه</div></div>
  </div>
  <div class="card"><h2>${I.online} · ${live.length}</h2>
    <div id="liv">
    ${live.length?live.map(l=>`<span class="orb-live"><span class="dot ok"></span>${l.uuid.slice(0,8)} · ${l.ips} IP</span>`).join(' '):`<span style="color:var(--txt-2)">اتصال فعالی نیست</span>`}
    </div>
  </div>
  <button class="btn" onclick="location.hash='#/cfgs'">${I.newc}</button>`);
  const timer=setInterval(async()=>{
    if(!document.getElementById('liv')){clearInterval(timer);return}
    try{
      const lv=await api('/api/live');
      $('#liv').innerHTML=lv.length?lv.map(l=>`<span class="orb-live"><span class="dot ok"></span>${l.uuid.slice(0,8)} · ${l.ips} IP</span>`).join(' '):`<span style="color:var(--txt-2)">اتصال فعالی نیست</span>`;
    }catch{}
  },4000);
}

function cfgForm(){
  const m=modal(`<h2>${I.newc}</h2><form id="cf">
  <label>${I.nname}</label><input id="n" required maxlength="32">
  <div class="row">
    <div><label>${I.nq}</label><input id="q" type="number" min="0" value="0"></div>
    <div><label>${I.nd}</label><input id="d" type="number" min="0" value="30"></div>
  </div>
  <div class="row">
    <div><label>${I.nsp}</label><input id="s" type="number" min="0" value="0"></div>
    <div><label>${I.nip}</label><input id="i" type="number" min="0" value="0"></div>
  </div>
  <button class="btn" style="width:100%;margin-top:16px">${I.mk}</button></form>`);
  const close=()=>m.remove();
  $('#cf').onsubmit=async e=>{e.preventDefault();
    const btn=$('#cf button');btn.disabled=true;btn.textContent='…';
    try{
      const c=await api('/api/configs',{method:'POST',body:JSON.stringify({
        name:$('#n').value,quota_gb:+$('#q').value,expires_days:+$('#d').value,
        speed_mbps:+$('#s').value,max_ips:+$('#i').value})});
      const cid=Number(c.id??c);
      close();
      toast('✅');
      await pCfgs();                  // fresh list — new row visible
      showCfg(cid);                   // then the details modal
    }catch(ex){btn.disabled=false;btn.textContent=I.mk;toast(ex.message,'bad')}
  };
}

async function showCfg(cid){
  const d=await api(`/api/configs/${cid}`);
  modal(`<h2>${esc(d.name)}</h2>
  <div class="linkbox"><code>${esc(d.link)}</code><button class="btn sm" id="cp">${I.copy}</button></div>
  <div class="qr-wrap"><img src="${d.qr}" alt="QR"></div>
  <div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap">
    <a class="btn sm ghost" style="padding:9px 15px;border-radius:11px" href="${d.sub_url}" target="_blank">${I.sub}</a>
    <button class="btn sm ghost" id="cp2">${I.copy} ${I.sub}</button>
  </div>`);
  $('#cp').onclick=()=>copy(d.link);
  $('#cp2').onclick=()=>copy(d.sub_url);
}

async function pCfgs(){
  const q=new URLSearchParams(location.hash.split('?')[1]||'').get('q')||'';
  const d=await api('/api/configs'+(q?`?q=${encodeURIComponent(q)}`:''));
  const rows=d.items.map(c=>{
    const st=!c.enabled?['off',I.off]:(c.expires_at&&c.expires_at<Date.now()/1e3)?['warn','منقضی']:(c.quota_bytes&&c.used_bytes>=c.quota_bytes)?['warn','سقف پر']:['on',I.on];
    const pct=c.quota_bytes?Math.min(100,c.used_bytes/c.quota_bytes*100):0;
    return `<tr>
    <td data-l="${I.name}"><b>${esc(c.name)}</b>${c.online_ips?` <span class="dot ok"></span>`:''}</td>
    <td data-l="${I.status}"><span class="badge ${st[0]}">${st[1]}</span></td>
    <td data-l="${I.quota}"><div class="bar"><i style="width:${pct}%"></i></div><small class="dim">${gb(c.used_bytes)} / ${c.quota_bytes?gb(c.quota_bytes):I.noexp}</small></td>
    <td data-l="${I.expire}">${fmtT(c.expires_at)}</td>
    <td data-l="${I.acts}" class="rowacts">
      <button class="btn sm ghost" data-v="${c.id}">${I.links}</button>
      <button class="btn sm ${c.enabled?'ghost':''}" data-t="${c.id}" data-e="${c.enabled?1:0}">${c.enabled?I.off:I.on}</button>
      <button class="btn sm ghost" data-r="${c.id}">${I.reset}</button>
      <button class="btn sm bad" data-d="${c.id}">${I.del}</button>
    </td></tr>`}).join('');
  $('#app').innerHTML=shell(`<h1>${I.cfgs}</h1>
  <div class="toolbar">
    <input id="q" placeholder="${I.search}" style="max-width:280px" value="${esc(q)}">
    <button class="btn" id="nw">${I.newc}</button>
  </div>
  <div class="card" style="padding:6px 14px">
  ${d.items.length?`<table><thead><tr><th>${I.name}</th><th>${I.status}</th><th>${I.quota}</th><th>${I.expire}</th><th>${I.acts}</th></tr></thead><tbody>${rows}</tbody></table>`
  :`<div class="empty"><div class="big">🔗</div>${I.empty}<br><br><button class="btn" id="nw2">${I.newc}</button></div>`}</div>`);
  requestAnimationFrame(()=>document.querySelectorAll('.bar>i').forEach(b=>b.style.transition='width .5s'));
  let tm;$('#q').oninput=e=>{clearTimeout(tm);tm=setTimeout(()=>{location.hash='#/cfgs?q='+encodeURIComponent(e.target.value);render()},350)};
  $('#nw').onclick=cfgForm;$('#nw2')?.addEventListener('click',cfgForm);
  document.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>showCfg(+b.dataset.v));
  document.querySelectorAll('[data-t]').forEach(b=>b.onclick=async()=>{try{await api(`/api/configs/${b.dataset.t}`,{method:'PATCH',body:JSON.stringify({enabled:b.dataset.e!=='1'})});render()}catch(e){toast(e.message,'bad')}});
  document.querySelectorAll('[data-r]').forEach(b=>b.onclick=async()=>{try{await api(`/api/configs/${b.dataset.r}/reset`,{method:'POST'});toast('✅');render()}catch(e){toast(e.message,'bad')}});
  document.querySelectorAll('[data-d]').forEach(b=>b.onclick=async()=>{if(!confirm(I.askdel))return;try{await api(`/api/configs/${b.dataset.d}`,{method:'DELETE'});render()}catch(e){toast(e.message,'bad')}});
}

async function pGroups(){
  const [gs,cs]=await Promise.all([api('/api/groups'),api('/api/configs')]);
  const rows=gs.map(g=>`<tr>
    <td data-l="${I.gname}"><b>${esc(g.name)}</b></td>
    <td data-l="اعضا">${g.members.length}</td>
    <td data-l="${I.sub}"><div class="linkbox sm0"><code>${esc(g.url)}</code><button class="btn sm" data-c="${esc(g.url)}${g.password?`?pw=${esc(g.password)}`:''}">${I.copy}</button></div></td>
    <td data-l="رمز">${g.password?'🔒':'—'}</td>
    <td data-l="${I.acts}" class="rowacts"><button class="btn sm bad" data-d="${g.id}">${I.del}</button></td></tr>`).join('');
  $('#app').innerHTML=shell(`<h1>${I.groups}</h1>
  <div class="card">
  ${gs.length?`<table><thead><tr><th>${I.gname}</th><th>اعضا</th><th>${I.sub}</th><th>رمز</th><th>${I.acts}</th></tr></thead><tbody>${rows}</tbody></table>`
  :`<div class="empty"><div class="big">👥</div>${I.gempty}</div>`}</div>
  <button class="btn" id="ng">＋ ${I.gmk}</button>`);
  document.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>copy(b.dataset.c));
  document.querySelectorAll('[data-d]').forEach(b=>b.onclick=async()=>{if(!confirm(I.askdel))return;try{await api(`/api/groups/${b.dataset.d}`,{method:'DELETE'});render()}catch(e){toast(e.message,'bad')}});
  $('#ng').onclick=()=>{
    const opts=cs.items.map(c=>`<label class="chk"><input type="checkbox" value="${c.id}"> ${esc(c.name)}</label>`).join('');
    modal(`<h2>${I.groups}</h2><form id="gf">
    <label>${I.gname}</label><input id="n" required maxlength="32">
    <label>${I.gpass}</label><input id="pw" type="password">
    <label style="margin:12px 0 6px">اعضا:</label>${opts||'<p class="dim">اول لینک بساز</p>'}
    <button class="btn" style="width:100%;margin-top:16px" ${opts?'':'disabled'}>${I.gmk}</button></form>`);
    $('#gf').onsubmit=async e=>{e.preventDefault();
      const members=[...document.querySelectorAll('#gf input[type=checkbox]:checked')].map(x=>+x.value);
      try{await api('/api/groups',{method:'POST',body:JSON.stringify({name:$('#n').value,members,password:$('#pw').value})});
        document.querySelector('.modal-bg')?.remove();toast('✅');render()}
      catch(ex){toast(ex.message,'bad')}};
  };
}

async function pSet(){
  $('#app').innerHTML=shell(`<h1>${I.set}</h1>
  <div class="card"><h2>${I.chp}</h2><form id="pf">
    <label>${I.old}</label><input id="o" type="password" required>
    <label>${I.new}</label><input id="n2" type="password" minlength="8" required>
    <button class="btn" style="margin-top:16px">${I.save}</button></form></div>
  <div class="card"><div style="text-align:center">${LOGO}</div>
    <p class="dim" style="text-align:center;margin-top:8px">NeonPanel v3.2 — پنل اتصال VLESS</p></div>`);
  $('#pf').onsubmit=async e=>{e.preventDefault();
    try{await api('/api/change-pass',{method:'POST',body:JSON.stringify({old:$('#o').value,new:$('#n2').value})});toast('✅')}
    catch(ex){toast(ex.message,'bad')}};
}

// ---------- router ----------
const routes={'':pDash,cfgs:pCfgs,groups:pGroups,set:pSet};
async function render(){
  const page=(location.hash.replace(/^#\/?/,'')||'').split('?')[0];
  try{
    if(page==='x'){await api('/api/logout',{method:'POST'});return location.hash='#/login'}
    if(page==='login')return await pLogin();
    const h=await fetch('/api/health');
    if(h.status===401&&!page)return location.hash='#/login';
    await (routes[page]||pDash)();nav();
  }catch(e){if(e.code==='NO_AUTH')location.hash='#/login';else if(!location.hash.startsWith('#/login'))toast(e.message,'bad')}
}
window.addEventListener('hashchange',render);
render();