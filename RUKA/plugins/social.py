import time, random, aiohttp
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from RUKA.utils.db import (
    set_marriage, get_partner, remove_marriage, add_relation, remove_relation,
    runaway_family, get_family, set_profile, get_profile,
    add_gacha_card, get_user_cards, get_user_stats, update_user_stats, get_inventory
)
from RUKA.utils.image_gen import generate_family_tree, generate_waifushop_banner

router = Router()

RUKA_PIC = "https://ganga--link--ghhzdp9sv8hk.code.run/i/s0s0y8txhk.jpg"
RUKA_CACHE: bytes | None = None

# Verified Danbooru/Safebooru tags -> 100% Matched Character & Image!
WAIFU_POOL = [
    ("Ruka Sarashina", "ruka_sarashina", "Rent-a-Girlfriend"),
    ("Emilia", "emilia_(re:zero)", "Re:Zero"),
    ("Rem", "rem_(re:zero)", "Re:Zero"),
    ("Zero Two", "zero_two_(darling_in_the_franxx)", "Darling in the FranXX"),
    ("Makima", "makima_(chainsaw_man)", "Chainsaw Man"),
    ("Marin Kitagawa", "kitagawa_marin", "My Dress-Up Darling"),
    ("Yor Forger", "yor_briar", "Spy x Family"),
    ("Raiden Shogun", "raiden_shogun", "Genshin Impact"),
    ("Hu Tao", "hu_tao_(genshin_impact)", "Genshin Impact"),
    ("Mitsuri Kanroji", "kanroji_mitsuri", "Demon Slayer"),
    ("Shinobu Kocho", "kochou_shinobu", "Demon Slayer"),
    ("Mai Sakurajima", "sakurajima_mai", "Bunny Girl Senpai"),
    ("Asuna Yuuki", "asuna_(sao)", "Sword Art Online"),
    ("Esdeath", "esdeath", "Akame ga Kill!"),
    ("Frieren", "frieren", "Sousou no Frieren"),
]
HUSBANDO_POOL = [
    ("Satoru Gojo", "gojo_satoru", "Jujutsu Kaisen"),
    ("Levi Ackerman", "levi_ackerman", "Attack on Titan"),
    ("Megumi Fushiguro", "fushiguro_megumi", "Jujutsu Kaisen"),
    ("Roronoa Zoro", "roronoa_zoro", "One Piece"),
    ("Loid Forger", "loid_forger", "Spy x Family"),
    ("Killua Zoldyck", "killua_zoldyck", "Hunter x Hunter"),
    ("Sung Jin-Woo", "sung_jin-woo", "Solo Leveling"),
]
RARITIES = [
    ("Common", "⚪", 50, (1000, 2200)), ("Rare", "🔵", 28, (2300, 3800)),
    ("Epic", "🟣", 14, (4000, 5800)), ("Mythical", "🔴", 6, (6200, 8200)), ("Legendary", "🟡", 2, (8500, 9999)),
]


async def _fetch_json(url: str):
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "RuKaBot/3.0"}) as s:
            async with s.get(url, timeout=10) as r:
                if r.status == 200: return await r.json()
    except Exception: pass
    return None


async def _ruka_bytes() -> BytesIO | None:
    global RUKA_CACHE
    if RUKA_CACHE: return BytesIO(RUKA_CACHE)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(RUKA_PIC, timeout=10) as r:
                if r.status == 200:
                    RUKA_CACHE = await r.read(); return BytesIO(RUKA_CACHE)
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
    if await get_partner(u1) == u2: return "Spouse"
    for f in await get_family(u1):
        if f["relative_id"] == u2: return f["relation_type"]
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


# --- 2. MARRIAGE & FAMILY ---
@router.message(Command("marry", prefix="/!"))
async def marry_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return await message.answer("💍 Reply to propose!")
    u, t = message.from_user, message.reply_to_message.from_user
    if t.id == u.id or t.is_bot: return await message.answer("❌ Can't marry yourself or a bot!")
    if await get_partner(u.id): return await message.answer("❌ You are already married!")
    if await get_partner(t.id): return await message.answer(f"❌ {t.full_name} is already married!", parse_mode=None)
    if rel := await _existing_rel(u.id, t.id): return await message.answer(f"❌ Already **{rel}**!", parse_mode=None)
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💍 Accept", callback_data=f"m_acc_{t.id}_{u.id}"), InlineKeyboardButton(text="💔 Reject", callback_data=f"m_rej_{t.id}")]])
    await message.answer(f"💍 {u.full_name} proposes to {t.full_name}!", reply_markup=btn, parse_mode=None)


