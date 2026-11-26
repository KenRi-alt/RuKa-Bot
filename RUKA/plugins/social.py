import random
import aiohttp
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, BufferedInputFile
)
from RUKA.utils.db import (
    set_marriage, get_partner, remove_marriage,
    add_relation, get_family, add_gacha_card, get_user_cards
)
from RUKA.utils.image_gen import generate_4k_anime_card

router = Router()

USER_GENDER: dict[int, str] = {}
USER_BIO: dict[int, str] = {}
CARD_COUNTER = 1000


async def fetch_json(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return None


async def fetch_bytes(url: str) -> BytesIO | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = BytesIO(await resp.read())
                    data.seek(0)
                    return data
    except Exception:
        pass
    return None


# --- 1. REAL ANIME GIF REACTIONS (waifu.pics + nekos.best fallback) ---
GIF_REACTIONS = {
    "hug": ("hug", "🤗 {u1} gives a warm hug to {u2}!"),
    "kiss": ("kiss", "💋 {u1} gives a sweet kiss to {u2}!"),
    "slap": ("slap", "💢 *SLAP!* {u1} slapped {u2}!"),
    "pat": ("pat", "👋 {u1} gently pats {u2}~"),
    "cuddle": ("cuddle", "🌸 {u1} cuddles with {u2}!"),
    "poke": ("poke", "👉 {u1} pokes {u2}!"),
    "wink": ("wink", "😉 {u1} winks at {u2}!"),
    "cringe": ("cringe", "😬 {u1} cringes at {u2}..."),
    "bite": ("bite", "🧛 {u1} bites {u2}!"),
    "bonk": ("bonk", "🔨 *BONK!* {u1} bonks {u2}!"),
    "blush": ("blush", "😳 {u1} is blushing!"),
    "cry": ("cry", "😭 {u1} is crying..."),
    "dance": ("dance", "💃 {u1} is dancing!"),
    "smile": ("smile", "😊 {u1} smiles warmly!"),
    "wave": ("wave", "👋 {u1} waves at {u2}!"),
    "highfive": ("highfive", "🙌 {u1} high-fives {u2}!"),
    "handhold": ("handhold", "🤝 {u1} holds hands with {u2}!"),
    "tickle": ("tickle", "🤭 {u1} tickles {u2}!"),
    "yeet": ("yeet", "🚀 {u1} YEETS {u2}!"),
    "kill": ("kill", "⚔️ {u1} eliminates {u2}!"),
    "happy": ("happy", "✨ {u1} is super happy!"),
    "smug": ("smug", "😏 {u1} looks smug~"),
    "glare": ("glare", "👀 {u1} glares at {u2}..."),
    "sleep": ("sleep", "😴 {u1} fell asleep~"),
}


@router.message(Command(*GIF_REACTIONS.keys(), prefix="/!"))
async def gif_reaction_cmd(message: Message):
    cmd = message.text.split()[0].lstrip("/!").split("@")[0].lower()
    endpoint, template = GIF_REACTIONS[cmd]

    # Try waifu.pics first, then nekos.best fallback
    url = None
    data = await fetch_json(f"https://api.waifu.pics/sfw/{endpoint}")
    if data and "url" in data:
        url = data["url"]
    else:
        nb = await fetch_json(f"https://nekos.best/api/v2/{endpoint}")
        if nb and nb.get("results"):
            url = nb["results"][0].get("url")

    if not url:
        return await message.answer("❌ Couldn't fetch GIF right now!")

    u1 = message.from_user.full_name
    u2 = message.reply_to_message.from_user.full_name if message.reply_to_message and message.reply_to_message.from_user else "everyone"
    caption = template.format(u1=u1, u2=u2)

    if url.endswith(".gif"):
        await message.answer_animation(url, caption=caption, parse_mode=None)
    else:
        await message.answer_photo(url, caption=caption, parse_mode=None)


# --- 2. MARRIAGE & SOULMATES ---
@router.message(Command("marry", prefix="/!"))
async def marry_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer("💍 Reply to the person you want to propose to!")
    target = message.reply_to_message.from_user
    if target.id == message.from_user.id:
        return await message.answer("❌ You can't marry yourself, baka!")

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💍 Accept", callback_data=f"m_acc_{target.id}_{message.from_user.id}"),
        InlineKeyboardButton(text="💔 Reject", callback_data=f"m_rej_{target.id}")
    ]])
    await message.answer(
        f"💍 {message.from_user.full_name} is proposing to {target.full_name}!\nWill you accept?",
        reply_markup=btn, parse_mode=None
    )


