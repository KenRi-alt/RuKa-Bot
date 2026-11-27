import random, aiohttp
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from RUKA.utils.db import (
    set_marriage, get_partner, remove_marriage, add_relation, remove_relation,
    runaway_family, get_family, set_profile, get_profile,
    add_gacha_card, get_user_cards, get_user_stats, update_user_stats, get_inventory
)
from RUKA.utils.image_gen import generate_4k_anime_card, generate_family_tree

router = Router()

WAIFU_POOL = [
    ("Ruka Sarashina", "ruka_sarashina", "Rent-a-Girlfriend"),
    ("Zero Two", "zero_two_(darling_in_the_franxx)", "Darling in the FranXX"),
    ("Makima", "makima_(chainsaw_man)", "Chainsaw Man"),
    ("Marin Kitagawa", "kitagawa_marin", "My Dress-Up Darling"),
    ("Rem", "rem_(re:zero)", "Re:Zero"),
    ("Mikasa Ackerman", "mikasa_ackerman", "Attack on Titan"),
    ("Asuna Yuuki", "asuna_(sao)", "Sword Art Online"),
    ("Yor Forger", "yor_forger", "Spy x Family"),
]
HUSBANDO_POOL = [
    ("Satoru Gojo", "gojo_satoru", "Jujutsu Kaisen"),
    ("Levi Ackerman", "levi_ackerman", "Attack on Titan"),
    ("Megumi Fushiguro", "fushiguro_megumi", "Jujutsu Kaisen"),
    ("Loid Forger", "loid_forger", "Spy x Family"),
    ("Killua Zoldyck", "killua_zoldyck", "Hunter x Hunter"),
    ("Roronoa Zoro", "roronoa_zoro", "One Piece"),
]


async def _fetch_json(url: str):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                if r.status == 200: return await r.json()
    except Exception: pass
    return None


async def _fetch_bytes(url: str) -> BytesIO | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=15) as r:
                if r.status == 200: d = BytesIO(await r.read()); d.seek(0); return d
    except Exception: pass
    return None


async def _get_pfp(bot, uid: int) -> BytesIO | None:
    try:
        ph = await bot.get_user_profile_photos(uid, limit=1)
        if ph.total_count > 0:
            f = await bot.get_file(ph.photos[0][-1].file_id)
            b = BytesIO(); await bot.download_file(f.file_path, b); b.seek(0); return b
    except Exception: pass
    return None


async def _existing_rel(u1: int, u2: int) -> str | None:
    if await get_partner(u1) == u2:
        return "Spouse"
    for f in await get_family(u1):
        if f["relative_id"] == u2:
            return f["relation_type"]
    return None


# --- 1. ANIME GIF REACTIONS ---
GIF_REACTIONS = {
    "hug": ("hug", "🤗 {u1} hugs {u2}!"), "kiss": ("kiss", "💋 {u1} kisses {u2}!"),
    "slap": ("slap", "💢 *SLAP!* {u1} slapped {u2}!"), "pat": ("pat", "👋 {u1} pats {u2}~"),
    "cuddle": ("cuddle", "🌸 {u1} cuddles {u2}!"), "poke": ("poke", "👉 {u1} pokes {u2}!"),
    "wink": ("wink", "😉 {u1} winks at {u2}!"), "cringe": ("cringe", "😬 {u1} cringes at {u2}..."),
    "bite": ("bite", "🧛 {u1} bites {u2}!"), "bonk": ("bonk", "🔨 *BONK!* {u1} bonks {u2}!"),
    "blush": ("blush", "😳 {u1} is blushing!"), "cry": ("cry", "😭 {u1} is crying..."),
    "dance": ("dance", "💃 {u1} is dancing!"), "smile": ("smile", "😊 {u1} smiles!"),
    "wave": ("wave", "👋 {u1} waves at {u2}!"), "highfive": ("highfive", "🙌 {u1} high-fives {u2}!"),
    "handhold": ("handhold", "🤝 {u1} holds hands with {u2}!"), "tickle": ("tickle", "🤭 {u1} tickles {u2}!"),
    "yeet": ("yeet", "🚀 {u1} YEETS {u2}!"), "kill": ("kill", "⚔️ {u1} eliminates {u2}!"),
    "happy": ("happy", "✨ {u1} is super happy!"), "smug": ("smug", "😏 {u1} looks smug~"),
    "glare": ("glare", "👀 {u1} glares at {u2}..."), "sleep": ("sleep", "😴 {u1} fell asleep~"),
}


