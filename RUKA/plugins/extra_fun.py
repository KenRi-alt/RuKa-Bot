import random
import aiohttp
from io import BytesIO
from pyrogram import Client, filters
from ..utils.admin import admin
from ..utils.group_only import groupOnly
from ..utils.image_gen import generate_4k_anime_card

TAGGING_CHATS: set[int] = set()


async def _fetch_bytes(url: str) -> BytesIO | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=15) as resp:
            if resp.status == 200:
                data = BytesIO(await resp.read())
                data.seek(0)
                return data
    return None


# 1. /manga <name> — AniList Manga + 4K Pillow Card
@Client.on_message(filters.command("manga"))
async def manga_search(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Tell me a manga name! Example: `/manga Chainsaw Man`")
    query = message.text.split(None, 1)[1]
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
        return await message.reply_text("❌ Couldn't find that manga on AniList!")

    title = media["title"].get("english") or media["title"].get("romaji")
    score = f"{media.get('averageScore', 'N/A')}%"
    genres = ", ".join(media.get("genres", [])[:3]) or "Manga"
    status = media.get("status", "UNKNOWN")
    cover_bytes = await _fetch_bytes(media["coverImage"]["extraLarge"])

    img = generate_4k_anime_card(title, score, genres, status, cover_bytes)
    await message.reply_photo(
        photo=img,
        caption=f"📖 **{title}**\n⭐ Score: `{score}` | 📚 `{status}`\n🔗 [View on AniList]({media['siteUrl']})"
    )


# 2. /animechar <name> — AniList Character Search
@Client.on_message(filters.command("animechar"))
async def char_search(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Tell me a character name! Example: `/animechar Ruka Sarashina`")
    query = message.text.split(None, 1)[1]
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
        async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"search": query}}) as resp:
            res = await resp.json()

    char = res.get("data", {}).get("Character")
    if not char:
        return await message.reply_text("❌ Couldn't find that character!")

    await message.reply_photo(
        photo=char["image"]["large"],
        caption=(
            f"🌸 **{char['name']['full']}** ({char['name'].get('native', '')})\n"
            f"💖 Favorites: `{char.get('favourites', 0)}`\n"
            f"🔗 [AniList Profile]({char['siteUrl']})"
        )
    )


# 3. /couple — Random Couple of the Day
@Client.on_message(filters.command("couple") & filters.group)
async def couple_cmd(client, message):
    members = []
    async for m in client.get_chat_members(message.chat.id, limit=50):
        if not m.user.is_bot:
            members.append(m.user)
    if len(members) < 2:
        return await message.reply_text("Not enough members to ship!")
    c1, c2 = random.sample(members, 2)
    await message.reply_text(
        f"💘 **Couple of the Day!**\n\n"
        f"{c1.mention} ❤️ {c2.mention}\n"
        f"💓 *Ruka approves this ship!*"
    )


