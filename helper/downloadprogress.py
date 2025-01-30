import time
from math import floor
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def progress_for_pyrogram(current, total, message, start, file_name):
    now = time.time()
    diff = now - start
    percentage = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff)
    time_to_completion = round((total - current) / speed) if speed else 0
    
    progress = "[{0}{1}]".format(
        ''.join(["⬢" for _ in range(floor(percentage / 5))]),
        ''.join(["⬡" for _ in range(20 - floor(percentage / 5))])
    )
    
    tmp = (
        f"**{file_name}**\n\n"
        f"**Download Started....**\n\n"
        f"{progress}\n\n"
        f"📁 **Size:** {humanbytes(current)} / {humanbytes(total)}\n"
        f"⏳️ **Done:** {round(percentage, 2)}%\n"
        f"🚀 **Speed:** {humanbytes(speed)}/s\n"
        f"⏰️ **ETA:** {TimeFormatter(time_to_completion)}"
    )
    
    try:
        # Edit message with new progress
        message.edit_text(
            text=tmp,
            parse_mode="markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data="cancel")]])
        )
    except FloodWait as e:
        time.sleep(e.value)
    except Exception:
        pass

def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            break
        size /= 1024
    return f"{size:.2f} {unit}"

def TimeFormatter(seconds: int) -> str:
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        (f"{days}d " if days else "") +
        (f"{hours}h " if hours else "") +
        (f"{minutes}m " if minutes else "") +
        (f"{seconds}s" if seconds else "")
    )
    return tmp.strip()
