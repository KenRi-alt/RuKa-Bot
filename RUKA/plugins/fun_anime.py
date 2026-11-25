import random
import aiohttp
from io import BytesIO
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..utils.chat_action import chatAction
from ..utils.image_gen import generate_4k_anime_card

ANIME_SYNOPSIS_CACHE: dict[int, str] = {}


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


@Client.on_message(filters.command(list(ANIME_REACTIONS.keys())))
async def anime_reaction_cmd(client, message):
    cmd = message.command[0].lower()
    endpoint, text = ANIME_REACTIONS[cmd]
    data = await fetch_json(f"https://api.waifu.pics/{endpoint}")
    if not data or "url" not in data:
        return await message.reply_text("❌ Couldn't reach the anime server right now!")

    target = f" → {message.reply_to_message.from_user.mention}" if message.reply_to_message and message.reply_to_message.from_user else ""
    url = data["url"]
    if url.endswith(".gif"):
        await message.reply_animation(url, caption=f"{text}{target}")
    else:
        await message.reply_photo(url, caption=f"{text}{target}")


# --- 27: /gacha & /waifugacha — Interactive Waifu Gacha Pull! ---
@Client.on_message(filters.command(["gacha", "waifugacha"]))
@chatAction("upload_photo")
async def waifu_gacha(client, message):
    data = await fetch_json("https://api.waifu.pics/sfw/waifu")
    if not data or "url" not in data:
        return await message.reply_text("❌ Gacha machine jammed! Try again~")

    roll = random.randint(1, 100)
    if roll >= 90:
        rarity = "🌟 **SSR (Ultra Rare!)**"
    elif roll >= 60:
        rarity = "💎 **SR (Super Rare)**"
    else:
        rarity = "🌸 **R (Rare)**"

    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎲 Pull Again", callback_data="gacha_pull")]])
    await message.reply_photo(
        photo=data["url"],
        caption=f"🎰 **Ruka's Waifu Gacha**\n\n{message.from_user.mention} pulled:\n{rarity}\nPower Level: `{random.randint(1000, 9999)}`",
        reply_markup=btn
    )


# --- 28: /anime <name> — AniList + 4K Pillow Card + Synopsis Button ---
@Client.on_message(filters.command("anime"))
@chatAction("upload_photo")
async def anilist_search(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Tell me an anime name! Example: `/anime Rent a Girlfriend`")

    query = message.text.split(None, 1)[1]
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
        async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"search": query}}) as resp:
            res = await resp.json()

    media = res.get("data", {}).get("Media")
    if not media:
        return await message.reply_text("❌ Couldn't find that anime on AniList!")

    mid = media["id"]
    ANIME_SYNOPSIS_CACHE[mid] = (media.get("description") or "No synopsis available.")[:350] + "..."
    title = media["title"].get("english") or media["title"].get("romaji")
    score = f"{media.get('averageScore', 'N/A')}%"
    genres = ", ".join(media.get("genres", [])[:3]) or "Anime"
    status = media.get("status", "UNKNOWN")
    cover_bytes = await fetch_bytes(media["coverImage"]["extraLarge"])

    img = generate_4k_anime_card(title, score, genres, status, cover_bytes)
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 Synopsis", callback_data=f"anisyn_{mid}"),
            InlineKeyboardButton("🔗 AniList", url=media["siteUrl"])
        ]
    ])
    await message.reply_photo(
        photo=img,
        caption=f"🎬 **{title}**\n⭐ Score: `{score}` | 📺 `{status}`",
        reply_markup=buttons
    )


# --- 29: /topanime — Live Top 10 Trending Anime ---
@Client.on_message(filters.command("topanime"))
async def top_anime(client, message):
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
        return await message.reply_text("❌ Couldn't fetch trending anime!")

    text = "🔥 **Top 10 Trending Anime Right Now:**\n\n"
    for i, m in enumerate(items, 1):
        t = m["title"].get("english") or m["title"].get("romaji")
        text += f"**{i}.** {t} — ⭐ `{m.get('averageScore', 'N/A')}%`\n"
    await message.reply_text(text)