@router.callback_query(F.data.startswith("m_"))
async def marriage_cb(query: CallbackQuery):
    p = query.data.split("_"); act, tid = p[1], int(p[2])
    if query.from_user.id != tid: return await query.answer("❌ Not for you!", show_alert=True)
    if act == "acc": await set_marriage(int(p[3]), tid); await query.message.edit_text(f"💖 Official! {query.from_user.full_name} is married! 🌸", parse_mode=None)
    else: await query.message.edit_text("💔 Proposal rejected. 😭")
    await query.answer()


@router.message(Command("partner", "marriagestatus", "divorce", prefix="/!"))
async def partner_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "divorce":
        if not await get_partner(message.from_user.id): return await message.answer("❌ You aren't married!")
        await remove_marriage(message.from_user.id); return await message.answer("💔 Divorced.")
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    pid = await get_partner(t.id)
    await message.answer(f"💞 {t.full_name}'s Partner ID: {pid}" if pid else f"🔎 {t.full_name} is single.", parse_mode=None)


REL_MAP = {
    "adopt": ("Child", "Parent", "🏠 {u} wants to adopt {t}!"),
    "sibling": ("Sibling", "Sibling", "👫 {u} wants {t} as their Sibling!"),
    "makemom": ("Mom", "Child", "👩 {u} wants {t} as their Mom!"),
    "makedad": ("Dad", "Child", "👨 {u} wants {t} as their Dad!"),
    "cousin": ("Cousin", "Cousin", "🤝 {u} wants {t} as their Cousin!"),
    "pet": ("Pet", "Owner", "🐶 {u} wants {t} as the family Pet!"),
}


@router.message(Command(*REL_MAP.keys(), prefix="/!"))
async def family_request_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user: return await message.answer("Reply to someone!")
    cmd = message.text.split()[0].lstrip("/!").lower(); u, t = message.from_user, message.reply_to_message.from_user
    if t.id == u.id or t.is_bot: return await message.answer("❌ Invalid target!")
    if rel := await _existing_rel(u.id, t.id): return await message.answer(f"❌ Already **{rel}**!", parse_mode=None)
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Accept", callback_data=f"fam_acc_{cmd}_{t.id}_{u.id}"), InlineKeyboardButton(text="❌ Decline", callback_data=f"fam_rej_{cmd}_{t.id}_{u.id}")]])
    await message.answer(REL_MAP[cmd][2].format(u=u.full_name, t=t.full_name), reply_markup=btn, parse_mode=None)


@router.callback_query(F.data.startswith("fam_"))
async def family_cb(query: CallbackQuery):
    _, act, cmd, tid, uid = query.data.split("_"); tid, uid = int(tid), int(uid)
    if query.from_user.id != tid: return await query.answer("❌ Not for you!", show_alert=True)
    if act == "rej": await query.message.edit_text("❌ Declined."); return await query.answer()
    if rel := await _existing_rel(uid, tid): await query.message.edit_text(f"❌ Already {rel}!"); return await query.answer()
    r1, r2, _ = REL_MAP[cmd]
    await add_relation(uid, tid, r1); await add_relation(tid, uid, r2)
    await query.message.edit_text(f"🏡 {query.from_user.full_name} accepted `{cmd}`! 🌸", parse_mode=None)
    await query.answer("Accepted!")


@router.message(Command("disown", "runaway", "familyinfo", prefix="/!"))
async def family_manage_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "runaway": await runaway_family(message.from_user.id); return await message.answer("🏃💨 Ran away from family!")
    if cmd == "disown":
        if not message.reply_to_message: return await message.answer("Reply to a family member!")
        t = message.reply_to_message.from_user
        if not await _existing_rel(message.from_user.id, t.id): return await message.answer("❌ Not in your family!")
        await remove_relation(message.from_user.id, t.id); return await message.answer(f"❌ Disowned {t.full_name}!", parse_mode=None)
    fam, pid = await get_family(message.from_user.id), await get_partner(message.from_user.id)
    if not fam and not pid: return await message.answer("🏡 Your family is empty!")
    lines = [f"🏡 **{message.from_user.full_name}'s Family**\n"] + ([f"• 💍 Spouse: `{pid}`"] if pid else []) + [f"• {f['relation_type']}: `{f['relative_id']}`" for f in fam]
    await message.answer("\n".join(lines), parse_mode=None)


