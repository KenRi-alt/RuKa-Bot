from aiogram.dispatcher.event.bases import SkipHandler
import html, time, random, asyncio, aiohttp
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from RUKA.utils.image_gen import generate_4k_profile, generate_shop_banner
from RUKA.utils.db import get_pool, get_user_stats, update_user_stats, add_inventory_item, get_inventory, get_user_cards

router = Router()
RUKA_PIC = "https://ganga--link--ghhzdp9sv8hk.code.run/i/s0s0y8txhk.jpg"
RUKA_CACHE: bytes | None = None
ROB_CD, ACTIVE_BOSS, LIVE_TRIVIA = {}, {}, {}

SHOP_ITEMS = {
    "katana": {"name": "🥷 Katana Blade", "price": 5000, "desc": "+20% Duel win rate"},
    "armor": {"name": "🛡️ Heavy Armor", "price": 3000, "desc": "Blocks /rob attempts"},
    "clover": {"name": "🍀 Lucky Clover", "price": 2000, "desc": "Boosts Gacha SSR odds"},
    "gold_ring": {"name": "💍 Gold Ring", "price": 1500, "desc": "+100 Bonus Daily Coins"},
    "energy": {"name": "⚡ Energy Drink", "price": 800, "desc": "+150 Instant XP"},
}
RANKS = [(0, "Newbie"), (100, "Genin"), (300, "Chunin"), (600, "Jonin"), (1000, "Hashira"), (2000, "Hokage"), (3500, "Ruka's Favorite")]
FALLBACK_TRIVIA = [
    ("In 'Rent-a-Girlfriend', what is Ruka Sarashina's signature accessory?", ["Ribbon", "Glasses", "Hat", "Scarf"], 0),
    ("Who is the main protagonist of 'Naruto'?", ["Sasuke", "Naruto", "Kakashi", "Itachi"], 1),
]


def get_rank(xp: int) -> str:
    r = RANKS[0][1]
    for req, name in RANKS:
        if xp >= req:
            r = name
    return r


async def _ruka_bytes() -> BytesIO | None:
    global RUKA_CACHE
    if RUKA_CACHE:
        return BytesIO(RUKA_CACHE)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(RUKA_PIC, timeout=10) as r:
                if r.status == 200:
                    RUKA_CACHE = await r.read()
                    return BytesIO(RUKA_CACHE)
    except Exception:
        pass
    return None


