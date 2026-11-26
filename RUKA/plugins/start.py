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
PHOTO_CACHE: dict[str, str] = {}


def _is_staff(uid: int) -> bool:
    return (
        uid in (CONFIG.OWNER_LIST or [])
        or uid in (CONFIG.DEV_LIST or [])
        or uid in (CONFIG.SUDO_LIST or [])
    )


def get_start_buttons(bot_username: str) -> InlineKeyboardMarkup:
    updates_url = CONFIG.UPDATES_CHANNEL or "https://t.me/sup_ruka_bot"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Add Ruka to Your Group",
                url=f"https://t.me/{bot_username}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(text="📢 Updates Channel", url=updates_url),
            InlineKeyboardButton(text="💬 Support Group", url="https://t.me/sup_ruka_bot"),
        ],
        [
            InlineKeyboardButton(text="💓 About Ruka", callback_data="about_ruka"),
        ],
    ])


def get_help_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Moderation", callback_data="help_admin"),
            InlineKeyboardButton(text="🟠 Warnings & Flood", callback_data="help_warns"),
        ],
        [
            InlineKeyboardButton(text="🟡 Locks & Filters", callback_data="help_locks"),
            InlineKeyboardButton(text="🔵 Security & Feds", callback_data="help_feds"),
        ],
        [
            InlineKeyboardButton(text="🟣 Notes & Rules", callback_data="help_notes"),
            InlineKeyboardButton(text="🟢 Economy & Shop", callback_data="help_econ"),
        ],
        [
            InlineKeyboardButton(text="⚔️ Bosses & Games", callback_data="help_games"),
            InlineKeyboardButton(text="🌸 Marriage & Family", callback_data="help_family"),
        ],
        [
            InlineKeyboardButton(text="💎 Gacha & Social", callback_data="help_gacha"),
            InlineKeyboardButton(text="🎬 Anime & Ruka AI", callback_data="help_ai"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Connections & Misc", callback_data="help_misc"),
            InlineKeyboardButton(text="❌ Close", callback_data="help_close"),
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
            f"My heart skips a beat every time I meet someone new—I'm **Ruka Sarashina**, "
            f"your devoted guardian and anime companion for Telegram groups! 🌸\n\n"
            f"Whether you need strict protection against spammers, warm welcomes for new members, "
            f"or fun games, gacha, and smart conversations—I'll give your community my all!\n\n"
            f"📖 Use **`/help`** anytime to explore all of my commands and features."
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
            "All commands work with both `/` and `!`.\n"
            "Select a category below for detailed usage and examples:"
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
        "👑 **Staff & Developer Command Suite**\n\n"
        "**Control & Diagnostics:**\n"
        "• `/ownerpanel` — Interactive God-Mode dashboard\n"
        "• `/stats` | `/botinfo` | `/sysinfo` | `/apihealth`\n"
        "• `/testdb` | `/dbstats` | `/pipcheck` | `/env`\n\n"
        "**Bot Profile & Menu:**\n"
        "• `/setbotcmds` | `/clearbotcmds`\n"
        "• `/setbotname` | `/setbotdesc` | `/setbotshort`\n"
        "• `/webhookinfo` | `/flushupdates`\n\n"
        "**Hierarchy & Global Moderation:**\n"
        "• `/sudolist` | `/addsudo` | `/rmsudo` | `/adddev` | `/rmdev`\n"
        "• `/gban` | `/ungban` | `/gbanlist`\n"
        "• `/send <chat_id> <text>` | `/leavechat <id>`\n\n"
        "**Economy, DB & Execution:**\n"
        "• `/addcoins` | `/rmcoins` | `/addxp` | `/resetuser`\n"
        "• `/giveallcoins` | `/giveallxp` | `/toprich`\n"
        "• `/sql <query>` | `/wipechat` | `/backup`\n"
        "• `/eval <code>` | `/sh <cmd>` | `/restart`"
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
            InlineKeyboardButton(text="📜 Group Rules", callback_data="rules_btn"),
            InlineKeyboardButton(text="💬 Support", url="https://t.me/sup_ruka_bot"),
        ]])

        await message.answer_photo(
            photo=photo_file,
            caption=(
                f"🌸 **Welcome to {message.chat.title}, {user.full_name}!**\n\n"
                f"We're so happy to have you here! Please check the group rules and enjoy your stay. 💓"
            ),
            reply_markup=buttons,
        )


