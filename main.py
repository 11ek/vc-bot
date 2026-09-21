import os
import asyncio
import random
from datetime import datetime, timedelta, timezone
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.enums import ChatMembersFilter
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from yt_dlp import YoutubeDL

API_ID = int(os.environ.get("API_ID", 31479209))
API_HASH = os.environ.get("API_HASH", "f84030d144bcc866208208d3ea00f20e")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8803836538:AAHcpZP3TojuDKqnO2wiPM_LRa_7PVzNMmo")
STRING_SESSION = os.environ.get("STRING_SESSION", "BQHgVakAamoK-EwqaqntFH6XM-PQsmzcpu91us6L15aSQUsIc_1BiczBn4sTTEkcKlYWZiy5nx6OyFkkdzBZKd3cCSDTxppKGiTODELZflqJYb3GbUGIwqs5PBHzV7o03zBOFVDtJsagDRtdQd05qJcOnN7EEJujDck2tccP1WsMm8FQN1oF8_XmDG44QXVNo0aQbmmtOdQm9KcGYSMXpmFIdbIln7AbLJr7qbYcwJ6POL1B6FpXWVaYSaa2LwAxzNLd2rVmOFX_1ikqiW8WRGTYSkMX0Hp06Xo3qnZx3upqIuVO-MRKKyfl-dq-7PzYyL7HcQAlV4LFrm0PvvgpnZAl4nrZdQAAAAGGr8EHAA")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "@epic_india_singer_bot")

if not all([API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, BOT_USERNAME]):
    raise ValueError("API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, BOT_USERNAME env me set karo!")

bot_app = Client("bot_client, api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_app = Client("user_client", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)
vc = PyTgCalls(user_app)

QUEUE = {}
AUTH_USERS = {}
VERIFIED_USERS = set() # captcha passed users
CAPTCHA_DATA = {} # {user_id: correct_answer}

YDL_OPTS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch'}

def _sync_get_info(query, video=False):
    opts = YDL_OPTS.copy()
    if video:
        opts['format'] = 'bestvideo[height<=720]+bestaudio/best'
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        if 'entries' in info:
            info = info['entries'][0]
        return {
            'title': info.get('title', 'Unknown'),
            'url': info.get('url'),
            'webpage_url': info.get('webpage_url'),
            'thumbnail': info.get('thumbnail'),
            'duration': info.get('duration_string', 'Live'),
        }

async def get_info(query, video=False):
    return await asyncio.to_thread(_sync_get_info, query, video)

async def is_admin_or_auth(client, message):
    if message.chat.type.value == "private":
        return True
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if user_id in VERIFIED_USERS:
        pass
    if chat_id in AUTH_USERS and user_id in AUTH_USERS[chat_id]:
        return True
    try:
        async for admin in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if admin.user.id == user_id:
                return True
    except:
        pass
    return False

async def play_next(chat_id):
    if not QUEUE.get(chat_id):
        return
    item = QUEUE[chat_id][0]
    try:
        if item['mode'] == 'audio':
            stream = MediaStream(item['url'], video_flags=MediaStream.Flags.IGNORE)
        else:
            stream = MediaStream(item['url'])
        await vc.play(chat_id, stream)
    except Exception as e:
        print(f"Play error: {e}")
        QUEUE[chat_id].pop(0)
        if QUEUE[chat_id]:
            await play_next(chat_id)
        return
    caption = f"**{'🎵' if item['mode']=='audio' else '🎬'} Now Playing**\n\n**Title:** {item['title']}\n**Duration:** {item['duration']}\n**Requested By:** [{item['requester_name']}](tg://user?id={item['requester_id']})\n\n-@epic_india"
    try:
        if item.get('thumbnail'):
            await bot_app.send_photo(chat_id, photo=item['thumbnail'], caption=caption)
        else:
            await bot_app.send_message(chat_id, caption)
    except:
        pass

@bot_app.on_message(filters.private & filters.command("start"))
async def start_dm(client, message):
    text = "🙏Heyy I'm music bot 🙏\n(मैं एक गाना चलाने वाला बॉट हूँ)\n\nJoin @epic_india have a nice day ahead🌸✨"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")]])
    await message.reply_text(text, reply_markup=buttons)

@bot_app.on_message(filters.group, group=-1)
async def group_guard(client, message):
    text = message.text or message.caption or ""
    if text.startswith("/"):
        try: await message.delete()
        except: pass
    elif "http://" in text or "https://" in text or "t.me/" in text:
        try:
            await message.delete()
            warn = await message.reply_text("⚠️ Links are not allowed!\n\n-@epic_india")
            await asyncio.sleep(5)
            await warn.delete()
        except: pass

# --- CAPTCHA ---
@bot_app.on_message(filters.group & filters.new_chat_members)
async def captcha_new_members(client, message):
    for member in message.new_chat_members:
        if member.is_bot:
            continue
        if member.id in VERIFIED_USERS:
            continue
        try:
            await client.restrict_chat_member(message.chat.id, member.id, ChatPermissions(can_send_messages=False))
            a, b = random.randint(1, 9), random.randint(1, 9)
            correct = a + b
            wrong = [correct+1, correct-1, correct+2]
            random.shuffle(wrong)
            options = [correct] + wrong[:2]
            random.shuffle(options)
            CAPTCHA_DATA[member.id] = correct
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(str(o), callback_data=f"cap_{member.id}_{o}") for o in options]])
            await message.reply_text(f"👋 {member.first_name}, captcha solve karo ({a} + {b} =?)\nSolve karke VC join kar sakte ho.\n\n-@epic_india", reply_markup=kb)
        except Exception as e:
            print(f"Captcha error: {e}")

