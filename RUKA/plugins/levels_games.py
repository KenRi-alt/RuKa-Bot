import html
import time
import random
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ..utils.chat_action import chatAction
from ..utils.image_gen import generate_4k_profile

# In-memory stores
USER_XP: dict[tuple[int, int], int] = {}
USER_COINS: dict[int, int] = {}
DAILY_CD: dict[int, float] = {}
ROB_CD: dict[int, float] = {}
ACTIVE_BOSS: dict[int, dict] = {}
LIVE_TRIVIA: dict[str, tuple[list[str], int]] = {}

RANKS = [
    (0, "🌱 Newbie"),
    (100, "🥷 Genin"),
    (300, "⚔️ Chunin"),
    (600, "🔥 Jonin"),
    (1000, "🌸 Hashira"),
    (1500, "👑 Hokage"),
    (2500, "💓 Ruka's Favorite"),
]

FALLBACK_TRIVIA = [
    ("In 'Rent-a-Girlfriend', what is Ruka Sarashina's signature accessory?", ["Ribbon", "Glasses", "Hat", "Scarf"], 0),
    ("Who is the main protagonist of 'Naruto'?", ["Sasuke", "Naruto", "Kakashi", "Itachi"], 1),
    ("What is Luffy's dream in 'One Piece'?", ["Hokage", "Pirate King", "Soul Reaper", "Hero"], 1),
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


# --- Auto XP Listener ---
@Client.on_message(filters.group & filters.text & ~filters.command(["start", "help"]), group=1)
async def xp_listener(client, message):
    if not message.from_user or message.from_user.is_bot:
        return
    uid = message.from_user.id
    key = (message.chat.id, uid)
    old_xp = USER_XP.get(key, 0)
    new_xp = old_xp + random.randint(5, 12)
    USER_XP[key] = new_xp
    USER_COINS[uid] = USER_COINS.get(uid, 100) + random.randint(1, 3)

    old_rank, _ = get_rank(old_xp)
    new_rank, _ = get_rank(new_xp)
    if new_rank != old_rank:
        await message.reply_text(
            f"🎉 **LEVEL UP!**\n💓 {message.from_user.mention} reached **{new_rank}**! Ruka is so proud of you~"
        )


# --- 1. /rank & /level (4K Pillow Profile Card) ---
@Client.on_message(filters.command(["rank", "level"]) & filters.group)
@chatAction("upload_photo")
async def rank_cmd(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    xp = USER_XP.get((message.chat.id, target.id), 0)
    coins = USER_COINS.get(target.id, 100)
    rank_name, progress = get_rank(xp)

    pfp_bytes = None
    if target.photo:
        pfp_bytes = await client.download_media(target.photo.big_file_id, in_memory=True)

    img = generate_4k_profile(target.first_name, target.id, rank=rank_name, xp=progress, pfp_bytes=pfp_bytes)
    await message.reply_photo(
        photo=img,
        caption=f"📊 **{target.mention}'s Stats**\n🏆 Rank: **{rank_name}**\n✨ XP: `{xp}` | 💎 Coins: `{coins}`"
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


# --- 3–7: Economy (/daily, /bal, /give, /rob, /bet) ---
@Client.on_message(filters.command("daily"))
async def daily_cmd(client, message):
    uid = message.from_user.id
    now = time.time()
    if now - DAILY_CD.get(uid, 0) < 86400:
        rem = int(86400 - (now - DAILY_CD[uid])) // 3600
        return await message.reply_text(f"⏳ Already claimed! Come back in `{rem}h`~")
    DAILY_CD[uid] = now
    reward = random.randint(150, 350)
    USER_COINS[uid] = USER_COINS.get(uid, 100) + reward
    await message.reply_text(f"🎁 **Daily Reward!**\nRuka gave you **`{reward}` 💎 Coins**!")


@Client.on_message(filters.command(["bal", "balance"]))
async def balance_cmd(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    coins = USER_COINS.get(target.id, 100)
    await message.reply_text(f"💎 {target.mention} has **`{coins}` Ruka Coins**!")


@Client.on_message(filters.command("give"))
async def give_coins(client, message):
    if not message.reply_to_message or len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("Reply to a user with `/give <amount>`!")
    amt = int(message.command[1])
    uid = message.from_user.id
    tid = message.reply_to_message.from_user.id
    if amt <= 0 or USER_COINS.get(uid, 100) < amt:
        return await message.reply_text("❌ Not enough 💎 Coins!")
    USER_COINS[uid] -= amt
    USER_COINS[tid] = USER_COINS.get(tid, 100) + amt
    await message.reply_text(f"💸 Sent **`{amt}` 💎** to {message.reply_to_message.from_user.mention}!")


@Client.on_message(filters.command("rob") & filters.group)
async def rob_cmd(client, message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id:
        return await message.reply_text("Reply to someone to rob them! 🥷")
    uid = message.from_user.id
    tid = message.reply_to_message.from_user.id
    if time.time() - ROB_CD.get(uid, 0) < 300:
        return await message.reply_text("⏳ Lay low for 5 minutes before robbing again!")
    ROB_CD[uid] = time.time()
    if random.random() < 0.45 and USER_COINS.get(tid, 100) > 20:
        stolen = random.randint(15, min(80, USER_COINS.get(tid, 100)))
        USER_COINS[tid] -= stolen
        USER_COINS[uid] = USER_COINS.get(uid, 100) + stolen
        await message.reply_text(f"🥷 **Success!** You stole **`{stolen}` 💎** from {message.reply_to_message.from_user.mention}!")
    else:
        fine = 25
        USER_COINS[uid] = max(0, USER_COINS.get(uid, 100) - fine)
        await message.reply_text(f"🚔 **Caught!** Ruka fined you **`{fine}` 💎**!")


@Client.on_message(filters.command("bet"))
async def bet_cmd(client, message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("Usage: `/bet <amount>`")
    amt = int(message.command[1])
    uid = message.from_user.id
    if amt <= 0 or USER_COINS.get(uid, 100) < amt:
        return await message.reply_text("❌ Not enough 💎 Coins!")
    if random.random() < 0.5:
        USER_COINS[uid] += amt
        await message.reply_text(f"🎉 **You WON `{amt}` 💎!** Total: `{USER_COINS[uid]}`")
    else:
        USER_COINS[uid] -= amt
        await message.reply_text(f"😭 **You LOST `{amt}` 💎!** Total: `{USER_COINS[uid]}`")


# --- 8. /boss — Group Anime Boss Raid! ---
@Client.on_message(filters.command("boss") & filters.group)
async def spawn_boss(client, message):
    cid = message.chat.id
    boss_name = random.choice(["Colossal Titan", "Demon King Muzan", "Madara Uchiha", "Sukuna"])
    ACTIVE_BOSS[cid] = {"name": boss_name, "hp": 500, "max": 500}
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Attack Boss!", callback_data="boss_atk")]])
    await message.reply_text(
        f"👹 **A WILD {boss_name.upper()} APPEARED!**\n"
        f"❤️❤️❤️❤️❤️ `500 / 500 HP`\n\nEveryone tap **Attack** to defeat it for **💎 Coins & XP**!",
        reply_markup=btn
    )


# --- 9. /rps ---
@Client.on_message(filters.command("rps"))
async def rps_cmd(client, message):
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("🪨 Rock", callback_data="rps_rock"),
        InlineKeyboardButton("📄 Paper", callback_data="rps_paper"),
        InlineKeyboardButton("✂️ Scissors", callback_data="rps_scissors"),
    ]])
    await message.reply_text("🎮 **Rock, Paper, Scissors!** Pick your move against Ruka~", reply_markup=buttons)


# --- 10. /trivia (Live Anime Trivia API + Fallback) ---
@Client.on_message(filters.command("trivia"))
async def trivia_cmd(client, message):
    q, opts, correct = None, None, 0
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://opentdb.com/api.php?amount=1&category=31&type=multiple", timeout=8) as resp:
                data = await resp.json()
                if data.get("results"):
                    item = data["results"][0]
                    q = html.unescape(item["question"])
                    ans = html.unescape(item["correct_answer"])
                    opts = [html.unescape(x) for x in item["incorrect_answers"]] + [ans]
                    random.shuffle(opts)
                    correct = opts.index(ans)
    except Exception:
        pass

    if not q:
        q, opts, correct = random.choice(FALLBACK_TRIVIA)

    tid = str(random.randint(10000, 99999))
    LIVE_TRIVIA[tid] = (opts, correct)
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"triv_{tid}_{i}")] for i, opt in enumerate(opts)])
    await message.reply_text(f"🧠 **Ruka's Anime Trivia!**\n\n{q}", reply_markup=buttons)


