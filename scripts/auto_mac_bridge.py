#!/usr/bin/env python3
"""Automated Zero-Config MacBook Ollama Bridge.

Automatically bridges your local MacBook Ollama to your 24/7 Render cloud trader.
- MacBook Awake: Cloud trader routes to your MacBook Ollama.
- MacBook Asleep/Off: Cloud trader routes to Groq & Gemini with zero downtime.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

RENDER_API = os.environ.get("RENDER_API_URL", "https://autonomous-ai-trader.onrender.com")


def check_local_ollama() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as res:
            return res.status == 200
    except Exception:
        return False


def register_with_render(tunnel_url: str) -> bool:
    try:
        req = urllib.request.Request(
            f"{RENDER_API}/api/ollama/register",
            data=json.dumps({"url": tunnel_url}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "MacBookAutoBridge/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status == 200
    except Exception as e:
        print(f"⚠️ [Bridge] Heartbeat error to Render: {e}")
        return False


def main():
    print("=" * 60)
    print("🍏 Autonomous Trader — Automated MacBook Ollama Bridge")
    print("=" * 60)

    if not check_local_ollama():
        print("❌ Local Ollama is not running on port 11434.")
        print("💡 Start Ollama first (open Ollama app or run 'ollama serve').")
        sys.exit(1)

    print("✅ Local Ollama detected.")

    # Check for cloudflared or ngrok
    tunnel_cmd = None
    has_cf = subprocess.run(["which", "cloudflared"], capture_output=True).returncode == 0
    has_ngrok = subprocess.run(["which", "ngrok"], capture_output=True).returncode == 0

    if has_cf:
        tunnel_cmd = ["cloudflared", "tunnel", "--url", "http://127.0.0.1:11434"]
        print("🌐 Using Cloudflare Quick Tunnel (Free, no token needed)...")
    elif has_ngrok:
        tunnel_cmd = ["ngrok", "http", "11434", "--log=stdout"]
        print("🌐 Using Ngrok Tunnel...")
    else:
        print("💡 Installing lightweight cloudflared via brew or downloading...")
        res = subprocess.run(["brew", "install", "cloudflared"], capture_output=True)
        if res.returncode == 0:
            tunnel_cmd = ["cloudflared", "tunnel", "--url", "http://127.0.0.1:11434"]
        else:
            print("⚠️ Please install cloudflared (`brew install cloudflared`) or ngrok (`brew install ngrok`).")
            sys.exit(1)

    proc = subprocess.Popen(tunnel_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tunnel_url = None

    # Scan output for tunnel URL
    for line in iter(proc.stdout.readline, ""):
        # Match trycloudflare.com or ngrok.app
        cf_match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        ng_match = re.search(r"https://[a-zA-Z0-9-]+\.ngrok(?:-free)?\.app", line)
        if cf_match:
            tunnel_url = cf_match.group(0)
            break
        if ng_match:
            tunnel_url = ng_match.group(0)
            break

    if not tunnel_url:
        print("❌ Could not obtain public tunnel URL.")
        proc.kill()
        sys.exit(1)

    print(f"🚀 Bridge Online: {tunnel_url}")
    print(f"📡 Auto-registering with Render cloud trader: {RENDER_API}")

    while True:
        success = register_with_render(tunnel_url)
        if success:
            print(f"💓 [Heartbeat OK] {time.strftime('%H:%M:%S')} — Cloud trader is actively routing to MacBook Ollama.")
        else:
            print(f"⚠️ [Heartbeat Retry] {time.strftime('%H:%M:%S')} — Retrying in 30s...")
        time.sleep(30)


if __name__ == "__main__":
    main()
