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
@Client.on_message(filters.command("set_username") & filters.private)
async def set_username(client, message):
    try:
        username = message.text.split("/set_username", 1)[1].strip()
        await madflixbotz.set_custom_username(message.from_user.id, username)
        await message.reply(f"✅ Custom username set to: {username}")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("setthumb") & filters.private)
async def set_thumbnail(client, message: Message):
    try:
        if not message.photo:
            return await message.reply("❗ Please send a photo to set as thumbnail.")
        
        # Get the file_id of the largest photo size
        file_id = message.photo.file_id
        
        # Save file_id in database
        await madflixbotz.set_thumbnail(message.from_user.id, file_id)
        await message.reply("✅ Thumbnail set successfully!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@Client.on_message(filters.command("delthumb") & filters.private)
async def delete_thumbnail(client, message: Message):
    try:
        await madflixbotz.set_thumbnail(message.from_user.id, None)
        await message.reply("✅ Thumbnail removed successfully!")
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
        template = await madflixbotz.get_format_template(user_id)
        username = await madflixbotz.get_custom_username(user_id)
        # media_type = await madflixbotz.get_media_preference(user_id)
        media_preference = await madflixbotz.get_media_preference(user_id)
        # thumb_file_id = await madflixbotz.get_thumbnail(user_id)  # Get thumbnail file_id
        
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

                    # Extract information from the incoming file name
                    if msg.document:
                        file_id = msg.document.file_id
                        media_type = media_preference or "document"  # Use preferred media type or default to document
                    elif msg.video:
                        file_id = msg.video.file_id
                        media_type = media_preference or "video"  # Use preferred media type or default to video
                    elif msg.audio:
                        file_id = msg.audio.file_id
                        media_type = media_preference or "audio"  # Use preferred media type or default to audio
                    else:
                        return await message.reply_text("Unsupported File Type")
            
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
                        file_name=original_name,
                        progress=progress_for_pyrogram,
                        progress_args=(original_name, progress_msg, time.time())  # Correct order
                    )

                    # duration = 0
                    # try:
                    #     metadata = extractMetadata(createParser(file_path))
                    #     if metadata.has("duration"):
                    #         duration = metadata.get('duration').seconds
                    # except Exception as e:
                    #     print(f"Error getting duration: {e}")
                        
                    c_thumb = await madflixbotz.get_thumbnail(message.chat.id)
                    # c_caption = await madflixbotz.get_caption(message.chat.id)
                    # caption = c_caption.format(filename=final_name) if c_caption else f"**{final_name}**"
            
                    if c_thumb:
                        ph_path = await client.download_media(c_thumb)
                        print(f"Thumbnail downloaded successfully. Path: {ph_path}")
                    elif media_type == "video" and message.video.thumbs:
                        ph_path = await client.download_media(msg.video.thumbs[0].file_id)
            
                    if ph_path:
                        Image.open(ph_path).convert("RGB").save(ph_path)
                        img = Image.open(ph_path)
                        img.resize((320, 320))
                        img.save(ph_path, "JPEG")

                    # Use thumbnail if available
                    # thumb = thumb_file_id if thumb_file_id else None
                
                    # Upload Process
                    await progress_msg.edit("📤 Uploading to channel...")
                    # await client.send_document(
                    #     Config.LOG_DATABASE,
                    #     document=file_path,
                    #     file_name=final_name,
                    #     caption=f"{final_name}",
                    #     progress=progress_for_pyrogram,
                    #     progress_args=(final_name, progress_msg, start_time)
                    # )

                    # Rename file
                    new_path = os.path.join(os.path.dirname(file_path), final_name)
                    os.rename(file_path, new_path)
            
                    # upload_msg = await download_msg.edit("Uploading file...")
                    
                    try:
                        type = media_type  # Use 'media_type' variable instead
                        if type == "document":
                            await client.send_document(
                                message.chat.id,
                                document=new_path,
                                caption=f"{final_name}",
                                thumb=ph_path,
                                progress=progress_for_pyrogram,
                                progress_args=(final_name, progress_msg, time.time())
                            )
                            # channel_msg = await client.send_document(
                            #     Config.LOG_DATABASE,
                            #     document=new_path,
                            #     file_name=final_name,
                            #     caption=f"{final_name}",
                            #     thumb=ph_path,
                            #     progress=progress_for_pyrogram,
                            #     progress_args=(final_name, progress_msg, start_time)
                            # )
                            # # Forward the uploaded file from the channel back to the bot without forwarder name
                            # if channel_msg:
                            #     await client.copy_message(
                            #         chat_id=message.chat.id,  # Send to user
                            #         from_chat_id=Config.LOG_DATABASE,  # From the channel
                            #         message_id=channel_msg.id  # Get the uploaded message ID
                            #     )
            
                        elif type == "video":
                            await client.send_video(
                                message.chat.id,
                                video=new_path,
                                caption=f"{final_name}",
                                thumb=ph_path,
                                duration=duration,
                                progress=progress_for_pyrogram,
                                progress_args=(final_name, progress_msg, time.time())
                            )
                            # channel_msg = await client.send_video(
                            #     Config.LOG_DATABASE,
                            #     video=new_path,
                            #     file_name=final_name,
                            #     caption=f"{final_name}",
                            #     duration=duration,
                            #     progress=progress_for_pyrogram,
                            #     progress_args=(final_name, progress_msg, start_time)
                            # )
                            # if channel_msg:
                            #     await client.copy_message(
                            #         chat_id=message.chat.id,  # Send to user
                            #         from_chat_id=Config.LOG_DATABASE,  # From the channel
                            #         message_id=channel_msg.id  # Get the uploaded message ID
                            #     )
                        elif type == "audio":
                            await client.send_audio(
                                message.chat.id,
                                audio=new_path,
                                caption=f"{final_name}",
                                thumb=ph_path,
                                duration=duration,
                                progress=progress_for_pyrogram,
                                progress_args=(final_name, progress_msg, time.time())
                            )
                            # channel_msg = await client.send_audio(
                            #     Config.LOG_DATABASE,
                            #     audio=new_path,
                            #     file_name=final_name,
                            #     caption=f"{final_name}",
                            #     thumb=ph_path,
                            #     duration=duration,
                            #     progress=progress_for_pyrogram,
                            #     progress_args=(final_name, progress_msg, start_time)
                            # )
                            # if channel_msg:
                            #     await client.copy_message(
                            #         chat_id=message.chat.id,  # Send to user
                            #         from_chat_id=Config.LOG_DATABASE,  # From the channel
                            #         message_id=channel_msg.id  # Get the uploaded message ID
                            #     )
                    except Exception as e:
                        os.remove(file_path)
                        if ph_path:
                            os.remove(ph_path)
                        # Mark the file as ignored
                        return await progress_msg.edit(f"Error: {e}")
        
                    print(f"{final_name} Downloading Completed✅")
                
                    await progress_msg.delete()
                    os.remove(file_path)
                    await processing_msg.edit(f"✅ Processed ID: {msg_id}")
            
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"Error processing message {msg_id}: {str(e)}")
                continue
        
        await processing_msg.edit("🎉 Processing Completed!")
        del user_settings[user_id]
        
    except Exception as e:
        await message.reply(f"Error during processing: {str(e)}")