# --- 11–16: /guess, /duel, /slot, /dart, /basket, /bowl ---
@Client.on_message(filters.command("guess"))
async def guess_cmd(client, message):
    secret = random.randint(1, 5)
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton(str(n), callback_data=f"guess_{secret}_{n}") for n in range(1, 6)]])
    await message.reply_text("🔢 **Guess the Number!** I'm thinking of **1 to 5**~", reply_markup=buttons)


@Client.on_message(filters.command("duel") & filters.group)
async def duel_cmd(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text("⚔️ Reply to someone to challenge them to an **Anime Duel**!")
    p1, p2 = message.from_user, message.reply_to_message.from_user
    if p1.id == p2.id:
        return await message.reply_text("Eh?! You can't duel yourself, baka!")
    winner = random.choice([p1, p2])
    USER_COINS[winner.id] = USER_COINS.get(winner.id, 100) + 50
    moves = ["Rasengan", "Kamehameha", "Ruka's Heartbeat Slash", "Domain Expansion", "Detroit Smash"]
    await message.reply_text(f"⚔️ **ANIME DUEL!**\n{p1.mention} 🆚 {p2.mention}\n\n💥 {winner.mention} used **{random.choice(moves)}** and WON **50 💎**! 🏆")


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


# --- Callback Handler ---
@Client.on_callback_query(filters.regex(r"^(rps_|triv_|guess_|boss_atk)"))
async def game_callbacks(client, query):
    data = query.data

    if data == "boss_atk":
        cid = query.message.chat.id
        boss = ACTIVE_BOSS.get(cid)
        if not boss:
            return await query.answer("The boss is already defeated!", show_alert=True)
        dmg = random.randint(35, 95)
        boss["hp"] = max(0, boss["hp"] - dmg)
        uid = query.from_user.id
        USER_COINS[uid] = USER_COINS.get(uid, 100) + 15
        USER_XP[(cid, uid)] = USER_XP.get((cid, uid), 0) + 10

        if boss["hp"] == 0:
            ACTIVE_BOSS.pop(cid, None)
            USER_COINS[uid] += 150
            return await query.message.edit_text(
                f"🏆 **{boss['name']} DEFEATED!**\n"
                f"💥 {query.from_user.mention} landed the final blow (`{dmg} DMG`) and won **150 💎**!"
            )
        hearts = "❤️" * max(1, (boss["hp"] * 5) // boss["max"]) + "🖤" * (5 - max(1, (boss["hp"] * 5) // boss["max"]))
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Attack Boss!", callback_data="boss_atk")]])
        await query.message.edit_text(
            f"👹 **{boss['name']}**\n{hearts} `{boss['hp']} / {boss['max']} HP`\n\n💥 {query.from_user.first_name} dealt `{dmg}` DMG!",
            reply_markup=btn
        )
        await query.answer(f"💥 Dealt {dmg} DMG! (+15 💎)")

    elif data.startswith("rps_"):
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
        _, tid, ans_idx = data.split("_")
        if tid not in LIVE_TRIVIA:
            return await query.answer("Trivia expired!", show_alert=True)
        opts, correct = LIVE_TRIVIA.pop(tid)
        if int(ans_idx) == correct:
            USER_COINS[query.from_user.id] = USER_COINS.get(query.from_user.id, 100) + 30
            await query.message.edit_text(f"✅ **Correct!** **{opts[correct]}** (+30 💎) 💓")
        else:
            await query.message.edit_text(f"❌ **Wrong, baka!** The answer was **{opts[correct]}**!")

    elif data.startswith("guess_"):
        _, secret, pick = data.split("_")
        if secret == pick:
            await query.message.edit_text(f"🎉 **Spot on!** It was **{secret}**! You're a mind reader~")
        else:
            await query.message.edit_text(f"😅 Nope! I was thinking of **{secret}**, not {pick}!")