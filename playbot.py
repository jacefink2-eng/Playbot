import time
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ffmpeg
from datetime import datetime

# ---------------- SETTINGS ----------------
WIDTH, HEIGHT = 1280, 720
FPS = 5
YOUTUBE_STREAM_KEY = "fvgb-pzbe-4j7g-vej0-6g7q"
YOUTUBE_URL = f"rtmp://a.rtmp.youtube.com/live2/{YOUTUBE_STREAM_KEY}"

# Fonts
FONT_LARGE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
FONT_MED   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
FONT_SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)

# Alert priority
PRIORITY = {
    "Tornado Emergency": 100,
    "Tornado Warning": 95,
    "Extreme Wind Warning": 90,
    "Hurricane Warning": 88,
    "Hurricane Watch": 85,
    "High Wind Warning": 70,
    "High Wind Watch": 60,
    "Severe Thunderstorm Warning": 80,
    "Flash Flood Warning": 75
}

# ---------------- TIME WINDOWS ----------------
def in_window(start, end):
    now = datetime.now()
    return start <= now <= end

def synthetic_alerts():
    alerts = []
    now = datetime.now()

    OR_WA = "Oregon / Washington"
    PLAINS = "South Dakota / North Dakota / Minnesota"

    if in_window(datetime(2026,1,27,18,0), datetime(2026,1,28,7,0)):
        alerts.append({"event":"Hurricane Watch","area":OR_WA,"severity":PRIORITY["Hurricane Watch"]})

    if in_window(datetime(2026,1,28,10,5), datetime(2026,1,28,12,30)):
        alerts.append({"event":"Hurricane Warning","area":OR_WA,"severity":PRIORITY["Hurricane Warning"]})

    if in_window(datetime(2026,1,28,12,30), datetime(2026,1,28,18,0)):
        alerts.append({"event":"Extreme Wind Warning","area":OR_WA,"severity":PRIORITY["Extreme Wind Warning"]})

    if in_window(datetime(2026,1,27,21,0), datetime(2026,1,28,10,0)):
        alerts.append({"event":"High Wind Watch","area":PLAINS,"severity":PRIORITY["High Wind Watch"]})

    if in_window(datetime(2026,1,28,10,25), datetime(2026,1,28,23,0)):
        alerts.append({"event":"High Wind Warning","area":PLAINS,"severity":PRIORITY["High Wind Warning"]})

    return alerts

# ---------------- START RTMP STREAM ----------------
def start_stream():
    print("🚀 Starting Y’allBot RTMP stream (silent audio enabled)...")
    return (
        ffmpeg
        .input("pipe:", format="rawvideo", pix_fmt="rgb24",
               s=f"{WIDTH}x{HEIGHT}", framerate=FPS)
        .input("anullsrc", format="lavfi")
        .output(
            YOUTUBE_URL,
            format="flv",
            vcodec="libx264",
            pix_fmt="yuv420p",
            acodec="aac",
            preset="veryfast",
            g=FPS*2,
            audio_bitrate="128k"
        )
        .overwrite_output()
        .run_async(pipe_stdin=True)
    )

# ---------------- FETCH NOAA ALERTS ----------------
def fetch_noaa_alerts():
    alerts = []
    try:
        res = requests.get("https://api.weather.gov/alerts/active", timeout=8)
        for f in res.json().get("features", []):
            p = f["properties"]
            if p["event"] in PRIORITY:
                alerts.append({
                    "event": p["event"],
                    "area": p.get("areaDesc",""),
                    "severity": PRIORITY[p["event"]]
                })
    except:
        pass

    alerts.extend(synthetic_alerts())
    alerts.sort(key=lambda x: x["severity"], reverse=True)
    return alerts

# ---------------- DRAW FRAME ----------------
def draw_frame(alerts, ticker_x):
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(pil)

    draw.rectangle((0,0,WIDTH,40), fill=(0,0,0))
    draw.text((10,5),"Y’allBot 24/7 USA Weather Alerts",font=FONT_LARGE,fill=(255,255,255))

    if alerts:
        top = alerts[0]
        color = (255,0,0) if "Warning" in top["event"] else (255,140,0)
        draw.rectangle((0,50,WIDTH,100), fill=color)
        draw.text((10,55), f"{top['event']} — {top['area']}", font=FONT_MED, fill=(0,0,0))

    draw.rectangle((WIDTH-280,110,WIDTH-10,270), fill=(20,20,20))
    draw.text((WIDTH-270,120),"Active Alerts",font=FONT_MED,fill=(255,255,255))

    y=155
    for a in alerts[:6]:
        draw.text((WIDTH-270,y),a["event"],font=FONT_SMALL,fill=(255,0,0))
        y+=24

    crawl=" | ".join([f"{a['event']} - {a['area']}" for a in alerts])
    draw.rectangle((0,HEIGHT-60,WIDTH,HEIGHT),fill=(0,0,0))
    draw.text((ticker_x,HEIGHT-45),crawl,font=FONT_MED,fill=(255,0,0))

    return np.array(pil), len(crawl)*12

# ---------------- MAIN LOOP ----------------
def main():
    ticker_x = WIDTH
    last_alert = 0
    alerts = []

    streamer = start_stream()

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

if __name__ == "__main__":
    main()
