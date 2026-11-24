from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps

def generate_4k_welcome(user_name: str, group_name: str, pfp_bytes: BytesIO = None) -> BytesIO:
    try:
        bg = Image.open("resources/welcome_4k.jpg").convert("RGBA").resize((3840, 2160), Image.Resampling.LANCZOS)
    except FileNotFoundError:
        bg = Image.new("RGBA", (3840, 2160), (18, 22, 38, 255))

    overlay = Image.new("RGBA", bg.size, (0, 0, 0, 110))
    bg = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(bg)

    pfp_size = (600, 600)
    if pfp_bytes:
        pfp = Image.open(pfp_bytes).convert("RGBA").resize(pfp_size, Image.Resampling.LANCZOS)
    else:
        pfp = Image.new("RGBA", pfp_size, (70, 130, 180, 255))

    mask = Image.new("L", pfp_size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + pfp_size, fill=255)
    pfp_circle = ImageOps.fit(pfp, pfp_size, centering=(0.5, 0.5))
    pfp_circle.putalpha(mask)
    bg.paste(pfp_circle, (1620, 420), pfp_circle)

    try:
        title_font = ImageFont.truetype("resources/font.ttf", 140)
        sub_font = ImageFont.truetype("resources/font.ttf", 90)
    except IOError:
        title_font = sub_font = ImageFont.load_default()

    draw.text((1920, 1180), f"Welcome, {user_name}!", font=title_font, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((1920, 1360), f"To {group_name}", font=sub_font, fill=(135, 206, 250, 255), anchor="mm")

    out = BytesIO()
    out.name = "welcome_4k.png"
    bg.convert("RGB").save(out, format="PNG", optimize=True)
    out.seek(0)
    return out