# CHANGELOG

## [3.0.0] — 2026-09-04
- **بازنویسی کامل (روش px-panel)**: رلهٔ VLESS خالص پایتون روی WebSocket — بدون Xray باینری
- تک‌پروتکل VLESS؛ حذف VMess/Trojan/SS/Reality
- کانفیگ‌ها: سقف حجم + سرعت (token-bucket) + حد IP هم‌زمان + انقضا
- گروه‌های ساب (رمزدار) + شمارش بایت واقعی + اتصال زنده
- لینک px-panel: ed=2560، alpn=http/1.1، fp=chrome
- Dockerfile سبک (پایتون فقط) — دیپلوی ~۴۰ ثانیه
- ۲۵ تست شامل E2E واقعی relay (echo + هندشیک VLESS)

## [2.0.0]
- پل WS واقعی + پورت‌های داخلی + فیکس‌های v1

## [1.0.0]
- نسخهٔ اول: FastAPI + Xray + UI
