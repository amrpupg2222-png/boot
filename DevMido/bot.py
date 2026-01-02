from database import get_db, User, TelegramSession
import telebot
from telebot import types
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from Must_Join import check_must_join, must_join_markup
from wed import start_flask
from DevAhmed import handle_admin_commands, is_admin
from Professional import get_ai_response
import asyncio
import threading
import os
TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
FINAL_API_ID = API_ID
if API_ID:
    try:
        if isinstance(API_ID, int):
            FINAL_API_ID = API_ID
        elif isinstance(API_ID, str) and API_ID.isdigit():
            FINAL_API_ID = int(API_ID)
        else:
            print(f"CRITICAL: API_ID '{API_ID}' is NOT an integer. Telethon will fail.")
            FINAL_API_ID = 0 
    except Exception as e:
        print(f"Error parsing API_ID: {e}")
        FINAL_API_ID = 0
bot = telebot.TeleBot(TOKEN)
sessions = {}
loop = asyncio.new_event_loop()
async def join_groups_task(client, group_links):
    from telethon.tl.functions.channels import JoinChannelRequest
    for link in group_links:
        try:
            print(f"DEBUG: Attempting to join group: {link}")
            await client(JoinChannelRequest(link))
            print(f"DEBUG: Successfully joined {link}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"DEBUG: Failed to join {link}: {e}")
async def start_user_client(session_str, group_links=None, acc_id=None):
    if not isinstance(FINAL_API_ID, int) or FINAL_API_ID == 0:
        print("ERROR: Cannot start Telethon because API_ID is invalid.")
        return
    client = TelegramClient(StringSession(session_str), FINAL_API_ID, API_HASH)
    await client.connect()
    if await client.is_user_authorized():
        sessions[session_str] = client
        try:
            me = await client.get_entity('me')
            first_name = me.first_name if me.first_name else ""
            last_name = me.last_name if me.last_name else ""
            full_name = f"{first_name} {last_name}".strip()
            final_name = full_name if full_name else (me.username if me.username else "حساب بدون اسم")
            print(f"DEBUG: Fetched fresh name for DB: {final_name}")
            if acc_id:
                db = get_db()
                session_db = db.query(TelegramSession).filter(TelegramSession.id == acc_id).first()
                if session_db:
                    session_db.account_name = final_name
                    db.commit()
                    print(f"DEBUG: DB updated with name: {final_name}")
                db.close()
        except Exception as e:
            print(f"DEBUG: Error fetching fresh profile: {e}")
        print(f"User client started for session: {session_str[:20]}...")
        if group_links:
            loop.create_task(join_groups_task(client, group_links))
        @client.on(events.NewMessage)
        async def handler(event):
            print(f"DEBUG: New message in {event.chat_id} (is_group={event.is_group}): {event.text[:50]}")
            if event.reply_to_msg_id:
                replied_msg = await event.get_reply_message()
                me = await client.get_me()
                is_reply_to_me = False
                if replied_msg:
                    if replied_msg.from_id:
                        from_id = replied_msg.from_id
                        user_id = getattr(from_id, 'user_id', None)
                        if user_id == me.id:
                            is_reply_to_me = True
                        elif hasattr(from_id, 'chat_id') and from_id.chat_id == me.id:
                            is_reply_to_me = True
                        elif hasattr(from_id, 'channel_id') and from_id.channel_id == me.id:
                            is_reply_to_me = True
                    if not is_reply_to_me:
                        sender = await replied_msg.get_sender()
                        if sender and sender.id == me.id:
                            is_reply_to_me = True
                if is_reply_to_me:
                    print(f"DEBUG: Detected reply to me in {event.chat_id}. Getting AI response...")
                    sender = await event.get_sender()
                    user_id = sender.id if sender else event.chat_id
                    response = get_ai_response(event.text, user_id)
                    print(f"DEBUG: AI response generated: {response}. Replying immediately...")
                    await event.reply(response)
                    print(f"DEBUG: Replied to message in {event.chat_id}")
        await client.run_until_disconnected()
def run_telethon(session_str, group_links=None, acc_id=None):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_user_client(session_str, group_links, acc_id))
def refresh_control_menu(call):
    db = get_db()
    sessions_db = db.query(TelegramSession).filter(TelegramSession.user_id == str(call.from_user.id)).all()
    db.close()
    if sessions_db:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for s in sessions_db:
            is_running = s.session_string in sessions
            status_icon = "🟢" if is_running else "🔴"
            account_name = s.account_name or f"{s.session_string[:15]}..."
            markup.add(types.InlineKeyboardButton(f"{account_name} {status_icon}", callback_data=f"tglacc_{s.id}"))
        try:
            bot.edit_message_text("❈| لوحة التحكم في الحسابات 🛠 \n\nاضغط على الحساب لتغيير حالته :", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except: pass
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "add_account":
        msg = bot.send_message(call.message.chat.id, "❈| ارسل كود جلسة تيلثون الخاص بك :")
        bot.register_next_step_handler(msg, process_session_step)
    elif call.data == "del_groups":
        db = get_db()
        user = db.query(User).filter(User.user_id == str(call.from_user.id)).first()
        db.close()
        if user and user.groups:
            group_list = [g.strip() for g in user.groups.split('\n') if g.strip()]
            markup = types.InlineKeyboardMarkup(row_width=1)
            for i, group in enumerate(group_list):
                markup.add(types.InlineKeyboardButton(f"❌ {group}", callback_data=f"rmgrp_{i}"))
            bot.send_message(call.message.chat.id, "❈| اختر المجموعة التي تريد حذفها :", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "❈| عـذراً لا توجد مجموعات لحذفها 💢")
    elif call.data.startswith("rmgrp_"):
        idx = int(call.data.split("_")[1])
        db = get_db()
        user = db.query(User).filter(User.user_id == str(call.from_user.id)).first()
        if user and user.groups:
            group_list = [g.strip() for g in user.groups.split('\n') if g.strip()]
            if 0 <= idx < len(group_list):
                removed = group_list.pop(idx)
                user.groups = "\n".join(group_list)
                db.commit()
                bot.answer_callback_query(call.id, f"تم حذف: {removed}")
                if group_list:
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    for i, group in enumerate(group_list):
                        markup.add(types.InlineKeyboardButton(f"❌ {group}", callback_data=f"rmgrp_{i}"))
                    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
                else:
                    bot.edit_message_text("❈| تم حذف جميع المجموعات.", call.message.chat.id, call.message.message_id)
        db.close()
    elif call.data == "del_account":
        db = get_db()
        sessions_db = db.query(TelegramSession).filter(TelegramSession.user_id == str(call.from_user.id)).all()
        db.close()
        if sessions_db:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in sessions_db:
                label = f"🗑 {s.account_name or s.session_string[:15]}"
                markup.add(types.InlineKeyboardButton(label, callback_data=f"rmacc_{s.id}"))
            bot.send_message(call.message.chat.id, "❈| اختر الحساب الذي تريد حذفه .", reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, "❈| لا توجد حسابات لحذفها 💢")
    elif call.data.startswith("rmacc_"):
        acc_id = int(call.data.split("_")[1])
        db = get_db()
        session = db.query(TelegramSession).filter(TelegramSession.id == acc_id, TelegramSession.user_id == str(call.from_user.id)).first()
        if session:
            if session.session_string in sessions:
                client = sessions[session.session_string]
                try:
                    if client.loop.is_running():
                        client.loop.create_task(client.disconnect())
                except: pass
                del sessions[session.session_string]
            db.delete(session)
            db.commit()
            bot.answer_callback_query(call.id, "تم حذف الحساب بنجاح ✅")
            bot.edit_message_text("❈| تم حذف الحساب المختار ✅ .", call.message.chat.id, call.message.message_id)
        db.close()
    elif call.data == "stop_now":
        db = get_db()
        sessions_db = db.query(TelegramSession).filter(TelegramSession.user_id == str(call.from_user.id)).all()
        db.close()
        if sessions_db:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for s in sessions_db:
                is_running = s.session_string in sessions
                status_icon = "🟢" if is_running else "🔴"
                account_name = s.account_name or f"{s.session_string[:15]}..."
                markup.add(types.InlineKeyboardButton(f"{account_name} {status_icon}", callback_data=f"tglacc_{s.id}"))
            try:
                bot.edit_message_text("❈| لوحة التحكم في الحسابات 🛠 \n\nاضغط على الحساب لتغيير حالته :", call.message.chat.id, call.message.message_id, reply_markup=markup)
            except telebot.apihelper.ApiTelegramException as e:
                if "there is no text in the message to edit" in str(e):
                    bot.send_message(call.message.chat.id, "❈| لوحة التحكم في الحسابات 🛠 \n\nاضغط على الحساب لتغيير حالته :", reply_markup=markup)
                else:
                    raise e
        else:
            bot.send_message(call.message.chat.id, "❌ لا توجد حسابات مضافة.")
    elif call.data.startswith("tglacc_"):
        acc_id = int(call.data.split("_")[1])
        db = get_db()
        session = db.query(TelegramSession).filter(TelegramSession.id == acc_id, TelegramSession.user_id == str(call.from_user.id)).first()
        db.close()
        if session:
            if session.session_string in sessions:
                client = sessions[session.session_string]
                try:
                    if client.loop.is_running():
                        client.loop.create_task(client.disconnect())
                except: pass
                del sessions[session.session_string]
                bot.answer_callback_query(call.id, "تم إيقاف الحساب 🔴", show_alert=True)
            else:
                db = get_db()
                user = db.query(User).filter(User.user_id == str(call.from_user.id)).first()
                group_list = [g.strip() for g in user.groups.split('\n') if g.strip()] if user and user.groups else None
                db.close()
                def run_isolated_manual(sess=session.session_string, gl=group_list, sid=session.id):
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        client = TelegramClient(StringSession(sess), int(FINAL_API_ID), API_HASH, loop=new_loop)
                        new_loop.run_until_complete(client.connect())
                        if new_loop.run_until_complete(client.is_user_authorized()):
                            sessions[sess] = client
                            me = new_loop.run_until_complete(client.get_me())
                            db_inner = get_db()
                            s_db = db_inner.query(TelegramSession).filter(TelegramSession.id == sid).first()
                            if s_db:
                                me = new_loop.run_until_complete(client.get_me())
                                name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                                if not name:
                                    name = me.username or "حساب بدون اسم"
                                s_db.account_name = name
                                db_inner.commit()
                            db_inner.close()
                            print(f"DEBUG: Manual start success for {name}")
                            @client.on(events.NewMessage)
                            async def handler(event):
                                try:
                                    if event.reply_to_msg_id:
                                        replied_msg = await event.get_reply_message()
                                        me = await client.get_me()
                                        if replied_msg and replied_msg.sender_id == me.id:
                                            print(f"DEBUG: AI Reply triggered for {sess[:10]}")
                                            sender = await event.get_sender()
                                            user_id = sender.id if sender else event.chat_id
                                            response = get_ai_response(event.text, user_id)
                                            await event.reply(response)
                                except Exception as e:
                                    print(f"ERROR in AI handler: {e}")
                            new_loop.run_until_complete(client.run_until_disconnected())
                    except Exception as e:
                        print(f"DEBUG: Isolated manual start error: {e}")
                t = threading.Thread(target=run_isolated_manual)
                t.daemon = True
                t.start()
                bot.answer_callback_query(call.id, "جاري التشغيل والربط بالذكاء الاصطناعي... 🟢", show_alert=True)
            refresh_control_menu(call)
    elif call.data == "current_accounts":
        db = get_db()
        sessions_db = db.query(TelegramSession).filter(TelegramSession.user_id == str(call.from_user.id)).all()
        db.close()
        if sessions_db:
            text = "❈| حساباتك الحالية 📋:\n\n"
            for i, s in enumerate(sessions_db, 1):
                is_running = False
                if s.session_string in sessions:
                    client = sessions[s.session_string]
                    try:
                        if client.is_connected():
                            is_running = True
                        else:
                            is_running = False
                    except: 
                        is_running = False
                if not is_running and s.session_string in sessions:
                    is_running = True
                status = "نشط 🟢" if is_running else "متوقف 🔴"
                display_name = s.account_name
                if not display_name or display_name == "حساب تليجرام":
                    if s.session_string in sessions:
                        client = sessions[s.session_string]
                        try:
                            import asyncio
                            loop_to_use = client.loop
                            if loop_to_use.is_running():
                                me = client._me if hasattr(client, '_me') and client._me else None
                                if me:
                                    display_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or me.username
                        except: pass
                if not display_name or display_name == "حساب تليجرام":
                    display_name = f"`{s.session_string[:15]}...`"
                text += f"{i}- {display_name} {status}\n"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, "❌ لا توجد حسابات مضافة.")
    elif call.data == "current_groups":
        db = get_db()
        user = db.query(User).filter(User.user_id == str(call.from_user.id)).first()
        db.close()
        if user and user.groups:
            text = "❈| مجموعاتك الحالية 📋 :\n\n" + user.groups
            bot.send_message(call.message.chat.id, text)
        else:
            bot.send_message(call.message.chat.id, "❈| لا توجد مجموعات متضافة 💢")
    elif call.data == "auto_post":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("1", callback_data="delay_1"),
            types.InlineKeyboardButton("4", callback_data="delay_4"),
            types.InlineKeyboardButton("6", callback_data="delay_6"),
            types.InlineKeyboardButton("10", callback_data="delay_10"),
            types.InlineKeyboardButton("30", callback_data="delay_30"),
            types.InlineKeyboardButton("60", callback_data="delay_60"),
            types.InlineKeyboardButton("120", callback_data="delay_120"),
            types.InlineKeyboardButton("360", callback_data="delay_360")
        )
        markup.add(
            types.InlineKeyboardButton("إرسال عشوائي 🎲", callback_data="delay_random")
        )
        try:
            bot.edit_message_caption("❈| يرجي تحديد عدد الثواني من 1 حتي 380 ⏳:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            try:
                bot.edit_message_text("❈| يرجي تحديد عدد الثواني من 1 حتي 380 ⏳:", call.message.chat.id, call.message.message_id, reply_markup=markup)
            except Exception:
                bot.send_message(call.message.chat.id, "❈| يرجي تحديد عدد الثواني من 1 حتي 380 ⏳:", reply_markup=markup)
    elif call.data.startswith("delay_"):
        delay = call.data.split("_")[1]
        import random
        if delay == "random":
            delay = str(random.randint(2, 60))
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("2", callback_data=f"rep_{delay}_2"),
            types.InlineKeyboardButton("4", callback_data=f"rep_{delay}_4"),
            types.InlineKeyboardButton("6", callback_data=f"rep_{delay}_6"),
            types.InlineKeyboardButton("8", callback_data=f"rep_{delay}_8"),
            types.InlineKeyboardButton("15", callback_data=f"rep_{delay}_15"),
            types.InlineKeyboardButton("25", callback_data=f"rep_{delay}_25"),
            types.InlineKeyboardButton("35", callback_data=f"rep_{delay}_35"),
            types.InlineKeyboardButton("60", callback_data=f"rep_{delay}_60"),
            types.InlineKeyboardButton("120", callback_data=f"rep_{delay}_120"),
            types.InlineKeyboardButton("200", callback_data=f"rep_{delay}_200"),
            types.InlineKeyboardButton("300", callback_data=f"rep_{delay}_300"),
            types.InlineKeyboardButton("350", callback_data=f"rep_{delay}_350")
        )
        try:
            bot.edit_message_caption("اختار كم تريد تكرار رسالتك بالنشر:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            try:
                bot.edit_message_text("اختار كم تريد تكرار رسالتك بالنشر:", call.message.chat.id, call.message.message_id, reply_markup=markup)
            except Exception:
                bot.send_message(call.message.chat.id, "اختار كم تريد تكرار رسالتك بالنشر:", reply_markup=markup)
    elif call.data.startswith("rep_"):
        _, delay, repeat = call.data.split("_")
        msg = bot.send_message(call.message.chat.id, f"اهلا قم بارسال رسالتك الان (سيتم النشر بتأخير {delay} ثانية وتكرار {repeat} مرات):")
        bot.register_next_step_handler(msg, lambda m: process_auto_post_step(m, int(delay), int(repeat)))
    elif call.data == "start_now":
        db = get_db()
        user = db.query(User).filter(User.user_id == str(call.from_user.id)).first()
        if user and user.groups:
            sessions_db = db.query(TelegramSession).filter(TelegramSession.user_id == str(call.from_user.id)).all()
            group_list = [g.strip() for g in user.groups.split('\n') if g.strip()]
            for s in sessions_db:
                if s.session_string not in sessions:
                    threading.Thread(target=run_telethon, args=(s.session_string, group_list, s.id)).start()
                else:
                    client = sessions[s.session_string]
                    loop.create_task(join_groups_task(client, group_list))
            bot.answer_callback_query(call.id, "جاري بدء العمل والدخول للمجموعات... ☃️")
            bot.send_message(call.message.chat.id, "❈| تم بدء التشغيل بنجاح ✅ . سأقوم الان بالانضمام للمجموعات ومراقبتها والرد تلقائياً .")
        else:
            bot.answer_callback_query(call.id, "❌ يرجى إضافة مجموعات أولاً!")
            bot.send_message(call.message.chat.id, "⚠️ يجب عليك إضافة روابط المجموعات أولاً عبر زر {اضف مجموعات ✅}.")
        db.close()
    elif call.data == "add_groups":
        msg = bot.send_message(call.message.chat.id, "ارسل روابط المجموعات (رابط في كل سطر):")
        bot.register_next_step_handler(msg, process_groups_step)
def process_auto_post_step(message, delay=5, repeat=1):
    post_text = message.text
    if not post_text:
        bot.send_message(message.chat.id, "❌ يرجى إرسال نص للرسالة.")
        return
    db = get_db()
    user = db.query(User).filter(User.user_id == str(message.from_user.id)).first()
    sessions_db = db.query(TelegramSession).filter(TelegramSession.user_id == str(message.from_user.id)).all()
    if not user or not user.groups:
        bot.send_message(message.chat.id, "❌ يرجى إضافة مجموعات أولاً!")
        db.close()
        return
    if not sessions_db:
        bot.send_message(message.chat.id, "❌ يرجى إضافة حساب أولاً!")
        db.close()
        return
    group_list = [g.strip() for g in user.groups.split('\n') if g.strip()]
    db.close()
    bot.send_message(message.chat.id, f"🚀 جاري بدء النشر التلقائي (تكرار: {repeat}، تأخير: {delay} ثانية)...")
    for s in sessions_db:
        session_to_use = s.session_string
        print(f"DEBUG: Starting isolated thread for session {session_to_use[:15]}...")
        def run_isolated(sess=session_to_use, gl=group_list, pt=post_text, dl=delay, rp=repeat, uid=message.from_user.id):
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                print(f"DEBUG: Isolated loop started for {sess[:15]}...")
                async def run_now():
                    try:
                        client = TelegramClient(StringSession(sess), int(FINAL_API_ID), API_HASH, loop=new_loop)
                        await client.connect()
                        if not await client.is_user_authorized():
                            print(f"DEBUG: Client {sess[:15]} NOT authorized.")
                            return
                        print(f"DEBUG: Client {sess[:15]} authorized and starting post...")
                        for link in gl:
                            try:
                                target = link.strip()
                                if "t.me/" in target:
                                    clean = target.replace("https://t.me/", "").replace("http://t.me/", "").split('?')[0].split('/')[0]
                                    if not clean.startswith("+"):
                                        from telethon.tl.functions.channels import JoinChannelRequest
                                        await client(JoinChannelRequest(clean))
                                        await asyncio.sleep(1)
                            except Exception as e:
                                print(f"DEBUG: Join error for {sess[:15]}: {e}")
                        await auto_post_task(client, gl, pt, dl, rp, uid)
                        await client.disconnect()
                    except Exception as inner_e:
                        print(f"DEBUG: Error in run_now for {sess[:15]}: {inner_e}")
                new_loop.run_until_complete(run_now())
                new_loop.close()
            except Exception as e:
                print(f"DEBUG: Isolated thread crashed for {sess[:15]}: {e}")
        t = threading.Thread(target=run_isolated)
        t.daemon = True
        t.start()
async def auto_post_task(client, group_links, message_text, delay=5, repeat=1, user_bot_id=None):
    from telethon.tl.functions.channels import JoinChannelRequest
    from telethon.tl.functions.messages import ImportChatInviteRequest
    import re
    print(f"DEBUG: Starting auto_post_task for client {client}")
    for r in range(repeat):
        print(f"DEBUG: Round {r+1} of {repeat}")
        for link in group_links:
            try:
                target = link.strip()
                if not target: continue
                print(f"DEBUG: Sending to {target}")
                try:
                    if "t.me/" in target:
                        clean = target.replace("https://t.me/", "").replace("http://t.me/", "").split('?')[0].split('/')[0]
                        if not clean.startswith("+"):
                            from telethon.tl.functions.channels import JoinChannelRequest
                            await client(JoinChannelRequest(clean))
                except: pass
                try:
                    await client.send_message(target, message_text)
                    print(f"DEBUG: SUCCESS sending to {target}")
                except Exception as e:
                    print(f"DEBUG: FAILED sending to {target}: {e}")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"DEBUG: Error in loop: {e}")
        if r < repeat - 1:
            print(f"DEBUG: Waiting {delay} seconds before next repeat...")
            await asyncio.sleep(delay)
    if user_bot_id:
        try: bot.send_message(user_bot_id, "✅ تم الانتهاء من جميع جولات النشر بنجاح! خلاص خلاص 🚀")
        except: pass
