# Crypto Paragraph API (alwaysdata backend)

این بک‌اند روی alwaysdata free plan اجرا می‌شود.

## ویژگی‌ها
- ✅ API برای مدیریت مانیتورها
- ✅ اسکریدیولر خودکار (به‌روزرسانی هر ۲ ساعت)
- ✅ بات تلگرام (ارسال و ویرایش خودکار پیام)
- ✅ دیتابیس SQLite (بدون نیاز به نصب)
- ✅ CORS فعال (دسترسی از داشبورد Vercel)

## نصب روی alwaysdata

1. **ساخت سایت Python:**
   - وارد پنل alwaysdata شوید
   - `Sites` → `Add a website`
   - `Python` → `Flask` یا `Passenger`
   - دامنه رایگان: `yourname.alwaysdata.net`

2. **آپلود فایل‌ها:**
   - از FTP/Sync استفاده کنید یا فایل‌ها را کپی کنید

3. **تنظیم Environment Variables:**
   - `TELEGRAM_BOT_TOKEN` ← توکن بات تلگرام
   - `PORT` ← پورت سرور (معمولاً 8080)
   - `FLASK_ENV` ← production

4. **نصب پکیج‌ها:**
   ```bash
   pip install -r requirements.txt
   ```

5. **راه‌اندازی:**
   ```
   python main.py
   ```

## API Endpoints

| Method | Path | توضیح |
|--------|------|--------|
| GET | `/api/monitors` | لیست مانیتورها با قیمت فعلی |
| POST | `/api/monitors` | افزودن مانیتور جدید |
| PUT | `/api/monitors/:id` | ویرایش مانیتور |
| DELETE | `/api/monitors/:id` | حذف مانیتور |
| POST | `/api/toggle/:id` | فعال/غیرفعال کردن |
| GET | `/api/prices` | قیمت‌های فعلی |
| POST | `/api/prices/refresh` | به‌روزرسانی دستی |
| GET | `/api/message` | پیش‌نمایش پیام تلگرام |
| POST | `/api/telegram/update` | ارسال پیام به تلگرام |
| GET/POST | `/api/settings` | تنظیمات |
| POST | `/api/bot/start` | شروع اسکریدیولر |
| POST | `/api/bot/stop` | توقف اسکریدیولر |
| GET | `/api/bot/status` | وضعیت بات |

## منابع قیمت
- **Bitpin:** USDT_IRT, TRX_IRT, PAXG_USDT
- **Frankfurter:** XAU (طلا), GBP (پوند), CNY (یوان)

## مانیتورهای پیشفرض
1. تتر تومان
2. ترون تومان
3. طلای دیجیتال (PAXG)
4. انس طلا
5. پوند انگلیس
6. یوان چین
