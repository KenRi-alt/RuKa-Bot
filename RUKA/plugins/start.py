from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..utils import chatAction
from ..utils.image_gen import generate_4k_welcome


def get_start_buttons(bot_username: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Me to Your Group", url=f"https://t.me/{bot_username}?startgroup=true")
        ],
        [
            InlineKeyboardButton("📚 Help & Commands", callback_data="help_main"),
            InlineKeyboardButton("💓 About Ruka", callback_data="about_ruka")
        ],
        [
            InlineKeyboardButton("💬 Support", url="https://t.me/sup_ruka_bot"),
            InlineKeyboardButton("📢 Updates", url="https://t.me/sup_ruka_bot")
        ]
    ])


# --- /start Command ---
@Client.on_message(filters.command("start"))
@chatAction(action="typing")
async def start_command(client, message):
    user = message.from_user
    if not user:
        return

    pfp_bytes = None
    if user.photo:
        pfp_bytes = await client.download_media(user.photo.big_file_id, in_memory=True)

    img = generate_4k_welcome(user.first_name, "RuKa-Bot ✨", pfp_bytes)

    await message.reply_photo(
        photo=img,
        caption=(
            f"💓 **Kon'nichiwa, {user.mention}!**\n\n"
            f"My heart's already racing—I'm **Ruka Sarashina**, your dedicated anime group management bot! 🌸\n\n"
            f"✨ **What I can do for you:**\n"
            f"• Keep your group safe with **20+ Admin & Anti-Spam tools**\n"
            f"• Greet new members with **4K Anime Welcome Cards**\n"
            f"• Bring fun with **AI, Anime GIFs & Waifu commands**\n\n"
            f"Tap **Help & Commands** below to see everything I can do~"
        ),
        reply_markup=get_start_buttons(client.me.username)
    )


# --- /help Command ---
@Client.on_message(filters.command("help"))
@chatAction(action="typing")
async def help_command(client, message):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔨 Admin (20)", callback_data="help_admin"),
            InlineKeyboardButton("🔒 Locks & Anti-Spam", callback_data="help_locks")
        ],
        [
            InlineKeyboardButton("🤖 AI & Anime", callback_data="help_anime"),
            InlineKeyboardButton("🔗 Connect & Misc", callback_data="help_misc")
        ],
        [
            InlineKeyboardButton("🏠 Back to Start", callback_data="help_home")
        ]
    ])
    await message.reply_text(
        "📚 **Ruka's Command Grimoire**\n\n"
        "Choose a category below to explore my commands! Don't worry, I'll guide you through all of them~",
        reply_markup=buttons
    )


# --- Auto-Welcome New Group Members (4K Card) ---
@Client.on_message(filters.new_chat_members & filters.group)
async def welcome_new_member(client, message):
    for user in message.new_chat_members:
        if user.is_bot:
            continue

        pfp_bytes = None
        if user.photo:
            pfp_bytes = await client.download_media(user.photo.big_file_id, in_memory=True)

        img = generate_4k_welcome(user.first_name, message.chat.title, pfp_bytes)

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📜 Group Rules", callback_data="rules_btn"),
                InlineKeyboardButton("💬 Support", url="https://t.me/sup_ruka_bot")
            ]
        ])

        await message.reply_photo(
            photo=img,
            caption=(
                f"🌸 **Welcome to {message.chat.title}, {user.mention}!**\n\n"
                f"Yay, a new friend! Make sure to read the rules, be kind, and have an amazing time with us! 💓"
            ),
            reply_markup=buttons
        )


# --- Callback Handlers for Help & About ---
@Client.on_callback_query(filters.regex(r"^(help_|about_ruka|rules_btn)"))
async def start_help_callbacks(client, query):
    data = query.data
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Help", callback_data="help_main")]])

    if data == "help_main":
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔨 Admin (20)", callback_data="help_admin"),
                InlineKeyboardButton("🔒 Locks & Anti-Spam", callback_data="help_locks")
            ],
            [
                InlineKeyboardButton("🤖 AI & Anime", callback_data="help_anime"),
                InlineKeyboardButton("🔗 Connect & Misc", callback_data="help_misc")
            ],
            [
                InlineKeyboardButton("🏠 Back to Start", callback_data="help_home")
            ]
        ])
        await query.message.edit_caption(
            "📚 **Ruka's Command Grimoire**\n\n"
            "Choose a category below to explore my commands!",
            reply_markup=buttons
        ) if query.message.photo else await query.message.edit_text(
            "📚 **Ruka's Command Grimoire**\n\nChoose a category below!",
            reply_markup=buttons
        )

    elif data == "help_home":
        await query.message.edit_caption(
            f"💓 **Kon'nichiwa!**\n\n"
            f"I'm **Ruka Sarashina**, your dedicated anime group management bot! 🌸\n"
            f"Tap **Help & Commands** below to see everything I can do~",
            reply_markup=get_start_buttons(client.me.username)
        )

    elif data == "about_ruka":
        await query.answer(
            "💓 Ruka-Bot v2.0 | Built with Pyrogram + PostgreSQL + 4K Pillow!",
            show_alert=True
        )

    elif data == "rules_btn":
        await query.answer(
            "📜 Be respectful, no spam, no NSFW, and listen to the admins!",
            show_alert=True
        )

    elif data == "help_admin":
        text = (
            "🔨 **Admin Commands (20):**\n"
            "• `/adminpanel` — Interactive Control Center\n"
            "• `/ban`, `/unban`, `/tban`, `/kick`\n"
            "• `/mute`, `/unmute`, `/tmute`\n"
            "• `/purge`, `/del`, `/pin`, `/unpin`\n"
            "• `/promote`, `/demote`, `/settitle`\n"
            "• `/invitelink`, `/setgtitle`, `/setgdesc`, `/zombies`"
        )
        await (query.message.edit_caption(text, reply_markup=back_btn) if query.message.photo else query.message.edit_text(text, reply_markup=back_btn))

    elif data == "help_locks":
        text = (
            "🔒 **Locks & Security:**\n"
            "• `/lock <type>` / `/unlock <type>`\n"
            "• `/antilink on|off` — Block unauthorized links\n"
            "• `/antiflood <limit>` — Stop spammers\n"
            "• `/nightmode on|off` — Auto-lock at night"
        )
        await (query.message.edit_caption(text, reply_markup=back_btn) if query.message.photo else query.message.edit_text(text, reply_markup=back_btn))

    elif data == "help_anime":
        text = (
            "🤖 **AI & Anime Fun:**\n"
            "• `/ai <prompt>` — Chat with Ruka AI\n"
            "• `/waifu`, `/neko`, `/hug`, `/pat`, `/slap`, `/kiss`\n"
            "• `/anime <name>`, `/manga <name>`"
        )
        await (query.message.edit_caption(text, reply_markup=back_btn) if query.message.photo else query.message.edit_text(text, reply_markup=back_btn))

    elif data == "help_misc":
        text = (
            "🔗 **Connect & Utility:**\n"
            "• `/connect <chat_id>` — Manage group from PM\n"
            "• `/info`, `/id`, `/afk`, `/ping`\n"
            "• `/backup` — PostgreSQL backup (Owner only)"
        )
        await (query.message.edit_caption(text, reply_markup=back_btn) if query.message.photo else query.message.edit_text(text, reply_markup=back_btn))