@bot_app.on_callback_query(filters.regex(r"^cap_"))
async def captcha_verify(client, query):
    _, uid, ans = query.data.split("_")
    uid, ans = int(uid), int(ans)
    if query.from_user.id!= uid:
        await query.answer("Ye tumhara captcha nahi hai!", show_alert=True)
        return
    if CAPTCHA_DATA.get(uid) == ans:
        VERIFIED_USERS.add(uid)
        CAPTCHA_DATA.pop(uid, None)
        try:
            await client.restrict_chat_member(query.message.chat.id, uid, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
        except: pass
        await query.message.edit_text(f"✅ {query.from_user.first_name} verified! Ab VC join kar sakte ho.\n\n-@epic_india")
    else:
        await query.answer("❌ Galat jawab! Dubara try karo.", show_alert=True)

@bot_app.on_message(filters.command("play"))
async def play(client, message):
    if message.from_user and message.from_user.id not in VERIFIED_USERS:
        # allow but warn once - VC join ke liye captcha jaruri
        pass
    if len(message.command) < 2:
        return
    query = message.text.split(None, 1)[1]
    sender = message.from_user
    status_msg = await message.reply_text(f"🔎 Searching `{query}`...")
    try:
        info = await get_info(query, video=False)
    except Exception as e:
        await status_msg.edit_text(f"❌ Search failed!\n\n-@epic_india")
        return
    info['mode'] = 'audio'
    info['requester_name'] = sender.first_name if sender else "User"
    info['requester_id'] = sender.id if sender else 0
    chat_id = message.chat.id
    QUEUE.setdefault(chat_id, []).append(info)
    await status_msg.delete()
    if len(QUEUE[chat_id]) == 1:
        await play_next(chat_id)
    else:
        await message.reply_text(f"➕ Queued at **#{len(QUEUE[chat_id])}**: {info['title']}\n\n-@epic_india")

@bot_app.on_message(filters.command("vplay"))
async def vplay(client, message):
    if len(message.command) < 2:
        return
    query = message.text.split(None, 1)[1]
    sender = message.from_user
    status_msg = await message.reply_text(f"🔎 Searching Video: `{query}`...")
    try:
        info = await get_info(query, video=True)
    except:
        await status_msg.edit_text("❌ Search failed!\n\n-@epic_india")
        return
    info['mode'] = 'video'
    info['requester_name'] = sender.first_name if sender else "User"
    info['requester_id'] = sender.id if sender else 0
    chat_id = message.chat.id
    QUEUE.setdefault(chat_id, []).append(info)
    await status_msg.delete()
    if len(QUEUE[chat_id]) == 1:
        await play_next(chat_id)
    else:
        await message.reply_text(f"➕ Video Queued at **#{len(QUEUE[chat_id])}**: {info['title']}\n\n-@epic_india")

@bot_app.on_message(filters.command("auth"))
async def auth_user(client, message):
    if not await is_admin_or_auth(client, message):
        return
    target_user = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try: target_user = await client.get_users(message.command[1])
        except: return
    if not target_user:
        return
    AUTH_USERS.setdefault(message.chat.id, set()).add(target_user.id)
    await message.reply_text(f"✅ [{target_user.first_name}](tg://user?id={target_user.id}) authorized!\n\n-@epic_india")

@bot_app.on_message(filters.command("refresh"))
async def refresh(client, message):
    try: await vc.leave_call(message.chat.id)
    except: pass
    QUEUE[message.chat.id] = []
    await message.reply_text("♻️ Server Refreshed\n\n-@epic_india")

@bot_app.on_message(filters.command(["queue", "q"]))
async def queue_list(client, message):
    q = QUEUE.get(message.chat.id, [])
    if not q:
        await message.reply_text("Queue Empty\n\n-@epic_india")
        return
    text = "**Queue:**\n" + "\n".join([f"{i+1}. {x['title']}" for i, x in enumerate(q)]) + "\n\n-@epic_india"
    await message.reply_text(text)

@bot_app.on_message(filters.command("stop"))
async def stop(client, message):
    if not await is_admin_or_auth(client, message):
        return
    QUEUE[message.chat.id] = []
    try: await vc.leave_call(message.chat.id)
    except: pass
    await message.reply_text("⏹️ Stopped\n\n-@epic_india")

@bot_app.on_message(filters.command(["skip", "next"]))
async def skip(client, message):
    if not await is_admin_or_auth(client, message):
        return
    chat_id = message.chat.id
    if QUEUE.get(chat_id):
        QUEUE[chat_id].pop(0)
        if QUEUE[chat_id]:
            await play_next(chat_id)
        else:
            try: await vc.leave_call(chat_id)
            except: pass
    await message.reply_text("⏭️ Skipped\n\n-@epic_india")

@vc.on_stream_end()
async def ended(_, update):
    chat_id = update.chat_id
    if QUEUE.get(chat_id):
        QUEUE[chat_id].pop(0)
        if QUEUE[chat_id]:
            await play_next(chat_id)

async def main():
    await user_app.start()
    await vc.start()
    await bot_app.start()
    print("Bot Started!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
