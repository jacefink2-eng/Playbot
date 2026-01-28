import os
import time
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ffmpeg
from datetime import datetime, timezone

# ------------------ STREAM SETTINGS ------------------
RTMP_URL = "rtmp://a.rtmp.youtube.com/live2"
STREAM_KEY = "fvgb-pzbe-4j7g-vej0-6g7q"
WIDTH, HEIGHT = 1280, 720
FPS = 5

# ------------------ FONTS ------------------
FONT_LARGE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
FONT_MED   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
FONT_SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)

# ------------------ ALERT PRIORITY ------------------
PRIORITY = {
    "Tornado Emergency": 100,
    "Tornado Warning": 95,
    "Hurricane Warning": 90,
    "Extreme Wind Warning": 85,
    "Severe Thunderstorm Warning": 80,
    "Flash Flood Warning": 75,
    "High Wind Warning": 70,
    "Hurricane Watch": 65,
    "Tornado Watch": 60,
    "High Wind Watch": 55,
    "Severe Thunderstorm Watch": 50
}

# ------------------ FFMPEG PROCESS ------------------
def start_ffmpeg():
    video = ffmpeg.input(
        'pipe:',
        format='rawvideo',
        pix_fmt='rgb24',
        s=f'{WIDTH}x{HEIGHT}',
        framerate=FPS
    )

    audio = ffmpeg.input('anullsrc=r=44100:cl=stereo', f='lavfi')

    return ffmpeg.output(
        video,
        audio,
        f"{RTMP_URL}/{STREAM_KEY}",
        format='flv',
        vcodec='libx264',
        pix_fmt='yuv420p',
        preset='veryfast',
        acodec='aac',
        audio_bitrate='128k'
    ).overwrite_output().run_async(pipe_stdin=True)

# ------------------ TIME-BASED INJECTED ALERTS ------------------
def injected_time_alerts():
    now = datetime.now(timezone.utc)
    alerts = []

    def between(start, end):
        return start <= now <= end

    # OREGON / WASHINGTON
    pnw = "Oregon; Washington"

    if between(datetime(2026,1,27,18,0,tzinfo=timezone.utc),
               datetime(2026,1,28,7,0,tzinfo=timezone.utc)):
        alerts.append({"event":"Hurricane Watch","area":pnw,"severity":PRIORITY["Hurricane Watch"]})

    if between(datetime(2026,1,28,10,5,tzinfo=timezone.utc),
               datetime(2026,1,28,12,30,tzinfo=timezone.utc)):
        alerts.append({"event":"Hurricane Warning","area":pnw,"severity":PRIORITY["Hurricane Warning"]})

    if between(datetime(2026,1,28,12,30,tzinfo=timezone.utc),
               datetime(2026,1,28,18,0,tzinfo=timezone.utc)):
        alerts.append({"event":"Extreme Wind Warning","area":pnw,"severity":PRIORITY["Extreme Wind Warning"]})

    # DAKOTAS / MINNESOTA
    plains = "South Dakota; North Dakota; Minnesota"

    if between(datetime(2026,1,27,21,0,tzinfo=timezone.utc),
               datetime(2026,1,28,10,0,tzinfo=timezone.utc)):
        alerts.append({"event":"High Wind Watch","area":plains,"severity":PRIORITY["High Wind Watch"]})

    if between(datetime(2026,1,28,10,25,tzinfo=timezone.utc),
               datetime(2026,1,28,23,0,tzinfo=timezone.utc)):
        alerts.append({"event":"High Wind Warning","area":plains,"severity":PRIORITY["High Wind Warning"]})

    return alerts

# ------------------ FETCH NOAA ALERTS ------------------
def fetch_noaa_alerts():
    alerts = []
    try:
        r = requests.get("https://api.weather.gov/alerts/active", timeout=8)
        data = r.json()

        for f in data.get("features", []):
            p = f.get("properties", {})
            event = p.get("event")
            if event in PRIORITY:
                alerts.append({
                    "event": event,
                    "area": p.get("areaDesc",""),
                    "severity": PRIORITY[event]
                })
    except:
        pass

    alerts.extend(injected_time_alerts())
    alerts.sort(key=lambda x: x["severity"], reverse=True)
    return alerts

# ------------------ DRAW FRAME ------------------
def draw_frame(alerts, ticker_x):
    # ... (previous code)
    
    # Title bar
    draw.text((10,5), "playBot 24/7 USA Weather Alerts", font=FONT_LARGE, fill=(255,255,255))

    # Top alert box
    if alerts:
        top = alerts[0]
        # ...
        draw.text((10,55), f"{top['event']} — {top['area']}", font=FONT_MED, fill=(0,0,0))

    # Side panel
    y = 155
    for a in alerts[:6]:
        draw.text((WIDTH-270,y), a["event"], font=FONT_SMALL, fill=(255,0,0))
        y += 24

    # Ticker
    crawl = " | ".join([f"{a['event']} - {a['area']}" for a in alerts]) if alerts else "No active alerts."
    draw.text((ticker_x, HEIGHT-45), crawl, font=FONT_MED, fill=(255,0,0))

    return np.array(pil), len(crawl)*12


# ------------------ MAIN LOOP ------------------
def main():
    print("🚀 Starting PlayBot 24/7 Weather Stream")
    streamer = start_ffmpeg()

    ticker_x = WIDTH
    last_fetch = 0
    alerts = []

    while True:
        if time.time() - last_fetch > 30:
            alerts = fetch_noaa_alerts()
            last_fetch = time.time()

        frame, crawl_width = draw_frame(alerts, ticker_x)
        ticker_x -= 5
        if ticker_x < -crawl_width:
            ticker_x = WIDTH

        try:
            streamer.stdin.write(frame.tobytes())
        except BrokenPipeError:
            print("🔴 Stream disconnected")
            break

        time.sleep(1 / FPS)

if __name__ == "__main__":
    main()
