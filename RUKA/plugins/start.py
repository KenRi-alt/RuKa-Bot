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
            InlineKeyboardButton(text="🛡️ Security & Warns", callback_data="help_locks"),
        ],
        [
            InlineKeyboardButton(text="🎮 Levels & Games", callback_data="help_games"),
            InlineKeyboardButton(text="🌸 Anime & Fun", callback_data="help_anime"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI & Utility", callback_data="help_ai"),
            InlineKeyboardButton(text="👑 Owner", callback_data="help_owner"),
        ],
        [
            InlineKeyboardButton(text="🏠 Back to Start", callback_data="help_home"),
        ],
    ])


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
            f"I'm **Ruka Sarashina**—and I'm here to keep your group lively, safe, and full of heart! 🌸\n\n"
            f"✨ **How I can help:**\n"
            f"• **Smart Moderation** — Keep troublemakers out effortlessly\n"
            f"• **Warm Welcomes** — Greet every new member in style\n"
            f"• **Anime, AI & Games** — Keep your community active and entertained\n\n"
            f"Tap **Help & Commands** below to see everything I can do."
        ),
        reply_markup=get_start_buttons(me.username),
    )
    if "ruka_main" not in PHOTO_CACHE and sent.photo:
        PHOTO_CACHE["ruka_main"] = sent.photo[-1].file_id


@router.message(Command("help"))
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
                f"We're so happy you're here! Please take a moment to check the group rules and enjoy your stay. 💓"
            ),
            reply_markup=buttons,
        )


@router.callback_query(F.data.startswith(("help_", "about_ruka", "rules_btn")))
async def help_callbacks(query: CallbackQuery):
    data = query.data
    back_btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Help", callback_data="help_main")]
    ])

    if data == "about_ruka":
        return await query.answer(
            "💓 Ruka Sarashina — Your energetic anime group companion.\n"
            "👨‍💻 Developer: @Nocis_creed",
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
                f"I'm **Ruka Sarashina**—and I'm here to keep your group lively, safe, and full of heart! 🌸\n\n"
                f"Tap **Help & Commands** below to see everything I can do."
            ),
            reply_markup=get_start_buttons(me.username)
        )

    elif data == "help_admin":
        await query.message.edit_caption(
            caption=(
                "🔨 **Moderation Commands**\n\n"
                "• `/adminpanel` — Open the interactive admin menu.\n"
                "• `/ban` | `/unban` — Reply to a user or pass their ID.\n"
                "• `/tban <time>` — Temp-ban a user (e.g. `/tban 1h`, `2d`).\n"
                "• `/dban` | `/sban` — Delete message & ban, or silent ban.\n"
                "• `/kick` | `/dkick` | `/skick` — Remove a user from the chat.\n"
                "• `/mute` | `/unmute` | `/tmute <time>` — Restrict messaging.\n"
                "• `/purge` | `/del` — Reply to a message to bulk-delete or delete.\n"
                "• `/pin` | `/unpin` | `/unpinall` — Manage pinned messages.\n"
                "• `/promote` | `/demote` | `/settitle <title>` — Manage admins.\n"
                "• `/slowmode <sec>` — Set slowmode delay (`0` to disable).\n"
                "• `/invitelink` | `/admins` — Get invite link or list admins."
            ),
            reply_markup=back_btn
        )

    elif data == "help_locks":
        await query.message.edit_caption(
            caption=(
                "🛡️ **Security, Warns & Filters**\n\n"
                "• `/settings` — Toggle Captcha, Welcome, Anti-Link & Night Mode.\n"
                "• `/warn` | `/unwarn` | `/warns` | `/resetwarns` — Manage user warnings.\n"
                "• `/setwarnlimit <num>` — Set max warns before auto-ban.\n"
                "• `/antiflood <num>` — Auto-mute spammers (`0` to disable).\n"
                "• `/blacklist <word>` | `/unblacklist <word>` — Block specific words.\n"
                "• `/lock <type>` | `/unlock <type>` — Lock `links`, `stickers`, `forwards`, `media`, or `all`.\n"
                "• `/nightmode on|off` — Lock media, stickers & links.\n"
                "• `/filter <word> <reply>` | `/stop <word>` — Auto-reply to keywords."
            ),
            reply_markup=back_btn
        )

    elif data == "help_games":
        await query.message.edit_caption(
            caption=(
                "🎮 **Levels, Economy & Games**\n\n"
                "• `/rank` (`/level`) — View your profile card, rank & XP.\n"
                "• `/leaderboard` (`/lb`) — See the top active members.\n"
                "• `/boss` — Spawn a group Boss Raid to fight together!\n"
                "• `/daily` | `/bal` — Claim daily coins & check balance.\n"
                "• `/give <amt>` | `/rob` | `/bet <amt>` — Trade, steal, or bet coins.\n"
                "• `/rps` | `/trivia` | `/guess` — Interactive button games.\n"
                "• `/duel` — Reply to a friend to challenge them.\n"
                "• `/slot` | `/dart` | `/basket` | `/bowl` — Mini-games."
            ),
            reply_markup=back_btn
        )

    elif data == "help_anime":
        await query.message.edit_caption(
            caption=(
                "🌸 **Anime, Gacha & Fun**\n\n"
                "• `/anime <name>` — Search anime with score & synopsis.\n"
                "• `/topanime` | `/airing <name>` — Trending & episode countdowns.\n"
                "• `/gacha` — Pull rare Waifu cards!\n"
                "• `/collection` | `/view <id/name>` — View your pulled cards.\n"
                "• `/ship` | `/8ball` | `/truth` | `/dare` | `/quote` — Party fun.\n"
                "• **Reactions:** `/waifu`, `/neko`, `/hug`, `/pat`, `/slap`, `/kiss`, `/cuddle`, `/poke`, `/wink`, `/baka`, `/blush`, `/dance`, `/smile` & more!"
            ),
            reply_markup=back_btn
        )

    elif data == "help_ai":
        await query.message.edit_caption(
            caption=(
                "🤖 **Ruka AI & Utilities**\n\n"
                "• `/ruka <msg>` (`/ai`, `/ask`) — Chat with Ruka.\n"
                "• `/imagine <prompt>` — Generate custom anime art.\n"
                "• `/clearai` — Reset your AI conversation memory.\n"
                "• `/roast` | `/compliment` — Reply to a user.\n"
                "• `/summarize` | `/translate <lang>` — Reply to any text.\n"
                "• `/animeidea` — Get a custom anime plot.\n"
                "• `/connect <id>` | `/disconnect` — Manage your group from PM.\n"
                "• `/setrules` | `/rules` | `/save` | `/get` | `/notes`\n"
                "• `/info` | `/id` | `/ping` | `/afk <reason>`"
            ),
            reply_markup=back_btn
        )

    elif data == "help_owner":
        await query.message.edit_caption(
            caption=(
                "👑 **Owner & Sudo Commands**\n\n"
                "• `/stats` | `/sudolist` — System uptime & staff list.\n"
                "• `/addsudo` | `/rmsudo` — Manage sudo access.\n"
                "• `/gban` | `/ungban` — Global ban/unban.\n"
                "• `/send <chat_id> <text>` | `/leavechat <id>`\n"
                "• `/eval <code>` | `/sh <cmd>` | `/restart` | `/backup`"
            ),
            reply_markup=back_btn
        )

    await query.answer()