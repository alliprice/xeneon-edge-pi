#!/usr/bin/env python3
"""Opens one Chromium window per tile and sizes them, under sway.

    python3 kiosk/launch.py --config ~/.config/xeneon-edge-pi/tiles.toml

sway starts this (see pi/install.sh). Each [[page]] in the config becomes a
sway workspace; its tiles sit side by side, left to right, with widths in
proportion to their `width` shares. When Chromium exits, everything is
started again.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

PROFILE = Path.home() / ".local/share/xeneon-edge-pi/chromium"
WINDOW_TIMEOUT = 60  # seconds to wait for a tile's window; a cold Pi 3 is slow
CHROMIUM_FLAGS = [
    "--ozone-platform=wayland",
    "--no-first-run",
    "--noerrdialogs",
    "--disable-session-crashed-bubble",
    "--disable-infobars",
    "--disable-features=Translate",
    "--overscroll-history-navigation=0",  # a sideways swipe must not go "back"
    "--password-store=basic",
]


class ConfigError(Exception):
    pass


def load_tiles(path):
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    return parse_tiles(raw)


def parse_tiles(raw):
    """A list of pages; each page is a list of {"url", "width"} tiles."""
    pages = []
    for p, page in enumerate(raw.get("page") or [], start=1):
        tiles = []
        for t, tile in enumerate(page.get("tile") or [], start=1):
            where = f"page {p}, tile {t}"
            url = tile.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ConfigError(f"{where}: url must be an http or https URL")
            width = tile.get("width", 1)
            if isinstance(width, bool) or not isinstance(width, (int, float)) or width <= 0:
                raise ConfigError(f"{where}: width must be a number above 0")
            tiles.append({"url": url, "width": width})
        if not tiles:
            raise ConfigError(f"page {p} has no tiles")
        pages.append(tiles)
    if not pages:
        raise ConfigError("no pages: add a [[page]] with at least one [[page.tile]]")
    return pages


def widths_percent(shares):
    """Whole percentages in proportion to the shares, adding up to 100."""
    total = sum(shares)
    exact = [100 * s / total for s in shares]
    out = [int(x) for x in exact]
    # Hand the points lost to rounding down to the largest remainders.
    by_remainder = sorted(range(len(exact)), key=lambda i: exact[i] - out[i], reverse=True)
    for i in by_remainder[:100 - sum(out)]:
        out[i] += 1
    return out


def sway_commands(page_number, con_ids, shares):
    """The swaymsg commands that size one page's windows. The last window
    takes what is left, so it is not resized."""
    percents = widths_percent(shares)
    return [f"[con_id={c}] resize set width {w} ppt"
            for c, w in list(zip(con_ids, percents))[:-1]]


def find_chromium():
    for name in ("chromium", "chromium-browser"):
        if shutil.which(name):
            return name
    raise SystemExit("launch: chromium is not installed")


def swaymsg(*args):
    subprocess.run(["swaymsg", *args], check=True, stdout=subprocess.DEVNULL)


def open_tile(chromium, url, events):
    """Starts a window for url and returns (process, sway container id)."""
    proc = subprocess.Popen([chromium, f"--user-data-dir={PROFILE}", *CHROMIUM_FLAGS,
                             f"--app={url}"])
    deadline = time.monotonic() + WINDOW_TIMEOUT
    for line in events.stdout:
        event = json.loads(line)
        if event.get("change") == "new":
            return proc, event["container"]["id"]
        if time.monotonic() > deadline:
            break
    raise RuntimeError(f"no window appeared for {url}")


def run_once(chromium, pages):
    """Opens every tile, then returns when the browser exits."""
    PROFILE.mkdir(parents=True, exist_ok=True)
    events = subprocess.Popen(["swaymsg", "-t", "subscribe", "-m", '["window"]'],
                              stdout=subprocess.PIPE, text=True)
    browser = None
    try:
        for number, tiles in enumerate(pages, start=1):
            swaymsg(f"workspace number {number}")
            swaymsg("layout splith")
            con_ids = []
            for tile in tiles:
                proc, con_id = open_tile(chromium, tile["url"], events)
                # The first process is the browser; later ones hand their
                # window to it and exit.
                browser = browser or proc
                con_ids.append(con_id)
            for command in sway_commands(number, con_ids, [t["width"] for t in tiles]):
                swaymsg(command)
        swaymsg("workspace number 1")
    finally:
        events.terminate()
    browser.wait()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--check", action="store_true",
                    help="read the config, print the layout and exit")
    args = ap.parse_args()
    try:
        pages = load_tiles(args.config)
    except ConfigError as e:
        raise SystemExit(f"launch: {e}")
    if args.check:
        for number, tiles in enumerate(pages, start=1):
            for tile, pct in zip(tiles, widths_percent([t["width"] for t in tiles])):
                print(f"page {number}: {pct:3d}%  {tile['url']}")
        return
    if not os.environ.get("SWAYSOCK"):
        raise SystemExit("launch: not running under sway")
    chromium = find_chromium()
    while True:
        try:
            run_once(chromium, pages)
        except (RuntimeError, subprocess.CalledProcessError) as e:
            print(f"launch: {e}", file=sys.stderr, flush=True)
        subprocess.run(["pkill", "-f", f"--user-data-dir={PROFILE}"])
        time.sleep(3)


if __name__ == "__main__":
    main()
