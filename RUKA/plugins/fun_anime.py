import random
import aiohttp
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from RUKA.utils.image_gen import generate_4k_anime_card

router = Router()

ANIME_SYNOPSIS_CACHE: dict[int, str] = {}
USER_COLLECTIONS: dict[int, list[dict]] = {}
CARD_COUNTER = 100

WAIFU_NAMES = [
    "Ruka Sarashina", "Chizuru Mizuhara", "Zero Two", "Rem", "Asuna Yuuki",
    "Mikasa Ackerman", "Nezuko Kamado", "Makima", "Marin Kitagawa", "Hinata Hyuga",
    "Megumin", "Mai Sakurajima", "Yor Forger", "Frieren", "Fern",
]


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


# --- 1–26: 26 Anime Reaction & Waifu Commands ---
ANIME_REACTIONS = {
    "waifu": ("sfw/waifu", "💖 Here's your waifu! (Still not as cute as Ruka though~)"),
    "neko": ("sfw/neko", "🐱 Nyaa~ Look at this cute neko!"),
    "hug": ("sfw/hug", "🤗 *Ruka gives a big warm hug!*"),
    "pat": ("sfw/pat", "👋 *Pat pat~* Good job!"),
    "slap": ("sfw/slap", "💢 *SLAP!* Don't make Ruka mad!"),
    "kiss": ("sfw/kiss", "💋 *Doki-doki!* A sweet kiss~"),
    "cuddle": ("sfw/cuddle", "🌸 *Cuddle time!* So cozy~"),
    "poke": ("sfw/poke", "👉 *Poke poke!* Pay attention to me!"),
    "wink": ("sfw/wink", "😉 *Wink!*"),
    "baka": ("sfw/bonk", "🔨 *BONK!* Baka!!"),
    "bite": ("sfw/bite", "🧛 *Nom!*"),
    "blush": ("sfw/blush", "😳 *B-Baka! Don't look at me like that!*"),
    "cry": ("sfw/cry", "😭 *Waaah!*"),
    "dance": ("sfw/dance", "💃 *Let's dance!*"),
    "smile": ("sfw/smile", "😊 *Smile~*"),
    "wave": ("sfw/wave", "👋 *Yahallo!*"),
    "highfive": ("sfw/highfive", "🙌 *High five!*"),
    "handhold": ("sfw/handhold", "🤝 *H-Handholding?! So lewd!*"),
    "tickle": ("sfw/tickle", "🤭 *Tickle attack!*"),
    "yeet": ("sfw/yeet", "🚀 *YEET!*"),
    "akick": ("sfw/kick", "🦵 *Hi-yah!*"),
    "kill": ("sfw/kill", "⚔️ *Omae wa mou shindeiru!*"),
    "happy": ("sfw/happy", "✨ *Yay! So happy!*"),
    "smug": ("sfw/smug", "😏 *Hmph, I knew it~*"),
    "stare": ("sfw/glare", "👀 *Jiiiiii...*"),
    "sleep": ("sfw/sleep", "😴 *Oyasumi~*"),
}


@router.message(Command(*ANIME_REACTIONS.keys()))
async def anime_reaction_cmd(message: Message):
    cmd = message.text.split()[0].lstrip("/").split("@")[0].lower()
    endpoint, text = ANIME_REACTIONS[cmd]
    data = await fetch_json(f"https://api.waifu.pics/{endpoint}")
    if not data or "url" not in data:
        return await message.answer("❌ Couldn't reach the anime server right now!")

    target = f" → {message.reply_to_message.from_user.full_name}" if message.reply_to_message and message.reply_to_message.from_user else ""
    url = data["url"]
    if url.endswith(".gif"):
        await message.answer_animation(url, caption=f"{text}{target}")
    else:
        await message.answer_photo(url, caption=f"{text}{target}")


# --- 27: /gacha & /waifugacha — 4K Waifu Gacha Pull! ---
async def _do_gacha(user_id: int, user_name: str):
    global CARD_COUNTER
    data = await fetch_json("https://api.waifu.pics/sfw/waifu")
    if not data or "url" not in data:
        return None, None

    CARD_COUNTER += 1
    card_id = CARD_COUNTER
    name = random.choice(WAIFU_NAMES)
    roll = random.randint(1, 100)
    rarity = "SSR" if roll >= 90 else ("SR" if roll >= 60 else "R")
    rarity_label = "🌟 **SSR (Ultra Rare!)**" if rarity == "SSR" else ("💎 **SR (Super Rare)**" if rarity == "SR" else "🌸 **R (Rare)**")
    power = random.randint(1000, 9999)

    card = {"id": card_id, "name": name, "rarity": rarity, "power": power, "url": data["url"]}
    USER_COLLECTIONS.setdefault(user_id, []).append(card)

    cover_bytes = await fetch_bytes(data["url"])
    img = generate_4k_anime_card(f"#{card_id} {name}", f"{power} PWR", rarity_label.replace("*", ""), "COLLECTED", cover_bytes)
    photo = BufferedInputFile(img.getvalue(), filename=f"card_{card_id}.png")
    caption = (
        f"🎰 **Ruka's 4K Waifu Gacha**\n\n"
        f"👤 **{user_name}** pulled:\n"
        f"🆔 ID: `#{card_id}` | 🌸 **{name}**\n"
        f"{rarity_label} | ⚡ Power: `{power}`\n\n"
        f"Use `/collection` to see all your cards!"
    )
    return photo, caption


