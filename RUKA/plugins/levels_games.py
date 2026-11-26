import random
import time
import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA.utils.image_gen import generate_4k_profile
from RUKA.utils.db import get_user_stats, update_user_stats # Assuming these exist in your db.py

router = Router()

# --- CONFIG & DATA ---
# In a production environment, these would be in a DB. 
# For now, we use these to define the "meta" of the game.
SHOP_ITEMS = {
    "katana": {"name": "🥷 Katana", "price": 5000, "img": "https://i.imgur.com/pI6pYpX.png", "desc": "Boosts Duel win chance!"},
    "waifu_card": {"name": "🌸 Anime Waifu", "price": 2500, "img": "https://i.imgur.com/YourWaifuImg.png", "desc": "A beautiful companion."},
    "gold_ring": {"name": "💍 Gold Ring", "price": 1000, "img": "https://i.imgur.com/GoldRing.png", "desc": "Increases Daily reward!"},
    "armor": {"name": "🛡️ Heavy Armor", "price": 3000, "img": "https://i.imgur.com/Armor.png", "desc": "Protects you from being robbed!"}
}

RANKS = [
    (0, "🌱 Newbie"), (100, "🥷 Genin"), (300, "⚔️ Chunin"), 
    (600, "🔥 Jonin"), (1000, "🌸 Hashira"), (2000, "👑 Hokage")
]

# --- HELPERS ---
async def get_stats(uid: int):
    stats = await get_user_stats(uid)
    return stats # {'coins': 100, 'xp': 0}

def get_rank_info(xp: int):
    current_rank = RANKS[0][1]
    next_xp = RANKS[1][0]
    for i, (req, name) in enumerate(RANKS):
        if xp >= req:
            current_rank = name
            next_xp = RANKS[i+1][0] if i+1 < len(RANKS) else req + 500
    return current_rank, int((xp / next_xp) * 100)

# --- 1. LEVELING & RANKING ---

@router.message(Command("rank", "level"), F.chat.type.in_({"group", "supergroup"}))
async def rank_cmd(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    stats = await get_user_stats(target.id)
    rank, progress = get_rank_info(stats['xp'])
    
    # 4K Profile Card (Fast Rendering)
    from io import BytesIO
    pfp = None
    try:
        photos = await message.bot.get_user_profile_photos(target.id, limit=1)
        if photos.total_count > 0:
            file = await message.bot.get_file(photos.photos[0][-1].file_id)
            pfp = BytesIO(); await message.bot.download_file(file.file_path, pfp); pfp.seek(0)
    except: pass

    img = generate_4k_profile(target.first_name, target.id, rank=rank, xp=progress, pfp_bytes=pfp)
    from aiogram.types import BufferedInputFile
    await message.answer_photo(
        photo=BufferedInputFile(img.getvalue(), filename="rank.jpg"),
        caption=f"📊 **{target.full_name}**\n🏆 Rank: `{rank}`\n✨ XP: `{stats['xp']}` | 💎 Coins: `{stats['coins']}`"
    )

# --- 2. ECONOMY & SHOP ---

@router.message(Command("daily"))
async def daily_cmd(message: Message):
    # In production, use a DB timestamp check here
    reward = 250
    await update_user_stats(message.from_user.id, coins=reward)
    await message.answer(f"🎁 **Daily Reward!** Ruka gave you **`{reward} 💎`**!")

@router.message(Command("bal", "balance"))
async def balance_cmd(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    stats = await get_user_stats(target.id)
    await message.answer(f"💎 **{target.full_name}**\n💰 Wallet: `{stats['coins']} 💎`\n✨ XP: `{stats['xp']}`")

@router.message(Command("shop"))
async def shop_cmd(message: Message):
    buttons = []
    for key, item in SHOP_ITEMS.items():
        buttons.append([InlineKeyboardButton(text=f"{item['name']} - {item['price']} 💎", callback_data=f"buy_{key}")])
    
    await message.answer("🛒 **Ruka's Premium Shop**\n\nUpgrade your power and style!", 
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("buy_"))
async def buy_callback(query: CallbackQuery):
    item_key = query.data.split("_")[1]
    item = SHOP_ITEMS[item_key]
    user_id = query.from_user.id
    stats = await get_user_stats(user_id)

    if stats['coins'] < item['price']:
        return await query.answer("❌ Not enough 💎 Coins!", show_alert=True)

    await update_user_stats(user_id, coins=-item['price'])
    # Logic to add item to user inventory would go here
    await query.answer(f"✅ Purchased {item['name']}!", show_alert=True)
    await query.message.edit_caption(caption=f"🛍️ **Purchase Successful!**\n\nYou bought: **{item['name']}**")

@router.message(Command("bet"))
async def bet_cmd(message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Usage: `/bet <amount>`")
    
    amt = int(parts[1])
    stats = await get_user_stats(message.from_user.id)
    if amt <= 0 or stats['coins'] < amt:
        return await message.answer("❌ Insufficient coins!")

    if random.random() < 0.45: # 45% Win Rate
        await update_user_stats(message.from_user.id, coins=amt * 2)
        await message.answer(f"🎉 **WIN!** You doubled your bet! Now you have `{stats['coins'] + amt}` 💎")
    else:
        await update_user_stats(message.from_user.id, coins=-amt)
        await message.answer(f"😭 **LOSS!** You lost `{amt}` 💎. Better luck next time!")

# --- 3. GAMES & BOSSES ---

@router.message(Command("boss"), F.chat.type.in_({"group", "supergroup"}))
async def boss_raid(message: Message):
    cid = message.chat.id
    boss_name = random.choice(["Madara", "Sukuna", "Frieza"])
    hp = 1000
    
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚔️ ATTACK BOSS!", callback_data=f"atk_{cid}_{boss_name}")]])
    await message.answer(f"👹 **BOSS RAID STARTED!**\n\n**{boss_name}** has entered the group!\n❤️ HP: `{hp}/1000`", reply_markup=btn)

@router.callback_query(F.data.startswith("atk_"))
async def attack_boss(query: CallbackQuery):
    # logic to reduce HP and reward coins/xp
    await query.answer("💥 *Attack!*", show_alert=False)
    # (In production, track HP in DB)
    await query.message.edit_text("💥 **Attack!**\nBoss HP: `950/1000`\n✨ +10 XP & +5 Coins!")

@router.message(Command("duel"), F.chat.type.in_({"group", "supergroup"}))
async def duel_cmd(message: Message):
    if not message.reply_to_message: return await message.answer("Reply to a user to duel them!")
    p1, p2 = message.from_user, message.reply_to_message.from_user
    
    await message.answer(f"⚔️ **DUEL INITIATED!**\n{p1.mention} 🆚 {p2.mention}")
    await asyncio.sleep(2)
    
    winner = random.choice([p1, p2])
    await message.answer(f"🏆 **{winner.mention} wins the duel!** ⚔️")