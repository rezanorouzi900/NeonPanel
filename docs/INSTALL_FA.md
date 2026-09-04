# نصب NeonPanel — قدم‌به‌قدم (فارسی)

## ۱) Railway (ساده‌ترین — ۳ دقیقه)

1. حساب [Railway](https://railway.app) داشته باش (با گیت‌هاب وارد شو)
2. دکمهٔ Deploy در README را بزن، یا: **New Project → Deploy from GitHub repo**
3. ریپوی `NeonPanel` را انتخاب کن
4. در **Variables** این‌ها را ست کن:

| متغیر | مقدار | توضیح |
|---|---|---|
| `ADMIN_USER` | مثلاً `RXpanel` | یوزرنیم ادمین |
| `ADMIN_PASS` | یک رمز قوی | یا خالی = رندوم در لاگ |
| `SS_PORT` | `8388` | یا `0` برای غیرفعال |

5. صبر کن بیلد تمام شود (حدود ۲ دقیقه)
6. در **Settings → Networking → Generate Domain** دامنه بساز
7. تمام! پنل خودش دامنهٔ Railway را می‌شناسد — هیچ‌جا تایپش نکن

> نکته: Reality پورت 8443 و MTProto پورت 4433 روی Railway فقط با TCP Proxy کار می‌کنند؛ WS ساب و لینک‌ها بدون تنظیم کار می‌کنند.

## ۲) Docker (VPS یا لوکال)

```bash
git clone https://github.com/rezanorouzi900/NeonPanel
cd NeonPanel
cp .env.example .env
nano .env            # ADMIN_USER/ADMIN_PASS را ست کن
docker compose up -d
```

- پنل: `http://SERVER_IP:8080`
- بهتر: پشت Cloudflare یا ریورس‌پروکسی با TLS بگذار
- برای تانل کلودفلر: `CF_MODE=token` + `CF_TUNNEL_TOKEN` + `docker compose --profile tunnel up`

## ۳) اجرای لوکال (توسعه)

```bash
./scripts/install.sh     # venv + نیازمندی‌ها + دانلود xray
source .venv/bin/activate
python -m app.main       # http://localhost:8080
```

تست: `pytest -q --cov=app`

## ۴) بعد از نصب — ۳ قدم

1. **ورود**: با `ADMIN_USER`/`ADMIN_PASS` (اگر ADMIN_PASS خالی بود، رمز رندوم در لاگ اولین اجراست — `docker compose logs panel | grep "رمز"`)
2. **کاربر بساز**: داشبورد ← «کاربر جدید» (نام، سقف حجم، روزهای انقضا)
3. **لینک بده**: صفحهٔ کاربر ← تب VLESS ← «کپی لینک» یا کد QR — یا کل ساب را بده

## ۵) بکاپ و ریستور

- بکاپ: تنظیمات ← «دانلود بکاپ» (zip شامل دیتابیس + سکرت‌ها)
- ریستور: تنظیمات ← «بازگردانی» (فایل zip همان فرمت)

## عیب‌یابی

جدول کامل در `docs/NETWORK.md` بخش «عیب‌یابی».
