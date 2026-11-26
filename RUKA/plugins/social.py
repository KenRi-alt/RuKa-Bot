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
    get_chat_settings, set_marriage, get_partner, remove_marriage,
    add_relation, get_family, add_gacha_card, get_user_cards
)
from RUKA.utils.image_gen import generate_4k_anime_card

router = Router()

# --- CONSTANTS ---
RUKA_PIC = "https://ganga--link--ghhzdp9sv8hk.code.run/i/s0s0y8txhk.jpg"
WAIFU_NAMES = ["Ruka Sarashina", "Chizuru Mizuhara", "Zero Two", "Rem", "Asuna", "Mikasa", "Nezuko", "Makima", "Marin", "Hinata"]
# In-memory for speed, but logic is ready for DB integration
USER_GENDER: dict[int, str] = {} # male/female
USER_BIO: dict[int, str] = {}
USER_RELATION: dict[tuple[int, int], str] = {} # (u1, u2) -> 'spouse' or 'child'

# --- HELPERS ---
async def fetch_bytes(url: str) -> BytesIO | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = BytesIO(await resp.read())
                    data.seek(0)
                    return data
    except: pass
    return None

def get_pronoun(gender: str):
    return {"male": "He", "female": "She"}.get(gender, "They")

# --- 1. MARRIAGE & FAMILY (The Soulmate System) ---

@router.message(Command("marry"))
async def marry_cmd(message: Message):
    if not message.reply_to_message: return await message.answer("💖 Reply to someone to propose!")
    target_id = message.reply_to_message.from_user.id
    if target_id == message.from_user.id: return await message.answer("❌ You can't marry yourself, baka!")

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💍 Accept", callback_data=f"m_acc_{target_id}_{message.from_user.id}"),
         InlineKeyboardButton(text="💔 Reject", callback_data=f"m_rej_{target_id}")]
    ])
    await message.answer(f"💍 **{message.from_user.mention}** is proposing to **{message.reply_to_message.from_user.mention}**! Will you accept?", reply_markup=btn)

@router.callback_query(F.data.startswith("m_"))
async def marriage_cb(query: CallbackQuery):
    data = query.data.split("_")
    if data[0] == "m_acc":
        target_id, proposer_id = int(data[1]), int(data[2])
        await set_marriage(proposer_id, target_id)
        await query.message.edit_text(f"💖 **Success!** {query.from_user.mention} and <a href='tg://user?id={proposer_id}'>Partner</a> are now bonded! 🌸", parse_mode="HTML")
    else:
        await query.answer("💔 Rejected!", show_alert=True)
        await query.message.edit_text("💔 The proposal was rejected. 😭")

@router.message(Command("partner"))
async def partner_cmd(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    pid = await get_partner(target.id)
    if not pid: return await message.answer(f"🔎 **{target.full_name}** is currently single.")
    await message.answer(f"💞 **{target.full_name}'s Soulmate:** <a href='tg://user?id={pid}'>Partner</a>", parse_mode="HTML")

@router.message(Command("adopt"))
async def adopt_cmd(message: Message):
    if not message.reply_to_message: return await message.answer("Reply to someone to adopt them!")
    await add_relation(message.from_user.id, message.reply_to_message.from_user.id, "child")
    await message.answer(f"🏠 **Adopted!** {message.reply_to_message.from_user.full_name} is now part of your family!")

@router.message(Command("disown"))
async def disown_cmd(message: Message):
    if not message.reply_to_message: return await message.answer("Reply to someone to disown them!")
    target_id = message.reply_to_message.from_user.id
    await remove_marriage(message.from_user.id) # Simplified for logic
    await message.answer(f"❌ You have disowned {message.reply_to_message.from_user.full_name}...")

@router.message(Command("family"))
async def family_cmd(message: Message):
    fam = await get_family(message.from_user.id)
    if not fam: return await message.answer("Your family is empty. Go adopt someone!")
    await message.answer("🏡 **Your Family Tree:**\n" + "\n".join([f"• {f['relation_type'].capitalize()}: `{f['relative_id']}`" for f in fam]))

# --- 2. GACHA & COLLECTION ---

@router.message(Command("gacha"))
async def gacha_cmd(message: Message):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.waifu.pics/sfw/waifu") as resp:
            data = await resp.json()
    
    card_id, name = random.randint(1000, 9999), random.choice(WAIFU_NAMES)
    rarity = random.choice(["R", "SR", "SSR"])
    power = random.randint(100, 5000)
    url = data["url"]
    
    await add_gacha_card(message.from_user.id, {"id": card_id, "name": name, "rarity": rarity, "power": power, "url": url})
    
    pfp = await fetch_bytes(url)
    img = await generate_4k_anime_card(f"#{card_id} {name}", f"{power} PWR", rarity, "COLLECTED", pfp)
    await message.answer_photo(photo=BufferedInputFile(img.getvalue(), filename="c.jpg"), caption=f"🎰 **Gacha Pull!**\n\n🆔 `#{card_id}` | **{name}**\n✨ **{rarity}** | ⚡ `{power}`")

@router.message(Command("collection"))
async def collection_cmd(message: Message):
    cards = await get_user_cards(message.from_user.id)
    if not cards: return await message.answer("📭 Your collection is empty!")
    await message.answer("🃏 **Your Collection:**\n" + "\n".join([f"• `#{c['card_id']}` **{c['card_name']}** ({c['rarity']})" for c in cards[:15]]))

# --- 3. PERSONALITY & IDENTITY ---

@router.message(Command("gender"))
async def set_gender(message: Message):
    if len(message.text.split()) < 2: return await message.answer("Usage: `/gender male` or `/gender female`")
    gender = message.text.split()[1].lower()
    if gender not in ["male", "female"]: return await message.answer("Use `male` or `female`!")
    USER_GENDER[message.from_user.id] = gender
    await message.answer(f"✅ Gender set to **{gender.capitalize()}**!")

@router.message(Command("bio"))
async def set_bio(message: Message):
    if len(message.text.split()) < 2: return await message.answer("Usage: `/bio <text>`")
    USER_BIO[message.from_user.id] = message.text.split(None, 1)[1]
    await message.answer("📝 Bio updated!")

@router.message(Command("mybio"))
async def get_bio(message: Message):
    bio = USER_BIO.get(message.from_user.id, "No bio set! Use `/bio`")
    await message.answer(f"👤 **{message.from_user.full_name}'s Bio:**\n\n{bio}")

# --- 4. SOCIAL REACTIONS ---

@router.message(Command("hug"))
async def hug_cmd(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"🤗 {message.from_user.mention} gives a warm hug to {t.mention}!")

@router.message(Command("kiss"))
async def kiss_cmd(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"💋 {message.from_user.mention} gives a sweet kiss to {t.mention}!")

@router.message(Command("slap"))
async def slap_cmd(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"💢 {message.from_user.mention} slapped {t.mention}!")

@router.message(Command("lovecalc"))
async def love_cmd(message: Message):
    if not message.reply_to_message: return await message.answer("Reply to someone!")
    await message.answer(f"💘 **Love Match:** {message.from_user.mention} ❤️ {message.reply_to_message.from_user.mention} = **{random.randint(1, 100)}%**")