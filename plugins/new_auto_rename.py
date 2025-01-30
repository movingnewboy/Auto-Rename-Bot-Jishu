from pyrogram import Client, filters
from pyrogram.errors import FloodWait, RPCError
from pyrogram.types import Message
import re
import os
import asyncio
from datetime import datetime
from helper.database import madflixbotz
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
@Client.on_message(filters.private & filters.command("set_username"))
async def set_custom_username(client, message: Message):
    try:
        username = message.text.split("/set_username", 1)[1].strip()
        user_id = message.from_user.id
        await madflixbotz.set_custom_username(user_id, username)
        await message.reply(f"Custom username set to: {username}")
    except Exception as e:
        await message.reply(f"Error setting username: {str(e)}")

# Handler for /process command
@Client.on_message(filters.private & filters.command("process"))
async def start_processing(client, message: Message):
    user_id = message.from_user.id
    settings = user_settings.get(user_id, {})
    
    if not settings.get("start_id") or not settings.get("end_id"):
        return await message.reply("Please set both start and end IDs first")
    
    try:
        custom_username = await madflixbotz.get_custom_username(user_id)
        format_template = await madflixbotz.get_format_template(user_id)
        
        if not format_template:
            return await message.reply("Please set a format template first using /autorename")
        
        if not custom_username:
            return await message.reply("Please set a custom username first using /set_username")

        processing_msg = await message.reply("Starting processing...")
        start_id = settings["start_id"]
        end_id = settings["end_id"]
        
        for msg_id in range(start_id, end_id + 1):
            try:
                msg = await client.get_messages(Config.CHANNEL_ID, msg_id)
                
                if msg and (msg.document or msg.video or msg.audio):
                    file_name = get_file_name(msg)
                    cleaned_name = re.sub(r'^@\w+\s*', '', file_name)
                    formatted_name = f"[{custom_username}] - {cleaned_name}"
                    final_name = format_template.replace("{file_name}", formatted_name)
                    
                    await process_and_forward(client, msg, final_name)
                    await processing_msg.edit(f"Processed message ID: {msg_id}")
            
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"Error processing message {msg_id}: {str(e)}")
                continue
        
        await processing_msg.edit("Processing completed!")
        
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
            caption=f"Renamed File: {new_name}\nOriginal Caption: {message.caption}"
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
    format_template = await madflixbotz.get_format_template(user_id)
    custom_username = await madflixbotz.get_custom_username(user_id)

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
def progress_for_pyrogram(current, total, message, start):
    # Your existing progress implementation
    pass

# Command handlers (keep your existing /autorename implementation)
@Client.on_message(filters.private & filters.command("autorename"))
async def auto_rename_command(client, message):
    user_id = message.from_user.id
    format_template = message.text.split("/autorename", 1)[1].strip()
    
    if "{file_name}" not in format_template:
        return await message.reply("Format template must include {file_name} placeholder")
    
    await madflixbotz.set_format_template(user_id, format_template)
    await message.reply("Format template updated successfully!")