@router.message(Command("gacha", "waifugacha"))
async def waifu_gacha(message: Message):
    photo, caption = await _do_gacha(message.from_user.id, message.from_user.full_name)
    if not photo:
        return await message.answer("❌ Gacha machine jammed! Try again~")
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎲 Pull Again", callback_data="gacha_pull")]])
    await message.answer_photo(photo=photo, caption=caption, reply_markup=btn)


# --- 28: /collection — View Your Pulled Cards ---
@router.message(Command("collection"))
async def view_collection(message: Message):
    cards = USER_COLLECTIONS.get(message.from_user.id, [])
    if not cards:
        return await message.answer("📭 Your collection is empty! Use `/gacha` to pull your first 4K Waifu Card~")

    text = f"🃏 **{message.from_user.full_name}'s Waifu Collection ({len(cards)} Cards)**\n\n"
    for c in cards[-15:]:
        text += f"• `#{c['id']}` **{c['name']}** — `{c['rarity']}` (⚡ `{c['power']}`)\n"
    text += "\nUse `/view <id or name>` to inspect any card in **4K**!"
    await message.answer(text)


# --- 29: /view <id or name> — View Specific Card in 4K ---
@router.message(Command("view"))
async def view_card(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/view 101` or `/view Ruka`")
    query = parts[1].lstrip("#").lower()
    cards = USER_COLLECTIONS.get(message.from_user.id, [])
    found = next((c for c in cards if str(c["id"]) == query or query in c["name"].lower()), None)
    if not found:
        return await message.answer("❌ Card not found in your collection!")

    cover_bytes = await fetch_bytes(found["url"])
    img = generate_4k_anime_card(f"#{found['id']} {found['name']}", f"{found['power']} PWR", found["rarity"], "OWNED", cover_bytes)
    photo = BufferedInputFile(img.getvalue(), filename=f"card_{found['id']}.png")
    await message.answer_photo(
        photo=photo,
        caption=f"🃏 **Card #{found['id']} — {found['name']}**\n🏆 Rarity: `{found['rarity']}` | ⚡ Power: `{found['power']}`"
    )


# --- 30: /anime <name> — AniList + 4K Pillow Card ---
@router.message(Command("anime"))
async def anilist_search(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Tell me an anime name! Example: `/anime Rent a Girlfriend`")

    gql = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        id
        title { romaji english }
        averageScore
        genres
        status
        description(asHtml: false)
        coverImage { extraLarge }
        siteUrl
      }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"search": parts[1]}}) as resp:
            res = await resp.json()

    media = res.get("data", {}).get("Media")
    if not media:
        return await message.answer("❌ Couldn't find that anime on AniList!")

    mid = media["id"]
    ANIME_SYNOPSIS_CACHE[mid] = (media.get("description") or "No synopsis available.")[:350] + "..."
    title = media["title"].get("english") or media["title"].get("romaji")
    score = f"{media.get('averageScore', 'N/A')}%"
    genres = ", ".join(media.get("genres", [])[:3]) or "Anime"
    status = media.get("status", "UNKNOWN")
    cover_bytes = await fetch_bytes(media["coverImage"]["extraLarge"])

    img = generate_4k_anime_card(title, score, genres, status, cover_bytes)
    photo = BufferedInputFile(img.getvalue(), filename="anime_4k.png")
    buttons = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📖 Synopsis", callback_data=f"anisyn_{mid}"),
        InlineKeyboardButton(text="🔗 AniList", url=media["siteUrl"])
    ]])
    await message.answer_photo(photo=photo, caption=f"🎬 **{title}**\n⭐ Score: `{score}` | 📺 `{status}`", reply_markup=buttons)


# --- 31: /topanime ---
@router.message(Command("topanime"))
async def top_anime(message: Message):
    gql = """
    query {
      Page(page: 1, perPage: 10) {
        media(sort: TRENDING_DESC, type: ANIME) {
          title { romaji english }
          averageScore
        }
      }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post("https://graphql.anilist.co", json={"query": gql}) as resp:
            res = await resp.json()
    items = res.get("data", {}).get("Page", {}).get("media", [])
    if not items:
        return await message.answer("❌ Couldn't fetch trending anime!")
    text = "🔥 **Top 10 Trending Anime Right Now:**\n\n"
    for i, m in enumerate(items, 1):
        t = m["title"].get("english") or m["title"].get("romaji")
        text += f"**{i}.** {t} — ⭐ `{m.get('averageScore', 'N/A')}%`\n"
    await message.answer(text)


# --- 32: /airing <name> ---
@router.message(Command("airing"))
async def airing_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/airing One Piece`")
    gql = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji english }
        nextAiringEpisode { episode timeUntilAiring }
      }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"search": parts[1]}}) as resp:
            res = await resp.json()
    media = res.get("data", {}).get("Media")
    if not media:
        return await message.answer("❌ Anime not found!")
    nxt = media.get("nextAiringEpisode")
    title = media["title"].get("english") or media["title"].get("romaji")
    if not nxt:
        return await message.answer(f"📺 **{title}** has no upcoming airing episode scheduled.")
    secs = nxt["timeUntilAiring"]
    days, rem = divmod(secs, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    await message.answer(f"⏳ **{title}**\nEpisode **{nxt['episode']}** airs in: `{days}d {hrs}h {mins}m`!")


# --- 33–40: Fun & Party Commands ---
@router.message(Command("ship"))
async def ship_users(message: Message):
    if not message.reply_to_message:
        return await message.answer("Reply to someone to ship yourself with them! 💘")
    pct = random.randint(1, 100)
    hearts = "❤️" * (pct // 20) + "🤍" * (5 - (pct // 20))
    await message.answer(
        f"💘 **Love Match!**\n{message.from_user.full_name} + {message.reply_to_message.from_user.full_name}\n"
        f"{hearts} **{pct}%**\n"
        + ("💓 *Doki-doki! True love!*" if pct > 75 else "😅 *Needs more effort!*")
    )


@router.message(Command("8ball"))
async def magic_8ball(message: Message):
    if len(message.text.split()) < 2:
        return await message.answer("Ask Ruka a yes/no question!")
    answers = ["Yes, definitely! 💓", "No way! 💢", "Ask again later~", "100% yes!", "My heart says no..."]
    await message.answer(f"🎱 **Ruka says:** {random.choice(answers)}")


@router.message(Command("truth"))
async def truth_cmd(message: Message):
    truths = ["Who is your secret crush?", "What's your most embarrassing anime moment?", "Have you ever lied to an admin?"]
    await message.answer(f"🤫 **Truth:** {random.choice(truths)}")


@router.message(Command("dare"))
async def dare_cmd(message: Message):
    dares = ["Send a voice note saying 'Ruka is best girl'!", "Change your bio to 'I love RuKa-Bot' for 1 hour!", "Tag a random member and say 'Doki-doki!'"]
    await message.answer(f"🔥 **Dare:** {random.choice(dares)}")


@router.message(Command("coin"))
async def coin_flip(message: Message):
    await message.answer(f"🪙 Flipped: **{random.choice(['Heads', 'Tails'])}**!")


@router.message(Command("dice"))
async def roll_dice(message: Message):
    await message.answer_dice(emoji="🎲")


@router.message(Command("roll"))
async def roll_number(message: Message):
    await message.answer(f"🎲 You rolled **{random.randint(1, 100)}**!")


@router.message(Command("quote"))
async def anime_quote(message: Message):
    quotes = [
        "\"A real girlfriend would never let you down!\" — Ruka Sarashina",
        "\"Hard work is worthless for those that don't believe in themselves.\" — Naruto",
        "\"Whatever you lose, you'll find it again.\" — Kenshin",
    ]
    await message.answer(f"💬 {random.choice(quotes)}")


# --- Callback Handler ---
@router.callback_query(F.data.startswith(("gacha_pull", "anisyn_")))
async def fun_anime_callbacks(query: CallbackQuery):
    if query.data == "gacha_pull":
        photo, caption = await _do_gacha(query.from_user.id, query.from_user.full_name)
        if not photo:
            return await query.answer("❌ Gacha machine jammed!", show_alert=True)
        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎲 Pull Again", callback_data="gacha_pull")]])
        await query.message.answer_photo(photo=photo, caption=caption, reply_markup=btn)
        await query.answer("🎲 Pulled!")

    elif query.data.startswith("anisyn_"):
        mid = int(query.data.split("_")[1])
        syn = ANIME_SYNOPSIS_CACHE.get(mid, "Synopsis expired. Search again!")
        await query.answer(syn, show_alert=True)