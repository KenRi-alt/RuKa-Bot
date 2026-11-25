from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..utils.chat_action import chatAction
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


def get_help_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔨 Admin (20)", callback_data="help_admin"),
            InlineKeyboardButton("🛡️ Security & Warns", callback_data="help_locks")
        ],
        [
            InlineKeyboardButton("🎮 Levels & Games", callback_data="help_games"),
            InlineKeyboardButton("🌸 Anime & Fun", callback_data="help_anime")
        ],
        [
            InlineKeyboardButton("🤖 AI & Utility", callback_data="help_ai"),
            InlineKeyboardButton("👑 Owner & Sudo", callback_data="help_owner")
        ],
        [
            InlineKeyboardButton("🏠 Back to Start", callback_data="help_home")
        ]
    ])


# --- /start Command ---
@Client.on_message(filters.command("start"))
@chatAction("upload_photo")
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
            f"• Protect your group with **20+ Admin & Anti-Spam tools**\n"
            f"• Greet new members with **4K Anime Welcome Cards**\n"
            f"• Entertain your chat with **Grok AI, Boss Raids, Gacha & 100+ commands**\n\n"
            f"Tap **Help & Commands** below to explore everything~"
        ),
        reply_markup=get_start_buttons(client.me.username)
    )


# --- /help Command ---
@Client.on_message(filters.command("help"))
@chatAction("typing")
async def help_command(client, message):
    await message.reply_text(
        "📚 **Ruka's Command Grimoire (100+ Commands)**\n\n"
        "Choose a category below to see detailed commands and how to use them~",
        reply_markup=get_help_buttons()
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

    async def edit_msg(text: str, markup):
        if query.message.photo:
            await query.message.edit_caption(text, reply_markup=markup)
        else:
            await query.message.edit_text(text, reply_markup=markup)

    if data == "help_main":
        await edit_msg(
            "📚 **Ruka's Command Grimoire (100+ Commands)**\n\n"
            "Choose a category below to see detailed commands and how to use them~",
            get_help_buttons()
        )

    elif data == "help_home":
        await edit_msg(
            "💓 **Kon'nichiwa!**\n\n"
            "I'm **Ruka Sarashina**, your dedicated anime group management bot! 🌸\n"
            "Tap **Help & Commands** below to explore everything~",
            get_start_buttons(client.me.username)
        )

    elif data == "about_ruka":
        await query.answer("💓 Ruka-Bot v2.0 | Pyrogram + PostgreSQL + 4K Pillow + Grok AI!", show_alert=True)

    elif data == "rules_btn":
        await query.answer("📜 Be respectful, no spam, no NSFW, and listen to the admins!", show_alert=True)

    elif data == "help_admin":
        await edit_msg(
            "🔨 **Admin Commands (20)**\n"
            "• `/adminpanel` — Open interactive admin menu\n"
            "• `/ban` / `/unban` — Reply or pass `@user` / ID\n"
            "• `/tban 1h` — Timed ban (`10m`, `2h`, `1d`)\n"
            "• `/mute` / `/unmute` / `/tmute 30m` — Mute users\n"
            "• `/kick` — Kick a user\n"
            "• `/purge` / `/del` — Delete messages\n"
            "• `/pin` / `/unpin` — Pin/unpin replied message\n"
            "• `/promote` / `/demote` / `/settitle <title>`\n"
            "• `/invitelink` / `/setgtitle` / `/setgdesc`\n"
            "• `/zombies` — Clean deleted accounts\n"
            "• `/tagall <msg>` / `/stoptag` — Tag all members",
            back_btn
        )

    elif data == "help_locks":
        await edit_msg(
            "🛡️ **Security, Warns & Locks**\n"
            "• `/warn` / `/unwarn` / `/warns` / `/resetwarns`\n"
            "• `/setwarnlimit 3` — Auto-ban after 3 warns\n"
            "• `/antiflood 5` — Auto-mute spammers (`0` to off)\n"
            "• `/blacklist <word>` / `/unblacklist` / `/blacklists`\n"
            "• `/lock <type>` / `/unlock <type>` / `/locks`\n"
            "  ↳ Types: `links`, `stickers`, `forwards`, `media`, `all`\n"
            "• `/nightmode on|off` — Lock media, stickers & links",
            back_btn
        )

    elif data == "help_games":
        await edit_msg(
            "🎮 **Levels, Economy & Games**\n"
            "• `/rank` / `/level` — Your 4K Anime Profile Card\n"
            "• `/leaderboard` (`/lb`) — Top 10 active members\n"
            "• `/boss` — Spawn a Group Anime Boss Raid!\n"
            "• `/daily` / `/bal` / `/give 50` / `/rob` / `/bet 50`\n"
            "• `/rps` — Rock Paper Scissors vs Ruka\n"
            "• `/trivia` — Live Anime & Manga Trivia\n"
            "• `/guess` — Guess the number (1–5)\n"
            "• `/duel` — Reply to battle a friend\n"
            "• `/slot`, `/dart`, `/basket`, `/bowl`",
            back_btn
        )

    elif data == "help_anime":
        await edit_msg(
            "🌸 **Anime, AniList & Fun**\n"
            "• `/anime <name>` — 4K AniList Card + Synopsis\n"
            "• `/manga <name>` — 4K Manga Card\n"
            "• `/animechar <name>` — Search anime characters\n"
            "• `/topanime` — Top 10 trending anime\n"
            "• `/airing <name>` — Next episode countdown\n"
            "• `/gacha` — Pull SSR/SR/R Waifus!\n"
            "• `/couple`, `/ship`, `/simprate`, `/iq`, `/waifurate`\n"
            "• `/poll Q | A | B`, `/choose A | B`, `/decide`\n"
            "• `/waifu`, `/neko`, `/hug`, `/pat`, `/slap`, `/kiss` (+20 more!)",
            back_btn
        )

    elif data == "help_ai":
        await edit_msg(
            "🤖 **Ruka AI & Group Utilities**\n"
            "• `/ruka <msg>` (`/ai`, `/ask`) — Chat with Ruka AI\n"
            "• `/clearai` — Reset AI conversation memory\n"
            "• `/roast` / `/compliment` — Reply to a user\n"
            "• `/summarize` — Reply to summarize long text\n"
            "• `/translate <lang>` — Reply to translate\n"
            "• `/animeidea` — Custom anime plot with you!\n"
            "• `/connect <chat_id>` / `/disconnect` / `/connection`\n"
            "• `/setrules` / `/rules` | `/save` / `/get` / `/notes` / `/clear`\n"
            "• `/info` (4K Card), `/id`, `/ping`, `/afk <reason>`",
            back_btn
        )

    elif data == "help_owner":
        await edit_msg(
            "👑 **Owner, Dev & Sudo Commands (18)**\n"
            "• `/stats` — Uptime & system info\n"
            "• `/sudolist` / `/addsudo` / `/rmsudo`\n"
            "• `/block` / `/unblock` — Block users from bot\n"
            "• `/gban` / `/ungban` / `/gmute` / `/ungmute`\n"
            "• `/broadcast` — Reply to send to all chats\n"
            "• `/chatlist` / `/leavechat` / `/send <id> <text>`\n"
            "• `/eval <code>` / `/sh <cmd>` / `/logs` / `/restart`\n"
            "• `/backup` — PostgreSQL backup",
            back_btn
        )