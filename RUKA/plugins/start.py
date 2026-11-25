from io import BytesIO
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from RUKA.utils.image_gen import generate_4k_welcome

router = Router()

RUKA_PIC = "https://ganga--link--ghhzdp9sv8hk.code.run/i/s0s0y8txhk.jpg"


def get_start_buttons(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Add Ruka to Your Group",
                url=f"https://t.me/{bot_username}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(text="📚 Help & Commands", callback_data="help_main"),
            InlineKeyboardButton(text="💓 About Ruka", callback_data="about_ruka"),
        ],
        [
            InlineKeyboardButton(text="💬 Support", url="https://t.me/sup_ruka_bot"),
            InlineKeyboardButton(text="📢 Updates", url="https://t.me/sup_ruka_bot"),
        ],
    ])


def get_help_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔨 Admin (32)", callback_data="help_admin"),
            InlineKeyboardButton(text="🛡️ Security & Warns", callback_data="help_locks"),
        ],
        [
            InlineKeyboardButton(text="🎮 Levels & Games", callback_data="help_games"),
            InlineKeyboardButton(text="🌸 Anime & Fun", callback_data="help_anime"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI & Utility", callback_data="help_ai"),
            InlineKeyboardButton(text="👑 Owner & Sudo", callback_data="help_owner"),
        ],
        [
            InlineKeyboardButton(text="🏠 Back to Start", callback_data="help_home"),
        ],
    ])


# --- /start Command ---
@router.message(CommandStart())
async def start_cmd(message: Message):
    user = message.from_user
    if not user:
        return

    me = await message.bot.get_me()
    await message.answer_photo(
        photo=RUKA_PIC,
        caption=(
            f"💓 **Kon'nichiwa, {user.full_name}!**\n\n"
            f"My heart's already racing—I'm **Ruka Sarashina**, your dedicated anime group management bot! 🌸\n\n"
            f"✨ **What I can do for you:**\n"
            f"• Protect your group with **32+ Admin & Anti-Spam tools**\n"
            f"• Greet new members with **4K Anime Welcome Cards**\n"
            f"• Entertain your chat with **Grok AI, Boss Raids, Gacha & 100+ commands**\n\n"
            f"Tap **Help & Commands** below to explore everything~"
        ),
        reply_markup=get_start_buttons(me.username),
    )


# --- /help Command ---
@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer_photo(
        photo=RUKA_PIC,
        caption=(
            "📚 **Ruka's Command Grimoire (100+ Commands)**\n\n"
            "Choose a category below to see detailed commands and how to use them~"
        ),
        reply_markup=get_help_buttons(),
    )


# --- Auto-Welcome New Group Members (4K Pillow Card) ---
@router.message(F.new_chat_members)
async def welcome_new_member(message: Message):
    for user in message.new_chat_members:
        if user.is_bot:
            continue

        pfp_bytes = None
        try:
            photos = await message.bot.get_user_profile_photos(user.id, limit=1)
            if photos.total_count > 0:
                file = await message.bot.get_file(photos.photos[0][-1].file_id)
                pfp_bytes = BytesIO()
                await message.bot.download_file(file.file_path, pfp_bytes)
                pfp_bytes.seek(0)
        except Exception:
            pass

        img = generate_4k_welcome(user.first_name, message.chat.title or "Group", pfp_bytes)
        photo_file = BufferedInputFile(img.getvalue(), filename="welcome_4k.png")

        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📜 Group Rules", callback_data="rules_btn"),
                InlineKeyboardButton(text="💬 Support", url="https://t.me/sup_ruka_bot"),
            ]
        ])

        await message.answer_photo(
            photo=photo_file,
            caption=(
                f"🌸 **Welcome to {message.chat.title}, {user.full_name}!**\n\n"
                f"Yay, a new friend! Make sure to read the rules, be kind, and have an amazing time with us! 💓"
            ),
            reply_markup=buttons,
        )


