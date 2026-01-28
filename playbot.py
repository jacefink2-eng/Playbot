import time
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ffmpeg
from datetime import datetime
from io import BytesIO

# ---------------- SETTINGS ----------------
WIDTH, HEIGHT = 1280, 720
FPS = 60
YOUTUBE_STREAM_KEY = ""
YOUTUBE_URL = f"rtmp://a.rtmp.youtube.com/live2/fvgb-pzbe-4j7g-vej0-6g7q"

# Fonts
FONT_LARGE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
FONT_MED   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
FONT_SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)

# Alert priority (OLD + NEW)
PRIORITY = {
    "Tornado Emergency": 100,
    "Tornado Warning": 95,
    "Extreme Wind Warning": 90,
    "Hurricane Warning": 88,
    "Hurricane Watch": 85,
    "Severe Thunderstorm Warning": 80,
    "Flash Flood Warning": 75,
    "High Wind Warning": 70,
    "Tornado Watch": 60,
    "High Wind Watch": 55,
    "Severe Thunderstorm Watch": 50
}

# ---------------- TIME HELPERS ----------------
def now_in(start, end):
    return start <= datetime.now() <= end

def synthetic_alerts():
    alerts = []

    OR_WA = "Oregon / Washington"
    PLAINS = "South Dakota / North Dakota / Minnesota"

    now = datetime.now()

    # 🌪️ Hurricane Watch
    if datetime(2026, 1, 27, 18, 0) <= now <= datetime(2026, 1, 28, 7, 0):
        alerts.append({
            "event": "Hurricane Watch",
            "area": OR_WA,
            "severity": PRIORITY["Hurricane Watch"]
        })

    # 🚨 Hurricane Warning
    if datetime(2026, 1, 28, 10, 5) <= now <= datetime(2026, 1, 28, 12, 30):
        alerts.append({
            "event": "Hurricane Warning",
            "area": OR_WA,
            "severity": PRIORITY["Hurricane Warning"]
        })

    # 💨 Extreme Wind Warning
    if datetime(2026, 1, 28, 12, 30) <= now <= datetime(2026, 1, 28, 18, 0):
        alerts.append({
            "event": "Extreme Wind Warning",
            "area": OR_WA,
            "severity": PRIORITY["Extreme Wind Warning"]
        })

    # 🌬️ High Wind Watch (Plains)
    if datetime(2026, 1, 27, 21, 0) <= now <= datetime(2026, 1, 28, 10, 0):
        alerts.append({
            "event": "High Wind Watch",
            "area": PLAINS,
            "severity": PRIORITY["High Wind Watch"]
        })

    # ⚠️ High Wind Warning (Plains)
    if datetime(2026, 1, 28, 10, 25) <= now <= datetime(2026, 1, 28, 23, 0):
        alerts.append({
            "event": "High Wind Warning",
            "area": PLAINS,
            "severity": PRIORITY["High Wind Warning"]
        })

    return alerts


# ---------------- START RTMP STREAM ----------------
def start_stream():
    print("🚀 Starting Y’allBot RTMP stream (silent audio)...")

    video = ffmpeg.input(
        "pipe:",
        format="rawvideo",
        pix_fmt="rgb24",
        s=f"{WIDTH}x{HEIGHT}",
        framerate=FPS
    )

    audio = ffmpeg.input(
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        format="lavfi"
    )

    stream = (
        ffmpeg
        .output(
            video,
            audio,
            YOUTUBE_URL,
            format="flv",
            vcodec="libx264",
            pix_fmt="yuv420p",
            acodec="aac",
            audio_bitrate="128k",
            preset="veryfast",
            g=FPS * 2,
            r=FPS,
            vsync="cfr"
        )
        .overwrite_output()
        .run_async(pipe_stdin=True)
    )

    # 🔴 Kick YouTube out of "No data"
    stream.stdin.write(np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8).tobytes())

    return stream



# ---------------- FETCH NOAA ALERTS ----------------
def fetch_noaa_alerts():
    alerts = []
    try:
        res = requests.get("https://api.weather.gov/alerts/active", timeout=8)
        for f in res.json().get("features", []):
            p = f.get("properties", {})
            event = p.get("event")
            if event in PRIORITY:
                alerts.append({
                    "event": event,
                    "area": p.get("areaDesc", ""),
                    "severity": PRIORITY[event]
                })
    except:
        pass

    # 🔹 KEEP OLD STUFF + ADD NEW STUFF
    alerts.extend(synthetic_alerts())

    alerts.sort(key=lambda x: x["severity"], reverse=True)
    return alerts

# ---------------- HELPER: Convert lat/lon to tile numbers ----------------
def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

