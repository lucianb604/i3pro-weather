from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import math

LAT = 49.2827
LON = -123.1207
TZ = "America/Vancouver"

# Final i3Pro size
BASE_W = 770
BASE_H = 325

# Render at 2x, then downsample with LANCZOS for sharper output
SCALE = 2
WIDTH = BASE_W * SCALE
HEIGHT = BASE_H * SCALE

URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&current=temperature_2m,relative_humidity_2m,weather_code,"
    "pressure_msl,wind_speed_10m,wind_direction_10m"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max"
    "&timezone=America%2FVancouver"
    "&forecast_days=7"
)

def S(v):
    return int(round(v * SCALE))

def get_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, S(size))
        except Exception:
            pass
    return ImageFont.load_default()

F_CITY = get_font(27, True)
F_DAY = get_font(17)
F_TEMP = get_font(48)
F_STAT = get_font(11)
F_COND = get_font(10)
F_TILE_DAY = get_font(14)
F_TILE_TEMP = get_font(11)
F_TILE_RAIN = get_font(8)

def condition(code):
    if code == 0:
        return "Clear"
    if code in (1, 2):
        return "Partly Cloudy"
    if code == 3:
        return "Cloudy"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow"
    if code in (95, 96, 99):
        return "Storm"
    return "Weather"

def wind_dir(deg):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((deg + 22.5) // 45) % 8]

def centered(draw, box, text, fnt, fill):
    x1, y1, x2, y2 = box
    bb = draw.textbbox((0, 0), text, font=fnt)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    draw.text(
        (x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2),
        text,
        font=fnt,
        fill=fill,
    )

def make_background():
    raw = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    px = raw.load()

    for y in range(HEIGHT):
        gy = y / HEIGHT
        for x in range(WIDTH):
            gx = x / WIDTH

            center = math.exp(
                -(((gx - 0.57) / 0.43) ** 2 +
                  ((gy - 0.08) / 0.52) ** 2)
            )

            lower = math.exp(
                -(((gx - 0.52) / 0.70) ** 2 +
                  ((gy - 0.82) / 0.55) ** 2)
            )

            edge = min(1.0, abs(gx - 0.5) * 2)

            r = 2 + 7 * center
            g = 48 + 110 * center + 12 * lower - 22 * edge
            b = 118 + 118 * center + 15 * lower - 12 * edge

            px[x, y] = (
                int(max(0, min(255, r))),
                int(max(0, min(255, g))),
                int(max(0, min(255, b))),
            )

    img = raw.convert("RGBA")

    bloom = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bloom)
    bd.ellipse(
        (S(220), S(-135), S(720), S(145)),
        fill=(120, 230, 255, 48),
    )
    bloom = bloom.filter(ImageFilter.GaussianBlur(S(46)))
    img.alpha_composite(bloom)

    # Square outer corners
    d = ImageDraw.Draw(img)
    d.rectangle(
        (S(1), S(1), WIDTH - S(2), HEIGHT - S(2)),
        outline=(220, 245, 255, 42),
        width=S(1),
    )

    return img

def ellipse_gradient(size, inner, outer):
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    px = img.load()

    cx = w / 2
    cy = h / 2
    rx = w / 2
    ry = h / 2

    for y in range(h):
        for x in range(w):
            d = min(
                1.0,
                math.sqrt(
                    ((x - cx) / rx) ** 2 +
                    ((y - cy) / ry) ** 2
                ),
            )
            px[x, y] = tuple(
                int(inner[i] * (1 - d) + outer[i] * d)
                for i in range(4)
            )

    return img

def draw_sun(layer, cx, cy, r, large=False):
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)

    gd.ellipse(
        (cx - r * 1.9, cy - r * 1.9,
         cx + r * 1.9, cy + r * 1.9),
        fill=(255, 205, 40, 105 if large else 70),
    )

    glow = glow.filter(
        ImageFilter.GaussianBlur(max(S(7), int(r * 0.55)))
    )

    layer.alpha_composite(glow)

    d = ImageDraw.Draw(layer)

    for angle in range(0, 360, 14 if large else 24):
        a = math.radians(angle)

        d.line(
            (
                cx + math.cos(a) * (r + S(3)),
                cy + math.sin(a) * (r + S(3)),
                cx + math.cos(a) * (r + (S(17) if large else S(9))),
                cy + math.sin(a) * (r + (S(17) if large else S(9))),
            ),
            fill=(255, 229, 80, 170),
            width=S(2) if large else S(1),
        )

    grad = ellipse_gradient(
        (int(r * 2 + 1), int(r * 2 + 1)),
        (255, 238, 95, 255),
        (255, 168, 10, 255),
    )

    layer.alpha_composite(
        grad,
        (int(cx - r), int(cy - r)),
    )

