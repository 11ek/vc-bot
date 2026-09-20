import os
import asyncio
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from pyrogram.enums import ChatMembersFilter

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from yt_dlp import YoutubeDL

# --- CONFIG (Environment Variables or Direct Values) ---
API_ID = int(os.environ.get("API_ID", 31479209))  # Replace with API ID
API_HASH = os.environ.get("API_HASH", "f84030d144bcc866208208d3ea00f20e")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8803836538:AAEcV58wdgvHQvH_boEe0qYVbPd5sDg6ppU")
STRING_SESSION = os.environ.get("STRING_SESSION", "BQHgVakAamoK-EwqaqntFH6XM-PQsmzcpu91us6L15aSQUsIc_1BiczBn4sTTEkcKlYWZiy5nx6OyFkkdzBZKd3cCSDTxppKGiTODELZflqJYb3GbUGIwqs5PBHzV7o03zBOFVDtJsagDRtdQd05qJcOnN7EEJujDck2tccP1WsMm8FQN1oF8_XmDG44QXVNo0aQbmmtOdQm9KcGYSMXpmFIdbIln7AbLJr7qbYcwJ6POL1B6FpXWVaYSaa2LwAxzNLd2rVmOFX_1ikqiW8WRGTYSkMX0Hp06Xo3qnZx3upqIuVO-MRKKyfl-dq-7PzYyL7HcQAlV4LFrm0PvvgpnZAl4nrZdQAAAAGGr8EHAA")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "@epic_guruji_bot")

# Clients Setup (Pyrogram)
bot_app = Client("bot_client", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_app = Client("user_client", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

vc = PyTgCalls(user_app)

QUEUE = {}
AUTH_USERS = {}  # {chat_id: set(user_ids)}

YDL_OPTS = {
    'format': 'bestvideo[height<=1080]+bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
}

def get_info(query, video=False):
    opts = YDL_OPTS.copy()
    if not video:
        opts['format'] = 'bestaudio/best'

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)
        if 'entries' in info:
            info = info['entries'][0]
        return {
            'title': info.get('title'),
            'url': info.get('url'),
            'webpage_url': info.get('webpage_url'),
            'thumbnail': info.get('thumbnail'),
            'duration': info.get('duration_string', 'Live'),
        }

async def is_admin_or_auth(client, message):
    if message.chat.type.value == "private":
        return True
    
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0

    # Check authorized users
    if chat_id in AUTH_USERS and user_id in AUTH_USERS[chat_id]:
        return True

    # Check Group Admins
    try:
        async for admin in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if admin.user.id == user_id:
                return True
    except Exception:
        pass

    return False

async def play_next(chat_id):
    if not QUEUE.get(chat_id):
        return
    item = QUEUE[chat_id][0]

    # Mediastream integration
    if item['mode'] == 'audio':
        stream = MediaStream(
            item['url'],
            video_flags=MediaStream.Flags.IGNORE
        )
    else:
        stream = MediaStream(item['url'])

    await vc.play(chat_id, stream)

    caption = f"""
**{'🎵' if item['mode']=='audio' else '🎬'} Now Playing**

**Title:** {item['title']}
**Duration:** {item['duration']}
**Requested By:** [{item['requester_name']}](tg://user?id={item['requester_id']})
**Type:** {item['mode'].upper()}

-@epic_india
"""
    if item.get('thumbnail'):
        await bot_app.send_photo(chat_id, photo=item['thumbnail'], caption=caption)
    else:
        await bot_app.send_message(chat_id, caption)

# --- DM /START COMMAND ---
@bot_app.on_message(filters.private & filters.command("start"))
async def start_dm(client, message):
    text = (
        "🙏Heyy I'm music bot 🙏\n"
        "(मैं एक गाना चलाने वाला बॉट हूँ)\n\n"
        "Join @epic_india have a nice day ahead🌸✨"
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")]
    ])
    await message.reply_text(text, reply_markup=buttons)

# --- AUTOMATIONS (Link Deletion, Command Deletion, New Member Mute) ---

@bot_app.on_message(filters.group, group=-1)
async def group_guard(client, message):
    text = message.text or message.caption or ""

    # Delete commands after receiving request
    if text.startswith("/"):
        try:
            await message.delete()
        except Exception:
            pass

    # Auto Delete Links
    elif "http://" in text or "https://" in text or "t.me/" in text:
        try:
            await message.delete()
            warn = await message.reply_text("⚠️ Links are not allowed in this group!\n\n-@epic_india")
            await asyncio.sleep(5)
            await warn.delete()
        except Exception:
            pass

@bot_app.on_message(filters.group & filters.new_chat_members)
async def mute_new_members(client, message):
    for member in message.new_chat_members:
        try:
            until_time = datetime.now(timezone.utc) + timedelta(hours=48)
            await client.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=member.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_time
            )
            msg = await message.reply_text(
                f"🔇 {member.first_name} has been muted for 48 hours as a safety measure.\n\n-@epic_india"
            )
            await asyncio.sleep(10)
            await msg.delete()
        except Exception as e:
            print(f"Mute error: {e}")