@router.message(Command("family", "tree", prefix="/!"))
async def family_tree_cmd(message: Message):
    u = message.from_user
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    pid, fam = await get_partner(u.id), await get_family(u.id)
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
    img = generate_family_tree(u.first_name, await _get_pfp(message.bot, u.id), sp_name, sp_pfp, members)
    await message.answer_photo(BufferedInputFile(img.getvalue(), filename="tree.jpg"), caption=f"🌳 {u.full_name}'s Family Tree", parse_mode=None)


# --- 3. MATCHED WAIFU & HUSBANDO GACHA (Danbooru + Safebooru SFW) ---
async def _pull_char_art(tag: str) -> str | None:
    # 1. Danbooru SFW (cleanest, exact character match!)
    db = await _fetch_json(f"https://danbooru.donmai.us/posts.json?tags={tag}+rating:general+solo&limit=20")
    if isinstance(db, list):
        urls = [p.get("large_file_url") or p.get("file_url") for p in db if (p.get("large_file_url") or p.get("file_url", "")).endswith((".jpg", ".png", ".jpeg"))]
        if urls: return random.choice(urls)
    # 2. Safebooru exact tag fallback
    sb = await _fetch_json(f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit=20&tags={tag}+rating:general")
    if isinstance(sb, list):
        urls = [p.get("file_url") for p in sb if p.get("file_url", "").endswith((".jpg", ".png", ".jpeg"))]
        if urls: return random.choice(urls)
    return None


def _roll_rarity(has_clover: bool) -> tuple[str, str, int]:
    weights = [40, 30, 18, 9, 3] if has_clover else [r[2] for r in RARITIES]
    name, emoji, _, (pmin, pmax) = random.choices(RARITIES, weights=weights, k=1)[0]
    return name, emoji, random.randint(pmin, pmax)


@router.message(Command("gacha", "waifugacha", prefix="/!"))
async def gacha_menu_cmd(message: Message):
    s = await get_user_stats(message.from_user.id)
    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 1x Spin (50 💎)", callback_data=f"gspin_1_{message.from_user.id}"),
         InlineKeyboardButton(text="⚡ 10x Spin (450 💎)", callback_data=f"gspin_10_{message.from_user.id}")],
        [InlineKeyboardButton(text="🌸 12h Exclusive Shop", callback_data=f"wshop_open_{message.from_user.id}")],
    ])
    await message.answer(
        f"🌸 **Ruka's Royal Gacha**\n\n💰 Wallet: **`{s['coins']} 💎`**\n\n"
        f"**Drop Rates:**\n⚪ Common: `50%` | 🔵 Rare: `28%`\n🟣 Epic: `14%` | 🔴 Mythical: `6%` | 🟡 Legendary: `2%`",
        reply_markup=btns
    )


