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
from RUKA.utils.db import get_chat_settings

router = Router()

RUKA_PIC = "https://ganga--link--ghhzdp9sv8hk.code.run/i/s0s0y8txhk.jpg"
PHOTO_CACHE: dict[str, str] = {}


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
            InlineKeyboardButton(text="🔨 Moderation", callback_data="help_admin"),
            InlineKeyboardButton(text="🛡️ Security & Feds", callback_data="help_locks"),
        ],
        [
            InlineKeyboardButton(text="🎮 Economy & Games", callback_data="help_games"),
            InlineKeyboardButton(text="🌸 Social & Gacha", callback_data="help_social"),
        ],
        [
            InlineKeyboardButton(text="🎬 Anime & AI", callback_data="help_ai"),
            InlineKeyboardButton(text="⚙️ Utilities & Staff", callback_data="help_misc"),
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
    photo_to_send = PHOTO_CACHE.get("ruka_main", RUKA_PIC)
    sent = await message.answer_photo(
        photo=photo_to_send,
        caption=(
            f"💓 **Kon'nichiwa, {user.full_name}!**\n\n"
            f"I'm **Ruka Sarashina**—your energetic, dependable companion for keeping groups safe, active, and unforgettable! 🌸\n\n"
            f"✨ **What I bring to your community:**\n"
            f"• **Pro-Grade Moderation** — Anti-Raid, Federations, Approvals & Smart Logs\n"
            f"• **Custom Welcomes** — Warm, personalized greeting cards for new members\n"
            f"• **Social, Gacha & AI** — Marriages, Family Trees, Boss Raids & smart conversations\n\n"
            f"All commands work with both `/` and `!`. Tap **Help & Commands** below to begin."
        ),
        reply_markup=get_start_buttons(me.username),
    )
    if "ruka_main" not in PHOTO_CACHE and sent.photo:
        PHOTO_CACHE["ruka_main"] = sent.photo[-1].file_id


# --- /help Command ---
@router.message(Command("help", prefix="/!"))
async def help_cmd(message: Message):
    photo_to_send = PHOTO_CACHE.get("ruka_main", RUKA_PIC)
    sent = await message.answer_photo(
        photo=photo_to_send,
        caption=(
            "📚 **Ruka's Command Guide**\n\n"
            "Select a category below for detailed usage instructions and examples."
        ),
        reply_markup=get_help_buttons(),
    )
    if "ruka_main" not in PHOTO_CACHE and sent.photo:
        PHOTO_CACHE["ruka_main"] = sent.photo[-1].file_id


# --- Auto-Welcome New Group Members (Respects /settings toggle) ---
@router.message(F.new_chat_members)
async def welcome_new_member(message: Message):
    try:
        s = await get_chat_settings(message.chat.id)
        if not s.get("welcome", True) or s.get("antiraid", False):
            return
    except Exception:
        pass

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
        photo_file = BufferedInputFile(img.getvalue(), filename="welcome.jpg")

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
                f"We're so glad you joined us! Take a moment to check the group rules and say hello. 💓"
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
            "💓 Ruka Sarashina\n"
            "Your intelligent anime group companion.\n\n"
            "👨‍💻 Creator: @Nocis_creed\n"
            "🛠️ Co-Creator: @dont_try_to_copy_mee",
            show_alert=True
        )

    if data == "rules_btn":
        return await query.answer(
            "📜 Be respectful, avoid spam, and follow the group admins' instructions!",
            show_alert=True
        )

    if data == "help_main":
        await query.message.edit_caption(
            caption="📚 **Ruka's Command Guide**\n\nSelect a category below for detailed usage instructions and examples.",
            reply_markup=get_help_buttons()
        )

    elif data == "help_home":
        me = await query.bot.get_me()
        await query.message.edit_caption(
            caption=(
                f"💓 **Kon'nichiwa!**\n\n"
                f"I'm **Ruka Sarashina**—your energetic, dependable companion for keeping groups safe, active, and unforgettable! 🌸\n\n"
                f"Tap **Help & Commands** below to explore."
            ),
            reply_markup=get_start_buttons(me.username)
        )

    elif data == "help_admin":
        await query.message.edit_caption(
            caption=(
                "🔨 **Moderation Commands** *(Group)*\n\n"
                "• `/adminpanel` — Open the interactive admin menu.\n"
                "• `/ban` | `/unban` | `/tban <1h/2d>` — Ban or temp-ban users.\n"
                "• `/dban` | `/sban` — Delete message & ban, or silent ban.\n"
                "• `/kick` | `/dkick` | `/skick` — Remove a user from the chat.\n"
                "• `/mute` | `/unmute` | `/tmute <30m>` — Restrict messaging.\n"
                "• `/purge` | `/del` — Reply to bulk-delete or remove a message.\n"
                "• `/pin` | `/unpin` | `/unpinall` — Manage pinned messages.\n"
                "• `/promote` | `/demote` | `/settitle <title>` — Manage admins.\n"
                "• `/slowmode <sec>` | `/invitelink` | `/admins` — Group controls."
            ),
            reply_markup=back_btn
        )

    elif data == "help_locks":
        await query.message.edit_caption(
            caption=(
                "🛡️ **Security, Warns & Federations** *(Group)*\n\n"
                "• `/settings` — Toggle CAPTCHA, Anti-Raid, Clean Service & more.\n"
                "• `/approve` | `/unapprove` | `/approved` — Exempt trusted users.\n"
                "• `/report` or `@admin` — Report rule-breakers with quick-action buttons.\n"
                "• `/setlog <id>` | `/unsetlog` | `/logchannel` — Group audit logs.\n"
                "• `/newfed <name>` | `/joinfed <id>` | `/fban` | `/funban` — Federations.\n"
                "• `/warn` | `/unwarn` | `/warns` | `/setwarnlimit <num>` — Warnings.\n"
                "• `/lock <type>` | `/unlock <type>` | `/nightmode on|off`\n"
                "• `/antiflood <num>` | `/blacklist <word>` | `/filter <word> <reply>`\n"
                "• `/disable <cmd>` | `/enable <cmd>` | `/disabled`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_games":
        await query.message.edit_caption(
            caption=(
                "🎮 **Levels, Economy & Games**\n\n"
                "• `/rank` (`/level`) — View your profile card, rank & XP *(Group)*.\n"
                "• `/leaderboard` (`/lb`) — Top active members *(Group)*.\n"
                "• `/daily` | `/bal` — Claim daily coins & check your wallet.\n"
                "• `/shop` — Buy weapons, armor & items with coins.\n"
                "• `/bet <amount>` — Gamble your coins to multiply them.\n"
                "• `/boss` — Spawn a group Boss Raid to fight together *(Group)*.\n"
                "• `/duel` — Reply to challenge a friend *(Group)*.\n"
                "• `/rps` | `/trivia` | `/guess` | `/slot` | `/dart` | `/basket`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_social":
        await query.message.edit_caption(
            caption=(
                "🌸 **Marriage, Family & Gacha**\n\n"
                "• `/marry` | `/divorce` | `/partner` — Propose & manage bonds.\n"
                "• `/adopt` | `/sibling` | `/disown` | `/family` | `/tree` — Family lineage.\n"
                "• `/gacha` — Pull rare Waifu & Husbando cards!\n"
                "• `/collection` | `/view <id/name>` — Browse your pulled cards.\n"
                "• `/gender <male/female>` | `/bio <text>` | `/mybio` — Your profile.\n"
                "• `/lovecalc` | `/couple` *(Group)* | `/simprate` | `/iq` | `/waifurate`\n"
                "• **Reactions:** `/hug`, `/kiss`, `/slap`, `/pat`, `/cuddle`, `/poke`, `/cringe`, `/bonk`, `/blush`, `/dance`, `/yeet` & more!"
            ),
            reply_markup=back_btn
        )

    elif data == "help_ai":
        await query.message.edit_caption(
            caption=(
                "🎬 **Anime & Ruka AI**\n\n"
                "• `/ruka <msg>` (`/ai`, `/ask`) — Chat with Ruka (or just say `Ruka`!).\n"
                "• `/imagine <prompt>` — Generate custom anime art.\n"
                "• `/roast` | `/compliment` — Context-aware roasts & compliments.\n"
                "• `/emojify` | `/summarize` | `/translate <lang>` | `/animeidea`\n"
                "• `/clearai` — Reset your conversation memory.\n"
                "• `/anime <name>` | `/manga <name>` | `/animechar <name>`\n"
                "• `/topanime` | `/airing <name>` | `/randomanime` | `/quote`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_misc":
        await query.message.edit_caption(
            caption=(
                "⚙️ **Utilities & Staff**\n\n"
                "• `/connect <id>` | `/disconnect` | `/connection` — Manage from PM.\n"
                "• `/setrules` | `/rules` | `/save <name> <text>` | `/get <name>` | `/notes`\n"
                "• `/info` | `/id` | `/ping` | `/afk <reason>`\n"
                "• `/poll Q | A | B` *(Group)* | `/choose A | B` | `/decide`\n"
                "• **Staff:** `/stats`, `/sudolist`, `/addsudo`, `/rmsudo`, `/gban`, `/ungban`, `/send`, `/eval`, `/sh`, `/restart`, `/backup`"
            ),
            reply_markup=back_btn
        )

    await query.answer()