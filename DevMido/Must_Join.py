import telebot
from telebot import types
CHANNELS = ["@akdoasa", "@akdoasa"]
def check_must_join(bot, user_id):
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            pass
    return True
def must_join_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btns = [types.InlineKeyboardButton(f"{c}", url=f"https://t.me/{c[1:]}") for c in CHANNELS]
    markup.add(*btns)
    return markup