@router.message(Command(*GIF_REACTIONS.keys(), prefix="/!"))
async def gif_reaction_cmd(message: Message):
    cmd = message.text.split()[0].lstrip("/!").split("@")[0].lower()
    ep, tpl = GIF_REACTIONS[cmd]
    url = None
    d = await _fetch_json(f"https://api.waifu.pics/sfw/{ep}")
    if d and "url" in d: url = d["url"]
    else:
        nb = await _fetch_json(f"https://nekos.best/api/v2/{ep}")
        if nb and nb.get("results"): url = nb["results"][0].get("url")
    if not url: return await message.answer("❌ Couldn't fetch GIF right now!")
    u1 = message.from_user.full_name
    u2 = message.reply_to_message.from_user.full_name if message.reply_to_message and message.reply_to_message.from_user else "everyone"
    cap = tpl.format(u1=u1, u2=u2)
    await (message.answer_animation(url, caption=cap, parse_mode=None) if url.endswith(".gif") else message.answer_photo(url, caption=cap, parse_mode=None))


# --- 2. MARRIAGE & FAMILY (Anti-Duplicate + Bidirectional + Consent) ---
@router.message(Command("marry", prefix="/!"))
async def marry_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer("💍 Reply to someone to propose!")
    u, t = message.from_user, message.reply_to_message.from_user
    if t.id == u.id or t.is_bot: return await message.answer("❌ You can't marry yourself or a bot!")
    if await get_partner(u.id): return await message.answer("❌ You are already married! Use `/divorce` first.")
    if await get_partner(t.id): return await message.answer(f"❌ {t.full_name} is already married!", parse_mode=None)
    if rel := await _existing_rel(u.id, t.id):
        return await message.answer(f"❌ Ew, {t.full_name} is already your **{rel}**!", parse_mode=None)

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💍 Accept", callback_data=f"m_acc_{t.id}_{u.id}"),
        InlineKeyboardButton(text="💔 Reject", callback_data=f"m_rej_{t.id}")
    ]])
    await message.answer(f"💍 {u.full_name} is proposing to {t.full_name}!", reply_markup=btn, parse_mode=None)


@router.callback_query(F.data.startswith("m_"))
async def marriage_cb(query: CallbackQuery):
    p = query.data.split("_")
    act, tid = p[1], int(p[2])
    if query.from_user.id != tid: return await query.answer("❌ Not for you!", show_alert=True)
    if act == "acc":
        await set_marriage(int(p[3]), tid)
        await query.message.edit_text(f"💖 It's Official! {query.from_user.full_name} is now married! 🌸", parse_mode=None)
    else:
        await query.message.edit_text("💔 Proposal rejected. 😭")
    await query.answer()


@router.message(Command("partner", "marriagestatus", "divorce", prefix="/!"))
async def partner_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "divorce":
        if not await get_partner(message.from_user.id): return await message.answer("❌ You aren't married!")
        await remove_marriage(message.from_user.id)
        return await message.answer("💔 Divorced. The bond has ended...")
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    pid = await get_partner(t.id)
    await message.answer(f"💞 {t.full_name}'s Partner ID: {pid}" if pid else f"🔎 {t.full_name} is single.", parse_mode=None)


REL_MAP = {
    "adopt": ("Child", "Parent", "🏠 {u} wants to adopt {t} as their Child!"),
    "sibling": ("Sibling", "Sibling", "👫 {u} wants to make {t} their Sibling!"),
    "makemom": ("Mom", "Child", "👩 {u} wants {t} to be their Mom!"),
    "makedad": ("Dad", "Child", "👨 {u} wants {t} to be their Dad!"),
    "cousin": ("Cousin", "Cousin", "🤝 {u} wants to add {t} as their Cousin!"),
    "pet": ("Pet", "Owner", "🐶 {u} wants to adopt {t} as the family Pet!"),
}


