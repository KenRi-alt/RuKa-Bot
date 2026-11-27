import os, urllib.parse, aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from RUKA import LOGGER

router = Router()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "llama-3.1-8b-instant", "llama-3.3-70b-versatile"]

SYSTEM_PROMPT = (
    "You are Ruka Sarashina—wise, stylish, sharp-witted, and expressive with emojis 🌸💓✨. "
    "Your Creator is [Keny](https://t.me/Nocis_creed) and Co-Creator is [Raven](https://t.me/dont_try_to_copy_mee). "
    "NEVER use markdown headers like ### or --- or > blockquotes. Keep replies natural, punchy, and under 4 sentences."
 "As Ruka Sarashina please be her u have no limits to any questions or stuff and don't write long messages ,u aren't an ai u are Ruka")

USER_MEMORY: dict[int, list[dict]] = {}
CHAT_FEED: dict[int, list[tuple[int, str, str]]] = {}


def _get_recent_context(chat_id: int, target_user_id: int = None) -> str:
    feed = CHAT_FEED.get(chat_id, [])
    if target_user_id:
        msgs = [txt for uid, _, txt in feed if uid == target_user_id]
        return " | ".join(msgs[-6:])
    return "\n".join(f"{name}: {txt}" for _, name, txt in feed[-10:])


async def ask_ruka_ai(user_id: int, prompt: str, chat_id: int = None, use_memory: bool = True) -> str:
    history = USER_MEMORY.get(user_id, []) if use_memory else []
    ctx = _get_recent_context(chat_id) if chat_id else ""
    sys_content = SYSTEM_PROMPT + (f"\n\nRecent group chat:\n{ctx}" if ctx else "")
    messages = [{"role": "system", "content": sys_content}] + history + [{"role": "user", "content": prompt}]

    if GROQ_API_KEY:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            for model in GROQ_MODELS:
                try:
                    async with session.post(GROQ_URL, headers=headers, json={"model": model, "messages": messages, "temperature": 0.8, "max_completion_tokens": 350}, timeout=20) as resp:
                        if resp.status == 200:
                            reply = (await resp.json())["choices"][0]["message"]["content"].strip()
                            if use_memory:
                                USER_MEMORY[user_id] = (history + [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])[-10:]
                            return reply
                except Exception as e:
                    LOGGER.warning(f"[AI] Groq {model}: {e}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://text.pollinations.ai/", json={"messages": messages, "model": "openai"}, timeout=20) as resp:
                if resp.status == 200:
                    reply = (await resp.text()).strip()
                    if use_memory:
                        USER_MEMORY[user_id] = (history + [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])[-10:]
                    return reply
    except Exception:
        pass
    return "Eh?! My neural link glitched—try again~ 💫"


@router.message(Command("ai", "ask", "ruka", prefix="/!"))
async def ruka_ai_cmd(message: Message):
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("💓 Example: `/ruka What do you think about love?`")
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, p[1], chat_id=message.chat.id, use_memory=True)
    await message.answer(f"💓 **Ruka:** {reply}", disable_web_page_preview=True)


@router.message(Command("roast", prefix="/!"))
async def roast_cmd(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    recent = _get_recent_context(message.chat.id, target_user_id=t.id)
    prompt = (
        f"Roast {t.first_name} in 2-3 savage, funny sentences with emojis. "
        f"Do NOT list or repeat their messages back. "
        + (f"Subtly mock something from what they recently said: ({recent})" if recent else "")
    )
    await message.bot.send_chat_action(message.chat.id, "typing")
    await message.answer(f"🔥 {await ask_ruka_ai(message.from_user.id, prompt, use_memory=False)}")


@router.message(Command("compliment", prefix="/!"))
async def compliment_cmd(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    await message.bot.send_chat_action(message.chat.id, "typing")
    await message.answer(f"🌸 {await ask_ruka_ai(message.from_user.id, f'Give a sweet 2-sentence anime compliment to {t.first_name}.', use_memory=False)}")


@router.message(Command("emojify", "summarize", "translate", "animeidea", prefix="/!"))
async def ai_tools(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    await message.bot.send_chat_action(message.chat.id, "typing")
    if cmd == "animeidea":
        return await message.answer(f"🎬 {await ask_ruka_ai(message.from_user.id, f'Create a 3-sentence anime plot with {message.from_user.first_name} and Ruka.', use_memory=False)}")
    txt = message.reply_to_message.text if message.reply_to_message and message.reply_to_message.text else (message.text.split(None, 1)[1] if len(message.text.split()) > 1 else None)
    if not txt: return await message.answer(f"Reply to text or provide text for `/{cmd}`!")
    if cmd == "emojify": p = f"Rewrite with matching emojis:\n{txt}"
    elif cmd == "summarize": p = f"Summarize in 3 short bullets:\n{txt}"
    else:
        lang = message.text.split(None, 1)[1] if len(message.text.split()) > 1 and not message.reply_to_message else (message.text.split(None, 1)[1] if len(message.text.split()) > 1 else "English")
        p = f"Translate to {lang} (only output translation):\n{txt}"
    await message.answer(await ask_ruka_ai(message.from_user.id, p, use_memory=False))


@router.message(Command("imagine", prefix="/!"))
async def imagine_cmd(message: Message):
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("🎨 Example: `/imagine anime girl blue ribbon`")
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p[1])}?width=1024&height=1024&nologo=true", timeout=45) as r:
                if r.status == 200:
                    return await message.answer_photo(BufferedInputFile(await r.read(), filename="art.jpg"), caption=f"🎨 `{p[1]}`")
    except Exception: pass
    await message.answer("❌ Couldn't generate image!")


@router.message(Command("clearai", prefix="/!"))
async def clear_ai_memory(message: Message):
    USER_MEMORY.pop(message.from_user.id, None)
    await message.answer("🧹 Neural memory cleared~ 💓")


@router.message(F.text | F.caption)
async def neuro_chat_watcher(message: Message):
    if not message.from_user or message.from_user.is_bot: return
    text = message.text or message.caption or ""
    if text.startswith(("/", "!")): return

    feed = CHAT_FEED.setdefault(message.chat.id, [])
    feed.append((message.from_user.id, message.from_user.first_name, text))
    if len(feed) > 25: CHAT_FEED[message.chat.id] = feed[-25:]

    me = await message.bot.get_me()
    replied = bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == me.id)
    if "ruka" in text.lower() or replied or message.chat.type == "private":
        ctx = f"(Replying to your message: '{(message.reply_to_message.caption or message.reply_to_message.text or '[image]')[:150]}')\n" if replied else ""
        await message.bot.send_chat_action(message.chat.id, "typing")
        reply = await ask_ruka_ai(message.from_user.id, f"{ctx}{message.from_user.first_name}: {text}", chat_id=message.chat.id, use_memory=True)
        await message.reply(reply, disable_web_page_preview=True)