@router.message(Command("rank", "level", prefix="/!"))
async def rank_cmd(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    s, cards = await get_user_stats(t.id), await get_user_cards(t.id)
    rk = get_rank(s["xp"])
    pfp = None
    try:
        ph = await message.bot.get_user_profile_photos(t.id, limit=1)
        if ph.total_count > 0:
            f = await message.bot.get_file(ph.photos[0][-1].file_id)
            pfp = BytesIO(); await message.bot.download_file(f.file_path, pfp); pfp.seek(0)
    except Exception:
        pass
    img = generate_4k_profile(t.first_name, t.id, rank=rk, xp=s["xp"], coins=s["coins"], cards=len(cards), pfp_bytes=pfp)
    await message.answer_photo(BufferedInputFile(img.getvalue(), filename="rank.jpg"),
                               caption=f"📊 {t.full_name}\n🏆 {rk} | ✨ {s['xp']} XP | 💎 {s['coins']} Coins", parse_mode=None)


@router.message(Command("leaderboard", "lb", prefix="/!"))
async def leaderboard_cmd(message: Message):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, xp, coins FROM user_stats ORDER BY xp DESC LIMIT 10")
    if not rows:
        return await message.answer("No stats yet! Start chatting~")
    lines = ["🏆 **Global XP Leaderboard**\n"]
    for i, r in enumerate(rows, 1):
        lines.append(f"**{i}.** `{r['user_id']}` — `{r['xp']} XP` ({get_rank(r['xp'])}) | `{r['coins']} 💎`")
    await message.answer("\n".join(lines))


@router.message(Command("daily", prefix="/!"))
async def daily_cmd(message: Message):
    uid, now = message.from_user.id, time.time()
    s, inv = await get_user_stats(uid), await get_inventory(uid)
    diff = now - float(s.get("last_daily") or 0)
    if diff < 86400:
        rem = int(86400 - diff)
        h, m = divmod(rem // 60, 60)
        return await message.answer(f"⏳ Already claimed! Come back in **{h}h {m}m**~")
    bonus = 100 if inv.get("gold_ring", 0) > 0 else 0
    reward = random.randint(200, 350) + bonus
    await update_user_stats(uid, coins=reward, xp=25, daily_ts=now)
    await message.answer(f"🎁 **Daily Claimed!**\n💎 `+{reward} Coins`" + (" *(💍 +100 Ring Bonus!)*" if bonus else "") + "\n✨ `+25 XP`")


@router.message(Command("bal", "balance", prefix="/!"))
async def balance_cmd(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    s = await get_user_stats(t.id)
    await message.answer(f"💰 {t.full_name}\n💎 Coins: `{s['coins']}` | ✨ XP: `{s['xp']}` ({get_rank(s['xp'])})", parse_mode=None)


@router.message(Command("give", prefix="/!"))
async def give_coins(message: Message):
    p = message.text.split()
    if not message.reply_to_message or len(p) < 2 or not p[1].isdigit():
        return await message.answer("Reply to a user with `/give <amount>`!")
    amt, uid, tid = int(p[1]), message.from_user.id, message.reply_to_message.from_user.id
    s = await get_user_stats(uid)
    if amt <= 0 or s["coins"] < amt:
        return await message.answer("❌ Not enough 💎 Coins!")
    await update_user_stats(uid, coins=-amt); await update_user_stats(tid, coins=amt)
    await message.answer(f"💸 Sent `{amt} 💎` to {message.reply_to_message.from_user.full_name}!", parse_mode=None)


@router.message(Command("rob", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def rob_cmd(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id:
        return await message.answer("Reply to someone to rob them! 🥷")
    uid, tid = message.from_user.id, message.reply_to_message.from_user.id
    if time.time() - ROB_CD.get(uid, 0) < 300:
        return await message.answer("⏳ Wait 5 minutes before robbing again!")
    ROB_CD[uid] = time.time()
    t_inv = await get_inventory(tid)
    if t_inv.get("armor", 0) > 0:
        await update_user_stats(uid, coins=-30)
        return await message.answer("🛡️ **BLOCKED!** Their Heavy Armor stopped you! Ruka fined you `30 💎`!")
    ts = await get_user_stats(tid)
    if random.random() < 0.45 and ts["coins"] > 25:
        st = random.randint(20, min(120, ts["coins"]))
        await update_user_stats(tid, coins=-st); await update_user_stats(uid, coins=st)
        await message.answer(f"🥷 Stole `{st} 💎` from {message.reply_to_message.from_user.full_name}!", parse_mode=None)
    else:
        await update_user_stats(uid, coins=-25)
        await message.answer("🚔 **Caught!** Ruka fined you `25 💎`!")


@router.message(Command("bet", prefix="/!"))
async def bet_cmd(message: Message):
    p = message.text.split()
    if len(p) < 2 or not p[1].isdigit():
        return await message.answer("Usage: `/bet <amount>`")
    amt, uid = int(p[1]), message.from_user.id
    s = await get_user_stats(uid)
    if amt <= 0 or s["coins"] < amt:
        return await message.answer("❌ Insufficient 💎 Coins!")
    if random.random() < 0.48:
        await update_user_stats(uid, coins=amt)
        await message.answer(f"🎉 **WON `{amt}` 💎!** Balance: `{s['coins'] + amt}`")
    else:
        await update_user_stats(uid, coins=-amt)
        await message.answer(f"😭 **LOST `{amt}` 💎!** Balance: `{s['coins'] - amt}`")


@router.message(Command("slot", prefix="/!"))
async def slot_cmd(message: Message):
    p = message.text.split()
    amt = int(p[1]) if len(p) > 1 and p[1].isdigit() else 50
    uid = message.from_user.id
    s = await get_user_stats(uid)
    if amt <= 0 or s["coins"] < amt:
        return await message.answer("❌ Not enough 💎 Coins! Usage: `/slot <amount>`")
    dice = await message.answer_dice(emoji="🎰")
    await asyncio.sleep(2.2)
    if dice.dice.value in (1, 22, 43, 64):
        win = amt * 4
        await update_user_stats(uid, coins=win)
        await message.answer(f"🎰 **JACKPOT! +{win} 💎!**")
    elif dice.dice.value % 4 == 0:
        await update_user_stats(uid, coins=amt)
        await message.answer(f"✨ **Nice Spin! +{amt} 💎!**")
    else:
        await update_user_stats(uid, coins=-amt)
        await message.answer(f"💨 **No luck! -{amt} 💎**")


@router.message(Command("shop", prefix="/!"))
async def shop_cmd(message: Message):
    s = await get_user_stats(message.from_user.id)
    img = generate_shop_banner(message.from_user.first_name, s["coins"], await _ruka_bytes())
    btns = [[InlineKeyboardButton(text=f"{v['name']} — {v['price']} 💎", callback_data=f"buy_{k}")] for k, v in SHOP_ITEMS.items()]
    await message.answer_photo(
        BufferedInputFile(img.getvalue(), filename="shop.jpg"),
        caption="🛒 **Ruka's Shop** — Tap an item to buy it!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
    )


@router.message(Command("inv", "inventory", prefix="/!"))
async def inv_cmd(message: Message):
    inv = await get_inventory(message.from_user.id)
    if not inv:
        return await message.answer("🎒 Your bag is empty! Visit `/shop` to gear up~")
    lines = ["🎒 **Your Inventory:**\n"] + [f"• {SHOP_ITEMS[k]['name']} `x{q}` — *{SHOP_ITEMS[k]['desc']}*" for k, q in inv.items() if k in SHOP_ITEMS]
    await message.answer("\n".join(lines))


@router.message(Command("boss", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def spawn_boss(message: Message):
    cid = message.chat.id
    name = random.choice(["Colossal Titan", "Demon King Muzan", "Madara Uchiha", "Sukuna"])
    ACTIVE_BOSS[cid] = {"name": name, "hp": 600, "max": 600}
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚔️ Attack Boss!", callback_data="boss_atk")]])
    await message.answer(f"👹 **WILD {name.upper()} APPEARED!**\n❤️❤️❤️❤️❤️ `600 / 600 HP`", reply_markup=btn)


@router.message(Command("duel", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def duel_cmd(message: Message):
    if not message.reply_to_message or message.reply_to_message.from_user.id == message.from_user.id:
        return await message.answer("⚔️ Reply to a friend to **Duel**!")
    p1, p2 = message.from_user, message.reply_to_message.from_user
    inv1, inv2 = await get_inventory(p1.id), await get_inventory(p2.id)
    p1_chance = 0.5 + (0.2 if inv1.get("katana", 0) > 0 else 0) - (0.2 if inv2.get("katana", 0) > 0 else 0)
    winner = p1 if random.random() < p1_chance else p2
    await update_user_stats(winner.id, coins=75, xp=30)
    await message.answer(f"⚔️ **DUEL:** {p1.full_name} 🆚 {p2.full_name}\n🏆 **{winner.full_name}** won `+75 💎` & `+30 XP`!", parse_mode=None)


@router.message(Command("rps", prefix="/!"))
async def rps_cmd(message: Message):
    btns = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🪨 Rock", callback_data="rps_rock"),
        InlineKeyboardButton(text="📄 Paper", callback_data="rps_paper"),
        InlineKeyboardButton(text="✂️ Scissors", callback_data="rps_scissors"),
    ]])
    await message.answer("🎮 **Rock, Paper, Scissors!**", reply_markup=btns)


@router.message(Command("trivia", prefix="/!"))
async def trivia_cmd(message: Message):
    q, opts, correct = None, None, 0
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://opentdb.com/api.php?amount=1&category=31&type=multiple", timeout=8) as r:
                d = await r.json()
                if d.get("results"):
                    it = d["results"][0]
                    q, ans = html.unescape(it["question"]), html.unescape(it["correct_answer"])
                    opts = [html.unescape(x) for x in it["incorrect_answers"]] + [ans]
                    random.shuffle(opts); correct = opts.index(ans)
    except Exception:
        pass
    if not q:
        q, opts, correct = random.choice(FALLBACK_TRIVIA)
    tid = str(random.randint(10000, 99999))
    LIVE_TRIVIA[tid] = (opts, correct)
    btns = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=o, callback_data=f"triv_{tid}_{i}")] for i, o in enumerate(opts)])
    await message.answer(f"🧠 **Anime Trivia!**\n\n{q}", reply_markup=btns, parse_mode=None)


@router.message(Command("guess", prefix="/!"))
async def guess_cmd(message: Message):
    sec = random.randint(1, 5)
    btns = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=str(n), callback_data=f"guess_{sec}_{n}") for n in range(1, 6)]])
    await message.answer("🔢 **Guess the Number (1–5)!**", reply_markup=btns)