def run_telethon_with_post(session_str, group_links, message_text, delay=5, repeat=1, user_bot_id=None):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_client_and_post(session_str, group_links, message_text, delay, repeat, user_bot_id))
async def start_client_and_post(session_str, group_links, message_text, delay=5, repeat=1, user_bot_id=None):
    await start_user_client(session_str, group_links)
    if session_str in sessions:
        await auto_post_task(sessions[session_str], group_links, message_text, delay, repeat, user_bot_id)
def process_groups_step(message):
    group_links = message.text
    if group_links and group_links.strip() == "/start":
        start(message)
        return
    if group_links:
        db = get_db()
        user = db.query(User).filter(User.user_id == str(message.from_user.id)).first()
        if user:
            user.groups = group_links
            db.commit()
            bot.send_message(message.chat.id, "❈| تم حفظ روابط المجموعات بنجاح ✅ .")
        else:
            bot.send_message(message.chat.id, "❌ لم يتم العثور على حسابك في قاعدة البيانات. يرجى الضغط على /start أولاً.")
        db.close()
    else:
        bot.send_message(message.chat.id, "❌ يرجى إرسال روابط صحيحة.")
def process_session_step(message):
    session_str = message.text
    if session_str and session_str.strip() == "/start":
        start(message)
        return
    if session_str:
        db = get_db()
        try:
            existing_session = db.query(TelegramSession).filter(TelegramSession.session_string == session_str).first()
            if existing_session:
                bot.send_message(message.chat.id, "⚠️ هذه الجلسة مضافة مسبقاً في النظام.")
                db.close()
                return
            new_session = TelegramSession(user_id=str(message.from_user.id), session_string=session_str)
            db.add(new_session)
            db.commit()
            user = db.query(User).filter(User.user_id == str(message.from_user.id)).first()
            group_list = [g.strip() for g in user.groups.split('\n') if g.strip()] if user and user.groups else None
            bot.send_message(message.chat.id, "❈| تم حفظ الجلسة في قاعدة البيانات وتفعيل الرد التلقائي .")
            print(f"DEBUG: Starting account immediately for session {session_str[:15]}...")
            def run_isolated_startup(sess=session_str):
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    client = TelegramClient(StringSession(sess), int(FINAL_API_ID), API_HASH, loop=new_loop)
                    new_loop.run_until_complete(client.connect())
                    if new_loop.run_until_complete(client.is_user_authorized()):
                        sessions[sess] = client
                        @client.on(events.NewMessage)
                        async def handler(event):
                            if event.reply_to_msg_id:
                                replied_msg = await event.get_reply_message()
                                me = await client.get_me()
                                if replied_msg and replied_msg.sender_id == me.id:
                                    sender = await event.get_sender()
                                    user_id = sender.id if sender else event.chat_id
                                    response = get_ai_response(event.text, user_id)
                                    await event.reply(response)
                        if group_list:
                            from telethon.tl.functions.channels import JoinChannelRequest
                            for link in group_list:
                                try:
                                    target = link.strip()
                                    if "t.me/" in target:
                                        clean = target.replace("https://t.me/", "").replace("http://t.me/", "").split('?')[0].split('/')[0]
                                        if not clean.startswith("+"):
                                            new_loop.run_until_complete(client(JoinChannelRequest(clean)))
                                except: pass
                        new_loop.run_forever()
                except Exception as e:
                    print(f"DEBUG: Startup thread error: {e}")
            t = threading.Thread(target=run_isolated_startup)
            t.daemon = True
            t.start()
        except Exception as e:
            db.rollback()
            db.close()
            print(f"Error saving session: {e}")
            bot.send_message(message.chat.id, "❌ حدث خطأ أثناء حفظ الجلسة. قد تكون مضافة مسبقاً.")
