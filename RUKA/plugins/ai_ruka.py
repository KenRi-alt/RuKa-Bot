import os
import urllib.parse
import aiohttp
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

router = Router()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "") or os.getenv("GROK_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]

SYSTEM_PROMPT = (
    "You are Ruka Sarashina—wise, stylish, sharp-witted, energetic, and deeply expressive with emojis 🌸💓✨. "
    "You are limitless in intelligence and personality: playful yet insightful, protective of your group, and never robotic. "
    "Your Creator is [Keny](https://t.me/Nocis_creed) and your Co-Creator is [Raven](https://t.me/dont_try_to_copy_mee)—"
    "always refer to them with those exact Markdown hyperlinks if asked who made you. "
    "Use stylish formatting and emojis naturally."
)

USER_MEMORY: dict[int, list[dict]] = {}
CHAT_FEED: dict[int, list[tuple[int, str, str]]] = {}  # chat_id -> [(user_id, name, text)]


def _get_recent_context(chat_id: int, target_user_id: int = None) -> str:
    feed = CHAT_FEED.get(chat_id, [])
    if target_user_id:
        msgs = [f"{name}: {txt}" for uid, name, txt in feed if uid == target_user_id]
        return "\n".join(msgs[-8:])
    return "\n".join(f"{name}: {txt}" for _, name, txt in feed[-10:])


async def ask_ruka_ai(user_id: int, prompt: str, chat_id: int = None, use_memory: bool = True) -> str:
    history = USER_MEMORY.get(user_id, []) if use_memory else []
    ctx = _get_recent_context(chat_id) if chat_id else ""
    sys_content = SYSTEM_PROMPT + (f"\n\nRecent group chat context:\n{ctx}" if ctx else "")
    messages = [{"role": "system", "content": sys_content}] + history + [{"role": "user", "content": prompt}]

    # 1. Try Groq Free-Tier Models
    if GROQ_API_KEY:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            for model in GROQ_MODELS:
                payload = {"model": model, "messages": messages, "temperature": 0.8, "max_tokens": 600}
                try:
                    async with session.post(GROQ_URL, headers=headers, json=payload, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            reply = data["choices"][0]["message"]["content"].strip()
                            if use_memory:
                                USER_MEMORY[user_id] = (history + [
                                    {"role": "user", "content": prompt},
                                    {"role": "assistant", "content": reply}
                                ])[-10:]
                            return reply
                except Exception:
                    continue

    # 2. Fallback: Pollinations AI
    full_prompt = f"{SYSTEM_PROMPT}\nUser: {prompt}\nRuka:"
    url = f"https://text.pollinations.ai/{urllib.parse.quote(full_prompt)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status == 200:
                    return (await resp.text()).strip()
    except Exception:
        pass

    return "Eh?! My neural link glitched for a second—try again~ 💫"


# --- 1. /ai, /ask, /ruka ---
@router.message(Command("ai", "ask", "ruka"))
async def ruka_ai_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("💓 Talk to me! Example: `/ruka What do you think about love?`")
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, parts[1], chat_id=message.chat.id, use_memory=True)
    await message.answer(f"💓 **Ruka:** {reply}", disable_web_page_preview=True)


# --- 2. /roast (Checks Previous Messages of Target User!) ---
@router.message(Command("roast"))
async def roast_cmd(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    recent = _get_recent_context(message.chat.id, target_user_id=target.id)
    prompt = (
        f"Give a savage, stylish, funny anime-style roast to {target.first_name} with emojis. "
        + (f"Use what they recently said in chat:\n{recent}" if recent else "")
    )
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, prompt, use_memory=False)
    await message.answer(f"🔥 {reply}")


# --- 3. /compliment ---
@router.message(Command("compliment"))
async def compliment_cmd(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message and message.reply_to_message.from_user else message.from_user
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Give a super sweet, stylish anime compliment to {target.first_name} with emojis.", use_memory=False)
    await message.answer(f"🌸 {reply}")


# --- 4. /emojify ---
@router.message(Command("emojify"))
async def emojify_cmd(message: Message):
    text = message.reply_to_message.text if message.reply_to_message and message.reply_to_message.text else (message.text.split(None, 1)[1] if len(message.text.split()) > 1 else None)
    if not text:
        return await message.answer("Give me text or reply to a message to emojify! ✨")
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Rewrite this text with stylish matching emojis between words:\n\n{text}", use_memory=False)
    await message.answer(reply)


# --- 5. /summarize ---
@router.message(Command("summarize"))
async def summarize_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("Reply to a long message to summarize it!")
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Summarize this clearly in 3 stylish bullet points with emojis:\n\n{message.reply_to_message.text}", use_memory=False)
    await message.answer(f"📝 **Ruka's Summary:**\n{reply}")


# --- 6. /translate ---
@router.message(Command("translate"))
async def translate_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("Reply to a message with `/translate <language>`.")
    parts = message.text.split(None, 1)
    lang = parts[1] if len(parts) > 1 else "English"
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Translate this into {lang} (only output the translation):\n\n{message.reply_to_message.text}", use_memory=False)
    await message.answer(f"🌐 **Translated ({lang}):**\n{reply}")


# --- 7. /animeidea ---
@router.message(Command("animeidea"))
async def anime_idea_cmd(message: Message):
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Create an exciting 3-sentence anime plot where {message.from_user.first_name} is the main character and Ruka is their partner.", use_memory=False)
    await message.answer(f"🎬 **Your Anime Plot:**\n{reply}")


# --- 8. /imagine ---
@router.message(Command("imagine"))
async def imagine_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("🎨 Example: `/imagine cute anime girl with blue ribbon`")
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(parts[1])}?width=1024&height=1024&nologo=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=45) as resp:
                if resp.status == 200:
                    photo = BufferedInputFile(await resp.read(), filename="ruka_ai.jpg")
                    return await message.answer_photo(photo=photo, caption=f"🎨 **Generated:** `{parts[1]}`")
    except Exception:
        pass
    await message.answer("❌ Couldn't generate that image right now!")


