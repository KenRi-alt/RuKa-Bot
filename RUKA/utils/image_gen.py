import unicodedata
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _clean(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii") or "User"


def _font(size: int):
    try:
        return ImageFont.truetype("resources/font.ttf", size)
    except IOError:
        return ImageFont.load_default(size=size)


def _base_canvas(accent=(255, 105, 180, 220)):
    bg = Image.new("RGBA", (1280, 720), (14, 16, 28, 255))
    d = ImageDraw.Draw(bg)
    # Outer frame & inner card
    d.rounded_rectangle((28, 28, 1252, 692), radius=28, fill=(24, 28, 48, 255), outline=accent, width=4)
    # Subtle top header bar
    d.rounded_rectangle((44, 44, 1236, 124), radius=18, fill=(38, 44, 74, 255))
    # Bottom watermark bar
    d.rounded_rectangle((44, 628, 1236, 676), radius=14, fill=(18, 21, 36, 255))
    d.text((640, 652), "RUKA SARASHINA  •  @RuukaChan_bot  •  OFFICIAL CARD", font=_font(20), fill=(170, 185, 220, 200), anchor="mm")
    return bg


def _circle_pfp(pfp_bytes: BytesIO | None, size: int = 180, ring=(255, 105, 180, 255)) -> Image.Image:
    rs = size + 12
    c = Image.new("RGBA", (rs, rs), (0, 0, 0, 0))
    ImageDraw.Draw(c).ellipse((0, 0, rs - 1, rs - 1), fill=ring)
    if pfp_bytes:
        pfp_bytes.seek(0)
        pfp = Image.open(pfp_bytes).convert("RGBA").resize((size, size), Image.Resampling.BILINEAR)
    else:
        pfp = Image.new("RGBA", (size, size), (65, 105, 225, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    pfp_c = ImageOps.fit(pfp, (size, size), centering=(0.5, 0.5))
    pfp_c.putalpha(mask)
    c.paste(pfp_c, (6, 6), pfp_c)
    return c


def _export(img: Image.Image, name: str) -> BytesIO:
    out = BytesIO()
    out.name = name
    img.convert("RGB").save(out, format="JPEG", quality=92)
    out.seek(0)
    return out


# 1. Ruka Trainer-Style Profile Card
def generate_4k_profile(user_name: str, user_id: int, rank: str = "Newbie", xp: int = 0, coins: int = 100, cards: int = 0, pfp_bytes: BytesIO = None) -> BytesIO:
    bg = _base_canvas(accent=(100, 200, 255, 220))
    d = ImageDraw.Draw(bg)

    # Header
    d.text((75, 84), "RUKA TRAINER CARD", font=_font(36), fill=(255, 255, 255, 255), anchor="lm")
    d.text((1200, 84), f"RANK: {_clean(rank).upper()}", font=_font(32), fill=(255, 215, 100, 255), anchor="rm")

    # ID Badge
    d.rounded_rectangle((780, 145, 1220, 195), radius=12, fill=(35, 42, 70, 255), outline=(100, 200, 255, 160), width=2)
    d.text((1000, 170), f"IDNo.  {user_id}", font=_font(26), fill=(210, 230, 255, 255), anchor="mm")

    # Stat Rows (Left)
    d.text((75, 175), _clean(user_name)[:20], font=_font(44), fill=(255, 182, 193, 255), anchor="lm")
    d.line((75, 218, 740, 218), fill=(80, 95, 140, 180), width=2)

    stats = [
        ("Exp. Points", f"{xp} XP"),
        ("Ruka Coins", f"{coins} Coins"),
        ("Waifu Cards", f"{cards} Collected"),
        ("Status", "Active Member"),
    ]
    y = 260
    for label, val in stats:
        d.text((75, y), label, font=_font(28), fill=(180, 195, 230, 255), anchor="lm")
        d.text((720, y), val, font=_font(28), fill=(255, 255, 255, 255), anchor="rm")
        y += 56

    # XP Progress Bar
    pct = max(5, min(100, xp % 100 if xp > 0 else 5))
    d.rounded_rectangle((75, 500, 740, 534), radius=16, fill=(40, 46, 75, 255))
    d.rounded_rectangle((75, 500, 75 + int(665 * (pct / 100)), 534), radius=16, fill=(255, 105, 180, 255))
    d.text((75, 558), f"Next Level Progress: {pct}%", font=_font(22), fill=(200, 215, 240, 230), anchor="lm")

    # Avatar Box (Right)
    d.rounded_rectangle((830, 220, 1180, 570), radius=24, fill=(32, 38, 64, 255), outline=(255, 105, 180, 180), width=3)
    pfp = _circle_pfp(pfp_bytes, size=270, ring=(255, 105, 180, 255))
    bg.paste(pfp, (1005 - pfp.width // 2, 395 - pfp.height // 2), pfp)

    return _export(bg, "profile.jpg")


# 2. Stylish Welcome Card
def generate_4k_welcome(user_name: str, group_name: str, pfp_bytes: BytesIO = None) -> BytesIO:
    bg = _base_canvas(accent=(255, 105, 180, 220))
    d = ImageDraw.Draw(bg)
    d.text((75, 84), "NEW MEMBER ARRIVAL", font=_font(34), fill=(255, 182, 193, 255), anchor="lm")
    d.text((1200, 84), "WELCOME", font=_font(30), fill=(100, 220, 255, 255), anchor="rm")

    pfp = _circle_pfp(pfp_bytes, size=220, ring=(255, 105, 180, 255))
    bg.paste(pfp, (640 - pfp.width // 2, 165), pfp)

    d.text((640, 445), f"Welcome, {_clean(user_name)[:22]}!", font=_font(48), fill=(255, 255, 255, 255), anchor="mm")
    d.text((640, 515), f"To {_clean(group_name)[:32]}", font=_font(32), fill=(173, 216, 230, 255), anchor="mm")
    return _export(bg, "welcome.jpg")


# 3. Collector Anime / Gacha Card
def generate_4k_anime_card(title: str, score: str, genres: str, status: str, cover_bytes: BytesIO = None) -> BytesIO:
    bg = _base_canvas(accent=(255, 190, 90, 220))
    d = ImageDraw.Draw(bg)
    d.text((75, 84), "RUKA COLLECTOR CARD", font=_font(34), fill=(255, 215, 100, 255), anchor="lm")
    d.text((1200, 84), _clean(status).upper(), font=_font(30), fill=(255, 105, 180, 255), anchor="rm")

    if cover_bytes:
        cover_bytes.seek(0)
        cover = Image.open(cover_bytes).convert("RGBA").resize((300, 430), Image.Resampling.BILINEAR)
        d.rounded_rectangle((72, 152, 388, 598), radius=18, outline=(255, 215, 100, 220), width=4)
        bg.paste(cover, (80, 160))

    d.text((440, 210), _clean(title)[:26], font=_font(44), fill=(255, 255, 255, 255), anchor="lm")
    d.line((440, 255, 1180, 255), fill=(90, 105, 150, 180), width=2)
    d.text((440, 315), f"Rating / Power:  {_clean(score)}", font=_font(30), fill=(255, 215, 100, 255), anchor="lm")
    d.text((440, 380), f"Details:  {_clean(genres)[:36]}", font=_font(26), fill=(180, 215, 255, 255), anchor="lm")
    d.rounded_rectangle((440, 450, 760, 510), radius=14, fill=(45, 52, 88, 255), outline=(255, 105, 180, 200), width=2)
    d.text((600, 480), f"TAG: {_clean(status)[:14]}", font=_font(24), fill=(255, 182, 193, 255), anchor="mm")
    return _export(bg, "card.jpg")


# 4. Visual Pillow Family Tree (Connected PFPs!)
def generate_family_tree(user_name: str, user_pfp: BytesIO | None, spouse_name: str = None, spouse_pfp: BytesIO | None = None, members: list[tuple[str, str, BytesIO | None]] = None) -> BytesIO:
    bg = _base_canvas(accent=(140, 230, 170, 220))
    d = ImageDraw.Draw(bg)
    d.text((75, 84), f"{_clean(user_name).upper()}'S FAMILY TREE", font=_font(34), fill=(160, 255, 190, 255), anchor="lm")
    d.text((1200, 84), "NAKAMA LINEAGE", font=_font(28), fill=(255, 182, 193, 255), anchor="rm")

    # Top Row: User (+ Spouse if married)
    if spouse_name:
        ux, sx = 440, 840
        d.line((ux, 240, sx, 240), fill=(255, 105, 180, 255), width=6)
        d.text((640, 215), "MARRIED", font=_font(20), fill=(255, 182, 193, 255), anchor="mm")
        sp = _circle_pfp(spouse_pfp, size=140, ring=(255, 105, 180, 255))
        bg.paste(sp, (sx - sp.width // 2, 240 - sp.height // 2), sp)
        d.text((sx, 335), f"{_clean(spouse_name)[:14]} (Spouse)", font=_font(22), fill=(255, 255, 255, 255), anchor="mm")
    else:
        ux = 640

    up = _circle_pfp(user_pfp, size=150, ring=(100, 200, 255, 255))
    bg.paste(up, (ux - up.width // 2, 240 - up.height // 2), up)
    d.text((ux, 338), f"{_clean(user_name)[:14]} (You)", font=_font(24), fill=(255, 255, 255, 255), anchor="mm")

    # Bottom Row: Children / Siblings connected by tree branches
    members = (members or [])[:4]
    if members:
        d.line((640, 355, 640, 410), fill=(140, 230, 170, 255), width=5)
        xs = [640] if len(members) == 1 else ([440, 840] if len(members) == 2 else ([320, 640, 960] if len(members) == 3 else [230, 500, 780, 1050]))
        if len(xs) > 1:
            d.line((xs[0], 410, xs[-1], 410), fill=(140, 230, 170, 255), width=5)
        for x, (m_name, rel, m_pfp) in zip(xs, members):
            d.line((x, 410, x, 450), fill=(140, 230, 170, 255), width=5)
            mp = _circle_pfp(m_pfp, size=115, ring=(140, 230, 170, 255))
            bg.paste(mp, (x - mp.width // 2, 505 - mp.height // 2), mp)
            d.text((x, 588), f"{_clean(m_name)[:12]} ({rel})", font=_font(20), fill=(220, 255, 230, 255), anchor="mm")
    else:
        d.text((640, 480), "No children or siblings yet! Use /adopt or /sibling", font=_font(26), fill=(180, 200, 220, 220), anchor="mm")

    return _export(bg, "tree.jpg")


# 5. Ruka's Shop Banner
def generate_shop_banner(user_name: str, coins: int, ruka_bytes: BytesIO = None) -> BytesIO:
    bg = _base_canvas(accent=(255, 215, 100, 220))
    d = ImageDraw.Draw(bg)
    d.text((75, 84), "RUKA'S PREMIUM SHOP", font=_font(36), fill=(255, 215, 100, 255), anchor="lm")
    d.text((1200, 84), f"WALLET: {coins} COINS", font=_font(30), fill=(140, 255, 180, 255), anchor="rm")

    if ruka_bytes:
        rp = _circle_pfp(ruka_bytes, size=240, ring=(255, 105, 180, 255))
        bg.paste(rp, (1040 - rp.width // 2, 370 - rp.height // 2), rp)
        d.text((1040, 525), "Shopkeeper Ruka", font=_font(24), fill=(255, 182, 193, 255), anchor="mm")

    items = [
        ("Katana Blade", "5000 C", "+20% Duel Win Rate"),
        ("Heavy Armor", "3000 C", "Blocks /rob attempts"),
        ("Lucky Clover", "2000 C", "Boosts Gacha SSR odds"),
        ("Gold Ring", "1500 C", "+100 Bonus Daily Coins"),
        ("Energy Drink", "800 C", "+150 Instant XP"),
    ]
    y = 175
    for name, price, perk in items:
        d.rounded_rectangle((75, y, 830, y + 72), radius=14, fill=(34, 40, 68, 255), outline=(90, 105, 160, 160), width=2)
        d.text((100, y + 36), name, font=_font(28), fill=(255, 255, 255, 255), anchor="lm")
        d.text((430, y + 36), perk, font=_font(22), fill=(180, 210, 245, 255), anchor="lm")
        d.text((805, y + 36), price, font=_font(26), fill=(255, 215, 100, 255), anchor="rm")
        y += 86

    return _export(bg, "shop.jpg")