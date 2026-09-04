# مرجع API — NeonPanel

> تولیدشده از روی کد (FastAPI/OpenAPI). خروجی کامل: `GET /openapi.json` + Swagger UI در `/docs`

## قواعد عمومی

- همهٔ پاسخ‌ها: موفق `{"ok": true, "data": {...}}` / خطا `{"ok": false, "code": "...", "msg_fa": "..."}`
- احراز هویت: `Authorization: Bearer <jwt>` (به‌جز موارد «عمومی»)
- کدهای خطا: `BAD_CRED, LOCKED, NO_AUTH, NOT_FOUND, DUPLICATE, BAD_INPUT, XRAY_FAIL, SUB_GONE`

## کتاب curl

```bash
BASE="http://127.0.0.1:8080"

# سلامت (عمومی)
curl -s $BASE/api/health

# لاگین
curl -s -X POST $BASE/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"RXpanel","password":"<ADMIN_PASS>"}'
# => {"ok":true,"data":{"access":"...","refresh":"..."}}

A="<access-jwt>"; R="<refresh-jwt>"

# رفرش
curl -s -X POST $BASE/api/auth/refresh \
  -H 'Content-Type: application/json' -d "{\"refresh\":\"$R\"}"

# تغییر پسورد (حداقل ۸ کاراکتر)
curl -s -X POST $BASE/api/auth/change-pass \
  -H "Authorization: Bearer $A" -H 'Content-Type: application/json' \
  -d '{"old":"<ADMIN_PASS>","new":"Passw0rd-jadid"}'

# لیست یوزرها + جست‌وجو + صفحه‌بندی
curl -s "$BASE/api/users?page=1&per=20&q=reza" -H "Authorization: Bearer $A"

# ساخت یوزر (۳۰ گیگ، ۳۰ روزه)
curl -s -X POST $BASE/api/users -H "Authorization: Bearer $A" \
  -H 'Content-Type: application/json' \
  -d '{"name":"reza-01","quota_gb":30,"expires_days":30,"enabled":true}'

# جزئیات + لینک‌ها + QR
curl -s $BASE/api/users/1 -H "Authorization: Bearer $A"

# ویرایش (قطع موقت)
curl -s -X PATCH $BASE/api/users/1 -H "Authorization: Bearer $A" \
  -H 'Content-Type: application/json' -d '{"enabled":false}'

# تمدید (۹۰ روز از امروز + ۵۰ گیگ)
curl -s -X PATCH $BASE/api/users/1 -H "Authorization: Bearer $A" \
  -H 'Content-Type: application/json' -d '{"enabled":true,"quota_gb":50,"expires_days":90}'

# ریست مصرف
curl -s -X POST $BASE/api/users/1/reset -H "Authorization: Bearer $A"

# حذف (با پاک کردن ترافیک)
curl -s -X DELETE "$BASE/api/users/1?wipe=true" -H "Authorization: Bearer $A"

# QR لینک VLESS یوزر ۱ (تصویر PNG)
curl -s "$BASE/api/users/1/qr?proto=vless" -H "Authorization: Bearer $A" -o qr.png

# ساب base64 (عمومی — توکن ساب یوزر)
curl -s $BASE/sub/<sub_token>

# ساب کلش / سینگ‌باکس / JSON
curl -s "$BASE/sub/<sub_token>?fmt=clash" -o clash.yaml
curl -s "$BASE/sub/<sub_token>?fmt=singbox" -o singbox.json
curl -si "$BASE/sub/<sub_token>?fmt=json" | head -20   # + هدر Subscription-Userinfo

# دامنه فعلی + override
curl -s $BASE/api/domain -H "Authorization: Bearer $A"
curl -s -X POST $BASE/api/domain/override -H "Authorization: Bearer $A" \
  -H 'Content-Type: application/json' -d '{"domain":"example.com"}'
curl -s -X POST $BASE/api/domain/override -H "Authorization: Bearer $A" \
  -H 'Content-Type: application/json' -d '{"domain":null}'   # حذف override

# وضعیت تانل
curl -s $BASE/api/tunnel -H "Authorization: Bearer $A"

# MTProto: وضعیت / روشن‌خاموش
curl -s $BASE/api/mtproto -H "Authorization: Bearer $A"
curl -s -X POST $BASE/api/mtproto/toggle -H "Authorization: Bearer $A" \
  -H 'Content-Type: application/json' -d '{"on":true}'

# آمار داشبورد (۷/۳۰ روز)
curl -s "$BASE/api/stats/summary?days=30" -H "Authorization: Bearer $A"

# ریلود Xray
curl -s -X POST $BASE/api/xray/reload -H "Authorization: Bearer $A"

# بکاپ / ریستور
curl -s $BASE/api/backup -H "Authorization: Bearer $A" -o backup.zip
curl -s -X POST $BASE/api/restore -H "Authorization: Bearer $A" -F "file=@backup.zip"
```

## هدرهای ساب (استاندارد v2board)

```
Subscription-Userinfo: upload=0; download=<used>; total=<quota|0>; expire=<ts|0>
```
- `total=0` یعنی نامحدود
- کلاینت‌های V2RayNG/Hiddify/Streisand پروگرس‌بار مصرف نشان می‌دهند