@router.callback_query(F.data.startswith("m_"))
async def marriage_cb(query: CallbackQuery):
    parts = query.data.split("_")
    action, target_id = parts[1], int(parts[2])
    if query.from_user.id != target_id:
        return await query.answer("❌ This proposal isn't for you!", show_alert=True)

    if action == "acc":
        await set_marriage(int(parts[3]), target_id)
        await query.message.edit_text(f"💖 It's Official! {query.from_user.full_name} is now married! 🌸", parse_mode=None)
    else:
        await query.message.edit_text("💔 The proposal was rejected. 😭")
    await query.answer()


@router.message(Command("partner", "marriagestatus", prefix="/!"))
async def partner_cmd(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    pid = await get_partner(target.id)
    if not pid:
        return await message.answer(f"🔎 {target.full_name} is currently single.", parse_mode=None)
    await message.answer(f"💞 {target.full_name}'s Partner ID: `{pid}`\nStatus: **Soulmates** ✨")


@router.message(Command("divorce", prefix="/!"))
async def divorce_cmd(message: Message):
    pid = await get_partner(message.from_user.id)
    if not pid:
        return await message.answer("❌ You aren't married!")
    await remove_marriage(message.from_user.id)
    await message.answer("💔 You are now divorced. The bond has ended...")


# --- 3. FAMILY & LINEAGE ---
@router.message(Command("adopt", prefix="/!"))
async def adopt_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer("Reply to someone to adopt them!")
    t = message.reply_to_message.from_user
    await add_relation(message.from_user.id, t.id, "child")
    await message.answer(f"🏠 Adopted! {t.full_name} is now your child!", parse_mode=None)


@router.message(Command("sibling", prefix="/!"))
async def sibling_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer("Reply to someone to add as your sibling!")
    t = message.reply_to_message.from_user
    await add_relation(message.from_user.id, t.id, "sibling")
    await message.answer(f"👫 Family! {t.full_name} is now your sibling!", parse_mode=None)


@router.message(Command("disown", prefix="/!"))
async def disown_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.answer("Reply to a family member to disown them!")
    t = message.reply_to_message.from_user
    await message.answer(f"❌ {t.full_name} has been disowned from your family!", parse_mode=None)


@router.message(Command("family", "tree", prefix="/!"))
async def family_tree_cmd(message: Message):
    fam = await get_family(message.from_user.id)
    pid = await get_partner(message.from_user.id)
    lines = [f"🌳 {message.from_user.full_name}'s Family Tree", f"👤 You ({message.from_user.id})"]
    if pid:
        lines.append(f" ├── 💍 Spouse: {pid}")
    for f in fam:
        icon = "👶" if f["relation_type"] == "child" else "👫"
        lines.append(f" └── {icon} {f['relation_type'].capitalize()}: {f['relative_id']}")
    if not pid and not fam:
        return await message.answer("🏡 Your family tree is empty! Use `/marry` or `/adopt`~")
    await message.answer("\n".join(lines), parse_mode=None)


# --- 4. MATCHED WAIFU & HUSBANDO GACHA ---
async def _pull_anilist_char():
    page = random.randint(1, 150)
    gql = """
    query ($page: Int) {
      Page(page: $page, perPage: 10) {
        characters(sort: FAVOURITES_DESC) {
          name { full }
          gender
          favourites
          image { large }
          media(perPage: 1) { nodes { title { english romaji } } }
        }
      }
    }
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"page": page}}, timeout=12) as resp:
                res = await resp.json()
        chars = res.get("data", {}).get("Page", {}).get("characters", [])
        return random.choice(chars) if chars else None
    except Exception:
        return None


@router.message(Command("gacha", "waifugacha", prefix="/!"))
async def gacha_cmd(message: Message):
    global CARD_COUNTER
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    char = await _pull_anilist_char()
    if not char:
        return await message.answer("❌ Gacha machine jammed! Try again~")

    CARD_COUNTER += 1
    cid = CARD_COUNTER
    name = char["name"]["full"]
    gender = char.get("gender") or "Unknown"
    tag = "💖 Waifu" if gender == "Female" else ("💙 Husbando" if gender == "Male" else "✨ Character")
    favs = char.get("favourites") or 0
    rarity = "SSR" if favs >= 5000 else ("SR" if favs >= 1000 else "R")
    power = random.randint(1000, 9999)
    anime = "Anime"
    nodes = char.get("media", {}).get("nodes", [])
    if nodes:
        anime = nodes[0]["title"].get("english") or nodes[0]["title"].get("romaji") or "Anime"

    url = char["image"]["large"]
    try:
        await add_gacha_card(message.from_user.id, {"id": cid, "name": name, "rarity": rarity, "power": power, "url": url})
    except Exception:
        pass

    img_bytes = await fetch_bytes(url)
    card_img = generate_4k_anime_card(f"#{cid} {name}", f"{power} PWR", f"{tag} • {anime}", rarity, img_bytes)
    await message.answer_photo(
        photo=BufferedInputFile(card_img.getvalue(), filename="card.jpg"),
        caption=f"🎰 Gacha Pull!\n\n🆔 #{cid} | {name} ({tag})\n📺 {anime}\n✨ Rarity: {rarity} | ⚡ {power}",
        parse_mode=None
    )


@router.message(Command("collection", prefix="/!"))
async def collection_cmd(message: Message):
    cards = await get_user_cards(message.from_user.id)
    if not cards:
        return await message.answer("📭 Your collection is empty! Use `/gacha` to pull!")
    lines = [f"🃏 {message.from_user.full_name}'s Collection ({len(cards)} Cards)\n"]
    for c in cards[:15]:
        lines.append(f"• #{c['card_id']} {c['card_name']} ({c['rarity']})")
    await message.answer("\n".join(lines), parse_mode=None)


@router.message(Command("view", prefix="/!"))
async def view_card_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/view <id or name>`")
    q = parts[1].lstrip("#").lower()
    cards = await get_user_cards(message.from_user.id)
    found = next((c for c in cards if str(c["card_id"]) == q or q in c["card_name"].lower()), None)
    if not found:
        return await message.answer("❌ Card not found in your collection!")
    img_bytes = await fetch_bytes(found["image_url"])
    card_img = generate_4k_anime_card(f"#{found['card_id']} {found['card_name']}", f"{found['power']} PWR", found["rarity"], "OWNED", img_bytes)
    await message.answer_photo(
        photo=BufferedInputFile(card_img.getvalue(), filename="view.jpg"),
        caption=f"🃏 #{found['card_id']} {found['card_name']} | {found['rarity']} | ⚡ {found['power']}",
        parse_mode=None
    )


# --- 5. IDENTITY & LOVE ---
@router.message(Command("gender", prefix="/!"))
async def set_gender(message: Message):
    parts = message.text.split()
    if len(parts) < 2 or parts[1].lower() not in ("male", "female"):
        return await message.answer("Usage: `/gender male` or `/gender female`")
    USER_GENDER[message.from_user.id] = parts[1].lower()
    await message.answer(f"✅ Gender set to **{parts[1].capitalize()}**!")


@router.message(Command("bio", prefix="/!"))
async def set_bio(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/bio <text>`")
    USER_BIO[message.from_user.id] = parts[1]
    await message.answer("📝 Bio updated!")


@router.message(Command("mybio", prefix="/!"))
async def get_bio(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    g = USER_GENDER.get(target.id, "Not set").capitalize()
    bio = USER_BIO.get(target.id, "No bio set yet!")
    await message.answer(f"👤 {target.full_name} ({g})\n\n📝 {bio}", parse_mode=None)


@router.message(Command("lovecalc", prefix="/!"))
async def love_cmd(message: Message):
    if not message.reply_to_message:
        return await message.answer("Reply to someone!")
    await message.answer(
        f"💘 {message.from_user.full_name} ❤️ {message.reply_to_message.from_user.full_name} = {random.randint(1, 100)}%",
        parse_mode=None
    )