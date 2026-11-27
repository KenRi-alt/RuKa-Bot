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
from RUKA import CONFIG
from RUKA.utils.image_gen import generate_4k_welcome
from RUKA.utils.db import get_chat_settings

router = Router()

RUKA_PIC = "https://ganga--link--ghhzdp9sv8hk.code.run/i/s0s0y8txhk.jpg"
UPDATES_URL = "https://t.me/RukaSarashinaUpdates"
SUPPORT_URL = "https://t.me/sup_ruka_bot"
PHOTO_CACHE: dict[str, str] = {}


def _is_staff(uid: int) -> bool:
    return (
        uid in (CONFIG.OWNER_LIST or [])
        or uid in (CONFIG.DEV_LIST or [])
        or uid in (CONFIG.SUDO_LIST or [])
    )


def get_start_buttons(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Add Ruka to Your Group",
                url=f"https://t.me/{bot_username}?startgroup=true",
                style="success",
            )
        ],
        [
            InlineKeyboardButton(text="📢 Updates Channel", url=UPDATES_URL, style="primary"),
            InlineKeyboardButton(text="💬 Support Group", url=SUPPORT_URL, style="primary"),
        ],
        [
            InlineKeyboardButton(text="💓 About Ruka", callback_data="about_ruka", style="danger"),
        ],
    ])


def get_help_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔨 Moderation", callback_data="help_admin", style="danger"),
            InlineKeyboardButton(text="⚠️ Warns & Flood", callback_data="help_warns", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🔒 Locks & Filters", callback_data="help_locks", style="primary"),
            InlineKeyboardButton(text="🛡️ Security & Feds", callback_data="help_feds", style="primary"),
        ],
        [
            InlineKeyboardButton(text="📜 Notes & Rules", callback_data="help_notes", style="primary"),
            InlineKeyboardButton(text="💎 Economy & Shop", callback_data="help_econ", style="success"),
        ],
        [
            InlineKeyboardButton(text="⚔️ Bosses & Games", callback_data="help_games", style="success"),
            InlineKeyboardButton(text="🌸 Marriage & Family", callback_data="help_family", style="primary"),
        ],
        [
            InlineKeyboardButton(text="🎰 Gacha & Social", callback_data="help_gacha", style="primary"),
            InlineKeyboardButton(text="🎬 Anime & Ruka AI", callback_data="help_ai", style="primary"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Connections & Misc", callback_data="help_misc", style="primary"),
            InlineKeyboardButton(text="❌ Close Menu", callback_data="help_close", style="danger"),
        ],
    ])


# --- /start Command ---
@router.message(CommandStart())
async def start_cmd(message: Message):
    user = message.from_user
    if not user:
        return

    me = await message.bot.get_me()
    photo = PHOTO_CACHE.get("ruka_main", RUKA_PIC)
    sent = await message.answer_photo(
        photo=photo,
        caption=(
            f"💓 **Kon'nichiwa, {user.full_name}!**\n\n"
            f"My heart starts racing every time I meet someone new—I'm **Ruka Sarashina**, "
            f"your devoted guardian and lively anime companion for Telegram groups! 🌸\n\n"
            f"I'll protect your community from spammers, welcome newcomers with custom cards, "
            f"and keep your chat entertained with AI, games, gacha, and family trees.\n\n"
            f"📖 Send **`/help`** anytime to explore all of my commands in detail!"
        ),
        reply_markup=get_start_buttons(me.username),
    )
    if "ruka_main" not in PHOTO_CACHE and sent.photo:
        PHOTO_CACHE["ruka_main"] = sent.photo[-1].file_id


# --- /help Command ---
@router.message(Command("help", prefix="/!"))
async def help_cmd(message: Message):
    photo = PHOTO_CACHE.get("ruka_main", RUKA_PIC)
    sent = await message.answer_photo(
        photo=photo,
        caption=(
            "📚 **Ruka's Command Guide**\n\n"
            "All commands can be used with `/` or `!`.\n"
            "Select a module below to view detailed explanations and usage examples:"
        ),
        reply_markup=get_help_buttons(),
    )
    if "ruka_main" not in PHOTO_CACHE and sent.photo:
        PHOTO_CACHE["ruka_main"] = sent.photo[-1].file_id