def draw_cloud(layer, cx, cy, scale=1.0, dark=False, large=False):
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)

    sd.ellipse(
        (
            cx - S(60) * scale,
            cy - S(10) * scale,
            cx + S(76) * scale,
            cy + S(42) * scale,
        ),
        fill=(0, 28, 70, 80 if large else 48),
    )

    shadow = shadow.filter(
        ImageFilter.GaussianBlur(S(9) if large else S(4))
    )

    layer.alpha_composite(shadow)

    cloud = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(cloud)

    if dark:
        top = (188, 204, 220, 255)
        mid = (126, 151, 186, 255)
        low = (76, 111, 162, 230)
    else:
        top = (255, 255, 255, 255)
        mid = (229, 241, 250, 255)
        low = (137, 185, 224, 220)

    d.rounded_rectangle(
        (
            cx - S(52) * scale,
            cy - S(3) * scale,
            cx + S(70) * scale,
            cy + S(31) * scale,
        ),
        radius=max(S(5), int(S(15) * scale)),
        fill=low,
    )

    puffs = [
        (-40, -4, 25),
        (-18, -28, 31),
        (15, -39, 35),
        (47, -20, 29),
    ]

    for ox, oy, rr in puffs:
        d.ellipse(
            (
                cx + (S(ox) - S(rr)) * scale,
                cy + (S(oy) - S(rr)) * scale,
                cx + (S(ox) + S(rr)) * scale,
                cy + (S(oy) + S(rr)) * scale,
            ),
            fill=mid,
        )

    d.ellipse(
        (
            cx - S(34) * scale,
            cy - S(28) * scale,
            cx + S(18) * scale,
            cy + S(8) * scale,
        ),
        fill=top,
    )

    d.ellipse(
        (
            cx + S(2) * scale,
            cy - S(42) * scale,
            cx + S(50) * scale,
            cy - S(3) * scale,
        ),
        fill=(255, 255, 255, 220),
    )

    shade = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    shd = ImageDraw.Draw(shade)

    shd.ellipse(
        (
            cx - S(50) * scale,
            cy + S(4) * scale,
            cx + S(68) * scale,
            cy + S(33) * scale,
        ),
        fill=(65, 115, 180, 70 if not dark else 110),
    )

    shade = shade.filter(
        ImageFilter.GaussianBlur(S(5) if large else S(2))
    )

    cloud.alpha_composite(shade)

    cloud = cloud.filter(ImageFilter.GaussianBlur(S(1)))
    layer.alpha_composite(cloud)

def draw_rain(layer, cx, cy, scale=1.0, heavy=False):
    d = ImageDraw.Draw(layer)

    xs = (-28, -10, 8, 26) if heavy else (-20, 0, 20)

    for dx in xs:
        d.line(
            (
                cx + S(dx) * scale,
                cy + S(19) * scale,
                cx + S(dx - 5) * scale,
                cy + S(35) * scale,
            ),
            fill=(92, 206, 255, 240),
            width=max(S(1), int(S(2.3) * scale)),
        )

def draw_snow(layer, cx, cy, scale=1.0):
    d = ImageDraw.Draw(layer)

    for dx in (-20, 0, 20):
        x = cx + S(dx) * scale
        y = cy + S(27) * scale
        r = S(3.5) * scale

        for a in (0, 45, 90, 135):
            rad = math.radians(a)

            d.line(
                (
                    x - math.cos(rad) * r,
                    y - math.sin(rad) * r,
                    x + math.cos(rad) * r,
                    y + math.sin(rad) * r,
                ),
                fill=(238, 251, 255, 245),
                width=S(1),
            )

def draw_lightning(layer, cx, cy, scale=1.0):
    d = ImageDraw.Draw(layer)

    pts = [
        (cx + S(5) * scale, cy + S(12) * scale),
        (cx - S(6) * scale, cy + S(31) * scale),
        (cx + S(2) * scale, cy + S(31) * scale),
        (cx - S(5) * scale, cy + S(50) * scale),
        (cx + S(16) * scale, cy + S(24) * scale),
        (cx + S(7) * scale, cy + S(24) * scale),
    ]

    d.polygon(pts, fill=(115, 225, 255, 255))

