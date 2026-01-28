import time
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import ffmpeg
import subprocess

# ---------------- SETTINGS ----------------
WIDTH, HEIGHT = 1280, 720
FPS = 5
YOUTUBE_STREAM_KEY = "fvgb-pzbe-4j7g-vej0-6g7q"  # replace with your actual key
YOUTUBE_URL = f"rtmp://a.rtmp.youtube.com/live2/{YOUTUBE_STREAM_KEY}"

# Fonts
FONT_LARGE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
FONT_MED   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
FONT_SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)

# Alert priority
PRIORITY = {
    "Tornado Emergency": 100,
    "Tornado Warning": 95,
    "Severe Thunderstorm Warning": 80,
    "Flash Flood Warning": 75,
    "Tornado Watch": 60,
    "Severe Thunderstorm Watch": 50
}

# ---------------- START RTMP STREAM ----------------
def start_stream():
    """Start FFmpeg process streaming to YouTube RTMPS."""
    try:
        print("🚀 Starting Y’allBot RTMPS stream...")
        streamer = (
            ffmpeg
            .input("pipe:", format="rawvideo", pix_fmt="rgb24",
                   s=f"{WIDTH}x{HEIGHT}", framerate=FPS)
            .output(YOUTUBE_URL, format="flv",
                    vcodec="libx264", pix_fmt="yuv420p",
                    preset="veryfast", g=FPS*2)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )
        # test if stdin is writable
        streamer.stdin.write(np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8).tobytes())
        print("✅ Connected to YouTube successfully!")
        return streamer
    except Exception as e:
        print(f"⚠️ Failed to start stream: {e}")
        return None

# ---------------- FETCH NOAA ALERTS ----------------
def fetch_noaa_alerts():
    try:
        res = requests.get("https://api.weather.gov/alerts/active", timeout=8)
        data = res.json()
        alerts = []
        for f in data.get("features", []):
            props = f.get("properties", {})
            event = props.get("event")
            if event in PRIORITY:
                alerts.append({
                    "event": event,
                    "area": props.get("areaDesc", ""),
                    "severity": PRIORITY[event]
                })
        alerts.sort(key=lambda x: x["severity"], reverse=True)
        return alerts
    except:
        return []

# ---------------- DRAW FRAME ----------------
def draw_frame(alerts, ticker_x):
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(pil)

    # Title bar
    draw.rectangle((0, 0, WIDTH, 40), fill=(0, 0, 0))
    draw.text((10, 5), "Y’allBot 24/7 USA Weather Alerts", font=FONT_LARGE, fill=(255, 255, 255))

    # Top alert box
    if alerts:
        top = alerts[0]
        fill = (255, 0, 0) if "Tornado" in top["event"] else (255, 140, 0)
        draw.rectangle((0, 50, WIDTH, 100), fill=fill)
        draw.text((10, 55), f"{top['event']} — {top['area']}", font=FONT_MED, fill=(0, 0, 0))

    # Side panel
    draw.rectangle((WIDTH-280, 110, WIDTH-10, 270), fill=(20, 20, 20))
    draw.text((WIDTH-270, 120), "Active Warnings", font=FONT_MED, fill=(255, 255, 255))
    y = 155
    for a in alerts[:6]:
        draw.text((WIDTH-270, y), a["event"], font=FONT_SMALL, fill=(255, 0, 0))
        y += 24

    # Ticker
    crawl = " | ".join([f"{a['event']} - {a['area']}" for a in alerts])
    draw.rectangle((0, HEIGHT-60, WIDTH, HEIGHT), fill=(0, 0, 0))
    draw.text((ticker_x, HEIGHT-45), crawl, font=FONT_MED, fill=(255, 0, 0))

    return np.array(pil), len(crawl)*12

# ---------------- MAIN LOOP ----------------
def main():
    ticker_x = WIDTH
    last_alert = 0
    alerts = []

    while True:
        streamer = start_stream()
        if streamer is None:
            print("⏱ Retry in 10 seconds...")
            time.sleep(10)
            continue  # try connecting again

        frame_id = 0
        try:
            while True:
                # Update alerts every 30 seconds
                if time.time() - last_alert > 30:
                    alerts = fetch_noaa_alerts()
                    last_alert = time.time()

                frame, crawl_width = draw_frame(alerts, ticker_x)
                ticker_x -= 5
                if ticker_x < -crawl_width:
                    ticker_x = WIDTH

                streamer.stdin.write(frame.tobytes())
                frame_id += 1
                time.sleep(1 / FPS)

        except BrokenPipeError:
            print("❌ Stream disconnected. Retrying in 10 seconds...")
            time.sleep(10)
        except Exception as e:
            print(f"⚠️ Error during streaming: {e}. Retrying in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    main()