# Modified auto-rename handler
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    format_template = await madflixbotz.get_format_template(user_id)
    custom_username = await madflixbotz.get_custom_username(user_id)
    media_preference = await madflixbotz.get_media_preference(user_id)
    # thumb_file_id = await madflixbotz.get_thumbnail(user_id)  # Get thumbnail file_id
    
    if not format_template or not custom_username:
        return await message.reply("Please set both username and format template first")

    try:
        # Extract information from the incoming file name
        if message.document:
            file_id = message.document.file_id
            # file_name = message.document.file_name
            media_type = media_preference or "document"  # Use preferred media type or default to document
        elif message.video:
            file_id = message.video.file_id
            # file_name = f"{message.video.file_name}.mp4"
            media_type = media_preference or "video"  # Use preferred media type or default to video
        elif message.audio:
            file_id = message.audio.file_id
            # file_name = f"{message.audio.file_name}.mp3"
            media_type = media_preference or "audio"  # Use preferred media type or default to audio
        else:
            return await message.reply_text("Unsupported File Type")

        # print(f"Original File Name: {file_name}")
                 
        if file_id in renaming_operations:
            return

        renaming_operations[file_id] = time.time()
        
        original_name = get_file_name(message)
        caption = message.caption
        caption_name = caption.strip().split("\n")[0]
        cleaned_name = re.sub(r'^@\w+\s*', '', caption_name)
        formatted_name = f"[{custom_username}] - {cleaned_name}"
        formatted_name = os.path.splitext(formatted_name)[0]  # Remove existing extension
        final_name = format_template.replace("{file_name}", formatted_name) + ".mkv" 

        # caption = message.caption
        # original_name = caption.strip().split("\n")[0]
        # cleaned_name = re.sub(r'^@\w+\s*', '', original_name)
        # base_name = f"[{custom_username}] - {cleaned_name}"
        # base_name = os.path.splitext(base_name)[0]  # Remove existing extension
        # final_name = template.replace("{file_name}", base_name) + ".mkv" 
        
        download_msg = await message.reply("Downloading file...")
        file_path = await client.download_media(
            message,
            progress=progress_for_pyrogram,
            progress_args=(original_name, download_msg, time.time())  # Correct order
        )

        duration = 0
        try:
            metadata = extractMetadata(createParser(file_path))
            if metadata.has("duration"):
                duration = metadata.get('duration').seconds
        except Exception as e:
            print(f"Error getting duration: {e}")
            
        c_thumb = await madflixbotz.get_thumbnail(message.chat.id)
        # c_caption = await madflixbotz.get_caption(message.chat.id)
        # caption = c_caption.format(filename=final_name) if c_caption else f"**{final_name}**"
        
        if c_thumb:
            ph_path = await client.download_media(c_thumb)
            print(f"Thumbnail downloaded successfully. Path: {ph_path}")
        elif media_type == "video" and message.video.thumbs:
            ph_path = await client.download_media(message.video.thumbs[0].file_id)

        if ph_path:
            Image.open(ph_path).convert("RGB").save(ph_path)
            img = Image.open(ph_path)
            img.resize((320, 320))
            img.save(ph_path, "JPEG")   
        
        # Rename file
        new_path = os.path.join(os.path.dirname(file_path), final_name)
        os.rename(file_path, new_path)

        upload_msg = await download_msg.edit("Uploading file...")
        
        try:
            type = media_type  # Use 'media_type' variable instead
            if type == "document":
                # await client.send_document(
                #     message.chat.id,
                #     document=new_path,
                #     caption=f"{final_name}",
                #     thumb=ph_path,
                #     progress=progress_for_pyrogram,
                #     progress_args=(final_name, upload_msg, time.time())
                # )
                channel_msg = await client.send_document(
                    Config.LOG_DATABASE,
                    document=new_path,
                    file_name=final_name,
                    caption=f"{final_name}",
                    thumb=ph_path,
                    progress=progress_for_pyrogram,
                    progress_args=(final_name, upload_msg, start_time)
                )
                if channel_msg:
                    await client.copy_message(
                        chat_id=message.chat.id,  # Send to user
                        from_chat_id=Config.LOG_DATABASE,  # From the channel
                        message_id=channel_msg.id  # Get the uploaded message ID
                    )
            elif type == "video":
                # await client.send_video(
                #     message.chat.id,
                #     video=new_path,
                #     caption=f"{final_name}",
                #     duration=duration,
                #     progress=progress_for_pyrogram,
                #     progress_args=(final_name, upload_msg, time.time())
                # )
                channel_msg = await client.send_video(
                    Config.LOG_DATABASE,
                    video=new_path,
                    file_name=final_name,
                    caption=f"{final_name}",
                    thumb=ph_path,
                    progress=progress_for_pyrogram,
                    progress_args=(final_name, upload_msg, start_time)
                )
                if channel_msg:
                    await client.copy_message(
                        chat_id=message.chat.id,  # Send to user
                        from_chat_id=Config.LOG_DATABASE,  # From the channel
                        message_id=channel_msg.id  # Get the uploaded message ID
                    )
            elif type == "audio":
                # await client.send_audio(
                #     message.chat.id,
                #     audio=new_path,
                #     caption=f"{final_name}",
                #     thumb=ph_path,
                #     duration=duration,
                #     progress=progress_for_pyrogram,
                #     progress_args=(final_name, upload_msg, time.time())
                # )
                channel_msg = await client.send_audio(
                    Config.LOG_DATABASE,
                    audio=new_path,
                    file_name=final_name,
                    caption=f"{final_name}",
                    thumb=ph_path,
                    progress=progress_for_pyrogram,
                    progress_args=(final_name, upload_msg, start_time)
                )
                if channel_msg:
                    await client.copy_message(
                        chat_id=message.chat.id,  # Send to user
                        from_chat_id=Config.LOG_DATABASE,  # From the channel
                        message_id=channel_msg.id  # Get the uploaded message ID
                    )
        except Exception as e:
            os.remove(file_path)
            if ph_path:
                os.remove(ph_path)
            # Mark the file as ignored
            return await upload_msg.edit(f"Error: {e}")
        
        # Upload to user
        # upload_msg = await download_msg.edit("Uploading file...")
        # sent_message = await client.send_document(
        #     message.chat.id,
        #     document=new_path,
        #     caption=f"{final_name}",
        #     progress=progress_for_pyrogram,
        #     progress_args=(final_name, upload_msg, time.time())
        # )
        
        # Upload to log channel
        # await client.send_document(
        #     Config.LOG_DATABASE,
        #     document=new_path,
        #     caption=f"{final_name}"
        # )
        
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

@Client.on_message(filters.command("autorename") & filters.private)
async def set_template(client, message):
    try:
        template = message.text.split("/autorename", 1)[1].strip()
        if "{file_name}" not in template:
            return await message.reply("❗ Template must contain {file_name} placeholder")
        await madflixbotz.set_format_template(message.from_user.id, template)
        await message.reply(f"✅ Format template updated:\n`{template}`")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")