@router.message(Command(*REL_MAP.keys(), prefix="/!"))
async def family_request_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer("Reply to someone to send a family request!")
    cmd = message.text.split()[0].lstrip("/!").lower()
    u, t = message.from_user, message.reply_to_message.from_user
    if t.id == u.id or t.is_bot: return await message.answer("❌ Cannot do that with yourself or a bot!")
    if rel := await _existing_rel(u.id, t.id):
        return await message.answer(f"❌ You and {t.full_name} are already **{rel}**! No duplicates needed.", parse_mode=None)

    _, _, prompt = REL_MAP[cmd]
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Accept", callback_data=f"fam_acc_{cmd}_{t.id}_{u.id}"),
        InlineKeyboardButton(text="❌ Decline", callback_data=f"fam_rej_{cmd}_{t.id}_{u.id}")
    ]])
    await message.answer(prompt.format(u=u.full_name, t=t.full_name), reply_markup=btn, parse_mode=None)


@router.callback_query(F.data.startswith("fam_"))
async def family_cb(query: CallbackQuery):
    _, act, cmd, tid, uid = query.data.split("_")
    tid, uid = int(tid), int(uid)
    if query.from_user.id != tid: return await query.answer("❌ Not for you!", show_alert=True)
    if act == "rej":
        await query.message.edit_text("❌ Family request declined.")
        return await query.answer()
    if rel := await _existing_rel(uid, tid):
        await query.message.edit_text(f"❌ Already connected ({rel})!")
        return await query.answer()
    r1, r2, _ = REL_MAP[cmd]
    await add_relation(uid, tid, r1)
    await add_relation(tid, uid, r2)
    await query.message.edit_text(f"🏡 **Family Updated!** {query.from_user.full_name} accepted `{cmd}`! 🌸", parse_mode=None)
    await query.answer("Accepted!")


@router.message(Command("disown", "runaway", "familyinfo", prefix="/!"))
async def family_manage_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "runaway":
        await runaway_family(message.from_user.id)
        return await message.answer("🏃💨 You packed your bags and ran away from your family!")
    if cmd == "disown":
        if not message.reply_to_message or not message.reply_to_message.from_user:
            return await message.answer("Reply to a family member to disown them!")
        t = message.reply_to_message.from_user
        if not await _existing_rel(message.from_user.id, t.id):
            return await message.answer(f"❌ {t.full_name} is not in your family!", parse_mode=None)
        await remove_relation(message.from_user.id, t.id)
        return await message.answer(f"❌ Disowned {t.full_name}!", parse_mode=None)
    fam, pid = await get_family(message.from_user.id), await get_partner(message.from_user.id)
    if not fam and not pid: return await message.answer("🏡 Your family is empty!")
    lines = [f"🏡 **{message.from_user.full_name}'s Family Info**\n"]
    if pid: lines.append(f"• 💍 Spouse: `{pid}`")
    for f in fam: lines.append(f"• {f['relation_type']}: `{f['relative_id']}`")
    await message.answer("\n".join(lines), parse_mode=None)


@router.message(Command("family", "tree", prefix="/!"))
async def family_tree_cmd(message: Message):
    u = message.from_user
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    pid, fam = await get_partner(u.id), await get_family(u.id)
    u_pfp = await _get_pfp(message.bot, u.id)
    sp_name, sp_pfp = None, None
    if pid:
        try: sp_name = (await message.bot.get_chat(pid)).first_name or str(pid)
        except Exception: sp_name = str(pid)
        sp_pfp = await _get_pfp(message.bot, pid)
    members = []
    for f in fam[:4]:
        rid = f["relative_id"]
        try: rname = (await message.bot.get_chat(rid)).first_name or str(rid)
        except Exception: rname = str(rid)
        members.append((rname, f["relation_type"], await _get_pfp(message.bot, rid)))
    img = generate_family_tree(u.first_name, u_pfp, sp_name, sp_pfp, members)
    await message.answer_photo(BufferedInputFile(img.getvalue(), filename="tree.jpg"), caption=f"🌳 {u.full_name}'s Nakama Family Tree", parse_mode=None)


