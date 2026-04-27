# دليل النشر على VPS Ubuntu

## ⚠️ قبل البدء — تجديد التوكنات

التوكنات اللي تم مشاركتها في المحادثة مكشوفة. لازم تتجدد قبل النشر:

1. **Telegram Bot Token:**
   - افتح `@BotFather` في تيليجرام
   - أرسل `/revoke` → اختر بوتك → احصل على توكن جديد

2. **Notion Integration Token:**
   - افتح https://www.notion.so/my-integrations
   - افتح الـ integration → اضغط "Show" بجانب Internal Integration Token → "Rotate"
   - تأكد إن الـ integration مشارك على جدول Family Bot:
     - افتح الجدول في Notion → ⋯ → Connections → Add the integration

---

## خطوات النشر

### 1. تجهيز VPS

```bash
# تحديث النظام
sudo apt update && sudo apt upgrade -y

# تثبيت Python و الأدوات اللازمة
sudo apt install -y python3 python3-venv python3-pip git
```

### 2. إنشاء مستخدم مخصص

```bash
sudo useradd -r -m -d /opt/family-bot -s /bin/bash familybot
```

### 3. نسخ الكود

```bash
# لو عندك git remote
sudo -u familybot git clone <repo-url> /opt/family-bot

# أو رفع يدوي عبر scp
scp -r ./Family_Bot user@vps:/tmp/
sudo mv /tmp/Family_Bot/* /opt/family-bot/
sudo chown -R familybot:familybot /opt/family-bot
```

### 4. إنشاء البيئة الافتراضية

```bash
sudo -u familybot bash -c "cd /opt/family-bot && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
```

### 5. ضبط ملف `.env`

```bash
sudo -u familybot cp /opt/family-bot/.env.example /opt/family-bot/.env
sudo -u familybot nano /opt/family-bot/.env
```

ضع التوكنات **الجديدة** (المتجددة):

```
TELEGRAM_BOT_TOKEN=<توكن جديد من @BotFather>
NOTION_TOKEN=<توكن جديد من Notion>
NOTION_DATABASE_ID=34f39125abb1807e9070d3de143e4c32
```

تأمين الملف:

```bash
sudo chmod 600 /opt/family-bot/.env
```

### 6. تثبيت الـ systemd service

```bash
sudo cp /opt/family-bot/deploy/family-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable family-bot
sudo systemctl start family-bot
```

### 7. التحقق

```bash
# تأكد إن البوت شغال
sudo systemctl status family-bot

# مراقبة اللوقات لايف
sudo journalctl -u family-bot -f

# آخر 50 سطر
sudo journalctl -u family-bot -n 50
```

### 8. أول استخدام

في تيليجرام:
1. أرسل `/start` للبوت → يسجلك كمالك
2. أرسل `/add` لإضافة أول قريب
3. أرسل `/list` للتأكد من الإضافة

---

## التحديث

```bash
sudo -u familybot bash -c "cd /opt/family-bot && git pull && .venv/bin/pip install -r requirements.txt"
sudo systemctl restart family-bot
```

## استكشاف الأخطاء

### البوت ما يرد
- `sudo systemctl status family-bot` — هل في active؟
- `sudo journalctl -u family-bot -n 100` — هل في أخطاء؟
- تأكد إن التوكن في `.env` صحيح

### "Missing Notion properties"
البوت يحاول يضيف الأعمدة الناقصة تلقائياً. لو ما قدر:
- افتح https://www.notion.so/my-integrations
- تأكد إن الـ integration عنده صلاحية تعديل المخطط
- أو أضف الأعمدة يدوياً في Notion:
  - `أيام الشهر للتواصل` (Text)
  - `تذكير معلق منذ` (Date)
  - `تم التواصل هذا الشهر` (Number)

### تذكيرات ما توصل
- تأكد من المنطقة الزمنية: `timedatectl` على VPS
- اللوقات يبين شي؟ `journalctl -u family-bot --since "1 hour ago"`
