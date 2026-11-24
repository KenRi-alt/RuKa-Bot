import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..utils import chatAction
from ..utils.image_gen import generate_4k_profile

# In-memory XP store (fast & zero-setup; can be synced to PostgreSQL anytime)
USER_XP: dict[tuple[int, int], int] = {}

RANKS = [
    (0, "🌱 Newbie"),
    (100, "🥷 Genin"),
    (300, "⚔️ Chunin"),
    (600, "🔥 Jonin"),
    (1000, "🌸 Hashira"),
    (1500, "👑 Hokage"),
    (2500, "💓 Ruka's Favorite"),
]


def get_rank(xp: int) -> tuple[str, int]:
    current_rank = RANKS[0][1]
    next_xp = RANKS[1][0]
    for i, (req, name) in enumerate(RANKS):
        if xp >= req:
            current_rank = name
            next_xp = RANKS[i + 1][0] if i + 1 < len(RANKS) else req + 500
    progress = int((xp / next_xp) * 100) if next_xp > 0 else 100
    return current_rank, min(progress, 100)


# --- Auto XP Listener (group=1 so it never blocks commands) ---
@Client.on_message(filters.group & filters.text & ~filters.command(["start", "help"]), group=1)
async def xp_listener(client, message):
    if not message.from_user or message.from_user.is_bot:
        return
    key = (message.chat.id, message.from_user.id)
    old_xp = USER_XP.get(key, 0)
    new_xp = old_xp + random.randint(5, 12)
    USER_XP[key] = new_xp

    old_rank, _ = get_rank(old_xp)
    new_rank, _ = get_rank(new_xp)
    if new_rank != old_rank:
        await message.reply_text(
            f"🎉 **LEVEL UP!**\n"
            f"💓 {message.from_user.mention} just reached **{new_rank}**! Ruka is so proud of you~"
        )


# --- 1. /rank & /level (4K Pillow Profile Card) ---
@Client.on_message(filters.command(["rank", "level"]) & filters.group)
@chatAction("upload_photo")
async def rank_cmd(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    xp = USER_XP.get((message.chat.id, target.id), 0)
    rank_name, progress = get_rank(xp)

    pfp_bytes = None
    if target.photo:
        pfp_bytes = await client.download_media(target.photo.big_file_id, in_memory=True)

    img = generate_4k_profile(target.first_name, target.id, rank=rank_name, xp=progress, pfp_bytes=pfp_bytes)
    await message.reply_photo(
        photo=img,
        caption=f"📊 **{target.mention}'s Stats**\n🏆 Rank: **{rank_name}**\n✨ Total XP: `{xp}`"
    )


# --- 2. /leaderboard & /lb ---
@Client.on_message(filters.command(["leaderboard", "lb"]) & filters.group)
async def leaderboard_cmd(client, message):
    chat_scores = [(uid, xp) for (cid, uid), xp in USER_XP.items() if cid == message.chat.id]
    if not chat_scores:
        return await message.reply_text("Nobody has earned XP yet! Start chatting~")

    chat_scores.sort(key=lambda x: x[1], reverse=True)
    text = f"🏆 **{message.chat.title} — Top Members**\n\n"
    for i, (uid, xp) in enumerate(chat_scores[:10], 1):
        rank_name, _ = get_rank(xp)
        text += f"**{i}.** User `{uid}` — `{xp} XP` ({rank_name})\n"
    await message.reply_text(text)


# --- 3. /rps (Rock Paper Scissors with Inline Buttons) ---
@Client.on_message(filters.command("rps"))
async def rps_cmd(client, message):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🪨 Rock", callback_data="rps_rock"),
            InlineKeyboardButton("📄 Paper", callback_data="rps_paper"),
            InlineKeyboardButton("✂️ Scissors", callback_data="rps_scissors"),
        ]
    ])
    await message.reply_text("🎮 **Rock, Paper, Scissors!**\nCome on, pick your move against Ruka~", reply_markup=buttons)