# ---------------- FETCH TILE ----------------
def fetch_tile(x, y, zoom=6):
    url = f"https://a.tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    resp = requests.get(url, timeout=5)
    tile = Image.open(resp.raw).convert("RGB")
    return tile

# ---------------- BUILD MAP ----------------
def build_map_image(width=250, height=160, center_lat=40.0, center_lon=-100.0, zoom=6):
    """
    Build a map overlay by stitching OSM tiles.
    """
    cx, cy = deg2num(center_lat, center_lon, zoom)
    tiles = []
    for dx in range(2):  # 2x2 tiles
        for dy in range(2):
            tiles.append(fetch_tile(cx+dx, cy+dy, zoom))

    map_img = Image.new("RGB", (512, 512))
    for i, tile in enumerate(tiles):
        x = (i % 2) * 256
        y = (i // 2) * 256
        map_img.paste(tile, (x, y))

    map_img = map_img.resize((width, height))
    return map_img

# ---------------- DRAW ALERT MARKERS ----------------
def latlon_to_pixel(lat, lon, img_width, img_height, bounds):
    min_lat, max_lat, min_lon, max_lon = bounds
    x = int((lon - min_lon) / (max_lon - min_lon) * img_width)
    y = int((max_lat - lat) / (max_lat - min_lat) * img_height)
    return x, y

def add_alert_markers(map_img, alerts):
    bounds = (24.0, 50.0, -125.0, -66.0)  # continental USA approx
    draw = ImageDraw.Draw(map_img)
    for a in alerts:
        area = a['area']
        color = (255,0,0) if "Warning" in a['event'] else (255,140,0)
        # Approx coordinates
        if "Oregon" in area or "Washington" in area:
            x, y = latlon_to_pixel(46.0, -120.5, map_img.width, map_img.height, bounds)
        elif "South Dakota" in area:
            x, y = latlon_to_pixel(44.5, -99.5, map_img.width, map_img.height, bounds)
        elif "North Dakota" in area:
            x, y = latlon_to_pixel(47.5, -100.5, map_img.width, map_img.height, bounds)
        elif "Minnesota" in area:
            x, y = latlon_to_pixel(46.5, -93.0, map_img.width, map_img.height, bounds)
        else:
            continue
        draw.ellipse((x-6, y-6, x+6, y+6), fill=color)
    return map_img

# ---------------- UPDATED DRAW FRAME ----------------
def draw_frame(alerts, ticker_x):
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(pil)

    # HEADER
    draw.rectangle((0,0,WIDTH,40), fill=(0,0,0))
    draw.text((10,5),"PlayBot 24/7 USA Weather Alerts", font=FONT_LARGE, fill=(255,255,255))

    # TOP ALERT
    if alerts:
        top = alerts[0]
        color = (255,0,0) if "Warning" in top['event'] else (255,140,0)
        draw.rectangle((0,50,WIDTH,100), fill=color)
        draw.text((10,55), f"{top['event']} — {top['area']}", font=FONT_MED, fill=(0,0,0))

    # ACTIVE ALERTS BOX
    draw.rectangle((WIDTH-280,110,WIDTH-10,270), fill=(20,20,20))
    draw.text((WIDTH-270,120),"Active Alerts", font=FONT_MED, fill=(255,255,255))
    y = 155
    for a in alerts[:6]:
        draw.text((WIDTH-270,y),a['event'], font=FONT_SMALL, fill=(255,0,0))
        y += 24

    # MAP OVERLAY
    map_img = build_map_image(width=250, height=160)
    map_img = add_alert_markers(map_img, alerts)
    pil.paste(map_img,(WIDTH-270,280))

    # TICKER
    crawl = " | ".join([f"{a['event']} - {a['area']}" for a in alerts])
    draw.rectangle((0,HEIGHT-60,WIDTH,HEIGHT), fill=(0,0,0))
    draw.text((ticker_x, HEIGHT-45), crawl, font=FONT_MED, fill=(255,0,0))

    return np.array(pil), len(crawl)*12




# ---------------- MAIN LOOP ----------------
def main():
    ticker_x = WIDTH
    last_alert = 0
    alerts = []

    while True:
        streamer = start_stream()
        try:
            while True:
                if time.time() - last_alert > 30:
                    alerts = fetch_noaa_alerts()
                    last_alert = time.time()

                frame, crawl_width = draw_frame(alerts, ticker_x)
                ticker_x -= 5
                if ticker_x < -crawl_width:
                    ticker_x = WIDTH

                streamer.stdin.write(frame.tobytes())
                time.sleep(1/FPS)
        except:
            time.sleep(10)

if __name__ == "__main__":
    main()
