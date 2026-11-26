import random
import aiohttp
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from RUKA.utils.image_gen import generate_4k_anime_card

router = Router()

# --- HELPER FUNCTIONS ---
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


# --- 1. /anime <name> — AniList 4K Encyclopedia Card ---
@router.message(Command("anime"))
async def anime_search(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("🔍 Please provide an anime name! Example: `/anime One Piece`")
    
    query = parts[1]
    gql = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
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
        return await message.answer(f"❌ No anime found matching: `{query}`")

    title = media["title"].get("english") or media["title"].get("romaji")
    score = f"{media.get('averageScore', 'N/A')}%"
    genres = ", ".join(media.get("genres", [])[:3]) or "Anime"
    status = media.get("status", "UNKNOWN")
    cover_bytes = await fetch_bytes(media["coverImage"]["extraLarge"])

    if cover_bytes:
        img = generate_4k_anime_card(title, score, genres, status, cover_bytes)
        photo = BufferedInputFile(img.getvalue(), filename="anime_card.jpg")
        await message.answer_photo(
            photo=photo,
            caption=f"🎬 **{title}**\n⭐ Score: `{score}` | 📺 `{status}`\n🔗 [View on AniList]({media['siteUrl']})"
        )
    else:
        await message.answer(f"🎬 **{title}**\n⭐ Score: `{score}`\n📺 Status: `{status}`\n🔗 [AniList]({media['siteUrl']})")


# --- 2. /manga <name> — Manga Encyclopedia ---
@router.message(Command("manga"))
async def manga_search(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("🔍 Please provide a manga name! Example: `/manga Berserk`")
    
    query = parts[1]
    gql = """
    query ($search: String) {
      Media(search: $search, type: MANGA) {
        title { romaji english }
        averageScore
        genres
        status
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
        return await message.answer(f"❌ No manga found matching: `{query}`")

    title = media["title"].get("english") or media["title"].get("romaji")
    score = f"{media.get('averageScore', 'N/A')}%"
    genres = ", ".join(media.get("genres", [])[:3]) or "Manga"
    status = media.get("status", "UNKNOWN")
    cover_bytes = await fetch_bytes(media["coverImage"]["extraLarge"])

    if cover_bytes:
        img = generate_4k_anime_card(title, score, genres, status, cover_bytes)
        photo = BufferedInputFile(img.getvalue(), filename="manga_card.jpg")
        await message.answer_photo(
            photo=photo,
            caption=f"📖 **{title}**\n⭐ Score: `{score}` | 📚 `{status}`\n🔗 [View on AniList]({media['siteUrl']})"
        )
    else:
        await message.answer(f"📖 **{title}**\n⭐ Score: `{score}`\n📚 Status: `{status}`\n🔗 [AniList]({media['siteUrl']})")


# --- 3. /animechar <name> — Character Finder ---
@router.message(Command("animechar"))
async def char_search(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("🔍 Please provide a character name!")
    
    gql = """
    query ($search: String) {
      Character(search: $search) {
        name { full native }
        favourites
        image { large }
        siteUrl
      }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"search": parts[1]}}) as resp:
            res = await resp.json()

    char = res.get("data", {}).get("Character")
    if not char:
        return await message.answer("❌ Character not found!")

    await message.answer_photo(
        photo=char["image"]["large"],
        caption=(
            f"🌸 **{char['name']['full']}** ({char['name'].get('native', '')})\n"
            f"💖 Favorites: `{char.get('favourites', 0)}`\n"
            f"🔗 [AniList Profile]({char['siteUrl']})"
        )
    )


# --- 4. /topanime — Trending Anime List ---
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
        return await message.answer("❌ Could not fetch trending anime.")

    text = "🔥 **Top 10 Trending Anime Right Now:**\n\n"
    for i, m in enumerate(items, 1):
        t = m["title"].get("english") or m["title"].get("romaji")
        text += f"**{i}.** {t} — ⭐ `{m.get('averageScore', 'N/A')}%`\n"
    await message.answer(text)


# --- 5. /airing <name> — Next Episode Countdown ---
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
        return await message.answer(f"📺 **{title}** has no upcoming episode scheduled.")
    
    secs = nxt["timeUntilAiring"]
    days, rem = divmod(secs, 86400)
    hrs, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    await message.answer(f"⏳ **{title}**\nEpisode **{nxt['episode']}** airs in: `{days}d {hrs}h {mins}m`!")


# --- 6. /randomanime — Get a random recommendation ---
@router.message(Command("randomanime"))
async def random_anime_cmd(message: Message):
    gql = """
    query {
      Page(page: 1, perPage: 50) {
        media(sort: POPULARITY_DESC, type: ANIME) {
          title { english romaji }
        }
      }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post("https://graphql.anilist.co", json={"query": gql}) as resp:
            res = await resp.json()
    
    items = res.get("data", {}).get("Page", {}).get("media", [])
    if not items: return await message.answer("❌ Error fetching recommendations.")
    
    choice = random.choice(items)
    title = choice["title"].get("english") or choice["title"].get("romaji")
    await message.answer(f"🎲 **Ruka's Random Pick:**\n\n✨ `{title}`\n\nGo watch it! 🌸")


# --- 7. /quote — Anime Quotes ---
@router.message(Command("quote"))
async def anime_quote_cmd(message: Message):
    quotes = [
        "\"A real girlfriend would never let you down!\" — Ruka Sarashina",
        "\"Hard work is worthless for those that don' don't believe in themselves.\" — Naruto",
        "\"Whatever you lose, you'll find it again.\" — Kenshin",
        "\"I'll protect you, no matter what!\" — Anime Protagonist",
    ]
    await message.answer(f"💬 **Anime Quote:**\n\n`{random.choice(quotes)}`")