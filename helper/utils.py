import math, time
from datetime import datetime
from pytz import timezone
from config import Config, Txt 
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# async def progress_for_pyrogram(current, total, file_name, message, start):
#     # start = float(start) if isinstance(start, str) else start
#     now = time.time()
#     diff = now - start
#     if round(diff % 5.00) == 0 or current == total:        
#         percentage = current * 100 / total
#         speed = current / diff
#         elapsed_time = round(diff) * 1000
#         time_to_completion = round((total - current) / speed) * 1000
#         estimated_total_time = elapsed_time + time_to_completion

#         elapsed_time = TimeFormatter(milliseconds=elapsed_time)
#         estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

#         progress = "{0}{1}".format(
#             ''.join(["⬢" for i in range(math.floor(percentage / 5))]),
#             ''.join(["⬡" for i in range(20 - math.floor(percentage / 5))])
#         )      
#         tmp = f"**{file_name}**\n\n**Download Started....**\n\n"  # Modified line
#         tmp += progress + Txt.PROGRESS_BAR.format(              # Modified line
#             round(percentage, 2),
#             humanbytes(current),
#             humanbytes(total),
#             humanbytes(speed),            
#             estimated_total_time if estimated_total_time != '' else "0 s"
#         )
#         # tmp = progress + Txt.PROGRESS_BAR.format( 
#         #     round(percentage, 2),
#         #     humanbytes(current),
#         #     humanbytes(total),
#         #     humanbytes(speed),            
#         #     estimated_total_time if estimated_total_time != '' else "0 s"
#         # )
#         try:
#             await message.edit(
#                 text=f"{ud_type}\n\n{tmp}",               
#                 reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel ✖️", callback_data="close")]])                                               
#             )
#         except:
#             pass

async def progress_for_pyrogram(current, total, file_name, message, start):
    try:
        now = time.time()
        diff = now - start
        
        # Update every 2 seconds or on completion
        if diff >= 2 or current == total:
            percentage = current * 100 / total
            speed = current / diff if diff > 0 else 0
            elapsed_time = round(diff) * 1000
            time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
            
            progress = "[{0}{1}]".format(
                ''.join("⬢" for _ in range(math.floor(percentage / 5))),
                ''.join("⬡" for _ in range(20 - math.floor(percentage / 5)))
            )
            
            tmp = (
                f"**{file_name}**\n\n"
                f"**Download Progress**\n{progress}\n\n"
                f"📦 **Size**: {humanbytes(current)} / {humanbytes(total)}\n"
                f"📊 **Done**: {round(percentage, 2)}%\n"
                f"🚀 **Speed**: {humanbytes(speed)}/s\n"
                f"⏳ **ETA**: {TimeFormatter(time_to_completion)}"
            )
            
            try:
                await message.edit_text(
                    text=tmp,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancel", callback_data="cancel")]])
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except RPCError:
                pass
                
    except Exception as e:
        print(f"Progress Error: {e}")
        
def humanbytes(size):    
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'b'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2] 

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)

async def send_log(b, u):
    if Config.LOG_CHANNEL is not None:
        curr = datetime.now(timezone("Asia/Kolkata"))
        date = curr.strftime('%d %B, %Y')
        time = curr.strftime('%I:%M:%S %p')
        await b.send_message(
            Config.LOG_CHANNEL,
            f"<b><u>New User Started The Bot</u></b> \n\n<b>User ID</b> : `{u.id}` \n<b>First Name</b> : {u.first_name} \n<b>Last Name</b> : {u.last_name} \n<b>User Name</b> : @{u.username} \n<b>User Mention</b> : {u.mention} \n<b>User Link</b> : <a href='tg://openmessage?user_id={u.id}'>Click Here</a>\n\nDate: {date}\nTime: {time}\n\nBy: {b.mention}"
        )
        



# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @Madflix_Bots
# Developer @JishuDeveloper
