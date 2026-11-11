# xeneon-edge-pi

A Raspberry Pi bolted to the back of a Corsair Xeneon Edge (14.5", 2560x720,
touch), showing tiled browser windows.

Status: the mount is modelled and not yet printed. The software passes its
tests on a desktop and has not yet run on a Pi; see "Not yet tested" below.

## Software

sway tiles one Chromium window per tile across the screen. Any web page can
be a tile.

- `kiosk/launch.py` reads `tiles.toml`, opens the windows and sets their
  widths. Each `[[page]]` is a sway workspace; each tile has a `url` and a
  `width` share, so 3 and 1 give 3/4 and 1/4.
- `buttons/server.py` serves a page of Home Assistant buttons at
  `http://127.0.0.1:8480/`, set up in `buttons.toml`. The Home Assistant
  token stays in the server and is never sent to the page.

### Install on the Pi

1. Flash Raspberry Pi OS Lite (64-bit), connect it to the network, and clone
   this repository on it.
2. Run `pi/install.sh`. `pi/install.sh --dry-run` prints the steps first.
3. Edit `~/.config/xeneon-edge-pi/tiles.toml` and `buttons.toml`.
4. Reboot.

A page that needs a login or a token gets it once, with a keyboard plugged
in; Chromium keeps one profile for all tiles.

### Develop without a Pi

    python3 -m unittest discover -s tests
    python3 tests/fake_home_assistant.py --port 8123      # token: fake-token
    python3 buttons/server.py --config my-buttons.toml

### Not yet tested

- The display coming up at 2560x720 on a Pi, and touch under sway.
- `kiosk/launch.py` against a real sway.
- `pi/install.sh` on a real Raspberry Pi OS image.
- The buttons server against a real Home Assistant.

## Mount

`mount/out/flirc-bottom.stl` replaces the bottom of a Flirc Raspberry Pi
case. A fork at the SD card end bolts to the two 1/4"-20 holes on the back of
the monitor. The case sits under the stand.

- Screws: 2 x 1/4"-20 x 3/8" into the monitor. The monitor's threads are
  4.95 mm deep, so do not use longer ones. The case's own 4 x M2.5 x 6 mm
  screws hold the bottom to the case.
- Assembly: fit the bottom to the case, then bolt it to the monitor.
- Fit: the outline is that of the Flirc Pi 3 (Gen 2) bottom, the smallest of
  the three, so the part also enters the Pi 4 and Pi 5 cases with 1 to 1.7 mm
  of play; the screws locate it. No fit has been tested on a printed part yet.
  The Pi 5 fit rests on one report (Printables 818687).

To change it, edit the constants in `mount/flirc_bottom.py` and run
`freecadcmd mount/flirc_bottom.py`. To check the part against the monitor,
download Corsair's STEP model from
<https://www.printables.com/model/1651858> to
`mount/ref/corsair-xeneon-edge.step` first.

Dimensions came from Corsair's model and from these models of the Flirc
bottoms: Thingiverse 2571763, Printables 80692, 818687, 342806, 282292,
415499 and 1672651.

## Wiring

- The monitor takes power (5 V, 2 A) and touch over its one USB-C port. A
  Pi 4's USB ports supply 1.2 A in total, so the monitor needs its own
  supply, through a powered hub or a USB-C power and data splitter.
- Video is HDMI. The cable in the box is DisplayPort to HDMI and does not
  work with a Pi.

## License

MIT, for the code and the printable models. See `LICENSE`.

This project is not affiliated with Corsair, Flirc or Raspberry Pi.
