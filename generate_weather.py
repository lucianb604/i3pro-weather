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
F_DAY = font(19)
F_TEMP = font(54)
F_STAT = font(12)
F_COND = font(11)
F_TILE_DAY = font(16)
F_TILE_TEMP = font(13)
F_TILE_RAIN = font(9)

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

def centered(draw, box, text, fnt, fill):
    x1, y1, x2, y2 = box
    bb = draw.textbbox((0, 0), text, font=fnt)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    draw.text((x1+(x2-x1-tw)/2, y1+(y2-y1-th)/2),
              text, font=fnt, fill=fill)

def make_background():
    raw = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    px = raw.load()
    for y in range(HEIGHT):
        gy = y / HEIGHT
        for x in range(WIDTH):
            gx = x / WIDTH
            center = math.exp(-(((gx-.57)/.43)**2 + ((gy-.10)/.55)**2))
            lower = math.exp(-(((gx-.52)/.70)**2 + ((gy-.78)/.55)**2))
            edge = min(1, abs(gx-.5)*2)
            r = 2 + 7*center
            g = 48 + 110*center + 12*lower - 22*edge
            b = 118 + 118*center + 15*lower - 12*edge
            px[x,y] = (
                int(max(0,min(255,r))),
                int(max(0,min(255,g))),
                int(max(0,min(255,b)))
            )

    img = raw.convert("RGBA")

    bloom = Image.new("RGBA", img.size, (0,0,0,0))
    bd = ImageDraw.Draw(bloom)
    bd.ellipse((220,-145,720,155), fill=(120,230,255,48))
    bloom = bloom.filter(ImageFilter.GaussianBlur(50))
    img.alpha_composite(bloom)

    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((1,1,WIDTH-2,HEIGHT-2), radius=28, fill=255)

    rounded = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
    rounded.paste(img, (0,0), mask)

    rd = ImageDraw.Draw(rounded)
    rd.rounded_rectangle((1,1,WIDTH-2,HEIGHT-2), radius=28,
                         outline=(220,245,255,55), width=1)
    return rounded

def ellipse_gradient(size, inner, outer):
    w,h = size
    img = Image.new("RGBA", size, (0,0,0,0))
    px = img.load()
    cx, cy = w/2, h/2
    rx, ry = w/2, h/2
    for y in range(h):
        for x in range(w):
            d = min(1.0, math.sqrt(((x-cx)/rx)**2 + ((y-cy)/ry)**2))
            t = d
            px[x,y] = tuple(int(inner[i]*(1-t)+outer[i]*t) for i in range(4))
    return img