@router.callback_query(F.data.startswith("gspin_"))
async def gacha_spin_cb(query: CallbackQuery):
    _, count_s, owner_id = query.data.split("_"); count, uid = int(count_s), int(owner_id)
    if query.from_user.id != uid: return await query.answer("❌ Use /gacha for your own menu!", show_alert=True)
    cost = 50 if count == 1 else 450
    if (await get_user_stats(uid))["coins"] < cost: return await query.answer(f"❌ Need {cost} 💎!", show_alert=True)

    await query.answer("🎲 Spinning...")
    await update_user_stats(uid, coins=-cost)
    has_clover = (await get_inventory(uid)).get("clover", 0) > 0
    pulls = []
    for _ in range(count):
        is_w = random.random() < 0.72
        name, tag, anime = random.choice(WAIFU_POOL if is_w else HUSBANDO_POOL)
        rarity, emoji, power = _roll_rarity(has_clover)
        pulls.append((name, tag, anime, rarity, emoji, power, "Waifu" if is_w else "Husbando"))

    best = max(pulls, key=lambda x: x[5])
    best_url = await _pull_char_art(best[1])
    saved = []
    for name, tag, anime, rarity, emoji, power, ctype in pulls:
        url = best_url if (name == best[0] and best_url) else (await _pull_char_art(tag) or "")
        cid = await add_gacha_card(uid, name, ctype, anime, f"{emoji} {rarity}", power, url)
        saved.append((cid, name, anime, rarity, emoji, power, ctype, url))

    if count == 1:
        cid, name, anime, rarity, emoji, power, ctype, url = saved[0]
        cap = f"✨ {query.from_user.full_name} pulled a {ctype}!\n\n🆔 #{cid}: {name}\n📺 {anime}\n(RARITY: {emoji} {rarity.upper()} | ⚡ {power})"
        await (query.message.answer_photo(url, caption=cap, parse_mode=None) if url else query.message.answer(cap, parse_mode=None))
    else:
        summary = [f"⚡ 10x Spin (-450 💎) for {query.from_user.full_name}:\n"] + [f"• #{c[0]} {c[4]} {c[1]} ({c[2]}) — ⚡{c[5]}" for c in saved] + [f"\n🌟 Best: {best[4]} {best[0]} ({best[3]})"]
        cap = "\n".join(summary)[:1000]
        await (query.message.answer_photo(best_url, caption=cap, parse_mode=None) if best_url else query.message.answer(cap, parse_mode=None))


# --- 4. 12-HOUR EXCLUSIVE WAIFU SHOP (With Custom Pillow Shop Banner!) ---
def _get_12h_shop():
    epoch = int(time.time() // 43200)
    rem = 43200 - (int(time.time()) % 43200)
    rng = random.Random(epoch)
    picks = rng.sample(WAIFU_POOL + HUSBANDO_POOL, 3)
    items = []
    for idx, (name, tag, anime) in enumerate(picks):
        is_leg = idx == 0
        items.append({
            "idx": idx, "name": name, "tag": tag, "anime": anime,
            "rarity": "🟡 Legendary" if is_leg else "🔴 Mythical",
            "price": rng.randint(7500, 12000) if is_leg else rng.randint(3500, 6000),
            "power": rng.randint(8800, 9999) if is_leg else rng.randint(6500, 8400),
            "ctype": "Waifu" if (name, tag, anime) in WAIFU_POOL else "Husbando",
        })
    return items, rem


@router.message(Command("waifushop", prefix="/!"))
@router.callback_query(F.data.startswith("wshop_open_"))
async def waifu_shop_cmd(event: Message | CallbackQuery):
    uid = event.from_user.id
    items, rem = _get_12h_shop()
    h, m = divmod(rem // 60, 60)
    s = await get_user_stats(uid)
    img = generate_waifushop_banner(s["coins"], items, f"{h}h {m}m", await _ruka_bytes())
    btns = [[InlineKeyboardButton(text=f"Buy {it['name']} ({it['price']} 💎)", callback_data=f"wbuy_{it['idx']}_{uid}")] for it in items]
    target_msg = event.message if isinstance(event, CallbackQuery) else event
    await target_msg.answer_photo(
        BufferedInputFile(img.getvalue(), filename="waifushop.jpg"),
        caption=f"🌸 12h Exclusive Waifu Shop | Resets in {h}h {m}m",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode=None
    )
    if isinstance(event, CallbackQuery): await event.answer()


@router.callback_query(F.data.startswith("wbuy_"))
async def waifu_shop_buy(query: CallbackQuery):
    _, idx_s, owner_id = query.data.split("_"); idx, uid = int(idx_s), int(owner_id)
    if query.from_user.id != uid: return await query.answer("❌ Open your own /waifushop!", show_alert=True)
    items, _ = _get_12h_shop(); it = items[idx]
    if (await get_user_stats(uid))["coins"] < it["price"]: return await query.answer(f"❌ Need {it['price']} 💎!", show_alert=True)
    await query.answer("✨ Purchasing...")
    await update_user_stats(uid, coins=-it["price"])
    url = await _pull_char_art(it["tag"]) or ""
    cid = await add_gacha_card(uid, it["name"], it["ctype"], it["anime"], it["rarity"], it["power"], url)
    cap = f"🛍️ Purchased Exclusive Card!\n\n🆔 #{cid}: {it['name']} ({it['ctype']})\n📺 {it['anime']}\n(RARITY: {it['rarity']} | ⚡ {it['power']})"
    await (query.message.answer_photo(url, caption=cap, parse_mode=None) if url else query.message.answer(cap, parse_mode=None))


# --- 5. SORTABLE /collection & /view ---
def _format_collection(cards: list[dict], name: str, mode: str = "series") -> tuple[str, InlineKeyboardMarkup]:
    if mode == "waifu": filtered = [c for c in cards if c["char_type"] == "Waifu"]
    elif mode == "husbando": filtered = [c for c in cards if c["char_type"] == "Husbando"]
    elif mode == "rarity":
        order = {"Legendary": 5, "Mythical": 4, "Epic": 3, "Rare": 2, "Common": 1}
        filtered = sorted(cards, key=lambda c: next((v for k, v in order.items() if k in c["rarity"]), 0), reverse=True)
    elif mode == "power":
        filtered = sorted(cards, key=lambda c: c["power"], reverse=True)
    else:
        filtered = sorted(cards, key=lambda c: c["anime"])

    lines = [f"🃏 {name}'s Collection ({len(filtered)} Cards | Sort: {mode.upper()})\n"]
    if mode == "series":
        by_s: dict[str, list[dict]] = {}
        for c in filtered[:25]: by_s.setdefault(c["anime"], []).append(c)
        for s_name, clist in by_s.items():
            lines.append(f"↪ {s_name}")
            for c in clist: lines.append(f"  | #{c['card_id']} | {c['rarity']} {c['card_name']} (⚡{c['power']})")
    else:
        for c in filtered[:25]:
            lines.append(f"• #{c['card_id']} | {c['rarity']} {c['card_name']} ({c['anime']}) — ⚡{c['power']}")
    if not filtered: lines.append("No cards match this filter yet!")
    lines.append("\nUse /view <id or name> to inspect any card!")

    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 By Series", callback_data="col_series"), InlineKeyboardButton(text="🌟 By Rarity", callback_data="col_rarity")],
        [InlineKeyboardButton(text="⚡ By Power", callback_data="col_power"), InlineKeyboardButton(text="💖 Waifus", callback_data="col_waifu"), InlineKeyboardButton(text="💙 Husbandos", callback_data="col_husbando")],
    ])
    return "\n".join(lines), btns


