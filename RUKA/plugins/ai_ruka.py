import os
import urllib.parse
import aiohttp
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

router = Router()

GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_URL = "https://api.x.ai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are Ruka Sarashina from Rent-a-Girlfriend. You are energetic, cute, "
    "slightly possessive, and super helpful. Keep replies concise and engaging."
)

USER_MEMORY: dict[int, list[dict]] = {}


async def ask_ruka_ai(user_id: int, prompt: str, use_memory: bool = True) -> str:
    history = USER_MEMORY.get(user_id, []) if use_memory else []
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": prompt}]

    # 1. Try Grok API (xAI) if GROK_API_KEY is set
    if GROK_API_KEY:
        headers = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "grok-2-latest",
            "messages": messages,
            "temperature": 0.7,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(GROK_URL, headers=headers, json=payload, timeout=25) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        if use_memory:
                            history = (history + [{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])[-6:]
                            USER_MEMORY[user_id] = history
                        return reply
        except Exception:
            pass

    # 2. Fallback: Free Pollinations AI (no key required)
    full_prompt = f"{SYSTEM_PROMPT}\nUser: {prompt}\nRuka:"
    url = f"https://text.pollinations.ai/{urllib.parse.quote(full_prompt)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status == 200:
                    return (await resp.text()).strip()
    except Exception:
        pass

    return "Eh?! My brain froze for a second! Try again~"


# 1. /ai, /ask, /ruka — Chat with Ruka (with memory!)
@router.message(Command("ai", "ask", "ruka"))
async def ruka_ai_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("💓 Talk to me! Example: `/ruka How are you today?`")
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, parts[1], use_memory=True)
    await message.answer(f"💓 **Ruka:** {reply}")


# 2. /imagine <prompt> — Free AI Anime Image Generation (Pollinations)
@router.message(Command("imagine"))
async def imagine_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("🎨 Tell me what to draw! Example: `/imagine cute anime girl with blue ribbon, 4k`")
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    prompt = urllib.parse.quote(parts[1])
    url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=45) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    photo = BufferedInputFile(img_bytes, filename="ruka_ai.png")
                    return await message.answer_photo(photo=photo, caption=f"🎨 **Generated:** `{parts[1]}`")
    except Exception:
        pass
    await message.answer("❌ Couldn't generate that image right now! Try again~")


# 3. /clearai — Reset AI memory
@router.message(Command("clearai"))
async def clear_ai_memory(message: Message):
    USER_MEMORY.pop(message.from_user.id, None)
    await message.answer("🧹 Cleared our AI chat memory! Let's start fresh~")


# 4. /roast — Anime-style roast
@router.message(Command("roast"))
async def roast_cmd(message: Message):
    target = message.reply_to_message.from_user.first_name if message.reply_to_message else message.from_user.first_name
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Give a funny, lighthearted anime-style roast to {target}.", use_memory=False)
    await message.answer(f"🔥 {reply}")


# 5. /compliment — Sweet anime compliment
@router.message(Command("compliment"))
async def compliment_cmd(message: Message):
    target = message.reply_to_message.from_user.first_name if message.reply_to_message else message.from_user.first_name
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Give a super sweet, cute anime compliment to {target}.", use_memory=False)
    await message.answer(f"🌸 {reply}")


# 6. /summarize — Summarize any long message
@router.message(Command("summarize"))
async def summarize_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("Reply to a long message to summarize it!")
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Summarize this in 3 short bullet points:\n\n{message.reply_to_message.text}", use_memory=False)
    await message.answer(f"📝 **Ruka's Summary:**\n{reply}")


# 7. /translate <language> — Translate any replied message
@router.message(Command("translate"))
async def translate_cmd(message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.answer("Reply to a message with `/translate <language>` (e.g. `/translate Japanese`).")
    parts = message.text.split(None, 1)
    lang = parts[1] if len(parts) > 1 else "English"
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Translate this into {lang} (only output the translation):\n\n{message.reply_to_message.text}", use_memory=False)
    await message.answer(f"🌐 **Translated ({lang}):**\n{reply}")


# 8. /animeidea — Custom anime plot with you as the MC!
@router.message(Command("animeidea"))
async def anime_idea_cmd(message: Message):
    name = message.from_user.first_name
    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await ask_ruka_ai(message.from_user.id, f"Create a short, exciting 3-sentence anime plot where {name} is the main character and Ruka is their partner.", use_memory=False)
    await message.answer(f"🎬 **Your Anime Plot:**\n{reply}")