from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message
from PIL import Image
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
import re
import os
import asyncio
import math, time
from datetime import datetime
from helper.database import madflixbotz
from helper.utils import progress_for_pyrogram, humanbytes, convert
from config import Config

user_settings = {}
renaming_operations = {}

# Set start_id
@Client.on_message(filters.private & filters.command("start_id"))
async def set_start_id(client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("Please provide a valid message URL after the command.")
        msg_id = int(parts[1].split("/")[-1])
        user_settings[message.from_user.id] = {"start_id": msg_id}
        await message.reply(f"✅ Start ID set to: {msg_id}")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Set end_id
@Client.on_message(filters.private & filters.command("end_id"))
async def set_end_id(client, message: Message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("Please provide a valid message URL after the command.")
        msg_id = int(parts[1].split("/")[-1])
        user_settings.setdefault(message.from_user.id, {})["end_id"] = msg_id
        await message.reply(f"✅ End ID set to: {msg_id}")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Set username
@Client.on_message(filters.command("set_username") & filters.private)
async def set_username(client, message):
    try:
        username = message.text.split("/set_username", 1)[1].strip()
        await madflixbotz.set_custom_username(message.from_user.id, username)
        await message.reply(f"✅ Custom username set to: {username}")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Set thumbnail
@Client.on_message(filters.command("setthumb") & filters.private)
async def set_thumbnail(client, message: Message):
    if not message.photo:
        return await message.reply("❗ Please send a photo to set as thumbnail.")
    try:
        file_id = message.photo.file_id
        await madflixbotz.set_thumbnail(message.from_user.id, file_id)
        await message.reply("✅ Thumbnail set successfully!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Delete thumbnail
@Client.on_message(filters.command("delthumb") & filters.private)
async def delete_thumbnail(client, message: Message):
    try:
        await madflixbotz.set_thumbnail(message.from_user.id, None)
        await message.reply("✅ Thumbnail removed successfully!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Set format template
@Client.on_message(filters.command("autorename") & filters.private)
async def set_template(client, message):
    try:
        template = message.text.split("/autorename", 1)[1].strip()
        if "{file_name}" not in template:
            return await message.reply("❗ Template must contain `{file_name}` placeholder.")
        await madflixbotz.set_format_template(message.from_user.id, template)
        await message.reply(f"✅ Format template updated:\n`{template}`")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Helper to get filename
def get_file_name(message):
    if message.document:
        return message.document.file_name
    elif message.video:
        return message.video.file_name
    elif message.audio:
        return message.audio.file_name
    return ""

# Auto rename handler
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    format_template = await madflixbotz.get_format_template(user_id)
    custom_username = await madflixbotz.get_custom_username(user_id)
    media_preference = await madflixbotz.get_media_preference(user_id)

    if not format_template or not custom_username:
        return await message.reply("❗ Please set both username and format template first.")

    media_type = None
    file_id = None
    ph_path = None

    try:
        if message.document:
            file_id = message.document.file_id
            media_type = media_preference or "document"
        elif message.video:
            file_id = message.video.file_id
            media_type = media_preference or "video"
        elif message.audio:
            file_id = message.audio.file_id
            media_type = media_preference or "audio"
        else:
            return await message.reply("❗ Unsupported file type.")

        if file_id in renaming_operations:
            return

        renaming_operations[file_id] = time.time()

        caption = message.caption or get_file_name(message)
        original_name = caption.strip().split("\n")[0]
        cleaned_name = re.sub(r'^@\w+\s*', '', original_name)
        formatted_name = f"[{custom_username}] - {cleaned_name}"
        formatted_name = os.path.splitext(formatted_name)[0]
        final_name = format_template.replace("{file_name}", formatted_name) + ".mkv"

        progress_msg = await message.reply("📥 Downloading file...")
        file_path = await client.download_media(
            message,
            progress=progress_for_pyrogram,
            progress_args=(original_name, progress_msg, time.time())
        )

        duration = 0
        try:
            metadata = extractMetadata(createParser(file_path))
            if metadata.has("duration"):
                duration = metadata.get("duration").seconds
        except Exception:
            pass

        c_thumb = await madflixbotz.get_thumbnail(message.chat.id)
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
        elif media_type == "video" and message.video.thumbs:
            ph_path = await client.download_media(message.video.thumbs[0].file_id)

        if ph_path:
            img = Image.open(ph_path).convert("RGB")
            img = img.resize((320, 320))
            img.save(ph_path, "JPEG")

        new_path = os.path.join(os.path.dirname(file_path), final_name)
        os.rename(file_path, new_path)

        await progress_msg.edit("📤 Uploading file...")
        if media_type == "document":
            await client.send_document(
                message.chat.id,
                document=new_path,
                caption=final_name,
                thumb=ph_path,
                progress=progress_for_pyrogram,
                progress_args=(final_name, progress_msg, time.time())
            )
        elif media_type == "video":
            await client.send_video(
                message.chat.id,
                video=new_path,
                caption=final_name,
                duration=duration,
                thumb=ph_path,
                progress=progress_for_pyrogram,
                progress_args=(final_name, progress_msg, time.time())
            )
        elif media_type == "audio":
            await client.send_audio(
                message.chat.id,
                audio=new_path,
                caption=final_name,
                duration=duration,
                thumb=ph_path,
                progress=progress_for_pyrogram,
                progress_args=(final_name, progress_msg, time.time())
            )

        await progress_msg.delete()
        os.remove(new_path)
        if ph_path:
            os.remove(ph_path)
        del renaming_operations[file_id]

    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")
        if file_id in renaming_operations:
            del renaming_operations[file_id]
        if os.path.exists(file_path):
            os.remove(file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