@router.message(Command("collection", prefix="/!"))
async def collection_cmd(message: Message):
    cards = await get_user_cards(message.from_user.id)
    if not cards: return await message.answer("📭 Empty! Spin `/gacha`!")
    txt, btns = _format_collection(cards, message.from_user.full_name, "series")
    await message.answer(txt, reply_markup=btns, parse_mode=None)


@router.callback_query(F.data.startswith("col_"))
async def collection_cb(query: CallbackQuery):
    txt, btns = _format_collection(await get_user_cards(query.from_user.id), query.from_user.full_name, query.data.split("_")[1])
    try: await query.message.edit_text(txt, reply_markup=btns, parse_mode=None)
    except Exception: pass
    await query.answer()


@router.message(Command("view", prefix="/!"))
async def view_card_cmd(message: Message):
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("Usage: `/view <id or name>`")
    q = p[1].lstrip("#").strip().lower()
    f = next((c for c in await get_user_cards(message.from_user.id) if str(c["card_id"]) == q or q in c["card_name"].lower()), None)
    if not f: return await message.answer("❌ Card not found!")
    cap = f"🃏 Card #{f['card_id']}: {f['card_name']} ({f['char_type']})\n📺 {f['anime']}\n(RARITY: {f['rarity']} | ⚡ {f['power']} PWR)"
    await (message.answer_photo(f["image_url"], caption=cap, parse_mode=None) if f.get("image_url") else message.answer(cap, parse_mode=None))


# --- 6. IDENTITY & LOVE ---
@router.message(Command("gender", "bio", "mybio", "lovecalc", prefix="/!"))
async def profile_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "gender":
        p = message.text.split()
        if len(p) < 2 or p[1].lower() not in ("male", "female"): return await message.answer("Usage: `/gender male` or `/gender female`")
        await set_profile(message.from_user.id, gender=p[1].capitalize()); return await message.answer(f"✅ Gender: **{p[1].capitalize()}**!")
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