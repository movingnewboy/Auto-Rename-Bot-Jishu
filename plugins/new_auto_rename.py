from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message
import re
import os
import asyncio
from datetime import datetime
from helper.database import db
from helper.downloadprogress import progress_for_pyrogram
from config import Config

# Dictionary to store user's processing settings
user_settings = {}
renaming_operations = {}

# Handler for /start_id command
@Client.on_message(filters.private & filters.command("start_id"))
async def set_start_id(client, message: Message):
    try:
        url_parts = message.text.split()
        if len(url_parts) < 2:
            return await message.reply("Please provide a valid message URL after the command")
        
        message_id = int(url_parts[1].split("/")[-1])
        user_id = message.from_user.id
        user_settings[user_id] = {"start_id": message_id, "processing": False}
        
        await message.reply(f"Start ID set to: {message_id}")
    except Exception as e:
        await message.reply(f"Error setting start ID: {str(e)}")

# Handler for /end_id command
@Client.on_message(filters.private & filters.command("end_id"))
async def set_end_id(client, message: Message):
    try:
        url_parts = message.text.split()
        if len(url_parts) < 2:
            return await message.reply("Please provide a valid message URL after the command")
        
        message_id = int(url_parts[1].split("/")[-1])
        user_id = message.from_user.id
        
        if user_id not in user_settings:
            user_settings[user_id] = {}
        user_settings[user_id]["end_id"] = message_id
        
        await message.reply(f"End ID set to: {message_id}")
    except Exception as e:
        await message.reply(f"Error setting end ID: {str(e)}")

# Handler for /set_username command
@app.on_message(filters.command("set_username") & filters.private)
async def set_username(client, message):
    try:
        username = message.text.split("/set_username", 1)[1].strip()
        await db.set_custom_username(message.from_user.id, username)
        await message.reply(f"✅ Custom username set to: {username}")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Handler for /process command
@Client.on_message(filters.private & filters.command("process"))
async def start_processing(client, message: Message):
    user_id = message.from_user.id
    settings = user_settings.get(user_id, {})
    
    if not settings.get("start_id") or not settings.get("end_id"):
        return await message.reply("❗ Please set both start_id and end_id first")
    
    try:
        # custom_username = await db.get_custom_username(user_id)
        # format_template = await db.get_format_template(user_id)
        
        # if not format_template:
        #     return await message.reply("Please set a format template first using /autorename")
        
        # if not custom_username:
        #     return await message.reply("Please set a custom username first using /set_username")

        # processing_msg = await message.reply("Starting processing...")
        # start_id = settings["start_id"]
        # end_id = settings["end_id"]

        template = await db.get_format_template(user_id)
        username = await db.get_custom_username(user_id)
        
        if not template or not username:
            return await message.reply("❗ Please set both username and template first")
        
        processing_msg = await message.reply("⏳ Starting processing...")
        start_id = settings["start_id"]
        end_id = settings["end_id"]
        
        for msg_id in range(start_id, end_id + 1):
            try:
                msg = await client.get_messages(Config.CHANNEL_ID, msg_id)

                if not msg or not (msg.document or msg.video):
                    continue
                    
                if msg and (msg.document or msg.video or msg.audio):
                    # Filename Processing
                    # original_name = msg.document.file_name if msg.document else msg.video.file_name
                    caption = msg.caption
                    original_name = caption.strip().split("\n")[0]
                    cleaned_name = re.sub(r'^@\w+\s*', '', original_name)
                    base_name = f"[{username}] - {cleaned_name}"
                    base_name = os.path.splitext(base_name)[0]  # Remove existing extension
                    final_name = template.replace("{file_name}", base_name) + ".mkv"
                    
                    # Download Process
                    start_time = time.time()
                    progress_msg = await message.reply_text(f"📥 Downloading: {original_name}")
                    file_path = await client.download_media(
                        msg,
                        progress=progress_for_pyrogram,
                        progress_args=(progress_msg, start_time, original_name)
                    )

                    # Upload Process
                    await progress_msg.edit("📤 Uploading to channel...")
                    await client.send_document(
                        Config.LOG_DATABASE,
                        document=file_path,
                        file_name=final_name,
                        caption=f"Renamed from: {original_name}",
                        progress=progress_for_pyrogram,
                        progress_args=(progress_msg, start_time, final_name)
                    )
                
                    await progress_msg.delete()
                    os.remove(file_path)
                    await processing_msg.edit(f"✅ Processed ID: {msg_id}")
                
                    # file_name = get_file_name(msg)
                    # caption = msg.caption
                    # file_name = caption.strip().split("\n")[0]
                    # cleaned_name = re.sub(r'^@\w+\s*', '', file_name)
                    # formatted_name = f"[{custom_username}] - {cleaned_name}"
                    # final_name = format_template.replace("{file_name}", formatted_name)
                    
                    # await process_and_forward(client, msg, final_name)
                    # await processing_msg.edit(f"Processed message ID: {msg_id}")
            
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"Error processing message {msg_id}: {str(e)}")
                continue
        
        await processing_msg.edit("🎉 Processing Completed!")
        del user_settings[user_id]
        
    except Exception as e:
        await message.reply(f"Error during processing: {str(e)}")

