import unicodedata
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _clean_text(text: str) -> str:
    # Converts fancy Unicode (e.g. 𝕂eny) into normal readable characters
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii") or "User"


def _load_font(size: int):
    try:
        return ImageFont.truetype("resources/font.ttf", size)
    except IOError:
        return ImageFont.load_default(size=size)


def _make_bg() -> Image.Image:
    return Image.new("RGBA", (1280, 720), (16, 18, 32, 255))


def _draw_glass_card(bg: Image.Image, box: tuple, radius: int = 30, outline=(255, 105, 180, 180)):
    draw = ImageDraw.Draw(bg)
    draw.rounded_rectangle(box, radius=radius, fill=(28, 32, 56, 255), outline=outline, width=3)
    return bg


def _make_circle_pfp(pfp_bytes: BytesIO, size: int = 220, ring_color=(255, 105, 180, 255)) -> Image.Image:
    ring_size = size + 14
    canvas = Image.new("RGBA", (ring_size, ring_size), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).ellipse((0, 0, ring_size - 1, ring_size - 1), fill=ring_color)

    if pfp_bytes:
        pfp = Image.open(pfp_bytes).convert("RGBA").resize((size, size), Image.Resampling.BILINEAR)
    else:
        pfp = Image.new("RGBA", (size, size), (65, 105, 225, 255))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    pfp_circle = ImageOps.fit(pfp, (size, size), centering=(0.5, 0.5))
    pfp_circle.putalpha(mask)

    canvas.paste(pfp_circle, (7, 7), pfp_circle)
    return canvas


def _export_img(img: Image.Image, filename: str) -> BytesIO:
    out = BytesIO()
    out.name = filename
    img.convert("RGB").save(out, format="JPEG", quality=90)
    out.seek(0)
    return out


def generate_4k_welcome(user_name: str, group_name: str, pfp_bytes: BytesIO = None) -> BytesIO:
    bg = _draw_glass_card(_make_bg(), (80, 60, 1200, 660), outline=(255, 105, 180, 200))
    pfp_ring = _make_circle_pfp(pfp_bytes, size=220, ring_color=(255, 105, 180, 255))
    bg.paste(pfp_ring, (640 - pfp_ring.width // 2, 110), pfp_ring)

    draw = ImageDraw.Draw(bg)
    draw.text((640, 410), f"Welcome, {_clean_text(user_name)}!", font=_load_font(50), fill=(255, 255, 255, 255), anchor="mm")
    draw.text((640, 480), f"To {_clean_text(group_name)}", font=_load_font(32), fill=(255, 182, 193, 255), anchor="mm")
    draw.text((640, 560), "RUKA SARASHINA  •  WELCOME", font=_load_font(22), fill=(160, 180, 210, 220), anchor="mm")
    return _export_img(bg, "welcome.jpg")


def generate_4k_profile(user_name: str, user_id: int, rank: str = "Member", xp: int = 45, pfp_bytes: BytesIO = None) -> BytesIO:
    bg = _draw_glass_card(_make_bg(), (80, 80, 1200, 640), outline=(100, 200, 255, 200))
    pfp_ring = _make_circle_pfp(pfp_bytes, size=240, ring_color=(100, 200, 255, 255))
    bg.paste(pfp_ring, (140, 235), pfp_ring)

    draw = ImageDraw.Draw(bg)
    draw.text((440, 210), _clean_text(user_name)[:22], font=_load_font(50), fill=(255, 255, 255, 255), anchor="lm")
    draw.text((440, 280), f"ID: {user_id}   |   Rank: {_clean_text(rank)}", font=_load_font(28), fill=(173, 216, 230, 255), anchor="lm")

    bar_x1, bar_y1, bar_x2, bar_y2 = 440, 350, 1120, 385
    draw.rounded_rectangle((bar_x1, bar_y1, bar_x2, bar_y2), radius=18, fill=(255, 255, 255, 45))
    fill_w = int((bar_x2 - bar_x1) * max(0.05, min(xp / 100, 1.0)))
    draw.rounded_rectangle((bar_x1, bar_y1, bar_x1 + fill_w, bar_y2), radius=18, fill=(255, 105, 180, 255))
    draw.text((440, 420), f"XP Progress: {xp}%", font=_load_font(24), fill=(255, 255, 255, 220), anchor="lm")
    return _export_img(bg, "profile.jpg")


def generate_4k_anime_card(title: str, score: str, genres: str, status: str, cover_bytes: BytesIO = None) -> BytesIO:
    bg = _draw_glass_card(_make_bg(), (60, 60, 1220, 660), outline=(255, 180, 100, 200))

    if cover_bytes:
        cover_bytes.seek(0)
        cover = Image.open(cover_bytes).convert("RGBA").resize((320, 460), Image.Resampling.BILINEAR)
        bg.paste(cover, (110, 130))

    draw = ImageDraw.Draw(bg)
    draw.text((480, 180), _clean_text(title)[:26], font=_load_font(48), fill=(255, 255, 255, 255), anchor="lm")
    draw.text((480, 265), f"Score: {_clean_text(score)}   •   {_clean_text(status)}", font=_load_font(30), fill=(255, 215, 100, 255), anchor="lm")
    draw.text((480, 330), f"Info: {_clean_text(genres)[:38]}", font=_load_font(26), fill=(200, 220, 255, 240), anchor="lm")
    draw.text((480, 560), "Ruka Sarashina  •  Anime Card", font=_load_font(22), fill=(255, 182, 193, 220), anchor="lm")
    return _export_img(bg, "anime.jpg")