from PIL import Image, ImageDraw, ImageFont
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

LAT = 49.2827
LON = -123.1207
TZ = "America/Vancouver"

WIDTH = 1200
HEIGHT = 420

URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&current=temperature_2m,weather_code"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    "&timezone=America%2FVancouver"
    "&forecast_days=7"
)

def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

F_TITLE = font(34, True)
F_SUB = font(19)
F_BIG = font(48, True)
F_DAY = font(21, True)
F_DATE = font(16)
F_SMALL = font(16)

def condition(code):
    if code == 0: return "Clear"
    if code in (1,2): return "Partly cloudy"
    if code == 3: return "Cloudy"
    if code in (45,48): return "Fog"
    if code in (51,53,55,56,57): return "Drizzle"
    if code in (61,63,65,66,67,80,81,82): return "Rain"
    if code in (71,73,75,77,85,86): return "Snow"
    if code in (95,96,99): return "Storm"
    return "Weather"

def sun(draw, cx, cy, r=24):
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(245,190,70))
    for dx,dy in [(0,-42),(0,42),(-42,0),(42,0),(-30,-30),(30,-30),(-30,30),(30,30)]:
        draw.line(
            (cx+dx*.7, cy+dy*.7, cx+dx, cy+dy),
            fill=(245,190,70), width=4
        )

def cloud(draw, cx, cy, scale=1, fill=(225,232,240)):
    for box in [
        (cx-40*scale,cy-5*scale,cx+35*scale,cy+25*scale),
        (cx-28*scale,cy-25*scale,cx+8*scale,cy+16*scale),
        (cx-2*scale,cy-34*scale,cx+38*scale,cy+14*scale),
    ]:
        draw.ellipse(box, fill=fill)

def icon(draw, code, cx, cy):
    if code == 0:
        sun(draw,cx,cy)
    elif code in (1,2):
        sun(draw,cx-16,cy-12,18)
        cloud(draw,cx+6,cy+8,.85)
    elif code in (3,45,48):
        cloud(draw,cx,cy,1,(205,215,228))
    elif code in (51,53,55,56,57,61,63,65,66,67,80,81,82):
        cloud(draw,cx,cy-8,1,(205,215,228))
        for x in (cx-22,cx,cx+22):
            draw.line((x,cy+26,x-5,cy+44), fill=(90,165,230), width=4)
    elif code in (71,73,75,77,85,86):
        cloud(draw,cx,cy-8,1,(215,225,235))
        for x in (cx-22,cx,cx+22):
            draw.ellipse((x-3,cy+30,x+3,cy+36), fill=(245,248,252))
    elif code in (95,96,99):
        cloud(draw,cx,cy-10,1,(190,200,216))
        draw.polygon(
            [(cx+2,cy+12),(cx-10,cy+36),(cx+2,cy+36),
             (cx-5,cy+58),(cx+18,cy+28),(cx+7,cy+28)],
            fill=(247,195,70)
        )
    else:
        cloud(draw,cx,cy)

def centered(draw, box, text, fnt, fill):
    x1,y1,x2,y2 = box
    bb = draw.textbbox((0,0), text, font=fnt)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((x1+(x2-x1-tw)/2, y1+(y2-y1-th)/2), text, font=fnt, fill=fill)

r = requests.get(URL, timeout=20)
r.raise_for_status()
data = r.json()
daily = data["daily"]
current = data["current"]

img = Image.new("RGB", (WIDTH, HEIGHT), (18,24,34))
draw = ImageDraw.Draw(img)

for y in range(HEIGHT):
    t = y/(HEIGHT-1)
    c = (int(19+18*t), int(29+18*t), int(43+28*t))
    draw.line((0,y,WIDTH,y), fill=c)

# Current panel
draw.rounded_rectangle((24,24,286,396), radius=26,
                       fill=(28,38,52), outline=(64,82,104), width=2)
draw.text((46,42), "Vancouver", font=F_TITLE, fill=(245,248,252))
updated = datetime.now(ZoneInfo(TZ)).strftime("Updated %a %I:%M %p")
draw.text((46,82), updated, font=F_SUB, fill=(178,191,205))

cc = int(current["weather_code"])
ct = round(current["temperature_2m"])
icon(draw, cc, 156, 170)
centered(draw,(46,205,266,272), f"{ct}°C", F_BIG, (248,250,252))
centered(draw,(46,270,266,300), condition(cc), F_SUB, (196,208,220))

hi0 = round(daily["temperature_2m_max"][0])
lo0 = round(daily["temperature_2m_min"][0])
pop0 = round(daily["precipitation_probability_max"][0])
draw.text((46,324), f"Today: {hi0}° / {lo0}°", font=F_SUB, fill=(244,247,251))
draw.text((46,352), f"Precipitation: {pop0}%", font=F_SUB, fill=(116,188,245))

# 7-day cards
left = 304
gap = 12
right = 24
card_w = (WIDTH-left-right-gap*6)//7

for i in range(7):
    x = left + i*(card_w+gap)
    y = 24
    draw.rounded_rectangle((x,y,x+card_w,396), radius=22,
                           fill=(31,41,55), outline=(67,83,102), width=2)

    dt = datetime.strptime(daily["time"][i], "%Y-%m-%d")
    day = "Today" if i == 0 else dt.strftime("%a")
    date = dt.strftime("%b %d")

    centered(draw,(x,y+18,x+card_w,y+48), day, F_DAY, (248,250,252))
    centered(draw,(x,y+48,x+card_w,y+72), date, F_DATE, (164,180,196))

    code = int(daily["weather_code"][i])
    icon(draw, code, x+card_w//2, y+125)

    hi = round(daily["temperature_2m_max"][i])
    lo = round(daily["temperature_2m_min"][i])
    centered(draw,(x+6,y+168,x+card_w-6,y+198),
             f"{hi}° / {lo}°", F_DAY, (248,250,252))
    centered(draw,(x+4,y+208,x+card_w-4,y+238),
             condition(code), F_SMALL, (196,207,220))

    pop = round(daily["precipitation_probability_max"][i])
    centered(draw,(x+4,y+334,x+card_w-4,y+360),
             f"Rain {pop}%", F_SMALL, (116,188,245))

img.save("vancouver.png", "PNG", optimize=True)
print("Generated vancouver.png")
