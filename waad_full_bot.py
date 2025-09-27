
#!/usr/bin/env python3
# waad_full_bot.py
# Full "Waad-like" Telegram Bot (Python)
# Requirements: python-telegram-bot==13.15
# Usage: set env var WAAD_BOT_TOKEN or edit TOKEN variable. Set OWNER_IDS to your Telegram user id(s).

import os, json, logging, time
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import List

from telegram import Update, ChatPermissions
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("WAAD_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
DATA_FILE = "bot_data.json"
# ضع هنا ايدي بتاعك كمالك اساسي لو حابب، مثال: [123456789]
OWNER_IDS = []  
RECENT_MSG_LIMIT = 300
# ----------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------- Persistence ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

DATA = load_data()

def ensure_chat(chat_id):
    sid = str(chat_id)
    if sid not in DATA:
        DATA[sid] = {
            "welcome":"أهلاً بك {name} في المجموعة 🎉",
            "filters":["سب","بذاءة"],
            "warns":{},
            "locks":{"links":False,"media":False,"stickers":False,"chat_locked":False},
            "managers":[],
            "muted":{},  # user_id: until_timestamp or 0 for permanent
            "banned":[],
            "recent_msgs": []
        }
        save_data()

# ---------------- Helpers ----------------
def is_owner(user_id):
    return user_id in OWNER_IDS

def is_creator(update: Update):
    try:
        member = update.effective_chat.get_member(update.effective_user.id)
        return member.status == "creator"
    except:
        return False

def is_admin_or_manager(update: Update):
    user = update.effective_user
    chat = update.effective_chat
    if user and is_owner(user.id):
        return True
    try:
        member = chat.get_member(user.id)
        if member.status in ("creator","administrator"):
            return True
    except:
        pass
    sid = str(chat.id)
    ensure_chat(chat.id)
    if user.id in DATA[sid].get("managers",[]):
        return True
    return False

def restrict_check_admin(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext, *a, **kw):
        if not is_admin_or_manager(update):
            try:
                update.message.reply_text("ما لكش صلاحية تستخدم الأمر ده. لازم تكون مالك/منشئ/مدير/أدمن.")
            except:
                pass
            return
        return func(update, context, *a, **kw)
    return wrapper

def save_recent(chat_id, message_id):
    sid = str(chat_id)
    ensure_chat(chat_id)
    lst = DATA[sid].get("recent_msgs", [])
    lst.append(message_id)
    if len(lst) > RECENT_MSG_LIMIT:
        lst = lst[-RECENT_MSG_LIMIT:]
    DATA[sid]["recent_msgs"] = lst
    save_data()

def reply(update: Update, text: str):
    try:
        update.message.reply_text(text)
    except Exception as e:
        logger.warning(f"reply failed: {e}")

# --------------- Handlers ---------------
def message_logger(update: Update, context: CallbackContext):
    # log every text/media message for recent deletion
    msg = update.message
    if not msg:
        return
    ensure_chat(update.effective_chat.id)
    save_recent(update.effective_chat.id, msg.message_id)

def text_handler(update: Update, context: CallbackContext):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    chat = update.effective_chat
    sid = str(chat.id)
    ensure_chat(chat.id)
    lowered = text.lower()

    # dot command: reply with bot username
    if text.startswith("."):
        uname = context.bot.username or "bot"
        reply(update, f"يوزر البوت: @{uname}")
        return

    # الاوامر list
    if lowered in ("الاوامر","اوامر","help"):
        cmds = (
"📜 قائمة الأوامر:\n\n"
"👑 الرتب:\n"
"- رفع ادمن (بالرد)\n- تنزيل ادمن (بالرد)\n- رفع مدير (بالرد)\n- تنزيل مدير (بالرد)\n- رفع منشئ (غير ممكن برمجياً — المنشئ تلقائي)\n\n"
"🚫 الحماية:\n"
"- حظر (بالرد)\n- فك الحظر (اكتب ايدي)\n- كتم [ثواني] (بالرد)\n- فك الكتم (بالرد)\n- قفل روابط / فتح روابط\n- قفل ميديا / فتح ميديا\n- قفل ملصقات / فتح ملصقات\n- قفل الدردشة / فتح الدردشة\n- مسح <عدد>\n- مسح الكل (يحذف السجلات المؤرشفة فقط)\n\n"
"📝 الفلتر:\n"
"- اضف فلتر كلمة\n- حذف فلتر كلمة\n- قائمة الفلتر\n\n"
"👋 الترحيب:\n"
"- تعيين ترحيب <النص>\n- عرض الترحيب\n\n"
"📌 تثبيت:\n"
"- تثبيت (رد على رسالة)\n- الغاء التثبيت\n\n"
"ℹ️ معلومات:\n"
"- ايدي (رد أو ايدي) - معلومات العضو\n- الادمنيه - عرض الأدمن\n- المدراء - عرض المدراء\n- المحظورين - عرض المحظورين\n- المكتومين - عرض المكتومين\n\n'.' يرد بيوزر البوت"
        )
        reply(update, cmds)
        return

    # Auto-filter: delete message containing bad words
    for bad in DATA[sid]["filters"]:
        if bad in lowered:
            try:
                msg.delete()
            except:
                pass
            uid = str(msg.from_user.id)
            DATA[sid]["warns"].setdefault(uid,0)
            DATA[sid]["warns"][uid] += 1
            save_data()
            reply(update, f"تم حذف الرسالة لاحتوائها على كلمة محظورة. التحذيرات: {DATA[sid]['warns'][uid]}")
            return

    # Locks handling
    if DATA[sid]["locks"].get("links", False):
        if "http://" in lowered or "https://" in lowered or "t.me/" in lowered:
            try:
                msg.delete()
                reply(update, "الوصلات مقفولة في الدردشة.")
            except:
                pass
            return
    if DATA[sid]["locks"].get("media", False):
        if msg.photo or msg.video or msg.document or msg.audio:
            try:
                msg.delete()
                reply(update, "الملفات مقفولة في الدردشة.")
            except:
                pass
            return
    if DATA[sid]["locks"].get("stickers", False):
        if msg.sticker:
            try:
                msg.delete()
                reply(update, "الملصقات مقفولة في الدردشة.")
            except:
                pass
            return

    # ---------- Plain Arabic commands (admin/manager restricted where needed) ----------
    # رفع ادمن (بناءً على رد)
    if text.startswith("رفع ادمن"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة العضو اللي عايز ترفعه أدمن.")
            return
        target = msg.reply_to_message.from_user
        try:
            chat.promote_member(user_id=target.id,
                                can_change_info=False,
                                can_delete_messages=True,
                                can_invite_users=True,
                                can_restrict_members=True,
                                can_pin_messages=True,
                                can_promote_members=False)
            reply(update, f"✅ تم رفع {target.first_name} أدمن.")
        except Exception as e:
            reply(update, f"فشل في رفع الأدمن: {e}")
        return

    if text.startswith("تنزيل ادمن"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة العضو اللي عايز تنزله.")
            return
        target = msg.reply_to_message.from_user
        try:
            chat.promote_member(user_id=target.id,
                                can_change_info=False,
                                can_delete_messages=False,
                                can_invite_users=False,
                                can_restrict_members=False,
                                can_pin_messages=False,
                                can_promote_members=False)
            reply(update, f"✅ تم تنزيل {target.first_name} من الأدمن.")
        except Exception as e:
            reply(update, f"فشل في تنزيل الأدمن: {e}")
        return

    if text.startswith("رفع مدير"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة العضو اللي عايز ترفعه مدير.")
            return
        target = msg.reply_to_message.from_user
        sid = str(chat.id)
        ensure_chat(chat.id)
        DATA[sid]["managers"].append(target.id)
        DATA[sid]["managers"] = list(set(DATA[sid]["managers"]))
        save_data()
        reply(update, f"✅ تم رفع {target.first_name} مدير.")
        return

    if text.startswith("تنزيل مدير"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة العضو اللي عايز تنزله مدير.")
            return
        target = msg.reply_to_message.from_user
        sid = str(chat.id)
        ensure_chat(chat.id)
        try:
            DATA[sid]["managers"].remove(target.id)
        except:
            pass
        save_data()
        reply(update, f"✅ تم تنزيل {target.first_name} من المنصب.")
        return

    # حظر
    if text.startswith("حظر"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة العضو اللي عايز تحظره.")
            return
        target = msg.reply_to_message.from_user
        try:
            chat.kick_member(target.id)
            sid = str(chat.id)
            ensure_chat(chat.id)
            DATA[sid]["banned"].append(target.id)
            DATA[sid]["banned"] = list(set(DATA[sid]["banned"]))
            save_data()
            reply(update, f"🚫 تم حظر {target.first_name}.")
        except Exception as e:
            reply(update, f"فشل في الحظر: {e}")
        return

    if text.startswith("فك الحظر"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        parts = text.split()
        if len(parts) < 2:
            reply(update, "اكتب ايدي المستخدم لفك الحظر.")
            return
        try:
            uid = int(parts[1])
            chat.unban_member(uid)
            sid = str(chat.id)
            ensure_chat(chat.id)
            try:
                DATA[sid]["banned"].remove(uid)
            except:
                pass
            save_data()
            reply(update, "تم فك الحظر.")
        except Exception as e:
            reply(update, f"فشل في فك الحظر: {e}")
        return

    # كتم
    if text.startswith("كتم"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة العضو اللي عايز تكتمه.")
            return
        parts = text.split()
        seconds = 0
        if len(parts) >= 2:
            try:
                seconds = int(parts[-1])
            except:
                seconds = 0
        target = msg.reply_to_message.from_user
        until = None
        if seconds > 0:
            until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            until_ts = int(until.timestamp())
        else:
            until_ts = 0
        try:
            chat.restrict_member(target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
            sid = str(chat.id)
            ensure_chat(chat.id)
            DATA[sid]["muted"][str(target.id)] = until_ts
            save_data()
            reply(update, f"🔇 تم كتم {target.first_name} لمدة {seconds} ثانية." if seconds else f"🔇 تم كتم {target.first_name} بشكل دائم.")
        except Exception as e:
            reply(update, f"فشل في الكتم: {e}")
        return

    if text.startswith("فك الكتم"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة العضو اللي عايز تفك عنه الكتم.")
            return
        target = msg.reply_to_message.from_user
        try:
            chat.restrict_member(target.id, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
            sid = str(chat.id)
            ensure_chat(chat.id)
            try:
                DATA[sid]["muted"].pop(str(target.id), None)
            except:
                pass
            save_data()
            reply(update, f"🔊 تم فك الكتم عن {target.first_name}.")
        except Exception as e:
            reply(update, f"فشل في فك الكتم: {e}")
        return

    # قفل / فتح للروابط، الميديا، الملصقات
    if lowered.startswith("قفل ") or lowered.startswith("فتح "):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        op = "قفل" if lowered.startswith("قفل ") else "فتح"
        what = lowered.replace("قفل ","").replace("فتح ","").strip()
        sid = str(chat.id)
        ensure_chat(chat.id)
        if what in ("روابط","link","links"):
            DATA[sid]["locks"]["links"] = (op == "قفل")
        elif what in ("ميديا","ملفات","media"):
            DATA[sid]["locks"]["media"] = (op == "قفل")
        elif what in ("ملصقات","ستيكر","stickers","ملصق"):
            DATA[sid]["locks"]["stickers"] = (op == "قفل")
        elif what in ("الدردشة","الدردشه","الدردشة كاملة","الدردشة_كاملة"):
            DATA[sid]["locks"]["chat_locked"] = (op == "قفل")
            # apply chat-wide permission change
            try:
                if DATA[sid]["locks"]["chat_locked"]:
                    chat.set_permissions(ChatPermissions(can_send_messages=False))
                else:
                    chat.set_permissions(ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
            except Exception as e:
                logger.warning(f"set_permissions failed: {e}")
        else:
            reply(update, "مش فاهم نوع القفل. جرب: قفل روابط / قفل ميديا / قفل ملصقات / قفل الدردشة")
            return
        save_data()
        reply(update, f"✅ تم {op} {what}.")
        return

    # تثبيت و الغاء التثبيت (pin/unpin)
    if text.startswith("تثبيت"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        if not msg.reply_to_message:
            reply(update, "رد على رسالة اللي عايز تثبتها.")
            return
        try:
            chat.pin_message(msg.reply_to_message.message_id)
            reply(update, "📌 تم تثبيت الرسالة.")
        except Exception as e:
            reply(update, f"فشل في التثبيت: {e}")
        return

    if text.startswith("الغاء التثبيت") or text.startswith("الغاء تثبيت"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        try:
            chat.unpin_message()
            reply(update, "✅ تم إلغاء تثبيت الرسالة المثبتة.")
        except Exception as e:
            reply(update, f"فشل في إلغاء التثبيت: {e}")
        return

    # مسح <n> -> delete last n tracked messages (excluding service messages)
    if lowered.startswith("مسح"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        parts = text.split()
        num = 1
        if len(parts) >= 2:
            try:
                num = int(parts[1])
            except:
                num = 1
        sid = str(chat.id)
        ensure_chat(chat.id)
        recent = DATA[sid].get("recent_msgs", [])[:]
        to_delete = recent[-num:] if num>0 else []
        deleted = 0
        for mid in reversed(to_delete):
            try:
                chat.delete_message(mid)
                deleted += 1
                # remove from recent list
                try:
                    DATA[sid]["recent_msgs"].remove(mid)
                except:
                    pass
            except:
                pass
        save_data()
        reply(update, f"تم مسح {deleted} رسالة.")
        return

    # ادمنيه و المدراء و المحظورين و المكتومين
    if lowered in ("الادمنيه","الادمنين"):
        try:
            admins = chat.get_administrators()
            names = [a.user.full_name + (" (@"+a.user.username+")" if a.user.username else "") for a in admins]
            reply(update, "قائمة الأدمن:\n" + "\n".join(names))
        except Exception as e:
            reply(update, f"فشل في جلب الأدمن: {e}")
        return

    if lowered in ("المدراء","المديرين"):
        sid = str(chat.id)
        ensure_chat(chat.id)
        mgrs = DATA[sid].get("managers",[])
        names = []
        for uid in mgrs:
            try:
                m = chat.get_member(uid)
                names.append(m.user.full_name + ((" @"+m.user.username) if m.user.username else ""))
            except:
                names.append(str(uid))
        reply(update, "قائمة المدراء:\n" + ("\n".join(names) if names else "لا يوجد مدراء"))
        return

    if lowered in ("المحظورين","المحظورين:"):
        sid = str(chat.id)
        ensure_chat(chat.id)
        banned = DATA[sid].get("banned",[])
        reply(update, "قائمة المحظورين:\n" + ("\n".join(str(x) for x in banned) if banned else "لا يوجد محظورين"))
        return

    if lowered in ("المكتومين","المكتومين:"):
        sid = str(chat.id)
        ensure_chat(chat.id)
        muted = DATA[sid].get("muted",{})
        lines = []
        for uid, until in muted.items():
            if int(until)==0:
                lines.append(f"{uid} -> مكتوم دائمًا")
            else:
                lines.append(f"{uid} -> حتى {datetime.fromtimestamp(int(until)).isoformat()}")
        reply(update, "قائمة المكتومين:\n" + ("\n".join(lines) if lines else "لا يوجد مكتومين"))
        return

    # ايدي / معلومات
    if lowered.startswith("ايدي") or lowered.startswith("معلومات"):
        target = None
        if msg.reply_to_message:
            target = msg.reply_to_message.from_user
        else:
            parts = text.split()
            if len(parts) >= 2:
                try:
                    uid = int(parts[1])
                    target = context.bot.get_chat(uid)
                except:
                    target = msg.from_user
            else:
                target = msg.from_user
        try:
            uname = ("@" + target.username) if getattr(target, "username", None) else ""
            reply(update, f"الاسم: {target.full_name}\nاليوزر: {uname}\nالايدي: {target.id}")
        except Exception as e:
            reply(update, f"فشل في جلب المعلومات: {e}")
        return

    # اضف فلتر / حذف فلتر / قائمة الفلتر
    if lowered.startswith("اضف فلتر") or lowered.startswith("اضف كلمه"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            reply(update, "اكتب الكلمة اللي عايز تضيفها.")
            return
        word = parts[-1].strip().lower()
        sid = str(chat.id)
        ensure_chat(chat.id)
        DATA[sid]["filters"].append(word)
        DATA[sid]["filters"] = list(set(DATA[sid]["filters"]))
        save_data()
        reply(update, f"تم إضافة '{word}' للفلتر.")
        return

    if lowered.startswith("حذف فلتر") or lowered.startswith("مسح كلمه"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        parts = text.split(maxsplit=2)
        if len(parts) < 2:
            reply(update, "اكتب الكلمة اللي عايز تمسحها.")
            return
        word = parts[-1].strip().lower()
        sid = str(chat.id)
        ensure_chat(chat.id)
        try:
            DATA[sid]["filters"].remove(word)
            save_data()
            reply(update, f"تم حذف '{word}' من الفلتر.")
        except:
            reply(update, "الكلمة مش موجودة.")
        return

    if lowered in ("قائمة الفلتر","الفلاتر","اظهر الفلتر"):
        sid = str(chat.id)
        ensure_chat(chat.id)
        reply(update, "كلمات الفلتر:\n" + ("\n".join(DATA[sid].get("filters",[])) if DATA[sid].get("filters") else "لا توجد كلمات"))
        return

    # تعيين ترحيب / عرض الترحيب
    if lowered.startswith("تعيين ترحيب") or lowered.startswith("ضبط ترحيب"):
        if not is_admin_or_manager(update):
            reply(update, "ما تقدرش تستخدم الأمر ده.")
            return
        new = text.replace(text.split()[0],"",1).strip()
        sid = str(chat.id)
        ensure_chat(chat.id)
        if not new:
            reply(update, "اكتب نص الترحيب بعد الامر. استخدم {name} لاسم العضو.")
            return
        DATA[sid]["welcome"] = new
        save_data()
        reply(update, "تم تحديث الترحيب.")
        return

    if lowered in ("عرض الترحيب","الترحيب"):
        sid = str(chat.id)
        ensure_chat(chat.id)
        reply(update, DATA[sid].get("welcome","أهلاً بك {name}"))
        return

    # اعدادات
    if lowered in ("اعدادات","الاعدادات"):
        sid = str(chat.id)
        ensure_chat(chat.id)
        locks = DATA[sid].get("locks",{})
        txt = "حالة القفل:\n"
        txt += f"- روابط: {'مقفول' if locks.get('links') else 'مفتوح'}\n"
        txt += f"- ميديا: {'مقفول' if locks.get('media') else 'مفتوح'}\n"
        txt += f"- ملصقات: {'مقفول' if locks.get('stickers') else 'مفتوح'}\n"
        txt += f"- الدردشة: {'مقفول' if locks.get('chat_locked') else 'مفتوح'}\n"
        reply(update, txt)
        return

# welcome handler
def welcome_handler(update: Update, context: CallbackContext):
    msg = update.message
    if not msg:
        return
    if msg.new_chat_members:
        sid = str(update.effective_chat.id)
        ensure_chat(update.effective_chat.id)
        for m in msg.new_chat_members:
            txt = DATA[sid].get("welcome","أهلاً بك {name} في المجموعة 🎉").replace("{name}", m.full_name)
            try:
                update.effective_chat.send_message(txt)
            except Exception as e:
                logger.warning(f"welcome failed: {e}")

def main():
    if TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        print("حط توكن البوت في متغير البيئة WAAD_BOT_TOKEN أو عدّل المتغير TOKEN في الكود.")
        return
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, welcome_handler))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), message_logger))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), text_handler))

    print("بوت وعد المتكامل شغال...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