# 4–6. Fun Rate Meters (/simprate, /iq, /waifurate)
@Client.on_message(filters.command("simprate"))
async def simp_rate(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.reply_text(f"🥺 {target.mention} is **{random.randint(0, 100)}%** simp!")


@Client.on_message(filters.command("iq"))
async def iq_rate(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.reply_text(f"🧠 {target.mention}'s IQ is **{random.randint(40, 200)}**!")


@Client.on_message(filters.command("waifurate"))
async def waifu_rate(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.reply_text(f"🌸 {target.mention} is **{random.randint(1, 100)}/100** waifu material!")


# 7–13. Text Stylers (/mock, /reverse, /spoiler, /vapor, /morse, /tiny, /count)
@Client.on_message(filters.command("mock"))
async def mock_text(client, message):
    text = message.reply_to_message.text if message.reply_to_message else (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not text:
        return await message.reply_text("Give me text or reply to a message!")
    mocked = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))
    await message.reply_text(mocked)


@Client.on_message(filters.command("reverse"))
async def reverse_text(client, message):
    text = message.reply_to_message.text if message.reply_to_message else (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not text:
        return await message.reply_text("Give me text to reverse!")
    await message.reply_text(text[::-1])


@Client.on_message(filters.command("spoiler"))
async def spoiler_text(client, message):
    text = message.reply_to_message.text if message.reply_to_message else (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not text:
        return await message.reply_text("Give me text to hide as a spoiler!")
    await message.reply_text(f"||{text}||")


@Client.on_message(filters.command("vapor"))
async def vapor_text(client, message):
    text = message.reply_to_message.text if message.reply_to_message else (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not text:
        return await message.reply_text("Give me text!")
    await message.reply_text(" ".join(text))


@Client.on_message(filters.command("morse"))
async def morse_text(client, message):
    MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..", " ": "/"}
    text = message.text.split(None, 1)[1] if len(message.command) > 1 else ""
    if not text:
        return await message.reply_text("Give me text to convert to Morse!")
    await message.reply_text(" ".join(MORSE.get(c.upper(), c) for c in text))


@Client.on_message(filters.command("count"))
async def count_text(client, message):
    text = message.reply_to_message.text if message.reply_to_message else (message.text.split(None, 1)[1] if len(message.command) > 1 else None)
    if not text:
        return await message.reply_text("Reply to a message to count its words & characters!")
    await message.reply_text(f"🔢 **Words:** `{len(text.split())}` | **Characters:** `{len(text)}`")


# 14–17. Group Utilities (/poll, /choose, /decide, /hugall)
@Client.on_message(filters.command("poll") & filters.group)
async def create_poll(client, message):
    if len(message.command) < 2 or "|" not in message.text:
        return await message.reply_text("Usage: `/poll Best girl? | Ruka | Chizuru | Sumi`")
    parts = [p.strip() for p in message.text.split(None, 1)[1].split("|") if p.strip()]
    if len(parts) < 3:
        return await message.reply_text("Give a question and at least 2 options separated by `|`!")
    await client.send_poll(message.chat.id, question=parts[0], options=parts[1:11])


@Client.on_message(filters.command("choose"))
async def choose_cmd(client, message):
    if len(message.command) < 2 or "|" not in message.text:
        return await message.reply_text("Usage: `/choose Pizza | Ramen | Sushi`")
    opts = [p.strip() for p in message.text.split(None, 1)[1].split("|") if p.strip()]
    await message.reply_text(f"💓 **Ruka chooses:** **{random.choice(opts)}**!")


@Client.on_message(filters.command("decide"))
async def decide_cmd(client, message):
    await message.reply_text(f"🤔 **Ruka's decision:** **{random.choice(['Yes! 💓', 'No! 💢', 'Maybe~ 🌸'])}**")


@Client.on_message(filters.command("hugall") & filters.group)
async def hug_all(client, message):
    await message.reply_text("🤗 *Ruka gives everyone in the group a giant warm hug!* 💓")


# 18–19. /tagall & /stoptag (Admin Only)
@Client.on_message(filters.command("tagall") & filters.group)
@groupOnly()
@admin(msg=True)
async def tag_all(client, message):
    TAGGING_CHATS.add(message.chat.id)
    reason = message.text.split(None, 1)[1] if len(message.command) > 1 else "Attention everyone! 💓"
    mentions = []
    async for m in client.get_chat_members(message.chat.id):
        if message.chat.id not in TAGGING_CHATS:
            break
        if not m.user.is_bot:
            mentions.append(m.user.mention)
            if len(mentions) == 5:
                await message.reply_text(f"{reason}\n\n" + " ".join(mentions))
                mentions.clear()
    if mentions and message.chat.id in TAGGING_CHATS:
        await message.reply_text(f"{reason}\n\n" + " ".join(mentions))
    TAGGING_CHATS.discard(message.chat.id)


@Client.on_message(filters.command("stoptag") & filters.group)
@groupOnly()
@admin(msg=True)
async def stop_tag(client, message):
    TAGGING_CHATS.discard(message.chat.id)
    await message.reply_text("🛑 Stopped tagging!")