# --- /dev Command (Owner / Dev / Sudo Only) ---
@router.message(Command("dev", prefix="/!"))
async def dev_help_cmd(message: Message):
    if not message.from_user or not _is_staff(message.from_user.id):
        return await message.answer("❌ You are not allowed to use this command.")

    await message.answer(
        "👑 **Staff & Developer Suite**\n\n"
        "✦ `/ownerpanel` — Open interactive diagnostics & toggles.\n"
        "✦ `/broadcast <users|groups|all>` — Reply to broadcast globally.\n"
        "✦ `/announce <text>` — Send an official notice to all groups.\n"
        "✦ `/forcesub <@channel|off>` — Enforce channel join.\n"
        "✦ `/maintenance <on|off> [reason]` — Toggle maintenance mode.\n"
        "✦ `/send <chat_id> [text]` — Deliver text or replied media remotely.\n"
        "✦ `/addcoins`, `/rmcoins`, `/addxp`, `/giveallcoins`, `/toprich`\n"
        "✦ `/gban`, `/ungban`, `/botban`, `/botunban`, `/sql`, `/eval`, `/sh`, `/backup`, `/restart`"
    )


# --- Auto-Welcome New Group Members ---
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
        buttons = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📜 Group Rules", callback_data="rules_btn", style="primary"),
            InlineKeyboardButton(text="💬 Support", url=SUPPORT_URL, style="success"),
        ]])

        await message.answer_photo(
            photo=photo_file,
            caption=(
                f"🌸 **Welcome to {message.chat.title}, {user.full_name}!**\n\n"
                f"We're thrilled to have you here! Take a moment to read the rules and say hi. 💓"
            ),
            reply_markup=buttons,
        )