# --- Callback Handlers ---
@router.callback_query(F.data.startswith(("help_", "about_ruka", "rules_btn")))
async def help_callbacks(query: CallbackQuery):
    data = query.data
    back_btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔙 Back to Menu", callback_data="help_main")
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
        return await query.answer(
            "📜 Be respectful, avoid spam, and listen to the group admins!",
            show_alert=True
        )

    if data == "help_close":
        return await query.message.delete()

    if data == "help_main":
        await query.message.edit_caption(
            caption="📚 **Ruka's Command Guide**\n\nAll commands work with both `/` and `!`.\nSelect a category below:",
            reply_markup=get_help_buttons()
        )
        return await query.answer()

    pages = {
        "help_admin": (
            "🔴 **Moderation Commands** *(Group Admins)*\n\n"
            "• `/adminpanel` — Open the interactive admin menu.\n\n"
            "• `/ban` | `/unban` — Ban or unban a user (reply or pass ID).\n"
            "• `/tban <time>` — Temp-ban a user (e.g. `/tban 1h`, `2d`).\n"
            "• `/dban` | `/sban` — Delete replied message & ban, or silent ban.\n\n"
            "• `/kick` | `/dkick` | `/skick` — Kick a user from the chat.\n"
            "• `/mute` | `/unmute` | `/tmute <time>` — Restrict messaging.\n"
            "• `/dmute` | `/smute` — Delete & mute, or silent mute.\n\n"
            "• `/purge` | `/del` — Reply to bulk-delete or remove a message.\n"
            "• `/pin` | `/unpin` | `/unpinall` — Manage pinned messages.\n"
            "• `/promote` | `/demote` | `/settitle <title>` — Manage admins.\n"
            "• `/slowmode <sec>` | `/invitelink` | `/admins` — Group controls."
        ),
        "help_warns": (
            "🟠 **Warnings & Anti-Flood** *(Group Admins)*\n\n"
            "• `/warn <reason>` — Warn a user by reply.\n"
            "• `/dwarn <reason>` — Delete message and warn user.\n"
            "• `/swarn <reason>` — Silently warn user.\n"
            "• `/rmwarn` | `/resetwarn` — Remove 1 warn or reset to 0.\n"
            "• `/warns` — Check a user's current warnings.\n\n"
            "• `/warnlimit <num>` — Set max warns before punishment.\n"
            "• `/warnmode <ban|mute|kick>` — Choose warn punishment.\n\n"
            "• `/setflood <num|off>` — Auto-punish rapid spam messages.\n"
            "• `/floodmode <ban|mute|kick>` — Choose flood punishment.\n"
            "• `/flood` — View current anti-flood settings."
        ),
        "help_locks": (
            "🟡 **Locks, Blocklists & Auto-Filters** *(Group Admins)*\n\n"
            "• `/lock <type>` | `/unlock <type>` — Block specific content.\n"
            "• `/locks` | `/locktypes` — View active & available locks.\n"
            "  ↳ Types: `links`, `url`, `stickers`, `gif`, `photo`, `video`, `voice`, `document`, `forwards`, `media`, `cjk`, `cyrillic`, `all`\n\n"
            "• `/nightmode on|off` — Lock media, stickers, GIFs & links.\n\n"
            "• `/addblocklist <word>` | `/rmblocklist <word>` — Block words (supports `*` wildcards).\n"
            "• `/blocklist` | `/blocklistmode <del|ban|mute|kick>`\n\n"
            "• `/filter <word> <reply>` | `/stop <word>` | `/stopall` | `/filters` — Custom auto-replies."
        ),
        "help_feds": (
            "🔵 **Security, Approvals, Reports & Feds**\n\n"
            "• `/settings` — Toggle CAPTCHA, Anti-Raid, Clean Service & Clean Cmds.\n"
            "• `/captcha on|off` | `/captchamode <button|math>`\n"
            "• `/antiraid` | `/cleanservice` | `/cleancommand`\n\n"
            "• `/approve` | `/unapprove` | `/approval` | `/approved` | `/unapproveall` — Exempt trusted users from locks & flood.\n\n"
            "• `/report` or `@admin` — Report rule-breakers with quick action buttons (`/reports on|off`).\n"
            "• `/setlog <id>` | `/unsetlog` | `/logchannel` — Audit logs.\n\n"
            "• `/newfed <name>` | `/joinfed <id>` | `/leavefed` | `/fban` | `/funban` — Cross-group ban network."
        ),
        "help_notes": (
            "🟣 **Rules, Notes & Command Disabling**\n\n"
            "• `/setrules <text>` — Set the group rules.\n"
            "• `/rules` — View the group rules.\n"
            "• `/resetrules` — Clear the group rules.\n\n"
            "• `/save <name> <text>` — Save a reusable note.\n"
            "• `/get <name>` — Retrieve a saved note.\n"
            "• `/notes` — List all saved notes in the chat.\n"
            "• `/clear <name>` — Delete a saved note.\n\n"
            "• `/disable <cmd>` | `/enable <cmd>` | `/disabled` — Disable specific commands in your group."
        ),
        "help_econ": (
            "🟢 **Levels, Economy & Shop**\n\n"
            "• `/rank` (`/level`) — View your Trainer Card, Rank, XP & Coins.\n"
            "• `/leaderboard` (`/lb`) — Top members by XP.\n\n"
            "• `/daily` — Claim your daily coins *(once every 24h)*.\n"
            "• `/bal` — Check your wallet & XP.\n"
            "• `/give <amount>` — Reply to send coins to a friend.\n\n"
            "• `/shop` — Buy Katana, Armor, Lucky Clover, Gold Ring & Energy Drinks.\n"
            "• `/inv` (`/inventory`) — View your owned items & perks."
        ),
        "help_games": (
            "⚔️ **Boss Raids, Gambling & Mini-Games**\n\n"
            "• `/boss` — Spawn an Anime Boss in your group to fight together for coins & XP!\n"
            "• `/duel` — Reply to a friend for a PvP duel *(Katana boosts win rate!)*.\n"
            "• `/rob` — Reply to steal coins *(Heavy Armor blocks robberies!)*.\n\n"
            "• `/bet <amount>` — Bet coins on a 2x flip.\n"
            "• `/slot <amount>` — Spin the slot machine for up to 4x jackpot!\n\n"
            "• `/rps` | `/trivia` | `/guess` — Interactive button games.\n"
            "• `/dart` | `/basket` | `/bowl` — Quick mini-games."
        ),
        "help_family": (
            "🌸 **Marriage & Family Lineage**\n\n"
            "• `/marry` — Reply to propose marriage with Accept/Reject buttons.\n"
            "• `/divorce` — End your current marriage.\n"
            "• `/partner` | `/marriagestatus` — View your soulmate.\n\n"
            "• `/adopt` — Reply to adopt someone as your child.\n"
            "• `/sibling` — Reply to add someone as your sibling.\n"
            "• `/disown` — Reply to remove a family member.\n"
            "• `/runaway` — Leave your current family.\n"
            "• `/family` | `/tree` — Generate your visual **Family Tree**!"
        ),
        "help_gacha": (
            "💎 **Waifu & Husbando Gacha & Social**\n\n"
            "• `/gacha` — Spin for a Waifu or Husbando card (`50 💎` per spin; Lucky Clover boosts SSR odds!).\n"
            "• `/collection` — View your collected cards.\n"
            "• `/view <id or name>` — Inspect any card up close.\n\n"
            "• `/gender <male|female>` | `/bio <text>` | `/mybio` — Customize your profile.\n"
            "• `/lovecalc` | `/simprate` | `/iq` | `/waifurate` | `/luck` | `/power` | `/love`\n\n"
            "• **GIF Reactions:** `/hug`, `/kiss`, `/slap`, `/pat`, `/cuddle`, `/poke`, `/wink`, `/cringe`, `/bonk`, `/blush`, `/dance`, `/yeet`, `/bite`, `/cry`, `/smug`, `/glare`, `/sleep`"
        ),
        "help_ai": (
            "🎬 **Anime Encyclopedia & Ruka AI**\n\n"
            "• `/ruka <msg>` (`/ai`, `/ask`) — Chat with Ruka (or just mention `Ruka` or reply to her messages/images!).\n"
            "• `/imagine <prompt>` — Generate custom anime art.\n"
            "• `/roast` | `/compliment` — Context-aware roasts & compliments.\n"
            "• `/emojify` | `/summarize` | `/translate <lang>` | `/animeidea` | `/clearai`\n\n"
            "• `/anime <name>` | `/manga <name>` | `/animechar <name>`\n"
            "• `/topanime` | `/airing <name>` | `/randomanime` | `/quote`"
        ),
        "help_misc": (
            "⚙️ **Connections, Privacy & Utilities**\n\n"
            "• `/connect <chat_id>` | `/disconnect` | `/reconnect` | `/connection` — Manage your group from PM.\n"
            "• `/info` | `/id` | `/ping` | `/afk <reason>` | `/privacy`\n\n"
            "• `/poll Question | Opt1 | Opt2` — Create a group poll.\n"
            "• `/choose Opt1 | Opt2` | `/decide` | `/toss` | `/hugall`\n"
            "• `/mock` | `/reverse` | `/spoiler` | `/vapor` | `/morse` | `/tiny` | `/count`\n"
            "• `/fact` | `/joke` | `/cat` | `/dog`"
        ),
    }

    if data in pages:
        await query.message.edit_caption(caption=pages[data], reply_markup=back_btn)

    await query.answer()