async def process_and_forward(client, message, new_name):
    try:
        file_path = await client.download_media(message)
        new_path = os.path.join(os.path.dirname(file_path), new_name)
        os.rename(file_path, new_path)
        
        # Send to user
        sent_message = await client.send_document(
            chat_id=message.chat.id,
            document=new_path,
            caption=message.caption
        )
        
        # Send to log channel
        await client.send_document(
            Config.LOG_DATABASE,
            document=new_path,
            caption=f"{new_name}"
        )
        
        os.remove(new_path)
        return sent_message
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        if os.path.exists(new_path):
            os.remove(new_path)

# Modified auto-rename handler
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    format_template = await db.get_format_template(user_id)
    custom_username = await db.get_custom_username(user_id)

    if not format_template or not custom_username:
        return await message.reply("Please set both username and format template first")

    try:
        file_id = message.document.file_id if message.document else \
                 message.video.file_id if message.video else \
                 message.audio.file_id
                 
        if file_id in renaming_operations:
            return

        renaming_operations[file_id] = datetime.now()
        
        original_name = get_file_name(message)
        cleaned_name = re.sub(r'^@\w+\s*', '', original_name)
        formatted_name = f"[{custom_username}] - {cleaned_name}"
        final_name = format_template.replace("{file_name}", formatted_name)
        
        download_msg = await message.reply("Downloading file...")
        file_path = await client.download_media(message, progress=progress_for_pyrogram, 
                                              progress_args=("Downloading...", download_msg, time.time()))
        
        # Rename file
        new_path = os.path.join(os.path.dirname(file_path), final_name)
        os.rename(file_path, new_path)
        
        # Upload to user
        upload_msg = await download_msg.edit("Uploading file...")
        sent_message = await client.send_document(
            message.chat.id,
            document=new_path,
            progress=progress_for_pyrogram,
            progress_args=("Uploading...", upload_msg, time.time())
        )
        
        # Upload to log channel
        await client.send_document(
            Config.LOG_DATABASE,
            document=new_path,
            caption=f"Renamed File: {final_name}\nOriginal Caption: {message.caption or 'No Caption'}"
        )
        
        await upload_msg.delete()
        os.remove(new_path)
        del renaming_operations[file_id]
        
    except Exception as e:
        await message.reply(f"Error processing file: {str(e)}")
        if os.path.exists(new_path):
            os.remove(new_path)
        del renaming_operations[file_id]

# Helper function
def get_file_name(message):
    if message.document:
        return message.document.file_name
    if message.video:
        return message.video.file_name
    if message.audio:
        return message.audio.file_name
    return ""

# Progress callback (keep your existing implementation)
# def progress_for_pyrogram(current, total, message, start):
#     # Your existing progress implementation
#     pass

# Command handlers (keep your existing /autorename implementation)
# @Client.on_message(filters.private & filters.command("autorename"))
# async def auto_rename_command(client, message):
#     user_id = message.from_user.id
#     format_template = message.text.split("/autorename", 1)[1].strip()
    
#     if "{file_name}" not in format_template:
#         return await message.reply("Format template must include {file_name} placeholder")
    
#     await db.set_format_template(user_id, format_template)
#     await message.reply("Format template updated successfully!")

@Client.on_message(filters.command("autorename") & filters.private)
async def set_template(client, message):
    try:
        template = message.text.split("/autorename", 1)[1].strip()
        if "{file_name}" not in template:
            return await message.reply("❗ Template must contain {file_name} placeholder")
        await db.set_format_template(message.from_user.id, template)
        await message.reply(f"✅ Format template updated:\n`{template}`")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")