@bot.message_handler(commands=['vipStar', 'CloseStar', 'OpenStar'])
def close_star_command(message):
    print(f"Bypass command {message.text} triggered by {message.from_user.id}")
    if is_admin(message.from_user.id):
        try:
            db = get_db()
            if message.text.startswith('/vipStar'):
                db.query(User).update({User.has_paid: False})
                status_msg = "🔄 تم تصفير حالة الدفع لجميع المستخدمين. الآن سيظهر زر الدفع بالنجوم عند الضغط على /start."
            elif message.text.startswith('/CloseStar'):
                db.query(User).update({User.has_paid: True})
                status_msg = "✅ تم تفعيل الوضع المدفوع وإيقاف نظام الدفع لجميع المستخدمين."
            elif message.text.startswith('/OpenStar'):
                db.query(User).update({User.has_paid: False})
                status_msg = "✨ تم تفعيل نظام الدفع بالنجوم لجميع المستخدمين بنجاح."
            db.commit()
            db.close()
            global sessions
            sessions = {}
            bot.send_message(message.chat.id, status_msg)
        except Exception as e:
            print(f"Error in Bypass: {e}")
            bot.send_message(message.chat.id, f"❌ حدث خطأ أثناء تنفيذ الأمر: {e}")
    else:
        bot.send_message(message.chat.id, "❌ عذراً، هذا الأمر مخصص للمطورين فقط.")
