import os
import urllib.parse
import aiohttp
from pyrogram import Client, filters
from ..utils import chatAction

GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_URL = "https://api.x.ai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are Ruka Sarashina from Rent-a-Girlfriend. You are energetic, cute, "
    "slightly possessive, and super helpful. Keep replies concise and engaging."
)

# Per-user short-term conversation memory (stores last 6 messages)
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
@Client.on_message(filters.command(["ai", "ask", "ruka"]))
@chatAction("typing")
async def ruka_ai_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("💓 Talk to me! Example: `/ruka How are you today?`")
    prompt = message.text.split(None, 1)[1]
    reply = await ask_ruka_ai(message.from_user.id, prompt, use_memory=True)
    await message.reply_text(f"💓 **Ruka:** {reply}")


# 2. /clearai — Reset AI memory
@Client.on_message(filters.command("clearai"))
async def clear_ai_memory(client, message):
    USER_MEMORY.pop(message.from_user.id, None)
    await message.reply_text("🧹 Cleared our AI chat memory! Let's start fresh~")


# 3. /roast — Anime-style roast
@Client.on_message(filters.command("roast"))
@chatAction("typing")
async def roast_cmd(client, message):
    target = message.reply_to_message.from_user.first_name if message.reply_to_message else message.from_user.first_name
    reply = await ask_ruka_ai(message.from_user.id, f"Give a funny, lighthearted anime-style roast to {target}.", use_memory=False)
    await message.reply_text(f"🔥 {reply}")


# 4. /compliment — Sweet anime compliment
@Client.on_message(filters.command("compliment"))
@chatAction("typing")
async def compliment_cmd(client, message):
    target = message.reply_to_message.from_user.first_name if message.reply_to_message else message.from_user.first_name
    reply = await ask_ruka_ai(message.from_user.id, f"Give a super sweet, cute anime compliment to {target}.", use_memory=False)
    await message.reply_text(f"🌸 {reply}")


# 5. /summarize — Summarize any long message
@Client.on_message(filters.command("summarize"))
@chatAction("typing")
async def summarize_cmd(client, message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.reply_text("Reply to a long message to summarize it!")
    reply = await ask_ruka_ai(message.from_user.id, f"Summarize this in 3 short bullet points:\n\n{message.reply_to_message.text}", use_memory=False)
    await message.reply_text(f"📝 **Ruka's Summary:**\n{reply}")


# 6. /translate <language> — Translate any replied message
@Client.on_message(filters.command("translate"))
@chatAction("typing")
async def translate_cmd(client, message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.reply_text("Reply to a message with `/translate <language>` (e.g. `/translate Japanese`).")
    lang = message.text.split(None, 1)[1] if len(message.command) > 1 else "English"
    reply = await ask_ruka_ai(message.from_user.id, f"Translate this into {lang} (only output the translation):\n\n{message.reply_to_message.text}", use_memory=False)
    await message.reply_text(f"🌐 **Translated ({lang}):**\n{reply}")


# 7. /animeidea — Custom anime plot with you as the MC!
@Client.on_message(filters.command("animeidea"))
@chatAction("typing")
async def anime_idea_cmd(client, message):
    name = message.from_user.first_name
    reply = await ask_ruka_ai(message.from_user.id, f"Create a short, exciting 3-sentence anime plot where {name} is the main character and Ruka is their partner.", use_memory=False)
    await message.reply_text(f"🎬 **Your Anime Plot:**\n{reply}")