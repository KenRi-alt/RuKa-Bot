from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..utils import chatAction
from ..utils.image_gen import generate_4k_welcome


@Client.on_message(filters.command("start"))
@chatAction(action="typing")
async def start_command(client, message):
    user = message.from_user
    name = user.first_name

    # Download user's profile picture in memory (if they have one)
    pfp_bytes = None
    if user.photo:
        pfp_bytes = await client.download_media(user.photo.big_file_id, in_memory=True)

    # Generate 4K Pillow card
    img = generate_4k_welcome(name, "RuKa-Bot ✨", pfp_bytes)

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Me to Your Group", url=f"https://t.me/{client.me.username}?startgroup=true")
        ],
        [
            InlineKeyboardButton("📚 Help & Commands", callback_data="help_menu"),
            InlineKeyboardButton("💬 Support", url="https://t.me/sup_ruka_bot")
        ]
    ])

    await message.reply_photo(
        photo=img,
        caption=(
            f"👋 **Kon'nichiwa, {user.mention}!**\n\n"
            f"I'm **RuKa-Bot**, your anime-themed group management assistant.\n"
            f"Use me to keep your groups safe, clean, and fun!"
        ),
        reply_markup=buttons
    )