# --- Callback Handlers ---
@router.callback_query(F.data.startswith(("help_", "about_ruka", "rules_btn")))
async def help_callbacks(query: CallbackQuery):
    data = query.data
    back_btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Back", callback_data="help_main", style="primary")
    ]])

    if data == "about_ruka":
        return await query.answer(
            "💓 Ruka Sarashina\n"
            "Your energetic anime guardian & group companion.\n\n"
            "👨‍💻 Creator: @Nocis_creed\n"
            "🛠️ Co-Creator: @dont_try_to_copy_mee",
            show_alert=True
        )

    if data == "rules_btn":
        return await query.answer("📜 Be respectful, avoid spam, and listen to the group admins!", show_alert=True)

    if data == "help_close":
        return await query.message.delete()

    if data == "help_main":
        await query.message.edit_caption(
            caption=(
                "📚 **Ruka's Command Guide**\n\n"
                "All commands can be used with `/` or `!`.\n"
                "Select a module below to view detailed explanations and usage examples:"
            ),
            reply_markup=get_help_buttons()
        )
        return await query.answer()

    pages = {
        "help_admin": (
            "✦ **Moderation Module** *(Group Admins)*\n\n"
            "✧ `/adminpanel` — Open a quick interactive control menu for group actions.\n"
            "✧ `/ban` — Permanently ban a user by replying to them or passing their ID.\n"
            "✧ `/tban <time>` — Temporarily ban a user (Examples: `10m`, `2h`, `3d`).\n"
            "✧ `/dban` / `/sban` — Delete the replied message and ban, or ban silently.\n"
            "✧ `/unban` — Remove a ban so the user can rejoin.\n"
            "✧ `/kick` / `/dkick` / `/skick` — Remove a user without banning them.\n"
            "✧ `/mute` / `/tmute <time>` / `/unmute` — Stop or allow a user from sending messages.\n"
            "✧ `/purge` / `/del` — Reply to a message to bulk-delete up to the current message, or delete one.\n"
            "✧ `/pin` / `/unpin` / `/unpinall` — Manage pinned messages in your chat.\n"
            "✧ `/promote` / `/demote` / `/settitle <title>` — Grant or remove admin rights and custom titles.\n"
            "✧ `/slowmode <seconds>` / `/invitelink` / `/admins` — Set chat cooldown, fetch invite link, or list admins."
        ),
        "help_warns": (
            "✦ **Warnings & Anti-Flood Module** *(Group Admins)*\n\n"
            "✧ `/warn <reason>` — Issue a formal warning to a user by replying to their message.\n"
            "✧ `/dwarn <reason>` — Delete the offending message and warn the user at the same time.\n"
            "✧ `/swarn <reason>` — Silently warn a user without posting in chat.\n"
            "✧ `/warns` — Check how many warnings you or a replied user currently have.\n"
            "✧ `/rmwarn` / `/resetwarn` — Remove the latest warning or reset a user's warnings to 0.\n"
            "✧ `/warnlimit <number>` — Set how many warnings trigger an automatic punishment.\n"
            "✧ `/warnmode <ban|mute|kick>` — Choose what happens when a user hits the warn limit.\n"
            "✧ `/setflood <number|off>` — Auto-punish users sending too many messages within 4 seconds.\n"
            "✧ `/floodmode <ban|mute|kick>` — Set the punishment for flooders.\n"
            "✧ `/flood` — View your group's current anti-flood configuration."
        ),
        "help_locks": (
            "✦ **Locks, Blocklists & Auto-Filters** *(Group Admins)*\n\n"
            "✧ `/lock <type>` — Automatically delete messages of a specific type.\n"
            "✧ `/unlock <type>` — Allow that content type in your group again.\n"
            "✧ `/locks` / `/locktypes` — View active locks or see all supported types (`links`, `url`, `stickers`, `gif`, `photo`, `video`, `voice`, `document`, `forwards`, `media`, `cjk`, `cyrillic`, `all`).\n"
            "✧ `/nightmode on|off` — Quickly lock media, stickers, GIFs, and links overnight.\n"
            "✧ `/addblocklist <word>` — Block a word or phrase (supports `*` wildcards).\n"
            "✧ `/rmblocklist <word>` / `/blocklist` — Remove a blocked word or list all blocked words.\n"
            "✧ `/blocklistmode <del|ban|mute|kick>` — Choose how Ruka punishes blocklist triggers.\n"
            "✧ `/filter <word> <reply>` — Make Ruka automatically reply whenever someone says a keyword.\n"
            "✧ `/stop <word>` / `/stopall` / `/filters` — Remove one filter, clear all, or list active filters."
        ),
        "help_feds": (
            "✦ **Security, Approvals, Reports & Federations**\n\n"
            "✧ `/settings` — Open the interactive toggle panel for CAPTCHA, Anti-Raid, Clean Service & Clean Commands.\n"
            "✧ `/captcha on|off` — Require new members to verify before chatting (auto-kicks after 2 mins).\n"
            "✧ `/captchamode <button|math>` — Switch between a simple verification button or a math puzzle.\n"
            "✧ `/antiraid` / `/cleanservice` / `/cleancommand` — Quick-toggle raid protection or auto-cleanup.\n"
            "✧ `/approve` / `/unapprove` / `/approval` / `/approved` — Exempt trusted members from locks, blocklists & flood.\n"
            "✧ `/report` or `@admin` — Reply to a rule-breaker to alert admins with one-tap Ban/Mute/Delete buttons.\n"
            "✧ `/setlog <channel_id>` / `/unsetlog` / `/logchannel` — Send moderation logs to a private channel.\n"
            "✧ `/newfed <name>` / `/joinfed <id>` / `/leavefed` / `/fban` / `/funban` — Ban spammers across all your linked groups."
        ),
        "help_notes": (
            "✦ **Rules, Notes & Command Disabling**\n\n"
            "✧ `/setrules <text>` — Save your group's official rules.\n"
            "✧ `/rules` — Display the group's rules to members.\n"
            "✧ `/resetrules` — Clear the saved group rules.\n"
            "✧ `/save <name> <text>` — Store a reusable note that anyone can call anytime.\n"
            "✧ `/get <name>` — Retrieve a saved note by its name.\n"
            "✧ `/notes` — List all saved notes in the current group.\n"
            "✧ `/clear <name>` — Delete a saved note.\n"
            "✧ `/disable <cmd>` / `/enable <cmd>` / `/disabled` — Disable or re-enable specific commands in your group."
        ),
        "help_econ": (
            "✦ **Levels, Economy & Shop**\n\n"
            "✧ `/rank` (or `/level`) — Generate your Trainer Card showing your Rank, XP, Coins, and Gacha count.\n"
            "✧ `/leaderboard` (or `/lb`) — View the top 10 users ranked by XP.\n"
            "✧ `/daily` — Claim your daily coin & XP reward (available once every 24 hours).\n"
            "✧ `/bal` (or `/balance`) — Check your or a replied user's coin wallet and XP.\n"
            "✧ `/give <amount>` — Reply to a friend to transfer coins to them.\n"
            "✧ `/shop` — Browse Ruka's Shop to buy Katana, Heavy Armor, Lucky Clover, Gold Ring, or Energy Drinks.\n"
            "✧ `/inv` (or `/inventory`) — View your owned items and their active perks."
        ),
        "help_games": (
            "✦ **Boss Raids, Gambling & Mini-Games**\n\n"
            "✧ `/boss` — Spawn a powerful Anime Boss in your group so everyone can attack it together for coins & XP!\n"
            "✧ `/duel` — Reply to a friend to start a PvP duel (owning a Katana boosts your win chance!).\n"
            "✧ `/rob` — Reply to a member to attempt a coin heist (Heavy Armor blocks robberies!).\n"
            "✧ `/bet <amount>` — Risk your coins on a 2x double-or-nothing flip.\n"
            "✧ `/slot <amount>` — Spin the slot machine for up to a 4x jackpot!\n"
            "✧ `/rps` — Play Rock, Paper, Scissors against Ruka.\n"
            "✧ `/trivia` — Answer live Anime & Manga trivia questions for coins.\n"
            "✧ `/guess` / `/dart` / `/basket` / `/bowl` — Quick interactive mini-games."
        ),
        "help_family": (
            "✦ **Marriage & Family Lineage**\n\n"
            "✧ `/marry` — Reply to someone to send a marriage proposal with Accept/Reject buttons.\n"
            "✧ `/divorce` — End your current marriage.\n"
            "✧ `/partner` (or `/marriagestatus`) — Check who you or a replied user are married to.\n"
            "✧ `/adopt` — Reply to someone to adopt them as your child.\n"
            "✧ `/sibling` — Reply to someone to add them as your sibling.\n"
            "✧ `/disown` — Reply to a family member to remove them from your family.\n"
            "✧ `/runaway` — Leave your current family lineage.\n"
            "✧ `/family` (or `/tree`) — Generate a visual Family Tree connecting your family's profile pictures!"
        ),
        "help_gacha": (
            "✦ **Waifu & Husbando Gacha & Social**\n\n"
            "✧ `/gacha` — Spend `50 💎` to pull a high-res Waifu or Husbando card (Lucky Clover boosts SSR odds!).\n"
            "✧ `/collection` — View all the cards you've collected.\n"
            "✧ `/view <id or name>` — Inspect any card from your collection up close.\n"
            "✧ `/gender <male|female>` — Set your profile gender.\n"
            "✧ `/bio <text>` / `/mybio` — Save and view your custom profile bio.\n"
            "✧ `/lovecalc` / `/simprate` / `/iq` / `/waifurate` / `/luck` / `/power` / `/love` — Fun social meters.\n"
            "✧ **GIF Reactions:** `/hug`, `/kiss`, `/slap`, `/pat`, `/cuddle`, `/poke`, `/wink`, `/cringe`, `/bonk`, `/blush`, `/dance`, `/yeet`, `/bite`, `/cry`, `/smug`, `/glare`, `/sleep`"
        ),
        "help_ai": (
            "✦ **Anime Encyclopedia & Ruka AI**\n\n"
            "✧ `/ruka <msg>` (or `/ai`, `/ask`) — Chat with Ruka AI (or just mention `Ruka` or reply to her messages/images!).\n"
            "✧ `/imagine <prompt>` — Generate custom anime artwork from your text prompt.\n"
            "✧ `/roast` / `/compliment` — Reply to someone for a context-aware anime roast or compliment.\n"
            "✧ `/emojify` / `/summarize` / `/translate <lang>` / `/animeidea` / `/clearai` — Smart AI utilities.\n"
            "✧ `/anime <name>` — Search an anime's score, genres, airing status & synopsis.\n"
            "✧ `/manga <name>` / `/animechar <name>` — Look up manga or anime characters.\n"
            "✧ `/topanime` / `/airing <name>` / `/randomanime` / `/quote` — Trending anime, episode countdowns & quotes."
        ),
        "help_misc": (
            "✦ **Connections, Privacy & Utilities**\n\n"
            "✧ `/connect <chat_id>` / `/disconnect` / `/reconnect` / `/connection` — Manage your group's notes & rules from PM.\n"
            "✧ `/info` — View a user's Trainer-style info card, ID, and username.\n"
            "✧ `/id` / `/ping` / `/afk <reason>` / `/privacy` — Grab IDs, check latency, set AFK status, or view privacy info.\n"
            "✧ `/poll Question | Opt1 | Opt2` — Create a native group poll.\n"
            "✧ `/choose Opt1 | Opt2` / `/decide` / `/toss` / `/hugall` — Quick group helpers.\n"
            "✧ `/mock` / `/reverse` / `/spoiler` / `/vapor` / `/morse` / `/tiny` / `/count` — Text formatters.\n"
            "✧ `/fact` / `/joke` / `/cat` / `/dog` — Random facts, jokes & pet pics."
        ),
    }

    if data in pages:
        await query.message.edit_caption(caption=pages[data], reply_markup=back_btn)

    await query.answer()