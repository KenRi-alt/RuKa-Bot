import random
import aiohttp
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from RUKA.utils.image_gen import generate_4k_anime_card

router = Router()


async def _fetch_bytes(url: str) -> BytesIO | None:
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


async def _fetch_json(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return None


def _get_text(message: Message) -> str | None:
    if message.reply_to_message and message.reply_to_message.text:
        return message.reply_to_message.text
    parts = message.text.split(None, 1)
    return parts[1] if len(parts) > 1 else None


# 1. /manga <name> — AniList Manga + HD Card
@router.message(Command("manga"))
async def manga_search(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Tell me a manga name! Example: `/manga Chainsaw Man`")
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
        async with session.post("https://graphql.anilist.co", json={"query": gql, "variables": {"search": parts[1]}}) as resp:
            res = await resp.json()

    media = res.get("data", {}).get("Media")
    if not media:
        return await message.answer("❌ Couldn't find that manga on AniList!")

    title = media["title"].get("english") or media["title"].get("romaji")
    score = f"{media.get('averageScore', 'N/A')}%"
    genres = ", ".join(media.get("genres", [])[:3]) or "Manga"
    status = media.get("status", "UNKNOWN")
    cover_bytes = await _fetch_bytes(media["coverImage"]["extraLarge"])

    img = generate_4k_anime_card(title, score, genres, status, cover_bytes)
    photo = BufferedInputFile(img.getvalue(), filename="manga.jpg")
    await message.answer_photo(
        photo=photo,
        caption=f"📖 **{title}**\n⭐ Score: `{score}` | 📚 `{status}`\n🔗 [View on AniList]({media['siteUrl']})"
    )


# 2. /animechar <name> — AniList Character Search
@router.message(Command("animechar"))
async def char_search(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Tell me a character name! Example: `/animechar Ruka Sarashina`")
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
        return await message.answer("❌ Couldn't find that character!")

    await message.answer_photo(
        photo=char["image"]["large"],
        caption=(
            f"🌸 **{char['name']['full']}** ({char['name'].get('native', '')})\n"
            f"💖 Favorites: `{char.get('favourites', 0)}`\n"
            f"🔗 [AniList Profile]({char['siteUrl']})"
        )
    )


# 3–8: Fun Meters (/simprate, /iq, /waifurate, /luck, /power, /love)
@router.message(Command("simprate"))
async def simp_rate(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"🥺 {target.full_name} is **{random.randint(0, 100)}%** simp!")


@router.message(Command("iq"))
async def iq_rate(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"🧠 {target.full_name}'s IQ is **{random.randint(40, 200)}**!")


@router.message(Command("waifurate"))
async def waifu_rate(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"🌸 {target.full_name} is **{random.randint(1, 100)}/100** waifu material!")


@router.message(Command("luck"))
async def luck_rate(message: Message):
    await message.answer(f"🍀 Your luck today is **{random.randint(1, 100)}%**!")


@router.message(Command("power"))
async def power_level(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"⚡ {target.full_name}'s Power Level is **{random.randint(1000, 99999)}**!")


@router.message(Command("love"))
async def love_calc(message: Message):
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.answer("Usage: `/love <name1> <name2>`")
    pct = random.randint(1, 100)
    await message.answer(f"💘 **{parts[1]}** + **{parts[2]}** = **{pct}%** Love!")


# 9–15: Text Stylers (/mock, /reverse, /spoiler, /vapor, /morse, /tiny, /count)
@router.message(Command("mock"))
async def mock_text(message: Message):
    text = _get_text(message)
    if not text:
        return await message.answer("Give me text or reply to a message!")
    await message.answer("".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text)))


@router.message(Command("reverse"))
async def reverse_text(message: Message):
    text = _get_text(message)
    if not text:
        return await message.answer("Give me text to reverse!")
    await message.answer(text[::-1])


@router.message(Command("spoiler"))
async def spoiler_text(message: Message):
    text = _get_text(message)
    if not text:
        return await message.answer("Give me text to hide as a spoiler!")
    await message.answer(f"||{text}||")


@router.message(Command("vapor"))
async def vapor_text(message: Message):
    text = _get_text(message)
    if not text:
        return await message.answer("Give me text!")
    await message.answer(" ".join(text))


@router.message(Command("morse"))
async def morse_text(message: Message):
    MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..", " ": "/"}
    text = _get_text(message)
    if not text:
        return await message.answer("Give me text to convert to Morse!")
    await message.answer(" ".join(MORSE.get(c.upper(), c) for c in text))


@router.message(Command("tiny"))
async def tiny_text(message: Message):
    text = _get_text(message)
    if not text:
        return await message.answer("Give me text!")
    normal = "abcdefghijklmnopqrstuvwxyz"
    small = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘqʀꜱᴛᴜᴠᴡxʏᴢ"
    trans = str.maketrans(normal, small)
    await message.answer(text.lower().translate(trans))


@router.message(Command("count"))
async def count_text(message: Message):
    text = _get_text(message)
    if not text:
        return await message.answer("Reply to a message to count its words & characters!")
    await message.answer(f"🔢 **Words:** `{len(text.split())}` | **Characters:** `{len(text)}`")


# 16–21: Group & Decision Utilities (/poll, /choose, /decide, /hugall, /toss, /insult)
@router.message(Command("poll"), F.chat.type.in_({"group", "supergroup"}))
async def create_poll(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        return await message.answer("Usage: `/poll Best girl? | Ruka | Chizuru | Sumi`")
    opts = [p.strip() for p in parts[1].split("|") if p.strip()]
    if len(opts) < 3:
        return await message.answer("Give a question and at least 2 options separated by `|`!")
    await message.bot.send_poll(message.chat.id, question=opts[0], options=opts[1:11])


@router.message(Command("choose"))
async def choose_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2 or "|" not in parts[1]:
        return await message.answer("Usage: `/choose Pizza | Ramen | Sushi`")
    opts = [p.strip() for p in parts[1].split("|") if p.strip()]
    await message.answer(f"💓 **Ruka chooses:** **{random.choice(opts)}**!")


@router.message(Command("decide"))
async def decide_cmd(message: Message):
    await message.answer(f"🤔 **Ruka's decision:** **{random.choice(['Yes! 💓', 'No! 💢', 'Maybe~ 🌸'])}**")


@router.message(Command("hugall"), F.chat.type.in_({"group", "supergroup"}))
async def hug_all(message: Message):
    await message.answer("🤗 *Ruka gives everyone in the group a giant warm hug!* 💓")


@router.message(Command("toss"))
async def toss_cmd(message: Message):
    await message.answer(f"🪙 **{random.choice(['Heads', 'Tails'])}**!")


@router.message(Command("insult"))
async def insult_cmd(message: Message):
    insults = [
        "You're like a cloud—when you disappear, it's a beautiful day!",
        "I'd agree with you, but then we'd both be wrong~",
        "Even a NPC has better dialogue than you, baka!",
    ]
    await message.answer(f"🔥 {random.choice(insults)}")


# 22–25: Live APIs (/fact, /joke, /cat, /dog)
@router.message(Command("fact"))
async def fact_cmd(message: Message):
    data = await _fetch_json("https://uselessfacts.jsph.pl/api/v2/facts/random")
    await message.answer(f"💡 **Fun Fact:**\n{data['text']}" if data and "text" in data else "❌ Couldn't fetch a fact!")


@router.message(Command("joke"))
async def joke_cmd(message: Message):
    data = await _fetch_json("https://official-joke-api.appspot.com/random_joke")
    if data and "setup" in data:
        await message.answer(f"😂 {data['setup']}\n\n||{data['punchline']}||")
    else:
        await message.answer("❌ Couldn't fetch a joke!")


@router.message(Command("cat"))
async def cat_cmd(message: Message):
    data = await _fetch_json("https://api.thecatapi.com/v1/images/search")
    if data and isinstance(data, list):
        await message.answer_photo(data[0]["url"], caption="🐱 Meow~")
    else:
        await message.answer("❌ Couldn't fetch a cat!")


@router.message(Command("dog"))
async def dog_cmd(message: Message):
    data = await _fetch_json("https://dog.ceo/api/breeds/image/random")
    if data and "message" in data:
        await message.answer_photo(data["message"], caption="🐶 Woof~")
    else:
        await message.answer("❌ Couldn't fetch a dog!")