# --- COMMAND HANDLERS ---

@bot_app.on_message(filters.command("auth"))
async def auth_user(client, message):
    if not await is_admin_or_auth(client, message):
        msg = await message.reply_text("❌ Only Admins can authorize users!\n\n-@epic_india")
        await asyncio.sleep(5)
        await msg.delete()
        return

    target_user = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
    elif len(message.command) > 1:
        try:
            target_user = await client.get_users(message.command[1])
        except Exception:
            msg = await message.reply_text("❌ User not found!\n\n-@epic_india")
            await asyncio.sleep(5)
            await msg.delete()
            return

    if not target_user:
        msg = await message.reply_text("❌ Reply to a user or pass username to auth.\n\n-@epic_india")
        await asyncio.sleep(5)
        await msg.delete()
        return

    chat_id = message.chat.id
    if chat_id not in AUTH_USERS:
        AUTH_USERS[chat_id] = set()

    AUTH_USERS[chat_id].add(target_user.id)
    msg = await message.reply_text(
        f"✅ [{target_user.first_name}](tg://user?id={target_user.id}) is now authorized for restricted commands!\n\n-@epic_india"
    )
    await asyncio.sleep(7)
    await msg.delete()

@bot_app.on_message(filters.command("play"))
async def play(client, message):
    if len(message.command) < 2:
        msg = await message.reply_text("Give a song name to play!\n\n-@epic_india")
        await asyncio.sleep(5)
        await msg.delete()
        return

    query = message.text.split(None, 1)[1]
    sender = message.from_user
    status_msg = await message.reply_text(f"🔎 Searching `{query}`...")

    info = get_info(query, video=False)
    info['mode'] = 'audio'
    info['requester_name'] = sender.first_name if sender else "User"
    info['requester_id'] = sender.id if sender else 0

    chat_id = message.chat.id
    if chat_id not in QUEUE:
        QUEUE[chat_id] = []
    QUEUE[chat_id].append(info)

    await status_msg.delete()

    if len(QUEUE[chat_id]) == 1:
        await play_next(chat_id)
    else:
        await message.reply_text(f"➕ Queued at **#{len(QUEUE[chat_id])}**: {info['title']}\n\n-@epic_india")

@bot_app.on_message(filters.command("vplay"))
async def vplay(client, message):
    if len(message.command) < 2:
        msg = await message.reply_text("Give a video name to play!\n\n-@epic_india")
        await asyncio.sleep(5)
        await msg.delete()
        return

    query = message.text.split(None, 1)[1]
    sender = message.from_user
    status_msg = await message.reply_text(f"🔎 Searching Video: `{query}`...")

    info = get_info(query, video=True)
    info['mode'] = 'video'
    info['requester_name'] = sender.first_name if sender else "User"
    info['requester_id'] = sender.id if sender else 0

    chat_id = message.chat.id
    if chat_id not in QUEUE:
        QUEUE[chat_id] = []
    QUEUE[chat_id].append(info)

    await status_msg.delete()

    if len(QUEUE[chat_id]) == 1:
        await play_next(chat_id)
    else:
        await message.reply_text(f"➕ Video Queued at **#{len(QUEUE[chat_id])}**: {info['title']}\n\n-@epic_india")

@bot_app.on_message(filters.command("refresh"))
async def refresh(client, message):
    try:
        await vc.leave_call(message.chat.id)
    except Exception:
        pass
    QUEUE[message.chat.id] = []
    await message.reply_text("♻️ Server Refreshed, VC Cleaned\n\n-@epic_india")

@bot_app.on_message(filters.command(["queue", "q"]))
async def queue_list(client, message):
    q = QUEUE.get(message.chat.id, [])
    if not q:
        await message.reply_text("Queue Empty\n\n-@epic_india")
        return
    text = "**Queue:**\n"
    for i, item in enumerate(q):
        text += f"{i+1}. {item['title']} - {item['requester_name']}\n"
    text += "\n-@epic_india"
    await message.reply_text(text)

@bot_app.on_message(filters.command("stop"))
async def stop(client, message):
    if not await is_admin_or_auth(client, message):
        msg = await message.reply_text("❌ Only Admins or Auth Users can stop playback!\n\n-@epic_india")
        await asyncio.sleep(5)
        await msg.delete()
        return

    QUEUE[message.chat.id] = []
    try:
        await vc.leave_call(message.chat.id)
    except Exception:
        pass
    await message.reply_text("⏹️ Stopped & Left VC\n\n-@epic_india")

@bot_app.on_message(filters.command(["skip", "next"]))
async def skip(client, message):
    if not await is_admin_or_auth(client, message):
        msg = await message.reply_text("❌ Only Admins or Auth Users can skip songs!\n\n-@epic_india")
        await asyncio.sleep(5)
        await msg.delete()
        return

    chat_id = message.chat.id
    if QUEUE.get(chat_id):
        QUEUE[chat_id].pop(0)
        if QUEUE[chat_id]:
            await play_next(chat_id)
        else:
            try:
                await vc.leave_call(chat_id)
            except Exception:
                pass
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
    print("Bot and VC Client Started Successfully!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