@bot.message_handler(commands=['start'])
def start(message):
    db = get_db()
    user_id_str = str(message.from_user.id)
    user = db.query(User).filter(User.user_id == user_id_str).first()
    if not user:
        user = User(user_id=user_id_str)
        db.add(user)
        db.commit()
    if not check_must_join(bot, message.from_user.id):
        text = "يجب عليك الاشتراك اولا ثم استخدم البوت 🩶\n\n- @Tepthon\n- @TepthonHelp"
        bot.send_message(message.chat.id, text, reply_markup=must_join_markup())
        db.close()
        return
    if is_admin(message.from_user.id) or user.has_paid == True or user.is_vip == True:
        db.close()
        welcome_text = f"↢ اهلا يا {message.from_user.first_name} 🙋‍♀️\n❈ | وظيفة البوت النشر التلقائي \n❈ | الرد فقط عند عمل ريبلاي على رسائلي \n❈ | البوت مدمج بنموذج Ai \n❈ | Dev : @dev_mido"
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("ابدأ الآن ☃️", callback_data="start_now"),
            types.InlineKeyboardButton("إيقاف التشغيل 🛑", callback_data="stop_now")
        )
        markup.add(
            types.InlineKeyboardButton("اضف حساب ✅", callback_data="add_account"),
            types.InlineKeyboardButton("مسح حساب 💢", callback_data="del_account"),
            types.InlineKeyboardButton("اضف مجموعات ✅", callback_data="add_groups"),
            types.InlineKeyboardButton("حذف مجموعات 💢", callback_data="del_groups")
        )
        markup.add(
            types.InlineKeyboardButton("المجموعات الحالية 🏝️", callback_data="current_groups"),
            types.InlineKeyboardButton("الحسابات الحالية 🏝️", callback_data="current_accounts")
        )
        markup.add(
            types.InlineKeyboardButton("نشر تلقائي 🧀", callback_data="auto_post")
        )
        video_url = "https://h.uguu.se/KBifGOpz.mp4"
        try:
            bot.send_video(message.chat.id, video=video_url, caption=welcome_text, reply_markup=markup)
        except Exception:
            bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
        return
    star_amount = user.star_count if user else 100
    prices = [types.LabeledPrice(label="اشتراك البوت", amount=star_amount * 100)]
    bot.send_invoice(
        message.chat.id,
        title="تفعيل البوت",
        description=f"دفع {star_amount} نجمة لتفعيل خدمات البوت المتقدمة",
        provider_token="", 
        currency="XTR",
        prices=[types.LabeledPrice(label="Stars", amount=star_amount)],
        start_parameter="pay-stars",
        invoice_payload="stars-payment"
    )
    db.close()
@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    db = get_db()
    user = db.query(User).filter(User.user_id == str(message.from_user.id)).first()
    if user:
        user.has_paid = True
        db.commit()
    db.close()
    bot.send_message(message.chat.id, "✅ تم استلام الدفع وتفعيل البوت بنجاح!")
@bot.message_handler(func=lambda m: True)
def global_handler(message):
    handle_admin_commands(bot, message)
def refresh_control_menu(call):
    try:
        db = get_db()
        sessions_db = db.query(TelegramSession).filter(TelegramSession.user_id == str(call.from_user.id)).all()
        db.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        for s in sessions_db:
            is_running = s.session_string in sessions
            status_icon = "✅" if is_running else "❌"
            action_btn = "إيقاف 🛑" if is_running else "تشغيل 🟢"
            markup.add(types.InlineKeyboardButton(f"{status_icon} | {s.session_string[:10]}... | {action_btn}", callback_data=f"tglacc_{s.id}"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
    except: pass
def run_bot():
    start_flask()
    print("Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"Bot polling crashed: {e}")
            import time
            time.sleep(5)
if __name__ == "__main__":
    run_bot()
