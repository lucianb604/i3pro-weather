from pathlib import Path
import py_compile

code = r'''from PIL import Image, ImageDraw, ImageFont, ImageFilter
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import math

LAT = 49.2827
LON = -123.1207
TZ = "America/Vancouver"

WIDTH = 770
HEIGHT = 373

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

def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

F_CITY = font(29, True)
F_DAY = font(20)
F_TEMP = font(52)
F_STAT = font(13)
F_COND = font(11)
F_TILE_DAY = font(17)
F_TILE_TEMP = font(14)
F_TILE_RAIN = font(10)

def condition(code):
    if code == 0: return "Clear"
    if code in (1, 2): return "Partly Cloudy"
    if code == 3: return "Cloudy"
    if code in (45, 48): return "Fog"
    if code in (51, 53, 55, 56, 57): return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82): return "Rain"
    if code in (71, 73, 75, 77, 85, 86): return "Snow"
    if code in (95, 96, 99): return "Storm"
    return "Weather"

def wind_dir(deg):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((deg + 22.5) // 45) % 8]

def center_text(draw, box, text, fnt, fill):
    x1, y1, x2, y2 = box
    bb = draw.textbbox((0, 0), text, font=fnt)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    draw.text(
        (x1 + (x2-x1-tw)/2, y1 + (y2-y1-th)/2),
        text,
        font=fnt,
        fill=fill
    )

def make_background():
    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    raw = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))

    px = raw.load()
    for y in range(HEIGHT):
        gy = y / HEIGHT
        for x in range(WIDTH):
            gx = x / WIDTH

            glow = math.exp(
                -(((gx - 0.56) / 0.40) ** 2 +
                  ((gy - 0.12) / 0.62) ** 2)
            )
            edge = min(1.0, abs(gx - 0.5) * 2.0)

            r = 4 + 8 * glow
            g = 55 + 112 * glow - 28 * edge + 10 * (1 - gy)
            b = 125 + 112 * glow - 18 * edge

            px[x, y] = (
                max(0, min(255, int(r))),
                max(0, min(255, int(g))),
                max(0, min(255, int(b))),
            )

    # Subtle upper cyan bloom
    bloom = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bloom)
    bd.ellipse((180, -120, 700, 185), fill=(110, 225, 255, 55))
    bloom = bloom.filter(ImageFilter.GaussianBlur(48))

    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((1, 1, WIDTH-2, HEIGHT-2), radius=28, fill=255)

    base.paste(raw.convert("RGBA"), (0, 0), mask)
    base.alpha_composite(bloom)

    # Thin glossy border
    bd = ImageDraw.Draw(base)
    bd.rounded_rectangle(
        (1, 1, WIDTH-2, HEIGHT-2),
        radius=28,
        outline=(220, 245, 255, 60),
        width=1
    )
    return base

def shadow_blob(layer, box, blur=10, alpha=80):
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.ellipse(box, fill=(0, 28, 70, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    layer.alpha_composite(sh)

def draw_sun(layer, cx, cy, r, large=False):
    # Glow
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        (cx-r*1.8, cy-r*1.8, cx+r*1.8, cy+r*1.8),
        fill=(255, 205, 35, 110 if large else 75)
    )
    glow = glow.filter(ImageFilter.GaussianBlur(max(8, int(r*0.50))))
    layer.alpha_composite(glow)

    d = ImageDraw.Draw(layer)

    # Rays
    ray_len = 18 if large else 9
    for angle in range(0, 360, 15 if large else 24):
        a = math.radians(angle)
        d.line(
            (
                cx + math.cos(a)*(r+3),
                cy + math.sin(a)*(r+3),
                cx + math.cos(a)*(r+ray_len),
                cy + math.sin(a)*(r+ray_len),
            ),
            fill=(255, 225, 70, 175),
            width=2 if large else 1
        )

    # Sun body
    d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(255, 191, 20, 255))
    d.ellipse(
        (cx-r*0.73, cy-r*0.83, cx+r*0.50, cy+r*0.30),
        fill=(255, 236, 95, 185)
    )

def draw_cloud(layer, cx, cy, scale=1.0, dark=False, large=False):
    shadow_blob(
        layer,
        (
            cx-55*scale, cy-14*scale,
            cx+72*scale, cy+40*scale
        ),
        blur=10 if large else 5,
        alpha=95 if large else 60
    )

    cloud = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(cloud)

    if dark:
        bright = (180, 195, 215, 255)
        mid = (125, 150, 185, 245)
        shade = (75, 110, 160, 210)
    else:
        bright = (250, 253, 255, 255)
        mid = (225, 239, 250, 255)
        shade = (135, 185, 225, 200)

    # Under-layer/shade
    d.ellipse(
        (cx-52*scale, cy+1*scale, cx+66*scale, cy+33*scale),
        fill=shade
    )

    # Cloud puffs
    puffs = [
        (-44, -2, 25),
        (-22, -25, 30),
        (8, -38, 34),
        (40, -22, 28),
    ]
    for ox, oy, rr in puffs:
        d.ellipse(
            (
                cx+(ox-rr)*scale,
                cy+(oy-rr)*scale,
                cx+(ox+rr)*scale,
                cy+(oy+rr)*scale,
            ),
            fill=bright
        )

    d.rounded_rectangle(
        (
            cx-48*scale, cy-5*scale,
            cx+68*scale, cy+30*scale
        ),
        radius=max(4, int(14*scale)),
        fill=mid
    )

    # Bright top highlights
    d.ellipse(
        (
            cx-25*scale, cy-29*scale,
            cx+29*scale, cy+11*scale
        ),
        fill=(255, 255, 255, 155)
    )

    cloud = cloud.filter(ImageFilter.GaussianBlur(0.7 if large else 0.25))
    layer.alpha_composite(cloud)

def draw_rain(layer, cx, cy, scale=1.0, heavy=False):
    d = ImageDraw.Draw(layer)
    drops = (-26, -9, 8, 25) if heavy else (-20, 0, 20)
    for dx in drops:
        d.line(
            (
                cx+dx*scale,
                cy+18*scale,
                cx+(dx-5)*scale,
                cy+34*scale,
            ),
            fill=(95, 205, 255, 235),
            width=max(1, int(2.4*scale))
        )

def draw_snow(layer, cx, cy, scale=1.0):
    d = ImageDraw.Draw(layer)
    for dx in (-20, 0, 20):
        x = cx + dx*scale
        y = cy + 27*scale
        r = 3.5*scale
        d.line((x-r, y, x+r, y), fill=(235, 250, 255, 245), width=1)
        d.line((x, y-r, x, y+r), fill=(235, 250, 255, 245), width=1)
        d.line((x-r*.7, y-r*.7, x+r*.7, y+r*.7),
               fill=(235, 250, 255, 245), width=1)
        d.line((x-r*.7, y+r*.7, x+r*.7, y-r*.7),
               fill=(235, 250, 255, 245), width=1)

def draw_lightning(layer, cx, cy, scale=1.0):
    d = ImageDraw.Draw(layer)
    pts = [
        (cx+4*scale, cy+12*scale),
        (cx-6*scale, cy+31*scale),
        (cx+2*scale, cy+31*scale),
        (cx-5*scale, cy+49*scale),
        (cx+15*scale, cy+24*scale),
        (cx+7*scale, cy+24*scale),
    ]
    d.polygon(pts, fill=(115, 225, 255, 255))

def draw_weather_icon(layer, code, cx, cy, scale=1.0, large=False):
    if code == 0:
        draw_sun(layer, cx, cy, (32 if large else 15)*scale, large=large)

    elif code in (1, 2):
        draw_sun(
            layer,
            cx-(25 if large else 13)*scale,
            cy-(18 if large else 10)*scale,
            (29 if large else 14)*scale,
            large=large
        )
        draw_cloud(
            layer,
            cx+(12 if large else 7)*scale,
            cy+(9 if large else 5)*scale,
            (1.15 if large else 0.62)*scale,
            large=large
        )

    elif code in (3, 45, 48):
        draw_cloud(
            layer, cx, cy,
            (1.25 if large else 0.72)*scale,
            large=large
        )

    elif code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        draw_cloud(
            layer, cx, cy-4*scale,
            (1.18 if large else 0.68)*scale,
            large=large
        )
        draw_rain(layer, cx, cy+3*scale, scale*(1.15 if large else 0.78),
                  heavy=code in (65, 67, 82))

    elif code in (71, 73, 75, 77, 85, 86):
        draw_cloud(
            layer, cx, cy-4*scale,
            (1.18 if large else 0.68)*scale,
            large=large
        )
        draw_snow(layer, cx, cy+2*scale, scale*(1.15 if large else 0.8))

    elif code in (95, 96, 99):
        draw_cloud(
            layer, cx, cy-5*scale,
            (1.18 if large else 0.68)*scale,
            dark=True,
            large=large
        )
        draw_rain(layer, cx, cy+2*scale, scale*(1.1 if large else 0.76), heavy=True)
        draw_lightning(layer, cx, cy+2*scale, scale*(1.15 if large else 0.75))

    else:
        draw_cloud(layer, cx, cy, 0.7*scale, large=large)

def draw_drop_icon(draw, x, y):
    pts = [(x+7, y), (x+2, y+9), (x+2, y+13),
           (x+4, y+16), (x+7, y+18), (x+10, y+16),
           (x+12, y+13), (x+12, y+9)]
    draw.line(pts + [pts[0]], fill=(220, 241, 255, 235), width=2, joint="curve")

def draw_wind_icon(draw, x, y):
    draw.arc((x, y, x+18, y+9), 200, 350, fill=(220,241,255,235), width=2)
    draw.arc((x+2, y+5, x+22, y+14), 190, 342, fill=(220,241,255,235), width=2)
    draw.arc((x, y+10, x+16, y+17), 200, 345, fill=(220,241,255,235), width=2)

def draw_pressure_icon(draw, x, y):
    draw.ellipse((x, y, x+18, y+18), outline=(220,241,255,235), width=2)
    draw.line((x+9, y+9, x+14, y+5), fill=(220,241,255,235), width=2)

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

# ----- CURRENT CONDITIONS -----
draw.text((37, 22), "Vancouver", font=F_CITY, fill=(250,253,255,255))
draw.text((39, 61), now.strftime("%A"), font=F_DAY, fill=(239,248,255,245))

# Stats with icons
y0 = 103
draw_drop_icon(draw, 39, y0)
draw.text((66, y0+1), f"{humidity}%", font=F_STAT, fill=(223,241,255,240))

draw_wind_icon(draw, 38, y0+31)
draw.text((66, y0+32), f"{direction}, {wind} km/h",
          font=F_STAT, fill=(223,241,255,240))

draw_pressure_icon(draw, 39, y0+64)
draw.text((66, y0+65), f"{pressure} hPa",
          font=F_STAT, fill=(223,241,255,240))

# Large current icon
current_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
draw_weather_icon(current_layer, code, 386, 108, scale=1.0, large=True)
img.alpha_composite(current_layer)

draw = ImageDraw.Draw(img)

# Temperature top right
temperature = f"{temp:+d}°C"
bb = draw.textbbox((0,0), temperature, font=F_TEMP)
draw.text(
    (WIDTH - 34 - (bb[2]-bb[0]), 24),
    temperature,
    font=F_TEMP,
    fill=(250,253,255,250)
)

center_text(
    draw,
    (270, 169, 505, 194),
    condition(code),
    F_COND,
    (224,242,255,238)
)

# ----- 7-DAY FORECAST -----
margin = 22
gap = 7
tile_y = 205
tile_h = 148
tile_w = (WIDTH - margin*2 - gap*6) // 7

for i in range(7):
    x = margin + i*(tile_w + gap)

    # Soft tile shadow
    sh = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle(
        (x+2, tile_y+4, x+tile_w+2, tile_y+tile_h+4),
        radius=13,
        fill=(0, 25, 70, 65)
    )
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    img.alpha_composite(sh)

    # Darker glass tile
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (x, tile_y, x+tile_w, tile_y+tile_h),
        radius=13,
        fill=(72, 125, 190, 112 if i == 0 else 92),
        outline=(210, 238, 255, 105),
        width=1
    )

    # Top gloss strip
    gloss = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    gd = ImageDraw.Draw(gloss)
    gd.rounded_rectangle(
        (x+2, tile_y+2, x+tile_w-2, tile_y+43),
        radius=11,
        fill=(220, 245, 255, 18)
    )
    img.alpha_composite(gloss)

    dt = datetime.strptime(daily["time"][i], "%Y-%m-%d")
    day = dt.strftime("%a").upper()

    forecast_code = int(daily["weather_code"][i])

    tile_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    draw_weather_icon(
        tile_layer,
        forecast_code,
        x + tile_w//2,
        tile_y + 39,
        scale=0.80,
        large=False
    )
    img.alpha_composite(tile_layer)

    draw = ImageDraw.Draw(img)

    center_text(
        draw,
        (x, tile_y+74, x+tile_w, tile_y+100),
        day,
        F_TILE_DAY,
        (210,238,255,248)
    )

    hi = round(daily["temperature_2m_max"][i])
    lo = round(daily["temperature_2m_min"][i])

    center_text(
        draw,
        (x, tile_y+101, x+tile_w, tile_y+126),
        f"{hi:+d}° / {lo:+d}°",
        F_TILE_TEMP,
        (248,252,255,252)
    )

    rain = round(daily["precipitation_probability_max"][i] or 0)

    center_text(
        draw,
        (x, tile_y+127, x+tile_w, tile_y+144),
        f"{rain}% rain",
        F_TILE_RAIN,
        (190,225,250,225)
    )

img.convert("RGB").save("vancouver.png", "PNG", optimize=True)
print("Generated polished 770x373 Vancouver weather PNG")
'''

path = Path("/mnt/data/generate_weather_polished.py")
path.write_text(code, encoding="utf-8")

# syntax check
py_compile.compile(str(path), doraise=True)

print(f"Created and syntax-checked: {path}")
