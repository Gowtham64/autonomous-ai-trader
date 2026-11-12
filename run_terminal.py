"""Trading terminal for the daily trend bot.

    .venv/bin/python run_terminal.py              # opens http://localhost:8787
    .venv/bin/python run_terminal.py --port 9000 --no-browser

Runs alongside the bot (./start_auto.sh). It reads the bot's records and live Delta
prices; buttons send commands that the ENGINE executes. Stopping the terminal never
stops the bot. Only this computer can open it (bound to 127.0.0.1).
"""

import argparse
import os
import sys
import webbrowser

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from apps.terminal.server import Terminal, make_server  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = make_server(Terminal(), a.port)
    url = f"http://localhost:{a.port}"
    print(f"Trading terminal: {url}   (Ctrl+C stops the terminal only; the bot keeps running)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