# --- Callback Handlers ---
@router.callback_query(F.data.startswith(("help_", "about_ruka", "rules_btn")))
async def help_callbacks(query: CallbackQuery):
    data = query.data
    back_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Help", callback_data="help_main")]
    ])

    if data == "about_ruka":
        return await query.answer(
            "💓 Ruka-Bot v3.0 | aiogram 3 + PostgreSQL + 4K Pillow + Grok AI!",
            show_alert=True
        )

    if data == "rules_btn":
        return await query.answer(
            "📜 Be respectful, no spam, no NSFW, and listen to the admins!",
            show_alert=True
        )

    if data == "help_main":
        await query.message.edit_caption(
            caption=(
                "📚 **Ruka's Command Grimoire (100+ Commands)**\n\n"
                "Choose a category below to see detailed commands and how to use them~"
            ),
            reply_markup=get_help_buttons()
        )

    elif data == "help_home":
        me = await query.bot.get_me()
        await query.message.edit_caption(
            caption=(
                f"💓 **Kon'nichiwa!**\n\n"
                f"I'm **Ruka Sarashina**, your dedicated anime group management bot! 🌸\n"
                f"Tap **Help & Commands** below to explore everything~"
            ),
            reply_markup=get_start_buttons(me.username)
        )

    elif data == "help_admin":
        await query.message.edit_caption(
            caption=(
                "🔨 **Admin Commands (32)**\n"
                "• `/adminpanel` — Interactive Control Center\n"
                "• `/ban`, `/unban`, `/tban 1h`, `/dban`, `/sban`\n"
                "• `/kick`, `/dkick`, `/skick`\n"
                "• `/mute`, `/unmute`, `/tmute 30m`, `/dmute`, `/smute`\n"
                "• `/purge`, `/spurge`, `/del`\n"
                "• `/pin`, `/unpin`, `/unpinall`\n"
                "• `/promote`, `/fullpromote`, `/demote`, `/settitle`\n"
                "• `/invitelink`, `/revokeinvite`, `/setgtitle`, `/setgdesc`, `/slowmode`\n"
                "• `/zombies`, `/admins`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_locks":
        await query.message.edit_caption(
            caption=(
                "🛡️ **Security, Warns & Settings**\n"
                "• `/settings` — Interactive PostgreSQL Settings Panel\n"
                "• `/warn`, `/unwarn`, `/warns`, `/resetwarns`, `/setwarnlimit 3`\n"
                "• `/antiflood 5` — Auto-mute spammers\n"
                "• `/blacklist <word>`, `/unblacklist`, `/blacklists`\n"
                "• `/lock <type>`, `/unlock <type>`, `/locks`\n"
                "• `/nightmode on|off`, `/filter`, `/stop`, `/filters`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_games":
        await query.message.edit_caption(
            caption=(
                "🎮 **Levels, Economy & Games**\n"
                "• `/rank`, `/level` — 4K Anime Profile Card\n"
                "• `/leaderboard` (`/lb`) — Top 10 members\n"
                "• `/boss` — Group Anime Boss Raid!\n"
                "• `/daily`, `/bal`, `/give`, `/rob`, `/bet`\n"
                "• `/rps`, `/trivia`, `/guess`, `/duel`, `/slot`, `/dart`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_anime":
        await query.message.edit_caption(
            caption=(
                "🌸 **Anime, AniList & Fun**\n"
                "• `/anime <name>` — 4K AniList Card + Synopsis\n"
                "• `/manga <name>`, `/animechar <name>`\n"
                "• `/topanime`, `/airing <name>`, `/gacha`\n"
                "• `/couple`, `/ship`, `/poll`, `/choose`, `/tagall`\n"
                "• `/waifu`, `/neko`, `/hug`, `/pat`, `/slap`, `/kiss` (+20 more!)"
            ),
            reply_markup=back_btn
        )

    elif data == "help_ai":
        await query.message.edit_caption(
            caption=(
                "🤖 **Ruka AI & Group Utilities**\n"
                "• `/ruka <msg>` (`/ai`, `/ask`), `/clearai`\n"
                "• `/roast`, `/compliment`, `/summarize`, `/translate <lang>`, `/animeidea`\n"
                "• `/connect`, `/disconnect`, `/connection`\n"
                "• `/setrules`, `/rules`, `/save`, `/get`, `/notes`, `/clear`\n"
                "• `/info` (4K Card), `/id`, `/ping`, `/afk`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_owner":
        await query.message.edit_caption(
            caption=(
                "👑 **Owner, Dev & Sudo Commands (18)**\n"
                "• `/stats`, `/sudolist`, `/addsudo`, `/rmsudo`\n"
                "• `/block`, `/unblock`, `/gban`, `/ungban`, `/gmute`, `/ungmute`\n"
                "• `/broadcast`, `/chatlist`, `/leavechat`, `/send`\n"
                "• `/eval`, `/sh`, `/logs`, `/restart`, `/backup`"
            ),
            reply_markup=back_btn
        )

    await query.answer()