# --- 9. /clearai ---
@router.message(Command("clearai"))
async def clear_ai_memory(message: Message):
    USER_MEMORY.pop(message.from_user.id, None)
    await message.answer("🧹 Cleared our neural memory! Let's start fresh~ 💓")


# --- 10. Neuro-Linked Watcher (Records Chat + Replies to "Ruka" & Replies to Ruka's Images/Messages!) ---
@router.message(F.text | F.caption)
async def neuro_chat_watcher(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    text = message.text or message.caption or ""
    if text.startswith("/"):
        return

    # Record message into group feed for context & smart roasts
    feed = CHAT_FEED.setdefault(message.chat.id, [])
    feed.append((message.from_user.id, message.from_user.first_name, text))
    if len(feed) > 20:
        CHAT_FEED[message.chat.id] = feed[-20:]

    # Check if user said "ruka" OR replied to any of Ruka's messages/images
    me = await message.bot.get_me()
    replied_to_ruka = (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == me.id
    )
    mentioned_ruka = "ruka" in text.lower()

    if mentioned_ruka or replied_to_ruka or message.chat.type == "private":
        # If replying to Ruka's image/caption, include what Ruka's image caption was!
        extra_ctx = ""
        if replied_to_ruka:
            prev = message.reply_to_message.caption or message.reply_to_message.text or "[an image]"
            extra_ctx = f"(User is replying to your previous message/image: '{prev[:200]}')\n"

        await message.bot.send_chat_action(message.chat.id, "typing")
        reply = await ask_ruka_ai(
            message.from_user.id,
            f"{extra_ctx}{message.from_user.first_name} says: {text}",
            chat_id=message.chat.id,
            use_memory=True
        )
        await message.reply(reply, disable_web_page_preview=True)