# --- 4. /trivia (Anime Trivia with Inline Buttons) ---
TRIVIA_QS = [
    ("In 'Rent-a-Girlfriend', what is Ruka Sarashina's signature accessory?", ["Ribbon", "Glasses", "Hat", "Scarf"], 0),
    ("Who is the main protagonist of 'Naruto'?", ["Sasuke", "Naruto", "Kakashi", "Itachi"], 1),
    ("What is Luffy's dream in 'One Piece'?", ["Hokage", "Pirate King", "Soul Reaper", "Hero"], 1),
]

@Client.on_message(filters.command("trivia"))
async def trivia_cmd(client, message):
    idx = random.randrange(len(TRIVIA_QS))
    q, opts, _ = TRIVIA_QS[idx]
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=f"triv_{idx}_{i}")] for i, opt in enumerate(opts)
    ])
    await message.reply_text(f"🧠 **Ruka's Anime Trivia!**\n\n{q}", reply_markup=buttons)


# --- 5. /guess (Number Guessing 1–5) ---
@Client.on_message(filters.command("guess"))
async def guess_cmd(client, message):
    secret = random.randint(1, 5)
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(str(n), callback_data=f"guess_{secret}_{n}") for n in range(1, 6)]
    ])
    await message.reply_text("🔢 **Guess the Number!**\nI'm thinking of a number between **1 and 5**~", reply_markup=buttons)


# --- 6. /duel (Anime Battle!) ---
@Client.on_message(filters.command("duel") & filters.group)
async def duel_cmd(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text("⚔️ Reply to someone to challenge them to an **Anime Duel**!")
    p1 = message.from_user
    p2 = message.reply_to_message.from_user
    if p1.id == p2.id:
        return await message.reply_text("Eh?! You can't duel yourself, baka!")
    winner = random.choice([p1, p2])
    moves = ["Rasengan", "Kamehameha", "Ruka's Heartbeat Slash", "Domain Expansion", "Detroit Smash"]
    await message.reply_text(
        f"⚔️ **ANIME DUEL!**\n{p1.mention} 🆚 {p2.mention}\n\n"
        f"💥 {winner.mention} used **{random.choice(moves)}** and WON! 🏆"
    )


# --- 7–10: Telegram Mini-Games (/slot, /dart, /basket, /bowl) ---
@Client.on_message(filters.command("slot"))
async def slot_cmd(client, message):
    await client.send_dice(message.chat.id, emoji="🎰")

@Client.on_message(filters.command("dart"))
async def dart_cmd(client, message):
    await client.send_dice(message.chat.id, emoji="🎯")

@Client.on_message(filters.command("basket"))
async def basket_cmd(client, message):
    await client.send_dice(message.chat.id, emoji="🏀")

@Client.on_message(filters.command("bowl"))
async def bowl_cmd(client, message):
    await client.send_dice(message.chat.id, emoji="🎳")


# --- Callback Handler for Games ---
@Client.on_callback_query(filters.regex(r"^(rps_|triv_|guess_)"))
async def game_callbacks(client, query):
    data = query.data

    if data.startswith("rps_"):
        user_pick = data.split("_")[1]
        bot_pick = random.choice(["rock", "paper", "scissors"])
        if user_pick == bot_pick:
            res = "🤝 **It's a tie!**"
        elif (user_pick, bot_pick) in [("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")]:
            res = "🎉 **You win!** Hmph, I'll beat you next time!"
        else:
            res = "💓 **Ruka wins!** Yay~"
        await query.message.edit_text(f"You chose **{user_pick}** | Ruka chose **{bot_pick}**\n\n{res}")

    elif data.startswith("triv_"):
        _, q_idx, ans_idx = data.split("_")
        _, opts, correct = TRIVIA_QS[int(q_idx)]
        if int(ans_idx) == correct:
            await query.message.edit_text(f"✅ **Correct!** The answer is **{opts[correct]}**! 💓")
        else:
            await query.message.edit_text(f"❌ **Wrong, baka!** The correct answer was **{opts[correct]}**!")

    elif data.startswith("guess_"):
        _, secret, pick = data.split("_")
        if secret == pick:
            await query.message.edit_text(f"🎉 **Spot on!** It was **{secret}**! You're a mind reader~")
        else:
            await query.message.edit_text(f"😅 Nope! I was thinking of **{secret}**, not {pick}!")