# --- 30: /airing <name> — Next Episode Countdown ---
@Client.on_message(filters.command("airing"))
async def airing_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/airing One Piece`")
    query = message.text.split(None, 1)[1]
    gql = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji english }
        nextAiringEpisode { episode timeUntilAiring }
      }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"search": query}}) as resp:
            res = await resp.json()

    media = res.get("data", {}).get("Media")
    if not media:
        return await message.reply_text("❌ Anime not found!")
    nxt = media.get("nextAiringEpisode")
    title = media["title"].get("english") or media["title"].get("romaji")
    if not nxt:
        return await message.reply_text(f"📺 **{title}** has no upcoming airing episode scheduled.")

    secs = nxt["timeUntilAiring"]
    days, rem = divmod(secs, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    await message.reply_text(f"⏳ **{title}**\nEpisode **{nxt['episode']}** airs in: `{days}d {hrs}h {mins}m`!")


# --- 31–38: Fun & Party Commands ---
@Client.on_message(filters.command("ship"))
async def ship_users(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to someone to ship yourself with them! 💘")
    pct = random.randint(1, 100)
    hearts = "❤️" * (pct // 20) + "🤍" * (5 - (pct // 20))
    await message.reply_text(
        f"💘 **Love Match!**\n{message.from_user.mention} + {message.reply_to_message.from_user.mention}\n"
        f"{hearts} **{pct}%**\n"
        + ("💓 *Doki-doki! True love!*" if pct > 75 else "😅 *Needs more effort!*")
    )


@Client.on_message(filters.command("8ball"))
async def magic_8ball(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Ask Ruka a yes/no question!")
    answers = ["Yes, definitely! 💓", "No way! 💢", "Ask again later~", "100% yes!", "My heart says no..."]
    await message.reply_text(f"🎱 **Ruka says:** {random.choice(answers)}")


@Client.on_message(filters.command("truth"))
async def truth_cmd(client, message):
    truths = ["Who is your secret crush?", "What's your most embarrassing anime moment?", "Have you ever lied to an admin?"]
    await message.reply_text(f"🤫 **Truth:** {random.choice(truths)}")


@Client.on_message(filters.command("dare"))
async def dare_cmd(client, message):
    dares = ["Send a voice note saying 'Ruka is best girl'!", "Change your bio to 'I love RuKa-Bot' for 1 hour!", "Tag a random member and say 'Doki-doki!'"]
    await message.reply_text(f"🔥 **Dare:** {random.choice(dares)}")


@Client.on_message(filters.command("coin"))
async def coin_flip(client, message):
    await message.reply_text(f"🪙 Flipped: **{random.choice(['Heads', 'Tails'])}**!")


@Client.on_message(filters.command("dice"))
async def roll_dice(client, message):
    await client.send_dice(message.chat.id, emoji="🎲")


@Client.on_message(filters.command("roll"))
async def roll_number(client, message):
    await message.reply_text(f"🎲 You rolled **{random.randint(1, 100)}**!")


@Client.on_message(filters.command("quote"))
async def anime_quote(client, message):
    quotes = [
        "\"A real girlfriend would never let you down!\" — Ruka Sarashina",
        "\"Hard work is worthless for those that don't believe in themselves.\" — Naruto",
        "\"Whatever you lose, you'll find it again.\" — Kenshin",
    ]
    await message.reply_text(f"💬 {random.choice(quotes)}")


# --- Callback Handler for Gacha & AniList Synopsis ---
@Client.on_callback_query(filters.regex(r"^(gacha_pull|anisyn_)"))
async def fun_anime_callbacks(client, query):
    if query.data == "gacha_pull":
        data = await fetch_json("https://api.waifu.pics/sfw/waifu")
        if not data or "url" not in data:
            return await query.answer("❌ Gacha machine jammed!", show_alert=True)
        roll = random.randint(1, 100)
        rarity = "🌟 **SSR (Ultra Rare!)**" if roll >= 90 else ("💎 **SR (Super Rare)**" if roll >= 60 else "🌸 **R (Rare)**")
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎲 Pull Again", callback_data="gacha_pull")]])
        await query.message.reply_photo(
            photo=data["url"],
            caption=f"🎰 **Ruka's Waifu Gacha**\n\n{query.from_user.mention} pulled:\n{rarity}\nPower Level: `{random.randint(1000, 9999)}`",
            reply_markup=btn
        )
        await query.answer("🎲 Pulled!")

    elif query.data.startswith("anisyn_"):
        mid = int(query.data.split("_")[1])
        syn = ANIME_SYNOPSIS_CACHE.get(mid, "Synopsis expired. Search again!")
        await query.answer(syn, show_alert=True)