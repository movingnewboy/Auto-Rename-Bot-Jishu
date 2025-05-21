# Auto rename bot with start_id and end_id functionality
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from PIL import Image
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
import os
import re
import asyncio
import time
from helper.database import madflixbotz
from helper.utils import progress_for_pyrogram
from config import Config

user_settings = {}

@Client.on_message(filters.private & filters.command("start_id"))
async def set_start_id(client, message: Message):
    try:
        msg_id = int(message.text.split()[1])
        user_settings[message.from_user.id] = {"start_id": msg_id}
        await message.reply(f"✅ Start ID set to: {msg_id}")
    except:
        await message.reply("❌ Usage: /start_id <message_id>")

@Client.on_message(filters.private & filters.command("end_id"))
async def set_end_id(client, message: Message):
    try:
        msg_id = int(message.text.split()[1])
        user_settings.setdefault(message.from_user.id, {})["end_id"] = msg_id
        await message.reply(f"✅ End ID set to: {msg_id}")
    except:
        await message.reply("❌ Usage: /end_id <message_id>")

@Client.on_message(filters.private & filters.command("process"))
async def process_range(client, message: Message):
    user_id = message.from_user.id
    settings = user_settings.get(user_id, {})
    start_id = settings.get("start_id")
    end_id = settings.get("end_id")

    if not start_id or not end_id:
        return await message.reply("❗ Please set both /start_id and /end_id.")

    format_template = await madflixbotz.get_format_template(user_id)
    username = await madflixbotz.get_custom_username(user_id)
    media_pref = await madflixbotz.get_media_preference(user_id)

    if not format_template or not username:
        return await message.reply("❗ Set template and username first with /autorename and /set_username")

    await message.reply(f"🔄 Processing from {start_id} to {end_id}...")

    for msg_id in range(start_id, end_id + 1):
        try:
            msg = await client.get_messages(Config.CHANNEL_ID, msg_id)
            if not msg or not (msg.document or msg.video or msg.audio):
                continue

            if msg.caption:
                original_name = msg.caption.strip().split("\n")[0]
            else:
                continue

            cleaned_name = re.sub(r'^@\w+\s*', '', original_name)
            base_name = f"[{username}] - {cleaned_name}"
            final_name = format_template.replace("{file_name}", os.path.splitext(base_name)[0]) + ".mkv"

            temp_msg = await message.reply(f"⬇️ Downloading {final_name}")
            file_path = await client.download_media(
                msg, progress=progress_for_pyrogram, progress_args=(final_name, temp_msg, time.time())
            )

            duration = 0
            try:
                metadata = extractMetadata(createParser(file_path))
                if metadata and metadata.has("duration"):
                    duration = metadata.get("duration").seconds
            except:
                pass

            thumb_id = await madflixbotz.get_thumbnail(user_id)
            ph_path = None
            if thumb_id:
                ph_path = await client.download_media(thumb_id)
            elif msg.video and msg.video.thumbs:
                ph_path = await client.download_media(msg.video.thumbs[0].file_id)

            if ph_path:
                img = Image.open(ph_path).convert("RGB")
                img.resize((320, 320)).save(ph_path, "JPEG")

            new_path = os.path.join(os.path.dirname(file_path), final_name)
            os.rename(file_path, new_path)

            media_type = media_pref or ("document" if msg.document else "video" if msg.video else "audio")

            await temp_msg.edit("⬆️ Uploading...")
            if media_type == "document":
                await client.send_document(Config.LOG_DATABASE, new_path, caption=final_name, thumb=ph_path)
            elif media_type == "video":
                await client.send_video(Config.LOG_DATABASE, new_path, caption=final_name, thumb=ph_path, duration=duration)
            elif media_type == "audio":
                await client.send_audio(Config.LOG_DATABASE, new_path, caption=final_name, thumb=ph_path, duration=duration)

            os.remove(new_path)
            if ph_path:
                os.remove(ph_path)
            await temp_msg.delete()
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"❌ Error on ID {msg_id}: {e}")

    await message.reply("✅ Batch processing complete.")