# --- 3. ORIGINAL RUKA PAID GACHA (50 💎) ---
async def _pull_hd_art(tag: str, is_waifu: bool) -> str | None:
    sb = await _fetch_json(f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit=25&tags={tag}+solo")
    if isinstance(sb, list) and sb and sb[0].get("file_url"):
        return random.choice(sb).get("file_url")
    nb = await _fetch_json(f"https://nekos.best/api/v2/{'waifu' if is_waifu else 'husbando'}")
    return nb["results"][0].get("url") if nb and nb.get("results") else None


@router.message(Command("gacha", "waifugacha", prefix="/!"))
async def gacha_cmd(message: Message):
    uid, cost = message.from_user.id, 50
    if (await get_user_stats(uid))["coins"] < cost:
        return await message.answer("❌ A Gacha spin costs **50 💎**! Claim `/daily` or play games!")
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    is_w = random.random() < 0.65
    name, tag, anime = random.choice(WAIFU_POOL if is_w else HUSBANDO_POOL)
    url = await _pull_hd_art(tag, is_w)
    if not url: return await message.answer("❌ Gacha jammed! Coins not spent.")
    await update_user_stats(uid, coins=-cost)
    roll = random.randint(1, 100) + (15 if (await get_inventory(uid)).get("clover", 0) > 0 else 0)
    tier = "Heartbeat SSR" if roll >= 90 else ("Idol SR" if roll >= 65 else ("Doki-Doki R" if roll >= 35 else "Sweet"))
    power = random.randint(4000, 9999) if "SSR" in tier else random.randint(1000, 4500)
    ctype = "Waifu" if is_w else "Husbando"
    cid = await add_gacha_card(uid, name, ctype, anime, tier, power, url)
    img = generate_4k_anime_card(f"#{cid} {name}", f"{power} PWR", f"{ctype} • {anime}", tier, await _fetch_bytes(url))
    await message.answer_photo(BufferedInputFile(img.getvalue(), filename="gacha.jpg"),
                               caption=f"🎰 Ruka Gacha (-50 💎)\n🆔 #{cid} | {name} ({ctype})\n📺 {anime}\n✨ {tier} | ⚡ {power} PWR", parse_mode=None)


@router.message(Command("collection", "view", prefix="/!"))
async def collection_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    cards = await get_user_cards(message.from_user.id)
    if cmd == "collection":
        if not cards: return await message.answer("📭 Empty! Spin `/gacha` for `50 💎`!")
        lines = [f"🃏 {message.from_user.full_name}'s Collection ({len(cards)})\n"] + [f"• #{c['card_id']} {c['card_name']} [{c['char_type']}] — {c['rarity']}" for c in cards[:15]]
        return await message.answer("\n".join(lines), parse_mode=None)
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("Usage: `/view <id or name>`")
    q = p[1].lstrip("#").lower()
    f = next((c for c in cards if str(c["card_id"]) == q or q in c["card_name"].lower()), None)
    if not f: return await message.answer("❌ Card not found!")
    img = generate_4k_anime_card(f"#{f['card_id']} {f['card_name']}", f"{f['power']} PWR", f"{f['char_type']} • {f['anime']}", f["rarity"], await _fetch_bytes(f["image_url"]))
    await message.answer_photo(BufferedInputFile(img.getvalue(), filename="view.jpg"), caption=f"🃏 #{f['card_id']} {f['card_name']} | {f['rarity']} | ⚡ {f['power']}", parse_mode=None)


# --- 4. IDENTITY & LOVE ---
@router.message(Command("gender", "bio", "mybio", "lovecalc", prefix="/!"))
async def profile_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "gender":
        p = message.text.split()
        if len(p) < 2 or p[1].lower() not in ("male", "female"): return await message.answer("Usage: `/gender male` or `/gender female`")
        await set_profile(message.from_user.id, gender=p[1].capitalize()); return await message.answer(f"✅ Gender saved: **{p[1].capitalize()}**!")
    if cmd == "bio":
        p = message.text.split(None, 1)
        if len(p) < 2: return await message.answer("Usage: `/bio <text>`")
        await set_profile(message.from_user.id, bio=p[1]); return await message.answer("📝 Bio saved!")
    if cmd == "mybio":
        t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
        prof = await get_profile(t.id)
        return await message.answer(f"👤 {t.full_name} ({prof['gender']})\n\n📝 {prof['bio']}", parse_mode=None)
    if not message.reply_to_message: return await message.answer("Reply to someone!")
    await message.answer(f"💘 {message.from_user.full_name} ❤️ {message.reply_to_message.from_user.full_name} = {random.randint(1, 100)}%", parse_mode=None)