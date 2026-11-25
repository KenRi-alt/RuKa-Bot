from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter


def _load_font(size: int):
    try:
        return ImageFont.truetype("resources/font.ttf", size)
    except IOError:
        return ImageFont.load_default()


def _make_4k_bg(bg_bytes: BytesIO = None, fallback_path: str = "resources/welcome_4k.jpg") -> Image.Image:
    if bg_bytes:
        bg = Image.open(bg_bytes).convert("RGBA").resize((3840, 2160), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=35))
    else:
        try:
            bg = Image.open(fallback_path).convert("RGBA").resize((3840, 2160), Image.Resampling.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=18))
        except FileNotFoundError:
            bg = Image.new("RGBA", (3840, 2160), (16, 18, 32, 255))

    overlay = Image.new("RGBA", (3840, 2160), (10, 12, 24, 130))
    return Image.alpha_composite(bg, overlay)


def _draw_glass_card(bg: Image.Image, box: tuple, radius: int = 80, fill=(255, 255, 255, 28), outline=(255, 130, 180, 140)):
    card = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=6)
    return Image.alpha_composite(bg, card)


def _make_circle_pfp(pfp_bytes: BytesIO, size: int = 620, ring_color=(255, 105, 180, 255)) -> Image.Image:
    ring_size = size + 36
    canvas = Image.new("RGBA", (ring_size, ring_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, ring_size - 1, ring_size - 1), fill=ring_color)

    if pfp_bytes:
        pfp = Image.open(pfp_bytes).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    else:
        pfp = Image.new("RGBA", (size, size), (65, 105, 225, 255))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    pfp_circle = ImageOps.fit(pfp, (size, size), centering=(0.5, 0.5))
    pfp_circle.putalpha(mask)

    canvas.paste(pfp_circle, (18, 18), pfp_circle)
    return canvas


def _export_4k(img: Image.Image, filename: str) -> BytesIO:
    out = BytesIO()
    out.name = filename.replace(".png", ".jpg")
    img.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)
    out.seek(0)
    return out


# 1. 4K Welcome Card
def generate_4k_welcome(user_name: str, group_name: str, pfp_bytes: BytesIO = None) -> BytesIO:
    bg = _make_4k_bg()
    bg = _draw_glass_card(bg, (320, 220, 3520, 1940), radius=90)

    pfp_ring = _make_circle_pfp(pfp_bytes, size=620, ring_color=(255, 105, 180, 255))
    bg.paste(pfp_ring, (1920 - pfp_ring.width // 2, 340), pfp_ring)

    draw = ImageDraw.Draw(bg)
    draw.text((1920, 1180), f"Welcome, {user_name}!", font=_load_font(150), fill=(255, 255, 255, 255), anchor="mm")
    draw.text((1920, 1360), f"To {group_name}", font=_load_font(95), fill=(255, 182, 193, 255), anchor="mm")
    draw.text((1920, 1520), "RUKA-BOT  •  ANIME GROUP MANAGEMENT", font=_load_font(65), fill=(180, 200, 230, 220), anchor="mm")

    return _export_4k(bg, "welcome_4k.jpg")


# 2. 4K Profile / Rank Card
def generate_4k_profile(user_name: str, user_id: int, rank: str = "Genin", xp: int = 45, pfp_bytes: BytesIO = None) -> BytesIO:
    bg = _make_4k_bg()
    bg = _draw_glass_card(bg, (280, 260, 3560, 1900), radius=90, outline=(100, 200, 255, 150))

    pfp_ring = _make_circle_pfp(pfp_bytes, size=680, ring_color=(100, 200, 255, 255))
    bg.paste(pfp_ring, (460, 740), pfp_ring)

    draw = ImageDraw.Draw(bg)
    draw.text((1320, 620), user_name, font=_load_font(145), fill=(255, 255, 255, 255), anchor="lm")
    draw.text((1320, 800), f"ID: {user_id}   |   Rank: {rank}", font=_load_font(85), fill=(173, 216, 230, 255), anchor="lm")

    bar_x1, bar_y1, bar_x2, bar_y2 = 1320, 1020, 3300, 1110
    draw.rounded_rectangle((bar_x1, bar_y1, bar_x2, bar_y2), radius=45, fill=(255, 255, 255, 45))
    fill_w = int((bar_x2 - bar_x1) * max(0.05, min(xp / 100, 1.0)))
    draw.rounded_rectangle((bar_x1, bar_y1, bar_x1 + fill_w, bar_y2), radius=45, fill=(255, 105, 180, 255))
    draw.text((1320, 1200), f"XP Progress: {xp}%", font=_load_font(70), fill=(255, 255, 255, 220), anchor="lm")

    return _export_4k(bg, "profile_4k.jpg")


# 3. 4K AniList / Anime Card
def generate_4k_anime_card(title: str, score: str, genres: str, status: str, cover_bytes: BytesIO = None) -> BytesIO:
    bg = _make_4k_bg(bg_bytes=cover_bytes)
    bg = _draw_glass_card(bg, (240, 200, 3600, 1960), radius=90, outline=(255, 180, 100, 150))

    if cover_bytes:
        cover_bytes.seek(0)
        cover = Image.open(cover_bytes).convert("RGBA").resize((920, 1340), Image.Resampling.LANCZOS)
        bg.paste(cover, (380, 410))

    draw = ImageDraw.Draw(bg)
    draw.text((1460, 520), title[:32], font=_load_font(135), fill=(255, 255, 255, 255), anchor="lm")
    draw.text((1460, 740), f"⭐ Score: {score}   •   📺 {status}", font=_load_font(85), fill=(255, 215, 100, 255), anchor="lm")
    draw.text((1460, 920), f"🎭 Genres: {genres[:45]}", font=_load_font(75), fill=(200, 220, 255, 240), anchor="lm")
    draw.text((1460, 1680), "Powered by AniList  •  RuKa-Bot 4K", font=_load_font(65), fill=(255, 182, 193, 220), anchor="lm")

    return _export_4k(bg, "anime_4k.jpg")