def draw_sun(layer, cx, cy, r, large=False):
    glow = Image.new("RGBA", layer.size, (0,0,0,0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((cx-r*1.9, cy-r*1.9, cx+r*1.9, cy+r*1.9),
               fill=(255,205,40,105 if large else 70))
    glow = glow.filter(ImageFilter.GaussianBlur(max(7,int(r*.55))))
    layer.alpha_composite(glow)

    d = ImageDraw.Draw(layer)
    for angle in range(0,360,14 if large else 24):
        a = math.radians(angle)
        d.line((cx+math.cos(a)*(r+3), cy+math.sin(a)*(r+3),
                cx+math.cos(a)*(r+(18 if large else 9)),
                cy+math.sin(a)*(r+(18 if large else 9))),
               fill=(255,229,80,170), width=2 if large else 1)

    grad = ellipse_gradient((r*2+1, r*2+1),
                            (255,238,95,255),(255,168,10,255))
    layer.alpha_composite(grad, (int(cx-r), int(cy-r)))

def draw_cloud(layer, cx, cy, scale=1.0, dark=False, large=False):
    shadow = Image.new("RGBA", layer.size, (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((cx-60*scale, cy-10*scale, cx+76*scale, cy+42*scale),
               fill=(0,28,70,85 if large else 50))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10 if large else 5))
    layer.alpha_composite(shadow)

    cloud = Image.new("RGBA", layer.size, (0,0,0,0))
    d = ImageDraw.Draw(cloud)

    if dark:
        top = (188,204,220,255)
        mid = (126,151,186,255)
        low = (76,111,162,230)
    else:
        top = (255,255,255,255)
        mid = (229,241,250,255)
        low = (137,185,224,220)

    # lower body
    d.rounded_rectangle(
        (cx-52*scale, cy-3*scale, cx+70*scale, cy+31*scale),
        radius=max(5,int(15*scale)),
        fill=low
    )

    # puffs
    puffs = [(-40,-4,25),(-18,-28,31),(15,-39,35),(47,-20,29)]
    for ox,oy,rr in puffs:
        d.ellipse((cx+(ox-rr)*scale, cy+(oy-rr)*scale,
                   cx+(ox+rr)*scale, cy+(oy+rr)*scale),
                  fill=mid)

    # highlights
    d.ellipse((cx-34*scale, cy-28*scale, cx+18*scale, cy+8*scale),
              fill=top)
    d.ellipse((cx+2*scale, cy-42*scale, cx+50*scale, cy-3*scale),
              fill=(255,255,255,220))

    # soft dimensional shading
    shade = Image.new("RGBA", layer.size, (0,0,0,0))
    shd = ImageDraw.Draw(shade)
    shd.ellipse((cx-50*scale, cy+4*scale, cx+68*scale, cy+33*scale),
                fill=(65,115,180,70 if not dark else 110))
    shade = shade.filter(ImageFilter.GaussianBlur(6 if large else 3))
    cloud.alpha_composite(shade)

    cloud = cloud.filter(ImageFilter.GaussianBlur(.6 if large else .25))
    layer.alpha_composite(cloud)

def draw_rain(layer, cx, cy, scale=1.0, heavy=False):
    d = ImageDraw.Draw(layer)
    xs = (-28,-10,8,26) if heavy else (-20,0,20)
    for dx in xs:
        d.line((cx+dx*scale, cy+19*scale,
                cx+(dx-5)*scale, cy+35*scale),
               fill=(92,206,255,240), width=max(1,int(2.3*scale)))

def draw_snow(layer, cx, cy, scale=1.0):
    d = ImageDraw.Draw(layer)
    for dx in (-20,0,20):
        x = cx+dx*scale
        y = cy+27*scale
        r = 3.5*scale
        for a in (0,45,90,135):
            rad = math.radians(a)
            d.line((x-math.cos(rad)*r, y-math.sin(rad)*r,
                    x+math.cos(rad)*r, y+math.sin(rad)*r),
                   fill=(238,251,255,245), width=1)

def draw_lightning(layer, cx, cy, scale=1.0):
    d = ImageDraw.Draw(layer)
    pts = [(cx+5*scale,cy+12*scale),(cx-6*scale,cy+31*scale),
           (cx+2*scale,cy+31*scale),(cx-5*scale,cy+50*scale),
           (cx+16*scale,cy+24*scale),(cx+7*scale,cy+24*scale)]
    d.polygon(pts, fill=(115,225,255,255))

def weather_icon(layer, code, cx, cy, scale=1.0, large=False):
    if code == 0:
        draw_sun(layer,cx,cy,(33 if large else 15)*scale,large)
    elif code in (1,2):
        draw_sun(layer,cx-(27 if large else 13)*scale,
                 cy-(18 if large else 10)*scale,
                 (31 if large else 14)*scale,large)
        draw_cloud(layer,cx+(13 if large else 7)*scale,
                   cy+(9 if large else 5)*scale,
                   (1.22 if large else .63)*scale,large=large)
    elif code in (3,45,48):
        draw_cloud(layer,cx,cy,(1.32 if large else .72)*scale,large=large)
    elif code in (51,53,55,56,57,61,63,65,66,67,80,81,82):
        draw_cloud(layer,cx,cy-4*scale,(1.25 if large else .69)*scale,large=large)
        draw_rain(layer,cx,cy+2*scale,scale*(1.18 if large else .80),
                  heavy=code in (65,67,82))
    elif code in (71,73,75,77,85,86):
        draw_cloud(layer,cx,cy-4*scale,(1.25 if large else .69)*scale,large=large)
        draw_snow(layer,cx,cy+1*scale,scale*(1.18 if large else .80))
    elif code in (95,96,99):
        draw_cloud(layer,cx,cy-5*scale,(1.25 if large else .69)*scale,dark=True,large=large)
        draw_rain(layer,cx,cy+2*scale,scale*(1.14 if large else .77),heavy=True)
        draw_lightning(layer,cx,cy+1*scale,scale*(1.20 if large else .78))

def droplet(draw,x,y):
    pts=[(x+7,y),(x+2,y+9),(x+2,y+13),(x+4,y+16),
         (x+7,y+18),(x+10,y+16),(x+12,y+13),(x+12,y+9),(x+7,y)]
    draw.line(pts,fill=(220,241,255,235),width=2,joint="curve")

def wind_icon(draw,x,y):
    draw.arc((x,y,x+18,y+9),200,350,fill=(220,241,255,235),width=2)
    draw.arc((x+2,y+5,x+22,y+14),190,342,fill=(220,241,255,235),width=2)
    draw.arc((x,y+10,x+16,y+17),200,345,fill=(220,241,255,235),width=2)

def pressure_icon(draw,x,y):
    draw.ellipse((x,y,x+18,y+18),outline=(220,241,255,235),width=2)
    draw.line((x+9,y+9,x+14,y+5),fill=(220,241,255,235),width=2)

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
humidity = round(current.get("relative_humidity_2m",0))
pressure = round(current.get("pressure_msl",0))
wind = round(current.get("wind_speed_10m",0))
direction = wind_dir(float(current.get("wind_direction_10m",0)))

# Header/current conditions
draw.text((38,23),"Vancouver",font=F_CITY,fill=(250,253,255,255))
draw.text((40,61),now.strftime("%A"),font=F_DAY,fill=(239,248,255,245))

y0=102
droplet(draw,40,y0)
draw.text((67,y0+1),f"{humidity}%",font=F_STAT,fill=(223,241,255,240))
wind_icon(draw,39,y0+31)
draw.text((67,y0+32),f"{direction}, {wind} km/h",
          font=F_STAT,fill=(223,241,255,240))
pressure_icon(draw,40,y0+64)
draw.text((67,y0+65),f"{pressure} hPa",
          font=F_STAT,fill=(223,241,255,240))

# Large current artwork
art = Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
weather_icon(art,code,391,111,scale=1.0,large=True)
img.alpha_composite(art)

draw = ImageDraw.Draw(img)
temperature=f"{temp:+d}°C"
bb=draw.textbbox((0,0),temperature,font=F_TEMP)
draw.text((WIDTH-35-(bb[2]-bb[0]),24),temperature,font=F_TEMP,
          fill=(250,253,255,250))

centered(draw,(280,171,502,193),condition(code),F_COND,(224,242,255,238))

# Forecast tiles
margin=23
gap=8
tile_y=205
tile_h=147
tile_w=(WIDTH-margin*2-gap*6)//7

for i in range(7):
    x=margin+i*(tile_w+gap)

    shadow=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    sd=ImageDraw.Draw(shadow)
    sd.rounded_rectangle((x+2,tile_y+4,x+tile_w+2,tile_y+tile_h+4),
                         radius=13,fill=(0,22,60,72))
    shadow=shadow.filter(ImageFilter.GaussianBlur(5))
    img.alpha_composite(shadow)

    draw=ImageDraw.Draw(img)
    draw.rounded_rectangle((x,tile_y,x+tile_w,tile_y+tile_h),
                           radius=13,
                           fill=(48,92,160,118 if i==0 else 100),
                           outline=(205,235,255,92),
                           width=1)

    gloss=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    gd=ImageDraw.Draw(gloss)
    gd.rounded_rectangle((x+2,tile_y+2,x+tile_w-2,tile_y+40),
                         radius=11,fill=(230,248,255,18))
    img.alpha_composite(gloss)

    dt=datetime.strptime(daily["time"][i],"%Y-%m-%d")
    day=dt.strftime("%a").upper()
    fc=int(daily["weather_code"][i])

    ti=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    weather_icon(ti,fc,x+tile_w//2,tile_y+39,scale=.82,large=False)
    img.alpha_composite(ti)

    draw=ImageDraw.Draw(img)
    centered(draw,(x,tile_y+73,x+tile_w,tile_y+98),
             day,F_TILE_DAY,(209,237,255,248))

    hi=round(daily["temperature_2m_max"][i])
    lo=round(daily["temperature_2m_min"][i])
    centered(draw,(x,tile_y+101,x+tile_w,tile_y+124),
             f"{hi:+d}° / {lo:+d}°",F_TILE_TEMP,(248,252,255,252))

    rain=round(daily["precipitation_probability_max"][i] or 0)
    centered(draw,(x,tile_y+126,x+tile_w,tile_y+142),
             f"{rain}% rain",F_TILE_RAIN,(190,225,250,220))

img.convert("RGB").save("vancouver.png","PNG",optimize=True)
print("Generated premium 770x373 Vancouver weather PNG")
'''

path = Path("/mnt/data/generate_weather_v3.py")
path.write_text(code, encoding="utf-8")
py_compile.compile(str(path), doraise=True)
print(path)
