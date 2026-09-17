"""Automated screen recording for AIONOS Assignment 1 Demo Video.
Follows the 7 beats in docs/DEMO.md with smooth scrolling, clicks, and exact timings (~3.5 minutes).
Outputs: demo_video.mp4 (< 10MB)
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import subprocess

OUT_DIR = Path("d:/AIONOS Assignment-1/recordings")
OUT_DIR.mkdir(exist_ok=True)

def smooth_scroll(page, target_y, steps=25, delay=0.03):
    current_y = page.evaluate("window.scrollY")
    diff = target_y - current_y
    for i in range(1, steps + 1):
        y = current_y + diff * (i / steps)
        page.evaluate(f"window.scrollTo(0, {y})")
        time.sleep(delay)

def run():
    print("Starting browser demo recording with Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        
        # Beat 1: Intro — Executive Productivity Agent header & overview (18s)
        print("Beat 1: Overview & Intro (18s)...")
        page.goto("http://127.0.0.1:8000/")
        page.wait_for_selector("text=THE STANDING")
        time.sleep(18)
        
        # Beat 2: The Standing — 3 core lines & summary counts (25s)
        print("Beat 2: The Standing (25s)...")
        smooth_scroll(page, 70)
        time.sleep(25)
        
        # Beat 3: Dedup — Click Vendor List to show 7 sources & deadline trail (40s)
        print("Beat 3: Dedup & Vendor List (40s)...")
        smooth_scroll(page, 310)
        time.sleep(4)
        btn = page.query_selector("article.jeop button.evb")
        if btn:
            btn.click()
            time.sleep(1)
        smooth_scroll(page, 380)
        time.sleep(35)
        
        # Beat 4: Time Travel — Click Thu 5pm preset (28s)
        print("Beat 4: Time travel to Thursday (28s)...")
        smooth_scroll(page, 0)
        time.sleep(2)
        thu_btn = page.query_selector("button.day:has-text('Thu 24')")
        if thu_btn:
            thu_btn.click()
        time.sleep(4)
        smooth_scroll(page, 310)
        time.sleep(22)
        
        # Beat 5: Unclear Ownership Refusal — Mumbai lease card (35s)
        print("Beat 5: Mumbai lease refusal (35s)...")
        smooth_scroll(page, 440)
        time.sleep(3)
        lease_btn = page.query_selector("article.unowned button.evb")
        if lease_btn:
            lease_btn.click()
            time.sleep(1)
        smooth_scroll(page, 510)
        time.sleep(31)
        
        # Beat 6: Ask the Record — Live Groq Q&A (45s)
        print("Beat 6: Ask the Record (45s)...")
        smooth_scroll(page, 820)
        time.sleep(4)
        
        # Click suggestion: What did I promise Raghav?
        raghav_chip = page.query_selector("button:has-text('What did I promise Raghav?')")
        if raghav_chip:
            raghav_chip.click()
        time.sleep(14)
        
        # Compare toggle
        compare = page.query_selector("summary:has-text('compare with the deterministic answer')")
        if compare:
            compare.click()
        time.sleep(8)
        
        # Click suggestion: Who owns Mumbai lease?
        mumbai_chip = page.query_selector("button:has-text('Who owns the Mumbai lease renewal?')")
        if mumbai_chip:
            mumbai_chip.click()
        time.sleep(19)
        
        # Beat 7: Complete Data Pack & Swagger docs (25s)
        print("Beat 7: Inspect Data Pack & API docs (25s)...")
        smooth_scroll(page, 1250)
        time.sleep(3)
        inspect_btn = page.query_selector("button.closed")
        if inspect_btn:
            inspect_btn.click()
        time.sleep(7)
        
        # Open /docs
        print("Opening API Swagger docs...")
        page.goto("http://127.0.0.1:8000/docs")
        page.wait_for_selector("text=Executive Productivity Agent")
        time.sleep(15)
        
        print("Closing page to finalize video...")
        raw_video_path = page.video.path()
        page.close()
        context.close()
        browser.close()
        
    print(f"Raw video recorded at: {raw_video_path}")
    
    # Re-encode to MP4 under 10MB using ffmpeg
    final_mp4 = Path("d:/AIONOS Assignment-1/demo_video.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", raw_video_path,
        "-c:v", "libx264", "-crf", "26", "-preset", "slow",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(final_mp4)
    ]
    print("Encoding final MP4 with ffmpeg...")
    subprocess.run(cmd, check=True)
    size_mb = final_mp4.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: Video generated at {final_mp4} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    run()