def weather_icon(layer, code, cx, cy, scale=1.0, large=False):
    if code == 0:
        draw_sun(
            layer,
            cx,
            cy,
            S(31 if large else 14) * scale,
            large,
        )

    elif code in (1, 2):
        draw_sun(
            layer,
            cx - S(25 if large else 12) * scale,
            cy - S(17 if large else 9) * scale,
            S(29 if large else 13) * scale,
            large,
        )

        draw_cloud(
            layer,
            cx + S(12 if large else 7) * scale,
            cy + S(8 if large else 5) * scale,
            (1.15 if large else 0.61) * scale,
            large=large,
        )

    elif code in (3, 45, 48):
        draw_cloud(
            layer,
            cx,
            cy,
            (1.23 if large else 0.69) * scale,
            large=large,
        )

    elif code in (
        51, 53, 55, 56, 57,
        61, 63, 65, 66, 67,
        80, 81, 82,
    ):
        draw_cloud(
            layer,
            cx,
            cy - S(4) * scale,
            (1.18 if large else 0.66) * scale,
            large=large,
        )

        draw_rain(
            layer,
            cx,
            cy + S(2) * scale,
            scale * (1.10 if large else 0.76),
            heavy=code in (65, 67, 82),
        )

    elif code in (71, 73, 75, 77, 85, 86):
        draw_cloud(
            layer,
            cx,
            cy - S(4) * scale,
            (1.18 if large else 0.66) * scale,
            large=large,
        )

        draw_snow(
            layer,
            cx,
            cy + S(1) * scale,
            scale * (1.10 if large else 0.76),
        )

    elif code in (95, 96, 99):
        draw_cloud(
            layer,
            cx,
            cy - S(5) * scale,
            (1.18 if large else 0.66) * scale,
            dark=True,
            large=large,
        )

        draw_rain(
            layer,
            cx,
            cy + S(2) * scale,
            scale * (1.08 if large else 0.74),
            heavy=True,
        )

        draw_lightning(
            layer,
            cx,
            cy + S(1) * scale,
            scale * (1.12 if large else 0.75),
        )

    else:
        draw_cloud(
            layer,
            cx,
            cy,
            0.72 * scale,
            large=large,
        )

def droplet(draw, x, y):
    pts = [
        (x + S(7), y),
        (x + S(2), y + S(8)),
        (x + S(2), y + S(12)),
        (x + S(4), y + S(15)),
        (x + S(7), y + S(17)),
        (x + S(10), y + S(15)),
        (x + S(12), y + S(12)),
        (x + S(12), y + S(8)),
        (x + S(7), y),
    ]

    draw.line(
        pts,
        fill=(220, 241, 255, 235),
        width=S(2),
        joint="curve",
    )

def wind_icon(draw, x, y):
    draw.arc(
        (x, y, x + S(18), y + S(8)),
        200,
        350,
        fill=(220, 241, 255, 235),
        width=S(2),
    )

    draw.arc(
        (x + S(2), y + S(5), x + S(22), y + S(13)),
        190,
        342,
        fill=(220, 241, 255, 235),
        width=S(2),
    )

    draw.arc(
        (x, y + S(9), x + S(16), y + S(16)),
        200,
        345,
        fill=(220, 241, 255, 235),
        width=S(2),
    )

def pressure_icon(draw, x, y):
    draw.ellipse(
        (x, y, x + S(17), y + S(17)),
        outline=(220, 241, 255, 235),
        width=S(2),
    )

    draw.line(
        (
            x + S(8),
            y + S(8),
            x + S(13),
            y + S(5),
        ),
        fill=(220, 241, 255, 235),
        width=S(2),
    )

# -----------------------
# FETCH WEATHER DATA
# -----------------------

r = requests.get(URL, timeout=20)
r.raise_for_status()

data = r.json()
current = data["current"]
daily = data["daily"]

img = make_background()
draw = ImageDraw.Draw(img)

now = datetime.now(ZoneInfo(TZ))

code = int(current["weather_code"])
temp = round(current["temperature_2m"])
humidity = round(current.get("relative_humidity_2m", 0))
pressure = round(current.get("pressure_msl", 0))
wind = round(current.get("wind_speed_10m", 0))
direction = wind_dir(float(current.get("wind_direction_10m", 0)))

# -----------------------
# CURRENT WEATHER
# -----------------------

draw.text(
    (S(37), S(18)),
    "Vancouver",
    font=F_CITY,
    fill=(250, 253, 255, 255),
)

draw.text(
    (S(39), S(52)),
    now.strftime("%A"),
    font=F_DAY,
    fill=(239, 248, 255, 245),
)

stats_y = S(88)

droplet(draw, S(39), stats_y)

draw.text(
    (S(66), stats_y + S(1)),
    f"{humidity}%",
    font=F_STAT,
    fill=(223, 241, 255, 240),
)

wind_icon(draw, S(38), stats_y + S(27))

draw.text(
    (S(66), stats_y + S(28)),
    f"{direction}, {wind} km/h",
    font=F_STAT,
    fill=(223, 241, 255, 240),
)