@router.message(Command("dart", "basket", "bowl", prefix="/!"))
async def mini_dice(message: Message):
    em = {"dart": "🎯", "basket": "🏀", "bowl": "🎳"}[message.text.split()[0].lstrip("/!").split("@")[0].lower()]
    await message.answer_dice(emoji=em)


@router.callback_query(F.data.startswith(("buy_", "boss_atk", "rps_", "triv_", "guess_")))
async def games_cb(query: CallbackQuery):
    d, uid = query.data, query.from_user.id
    if d.startswith("buy_"):
        k = d.split("_", 1)[1]
        item = SHOP_ITEMS[k]
        s = await get_user_stats(uid)
        if s["coins"] < item["price"]:
            return await query.answer("❌ Not enough 💎 Coins!", show_alert=True)
        await update_user_stats(uid, coins=-item["price"])
        if k == "energy":
            await update_user_stats(uid, xp=150)
            return await query.answer("⚡ Drank Energy Drink! +150 XP!", show_alert=True)
        await add_inventory_item(uid, k, 1)
        return await query.answer(f"✅ Bought {item['name']}!", show_alert=True)

    if d == "boss_atk":
        cid = query.message.chat.id
        boss = ACTIVE_BOSS.get(cid)
        if not boss:
            return await query.answer("Boss already defeated!", show_alert=True)
        inv = await get_inventory(uid)
        dmg = random.randint(40, 100) + (35 if inv.get("katana", 0) > 0 else 0)
        boss["hp"] = max(0, boss["hp"] - dmg)
        await update_user_stats(uid, coins=15, xp=10)
        if boss["hp"] == 0:
            ACTIVE_BOSS.pop(cid, None)
            await update_user_stats(uid, coins=200, xp=50)
            return await query.message.edit_text(f"🏆 **{boss['name']} DEFEATED!**\n💥 {query.from_user.full_name} dealt the final blow (`{dmg}`) & won **200 💎**!", parse_mode=None)
        hearts = "❤️" * max(1, (boss["hp"] * 5) // boss["max"]) + "🖤" * (5 - max(1, (boss["hp"] * 5) // boss["max"]))
        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚔️ Attack Boss!", callback_data="boss_atk")]])
        await query.message.edit_text(f"👹 **{boss['name']}**\n{hearts} `{boss['hp']}/{boss['max']} HP`\n💥 {query.from_user.first_name}: `{dmg}` DMG!", reply_markup=btn)
        return await query.answer(f"💥 {dmg} DMG! (+15 💎)")

    if d.startswith("rps_"):
        up, bp = d.split("_")[1], random.choice(["rock", "paper", "scissors"])
        win = (up, bp) in [("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")]
        res = "🤝 Tie!" if up == bp else ("🎉 You win! (+20 💎)" if win else "💓 Ruka wins!")
        if win:
            await update_user_stats(uid, coins=20)
        await query.message.edit_text(f"You: **{up}** | Ruka: **{bp}**\n\n{res}")
    elif d.startswith("triv_"):
        _, tid, idx = d.split("_")
        if tid not in LIVE_TRIVIA:
            return await query.answer("Expired!", show_alert=True)
        opts, cor = LIVE_TRIVIA.pop(tid)
        if int(idx) == cor:
            await update_user_stats(uid, coins=35, xp=15)
            await query.message.edit_text(f"✅ Correct! {opts[cor]} (+35 💎)", parse_mode=None)
        else:
            await query.message.edit_text(f"❌ Wrong! Answer: {opts[cor]}", parse_mode=None)
    elif d.startswith("guess_"):
        _, sec, pick = d.split("_")
        if sec == pick:
            await update_user_stats(uid, coins=25)
            await query.message.edit_text(f"🎉 Spot on! It was **{sec}** (+25 💎)!")
        else:
            await query.message.edit_text(f"😅 Nope! It was **{sec}**, not {pick}!")
    await query.answer()


@router.message(F.chat.type.in_({"group", "supergroup"}), F.text, ~F.text.startswith(("/", "!")))
async def xp_listener(message: Message):
    if not message.from_user or message.from_user.is_bot or message.text.startswith(("/", "!")):
        raise SkipHandler()
    await update_user_stats(message.from_user.id, coins=2, xp=random.randint(5, 10))