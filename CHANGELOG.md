# CHANGELOG

## [1.0.0] — 2026-09-04

### Added
- پنل کامل FastAPI + SQLite (SQLModel) با JWT + bcrypt
- ۴ پروتکل: VLESS/VMess/Trojan (WS) + Shadowsocks + Reality
- تشخیص خودکار دامنه (۶ شاخه) + override دستی
- ساب ۴ فرمت (base64/Clash/Sing-box/JSON) + هدر `Subscription-Userinfo`
- اکانتینگ ترافیک (Xray Stats gRPC، پولینگ ۶۰ ثانیه)
- MTProto (پروکسی تلگرام) با toggle و لینک dd/ee
- تانل کلودفلار (token/quick) + نمایش وضعیت
- فرانت SPA تک‌صفحه‌ای: ۸ صفحه، تم تیره/نئونی، فارسی/انگلیسی، موبایل‌فرست
- بکاپ/ریستور zip با rollback خودکار
- Docker چندمرحله‌ای + docker-compose + railway.toml
- CI: ruff + pytest (کاورج ≥70٪) + Docker smoke
- داک کامل: README فارسی/انگلیسی + INSTALL + API + NETWORK + i18n

### Security
- ریت‌لیمیت لاگین (۵/۵ دقیقه → قفل ۱۵ دقیقه) و ساب (۳۰/دقیقه)
- هدرهای امنیتی + CSP + CORS پیش‌فرض بسته
- سکرت‌ها فقط از env؛ هیچ توکنی در کد/داک/لاگ
