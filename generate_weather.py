from PIL import Image, ImageDraw, ImageFont, ImageFilter
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
    path = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    return ImageFont.truetype(path, size)

F_CITY = font(28, True)
F_DAY = font(20)
F_TEMP = font(50)
F_STAT = font(13)
F_TILE_DAY = font(16)
F_TILE_TEMP = font(13)
F_SMALL = font(10)

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
    names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return names[int((deg + 22.5) // 45) % 8]

def centered(draw, box, text, fnt, colour):
    x1, y1, x2, y2 = box
    b = draw.textbbox((0, 0), text, font=fnt)
    w = b[2] - b[0]
    h = b[3] - b[1]
    draw.text(
        (x1 + (x2-x1-w)/2, y1 + (y2-y1-h)/2),
        text,
        font=fnt,
        fill=colour
    )

def make_background():
    img = Image.new("RGB", (WIDTH, HEIGHT))
    p = img.load()

    for y in range(HEIGHT):
        for x in range(WIDTH):
            gx = x / WIDTH
            gy = y / HEIGHT

            glow = math.exp(
                -(((gx - .55) / .42) ** 2 +
                  ((gy - .12) / .65) ** 2)
            )

            edge = abs(gx - .5) * 2

            p[x, y] = (
                int(5 + 10 * glow),
                int(55 + 115 * glow - edge * 18),
                int(130 + 100 * glow - edge * 15)
            )

    return img.convert("RGBA")

def sun(layer, cx, cy, r):
    glow = Image.new("RGBA", layer.size)
    gd = ImageDraw.Draw(glow)

    gd.ellipse(
        (cx-r*1.7, cy-r*1.7,
         cx+r*1.7, cy+r*1.7),
        fill=(255, 210, 35, 100)
    )

    glow = glow.filter(ImageFilter.GaussianBlur(12))
    layer.alpha_composite(glow)

    d = ImageDraw.Draw(layer)

    for angle in range(0, 360, 20):
        a = math.radians(angle)

        d.line(
            (
                cx + math.cos(a)*(r+3),
                cy + math.sin(a)*(r+3),
                cx + math.cos(a)*(r+14),
                cy + math.sin(a)*(r+14)
            ),
            fill=(255, 225, 60, 180),
            width=2
        )

    d.ellipse(
        (cx-r, cy-r, cx+r, cy+r),
        fill=(255, 200, 25, 255)
    )

def cloud(layer, cx, cy, scale=.8, dark=False):
    d = ImageDraw.Draw(layer)

    c = (
        (185, 198, 215, 250)
        if dark else
        (248, 251, 255, 250)
    )

    shapes = [
        (-40, -5, 40, 22),
        (-28, -23, 16, 20),
        (-4, -34, 43, 20),
        (18, -20, 59, 22)
    ]

    for x1, y1, x2, y2 in shapes:
        d.ellipse(
            (
                cx+x1*scale,
                cy+y1*scale,
                cx+x2*scale,
                cy+y2*scale
            ),
            fill=c
        )

def weather_icon(layer, code, cx, cy, scale=1):
    if code == 0:
        sun(layer, cx, cy, 20*scale)

    elif code in (1, 2):
        sun(layer, cx-15*scale, cy-12*scale, 19*scale)
        cloud(layer, cx+7*scale, cy+6*scale, .8*scale)

    elif code in (3, 45, 48):
        cloud(layer, cx, cy, .9*scale)

    elif code in (51,53,55,56,57,61,63,65,66,67,80,81,82):
        cloud(layer, cx, cy-4, .85*scale)
        d = ImageDraw.Draw(layer)

        for dx in (-15, 0, 15):
            d.line(
                (cx+dx, cy+18, cx+dx-4, cy+30),
                fill=(120, 210, 255, 255),
                width=2
            )

    elif code in (71,73,75,77,85,86):
        cloud(layer, cx, cy-4, .85*scale)

        d = ImageDraw.Draw(layer)

        for dx in (-15, 0, 15):
            d.ellipse(
                (cx+dx-2, cy+20,
                 cx+dx+2, cy+24),
                fill="white"
            )

    else:
        cloud(layer, cx, cy-5, .85*scale, True)

        d = ImageDraw.Draw(layer)

        d.polygon(
            [
                (cx+3, cy+15),
                (cx-5, cy+31),
                (cx+2, cy+31),
                (cx-5, cy+46),
                (cx+12, cy+25),
                (cx+5, cy+25)
            ],
            fill=(120, 220, 255, 255)
        )

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
humidity = round(current["relative_humidity_2m"])
pressure = round(current["pressure_msl"])
wind = round(current["wind_speed_10m"])
direction = wind_dir(current["wind_direction_10m"])

# ---------------------------
# CURRENT WEATHER - TOP
# ---------------------------

draw.text(
    (38, 22),
    "Vancouver",
    font=F_CITY,
    fill="white"
)

draw.text(
    (40, 62),
    now.strftime("%A"),
    font=F_DAY,
    fill=(240, 248, 255)
)

draw.text(
    (40, 106),
    f"Humidity  {humidity}%",
    font=F_STAT,
    fill=(220, 240, 255)
)

draw.text(
    (40, 132),
    f"Wind  {direction}, {wind} km/h",
    font=F_STAT,
    fill=(220, 240, 255)
)

draw.text(
    (40, 158),
    f"Pressure  {pressure} hPa",
    font=F_STAT,
    fill=(220, 240, 255)
)

# Large current icon
layer = Image.new(
    "RGBA",
    (WIDTH, HEIGHT),
    (0,0,0,0)
)

weather_icon(
    layer,
    code,
    390,
    105,
    2.25
)

img.alpha_composite(layer)

draw = ImageDraw.Draw(img)

# Current temperature
temperature = f"{temp:+d}°C"

bbox = draw.textbbox(
    (0,0),
    temperature,
    font=F_TEMP
)

draw.text(
    (
        WIDTH - 35 - (bbox[2]-bbox[0]),
        25
    ),
    temperature,
    font=F_TEMP,
    fill="white"
)

centered(
    draw,
    (280, 170, 500, 195),
    condition(code),
    F_SMALL,
    (225, 243, 255)
)

# ---------------------------
# 7 DAY FORECAST
# ---------------------------

margin = 23
gap = 7

tile_y = 205
tile_h = 148

tile_w = (
    WIDTH -
    margin*2 -
    gap*6
) // 7

for i in range(7):

    x = margin + i*(tile_w+gap)

    # Glass tile
    draw.rounded_rectangle(
        (
            x,
            tile_y,
            x+tile_w,
            tile_y+tile_h
        ),
        radius=12,
        fill=(120, 175, 230, 75),
        outline=(210, 235, 255, 110),
        width=1
    )

    dt = datetime.strptime(
        daily["time"][i],
        "%Y-%m-%d"
    )

    day = dt.strftime("%a").upper()

    forecast_code = int(
        daily["weather_code"][i]
    )

    layer = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0,0,0,0)
    )

    weather_icon(
        layer,
        forecast_code,
        x + tile_w//2,
        tile_y + 39,
        .75
    )

    img.alpha_composite(layer)

    draw = ImageDraw.Draw(img)

    centered(
        draw,
        (
            x,
            tile_y+73,
            x+tile_w,
            tile_y+99
        ),
        day,
        F_TILE_DAY,
        (205,235,255)
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
            tile_y+101,
            x+tile_w,
            tile_y+125
        ),
        f"{high:+d}° / {low:+d}°",
        F_TILE_TEMP,
        "white"
    )

    rain = round(
        daily["precipitation_probability_max"][i] or 0
    )

    centered(
        draw,
        (
            x,
            tile_y+126,
            x+tile_w,
            tile_y+143
        ),
        f"{rain}% rain",
        F_SMALL,
        (195,225,245)
    )

img.convert("RGB").save(
    "vancouver.png",
    "PNG",
    optimize=True
)

print("Generated 770x373 Vancouver weather PNG")
