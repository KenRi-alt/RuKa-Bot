import urllib.parse
import aiohttp
from pyrogram import Client, filters
from ..utils import chatAction


async def ask_ruka_ai(prompt: str) -> str:
    system = "You are Ruka Sarashina from Rent-a-Girlfriend. You are energetic, cute, slightly possessive, and helpful. Keep replies concise."
    full_prompt = f"{system}\nUser: {prompt}\nRuka:"
    url = f"https://text.pollinations.ai/{urllib.parse.quote(full_prompt)}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as resp:
            if resp.status == 200:
                return await resp.text()
    return "Eh?! My brain froze for a second! Try again~"


@Client.on_message(filters.command(["ai", "ask", "ruka"]))
@chatAction("typing")
async def ruka_ai_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("💓 Talk to me! Example: `/ruka How are you today?`")
    prompt = message.text.split(None, 1)[1]
    reply = await ask_ruka_ai(prompt)
    await message.reply_text(f"💓 **Ruka:** {reply}")


@Client.on_message(filters.command("roast"))
@chatAction("typing")
async def roast_cmd(client, message):
    target = message.reply_to_message.from_user.first_name if message.reply_to_message else message.from_user.first_name
    reply = await ask_ruka_ai(f"Give a funny, lighthearted anime-style roast to {target}.")
    await message.reply_text(f"🔥 {reply}")


@Client.on_message(filters.command("compliment"))
@chatAction("typing")
async def compliment_cmd(client, message):
    target = message.reply_to_message.from_user.first_name if message.reply_to_message else message.from_user.first_name
    reply = await ask_ruka_ai(f"Give a super sweet, cute anime compliment to {target}.")
    await message.reply_text(f"🌸 {reply}")