pressure_icon(draw, S(39), stats_y + S(56))

draw.text(
    (S(66), stats_y + S(57)),
    f"{pressure} hPa",
    font=F_STAT,
    fill=(223, 241, 255, 240),
)

# Large weather illustration
art = Image.new(
    "RGBA",
    (WIDTH, HEIGHT),
    (0, 0, 0, 0),
)

weather_icon(
    art,
    code,
    S(390),
    S(90),
    scale=0.91,
    large=True,
)

img.alpha_composite(art)

draw = ImageDraw.Draw(img)

temperature = f"{temp:+d}°C"

bb = draw.textbbox(
    (0, 0),
    temperature,
    font=F_TEMP,
)

draw.text(
    (
        WIDTH - S(34) - (bb[2] - bb[0]),
        S(20),
    ),
    temperature,
    font=F_TEMP,
    fill=(250, 253, 255, 250),
)

centered(
    draw,
    (S(280), S(147), S(502), S(167)),
    condition(code),
    F_COND,
    (224, 242, 255, 238),
)

# -----------------------
# 7-DAY FORECAST
# -----------------------

margin = S(22)
gap = S(8)

tile_y = S(171)
tile_h = S(137)

tile_w = (
    WIDTH -
    margin * 2 -
    gap * 6
) // 7

for i in range(7):

    x = margin + i * (tile_w + gap)

    # Tile shadow
    shadow = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    sd = ImageDraw.Draw(shadow)

    sd.rounded_rectangle(
        (
            x + S(2),
            tile_y + S(4),
            x + tile_w + S(2),
            tile_y + tile_h + S(4),
        ),
        radius=S(12),
        fill=(0, 22, 60, 70),
    )

    shadow = shadow.filter(
        ImageFilter.GaussianBlur(S(4))
    )

    img.alpha_composite(shadow)

    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        (
            x,
            tile_y,
            x + tile_w,
            tile_y + tile_h,
        ),
        radius=S(12),
        fill=(48, 92, 160, 116 if i == 0 else 98),
        outline=(205, 235, 255, 90),
        width=S(1),
    )

    # Tile gloss
    gloss = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    gd = ImageDraw.Draw(gloss)

    gd.rounded_rectangle(
        (
            x + S(2),
            tile_y + S(2),
            x + tile_w - S(2),
            tile_y + S(34),
        ),
        radius=S(10),
        fill=(230, 248, 255, 18),
    )

    img.alpha_composite(gloss)

    dt = datetime.strptime(
        daily["time"][i],
        "%Y-%m-%d",
    )

    day = dt.strftime("%a").upper()

    forecast_code = int(
        daily["weather_code"][i]
    )

    tile_icon = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0, 0, 0, 0),
    )

    weather_icon(
        tile_icon,
        forecast_code,
        x + tile_w // 2,
        tile_y + S(33),
        scale=0.73,
        large=False,
    )

    img.alpha_composite(tile_icon)

    draw = ImageDraw.Draw(img)

    centered(
        draw,
        (
            x,
            tile_y + S(63),
            x + tile_w,
            tile_y + S(86),
        ),
        day,
        F_TILE_DAY,
        (209, 237, 255, 248),
    )

    high = round(
        daily["temperature_2m_max"][i]
    )

    low = round(
        daily["temperature_2m_min"][i]
    )

    centered(
        draw,
        (
            x,
            tile_y + S(88),
            x + tile_w,
            tile_y + S(109),
        ),
        f"{high:+d}° / {low:+d}°",
        F_TILE_TEMP,
        (248, 252, 255, 252),
    )

    rain = round(
        daily["precipitation_probability_max"][i]
        or 0
    )

    centered(
        draw,
        (
            x,
            tile_y + S(111),
            x + tile_w,
            tile_y + S(127),
        ),
        f"{rain}% rain",
        F_TILE_RAIN,
        (190, 225, 250, 220),
    )

# -----------------------
# HIGH QUALITY FINAL OUTPUT
# -----------------------

# Draw at 1540 x 650, then perform our own high-quality resize
# so i3Pro receives the exact target size and does not need to resample it.
final_img = img.convert("RGB").resize(
    (BASE_W, BASE_H),
    resample=Image.Resampling.LANCZOS,
)

# Light sharpening for small text/icons after downsampling
final_img = final_img.filter(
    ImageFilter.UnsharpMask(
        radius=0.55,
        percent=110,
        threshold=2,
    )
)

final_img.save(
    "vancouver.png",
    "PNG",
    optimize=True,
)

print(
    f"Generated Vancouver weather PNG: "
    f"{BASE_W}x{BASE_H} "
    f"(rendered internally at {WIDTH}x{HEIGHT})"
)
