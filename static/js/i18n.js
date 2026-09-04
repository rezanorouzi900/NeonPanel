// js/i18n.js — fa/en dictionary + t() (PART 2 §9). Author: OpenCode
const I18N = {
  fa: {
    "app.title": "NeonPanel",
    "nav.dashboard": "داشبورد", "nav.users": "کاربران", "nav.mtproto": "پروکسی تلگرام",
    "nav.domain": "دامنه", "nav.settings": "تنظیمات", "nav.logout": "خروج",
    "login.title": "ورود مدیر", "login.user": "نام کاربری", "login.pass": "رمز عبور",
    "login.go": "وارد شو", "login.bad": "نام کاربری یا رمز اشتباه است",
    "login.locked": "به دلیل تلاش زیاد موقتاً قفل شدی — ۱۵ دقیقه صبر کن",
    "dash.services": "وضعیت سرویس‌ها", "dash.domain_now": "دامنه فعلی",
    "dash.users_active": "کاربران فعال", "dash.use_today": "مصرف امروز",
    "dash.quick_new": "کاربر جدید", "dash.quick_restart": "ری‌استارت Xray",
    "dash.localhost_warn": "دامنه عمومی شناسایی نشد — لینک‌ها با localhost ساخته شدند",
    "users.search": "جست‌وجو…", "users.new": "＋ کاربر جدید",
    "users.empty": "هنوز یوزری نساختی", "users.empty_cta": "بزن بساز 👇",
    "users.on": "فعال", "users.off": "قطع", "users.expired": "منقضی", "users.quota_full": "سقف پر",
    "users.copy_link": "کپی لینک", "users.copied": "کپی شد ✅",
    "users.qr": "کد QR", "users.sub": "سابسکریپشن", "users.renew": "تمدید",
    "users.delete": "حذف", "users.delete_ask": "مطمئنی حذف شود؟",
    "users.reset_use": "ریست مصرف", "users.name": "نام", "users.status": "وضعیت",
    "users.quota": "حجم", "users.expire": "انقضا", "users.actions": "عملیات",
    "users.links": "لینک‌ها", "users.details": "جزئیات",
    "users.open_client": "باز کردن در کلاینت", "users.client_missing": "اول اپ را نصب کن",
    "users.new_name": "نام کاربر", "users.new_quota": "سقف حجم (گیگ — ۰ = نامحدود)",
    "users.new_days": "روزهای انقضا (۰ = بدون انقضا)", "users.create": "بساز",
    "users.traffic": "ترافیک", "users.day": "روز", "users.up": "آپلود", "users.down": "دانلود",
    "sub.how": "لینک زیر را در اپ وارد کن", "sub.copy": "کپی ساب",
    "err.retry": "تلاش مجدد", "err.net": "اینترنت را چک کن", "err.generic": "مشکلی پیش آمد",
    "domain.source": "منبع تشخیص", "domain.override": "ثبت دامنه دستی",
    "domain.clear": "حذف دستی (خودکار شود)", "domain.set": "ثبت",
    "domain.now": "دامنه فعلی", "domain.at": "زمان تشخیص",
    "mt.on": "روشن", "mt.off": "خاموش", "mt.toggle": "روشن/خاموش",
    "mt.how1": "تلگرام را باز کن", "mt.how2": "روی لینک بزن", "mt.how3": "وصل شو ✅",
    "mt.links": "لینک‌ها", "mt.simple": "ساده", "mt.cloaked": "مخفی‌شونده",
    "mt.port": "پورت", "mt.host": "هاست پیشنهادی",
    "set.lang": "زبان", "set.backup": "دانلود بکاپ", "set.restore": "بازگردانی",
    "set.chpass": "تغییر رمز", "set.old": "رمز فعلی", "set.new": "رمز جدید",
    "set.version": "نسخه", "set.restore_ask": "مطمئنی؟ داده فعلی جایگزین می‌شود",
    "tunnel.state": "وضعیت تانل", "tunnel.url": "آدرس تانل", "tunnel.none": "خاموش",
    "chart.month": "مصرف ۳۰ روز", "chart.nodata": "داده‌ای نیست",
    "u.gb": "گیگ", "u.unlimited": "نامحدود", "u.noexpire": "بدون انقضا",
  },
  en: {
    "app.title": "NeonPanel",
    "nav.dashboard": "Dashboard", "nav.users": "Users", "nav.mtproto": "Telegram proxy",
    "nav.domain": "Domain", "nav.settings": "Settings", "nav.logout": "Logout",
    "login.title": "Admin login", "login.user": "Username", "login.pass": "Password",
    "login.go": "Sign in", "login.bad": "Wrong username or password",
    "login.locked": "Too many attempts — locked for 15 minutes",
    "dash.services": "Services", "dash.domain_now": "Current domain",
    "dash.users_active": "Active users", "dash.use_today": "Today's usage",
    "dash.quick_new": "New user", "dash.quick_restart": "Restart Xray",
    "dash.localhost_warn": "No public domain detected — links use localhost",
    "users.search": "Search…", "users.new": "+ New user",
    "users.empty": "No users yet", "users.empty_cta": "Create one 👇",
    "users.on": "Active", "users.off": "Disabled", "users.expired": "Expired",
    "users.quota_full": "Quota full", "users.copy_link": "Copy link",
    "users.copied": "Copied ✅", "users.qr": "QR code", "users.sub": "Subscription",
    "users.renew": "Renew", "users.delete": "Delete",
    "users.delete_ask": "Are you sure?", "users.reset_use": "Reset usage",
    "users.name": "Name", "users.status": "Status", "users.quota": "Quota",
    "users.expire": "Expires", "users.actions": "Actions", "users.links": "Links",
    "users.details": "Details", "users.open_client": "Open in app",
    "users.client_missing": "Install the app first", "users.new_name": "User name",
    "users.new_quota": "Quota GB (0 = unlimited)", "users.new_days": "Expiry days (0 = none)",
    "users.create": "Create", "users.traffic": "Traffic", "users.day": "Day",
    "users.up": "Upload", "users.down": "Download", "sub.how": "Paste this URL into your app",
    "sub.copy": "Copy sub", "err.retry": "Retry", "err.net": "Check your connection",
    "err.generic": "Something went wrong", "domain.source": "Detected from",
    "domain.override": "Set manual domain", "domain.clear": "Clear (go auto)",
    "domain.set": "Set", "domain.now": "Current domain", "domain.at": "Detected at",
    "mt.on": "On", "mt.off": "Off", "mt.toggle": "Toggle",
    "mt.how1": "Open Telegram", "mt.how2": "Tap the link", "mt.how3": "Connect ✅",
    "mt.links": "Links", "mt.simple": "Simple", "mt.cloaked": "Cloaked",
    "mt.port": "Port", "mt.host": "Suggested host", "set.lang": "Language",
    "set.backup": "Download backup", "set.restore": "Restore",
    "set.chpass": "Change password", "set.old": "Current password",
    "set.new": "New password", "set.version": "Version",
    "set.restore_ask": "Are you sure? Current data will be replaced",
    "tunnel.state": "Tunnel status", "tunnel.url": "Tunnel URL", "tunnel.none": "Off",
    "chart.month": "30-day usage", "chart.nodata": "No data",
    "u.gb": "GB", "u.unlimited": "unlimited", "u.noexpire": "no expiry",
  },
};

let LANG = localStorage.getItem("lang") || "fa";

function t(key) {
  return (I18N[LANG] && I18N[LANG][key]) || I18N.fa[key] || key;
}

function setLang(l) {
  LANG = l;
  localStorage.setItem("lang", l);
  document.documentElement.lang = l;
  document.documentElement.dir = l === "fa" ? "rtl" : "ltr";
  render(); // full re-render of current route
}
