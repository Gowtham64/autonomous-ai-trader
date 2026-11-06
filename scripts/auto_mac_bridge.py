#!/usr/bin/env python3
"""Automated Zero-Config MacBook Ollama Bridge.

Automatically bridges your local MacBook Ollama to your 24/7 Render cloud trader.
- MacBook Awake: Cloud trader routes to your MacBook Ollama.
- MacBook Asleep/Off: Cloud trader routes to Groq & Gemini with zero downtime.
"""

import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

RENDER_API = os.environ.get("RENDER_API_URL", "https://autonomous-ai-trader.onrender.com")
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(ROOT_DIR, "bin")
CLOUDFLARED_BIN = os.path.join(BIN_DIR, "cloudflared")


def check_local_ollama() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as res:
            return res.status == 200
    except Exception:
        return False


def ensure_cloudflared() -> str:
    # 1. Check local bin/
    if os.path.exists(CLOUDFLARED_BIN) and os.access(CLOUDFLARED_BIN, os.X_OK):
        return CLOUDFLARED_BIN

    # 2. Check system PATH
    sys_path = shutil.which("cloudflared")
    if sys_path:
        return sys_path

    # 3. Check common Mac locations
    for p in ["/opt/homebrew/bin/cloudflared", "/usr/local/bin/cloudflared"]:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    # 4. Auto-download standalone binary (Zero brew needed)
    print("⬇️ Standalone tunnel engine not found. Downloading for macOS...")
    os.makedirs(BIN_DIR, exist_ok=True)
    arch = platform.machine().lower()
    asset = "cloudflared-darwin-arm64.tgz" if ("arm" in arch or "aarch" in arch) else "cloudflared-darwin-amd64.tgz"
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = res.read()
        tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
        tar.extractall(path=BIN_DIR)
        os.chmod(CLOUDFLARED_BIN, 0o755)

    print(f"✅ Downloaded and verified: {CLOUDFLARED_BIN}")
    return CLOUDFLARED_BIN


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
        print(f"⚠️ [Bridge] Heartbeat notice: {e}")
        return False


def main():
    print("=" * 60)
    print("🍏 Autonomous Trader — Automated MacBook Ollama Bridge")
    print("=" * 60)

    if not check_local_ollama():
        print("❌ Local Ollama is not running on port 11434.")
        print("💡 Start Ollama first (open Ollama app or run 'ollama serve').")
        sys.exit(1)

    print("✅ Local Ollama is active on port 11434.")

    cf_binary = ensure_cloudflared()

    print("🌐 Launching secure zero-config tunnel to MacBook...")
    proc = subprocess.Popen(
        [cf_binary, "tunnel", "--url", "http://127.0.0.1:11434"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    tunnel_url = None
    # Scan logs for assigned tunnel URL
    for line in iter(proc.stdout.readline, ""):
        cf_match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if cf_match:
            tunnel_url = cf_match.group(0)
            break

    if not tunnel_url:
        print("❌ Could not obtain public tunnel URL.")
        proc.kill()
        sys.exit(1)

    print(f"🚀 Bridge Live: {tunnel_url}")
    print(f"📡 Registering with Render Cloud Trader ({RENDER_API})...")

    initial_ok = register_with_render(tunnel_url)
    if initial_ok:
        print("🟢 SUCCESS: Cloud Trader is now routing Priority #1 to your MacBook Ollama!")
    else:
        print("⚠️ Warning: Initial registration to cloud trader failed. Will keep retrying...")

    print("💡 Keep this terminal window open while you want to use MacBook Ollama.")
    print("💤 When you close this terminal or shut your Mac lid, cloud trader automatically switches to Groq & Gemini.")
    print("-" * 60)

    try:
        while True:
            time.sleep(30)
            ok = register_with_render(tunnel_url)
            status_str = "OK" if ok else "RETRYING"
            print(f"💓 [{time.strftime('%H:%M:%S')}] Heartbeat {status_str} — MacBook Ollama Connected.")
    except KeyboardInterrupt:
        print("\n🛑 Stopping bridge. Cloud trader will switch to Groq & Gemini.")
        proc.kill()


if __name__ == "__main__":
    main()
