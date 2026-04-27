"""قوالب الرسائل العربية."""

from __future__ import annotations

WEEKDAY_NAMES_AR = {
    0: "الاثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}

WEEKDAY_NAMES_AR_BY_NOTION = {
    "الأحد": 6,
    "الاحد": 6,
    "الاثنين": 0,
    "الثلاثاء": 1,
    "الأربعاء": 2,
    "الاربعاء": 2,
    "الخميس": 3,
    "الجمعة": 4,
    "السبت": 5,
}

# أسماء الأعمدة في Notion (بدون همزة الألف، مطابقة للمخطط الحالي)
NOTION_WEEKDAY_PROPERTIES = [
    "الاحد",
    "الاثنين",
    "الثلاثاء",
    "الاربعاء",
    "الخميس",
    "الجمعة",
    "السبت",
]

NOTION_NAME_PROPERTY = "الاسم"
NOTION_TARGET_PROPERTY = "عدد مرات التواصل في الشهر"
NOTION_DONE_PROPERTY = "تم التواصل هذا الشهر"
NOTION_SCHEDULE_PROPERTY = "أيام الشهر للتواصل"
NOTION_PENDING_PROPERTY = "تذكير معلق منذ"

WELCOME = (
    "🤲 أهلاً بك في بوت صلة الرحم\n\n"
    "هذا البوت يساعدك على الالتزام بصلة الرحم بشكل منتظم.\n\n"
    "اكتب /help لعرض الأوامر المتاحة."
)

UNAUTHORIZED = "🚫 هذا البوت خاص ولا يمكنك استخدامه."

OWNER_REGISTERED = (
    "✅ تم تسجيلك كمالك للبوت.\n\n"
    "بإمكانك الآن استخدام كل الأوامر. اكتب /help لعرضها."
)

HELP = (
    "📚 الأوامر المتاحة:\n\n"
    "/add — إضافة قريب جديد\n"
    "/list — عرض كل الأقارب وحالة الشهر\n"
    "/edit — تعديل بيانات قريب\n"
    "/remove — حذف قريب\n"
    "/status — جدول الشهر الكامل\n"
    "/today — تذكيرات اليوم\n"
    "/help — هذه الرسالة\n"
)


def reminder_message(name: str, count_done: int, count_target: int) -> str:
    return (
        f"🤲 *تذكير صلة الرحم*\n\n"
        f"اليوم تواصل مع: *{name}*\n\n"
        f"الرصيد: {count_done} من {count_target}"
    )


def confirmed_message(name: str, count_done: int, count_target: int) -> str:
    return (
        f"✅ تم التواصل مع *{name}*\n\n"
        f"الرصيد هذا الشهر: {count_done} من {count_target}\n"
        f"بارك الله لك 🤲"
    )


def already_confirmed_message(name: str) -> str:
    return f"ℹ️ تم تأكيد التواصل مع {name} مسبقاً."


def add_ask_name() -> str:
    return "📝 وش اسم القريب؟"


def add_ask_days() -> str:
    return (
        "📅 اختر الأيام المناسبة للتواصل (اضغط على الأيام ثم 'تم'):"
    )


def add_ask_count() -> str:
    return "🔢 كم مرة تبغا تتواصل معه في الشهر؟ (أرسل رقم)"


def add_invalid_count() -> str:
    return "⚠️ الرجاء إرسال رقم صحيح أكبر من صفر."


def add_no_days_selected() -> str:
    return "⚠️ لازم تختار يوم واحد على الأقل."


def add_success(name: str, days: list[str], count: int) -> str:
    days_str = "، ".join(days)
    return (
        f"✅ تمت إضافة *{name}*\n\n"
        f"الأيام: {days_str}\n"
        f"المرات: {count} شهرياً\n\n"
        f"📅 التغيير يدخل حيز التنفيذ الشهر القادم."
    )


def list_empty() -> str:
    return "📭 لا يوجد أقارب مضافون بعد. استخدم /add لإضافة أول قريب."


def list_header() -> str:
    return "👨‍👩‍👧‍👦 *قائمة الأقارب:*\n"


def list_item(name: str, days: list[str], done: int, target: int) -> str:
    days_str = "، ".join(days) if days else "لا توجد أيام"
    bar = progress_bar(done, target)
    return f"\n• *{name}*\n  📅 {days_str}\n  {bar} ({done}/{target})"


def progress_bar(done: int, target: int) -> str:
    if target <= 0:
        return "—"
    filled = min(done, target)
    empty = max(target - filled, 0)
    return "🟢" * filled + "⚪" * empty


def status_empty() -> str:
    return "📭 لا توجد تذكيرات مجدولة هذا الشهر."


def today_empty() -> str:
    return "🌿 ما في تذكيرات اليوم. يوم هادئ."


def today_header(date_str: str) -> str:
    return f"📅 *تذكيرات اليوم ({date_str}):*\n"


def edit_pick() -> str:
    return "✏️ اختر القريب اللي تبغا تعدله:"


def edit_what() -> str:
    return "وش تبغا تعدل؟"


def remove_pick() -> str:
    return "🗑 اختر القريب اللي تبغا تحذفه:"


def remove_confirm(name: str) -> str:
    return f"⚠️ متأكد تبغا تحذف *{name}*؟ هذا الإجراء نهائي."


def removed(name: str) -> str:
    return f"✅ تم حذف {name}."


def cancelled() -> str:
    return "❌ تم الإلغاء."


def edit_count_updated(name: str, count: int) -> str:
    return f"✅ تم تحديث عدد المرات لـ {name} إلى {count}.\n\n📅 التغيير يدخل حيز التنفيذ الشهر القادم."


def edit_days_updated(name: str, days: list[str]) -> str:
    days_str = "، ".join(days)
    return (
        f"✅ تم تحديث أيام {name} إلى: {days_str}.\n\n"
        f"📅 التغيير يدخل حيز التنفيذ الشهر القادم."
    )


def edit_name_updated(old: str, new: str) -> str:
    return f"✅ تم تغيير الاسم من {old} إلى {new}."


def schedule_warning(name: str, requested: int, available: int) -> str:
    return (
        f"⚠️ {name}: طلبت {requested} تواصل لكن متاح فقط {available} يوم في الشهر. "
        f"تم جدولة {available}."
    )


def no_days_warning(name: str) -> str:
    return f"⚠️ {name}: لم تحدد أيام للتواصل. الرجاء التعديل."


def monthly_reset_done(month_name: str, count: int) -> str:
    return (
        f"🌙 *بداية شهر جديد ({month_name})*\n\n"
        f"تم تصفير العدادات وإعداد جدول جديد لـ {count} قريب."
    )
