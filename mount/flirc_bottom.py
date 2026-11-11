"""Replacement bottom for the Flirc Raspberry Pi 3 / 4 / 5 cases, with a tab
that bolts to the two 1/4"-20 holes on the back of the Corsair Xeneon Edge.

Run with `freecadcmd mount/flirc_bottom.py`, or as a macro in FreeCAD.
It adds or replaces the object "FlircBottom" in the document "EdgePiMount"
(mount/edge-pi-mount.FCStd) and exports mount/out/flirc-bottom.{step,stl}.
If Corsair's STEP model of the monitor is at mount/ref/corsair-xeneon-edge.step,
the part is also checked against it.

Case frame, mm: origin at the centre of the four board screws, +x toward the
USB/Ethernet end, +y toward the GPIO side, z = 0 on the face that lies against
the monitor. The aluminium shell rests on the slab's top face (the ledge).

Dimensions of the insert come from community models of the stock bottoms
(see the README). The outline is the Pi 3 (Gen 2) one, the
smallest of the three, so it also enters the Pi 4 and Pi 5 shells, where the
four screws locate it. No model of the stock Pi 5 bottom was found.
"""
import os

import FreeCAD
import Part
from FreeCAD import Placement, Rotation, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
EDGE_STEP = os.path.join(HERE, "ref", "corsair-xeneon-edge.step")
FCSTD = os.path.join(HERE, "edge-pi-mount.FCStd")

# Insert: the part that enters the shell
OUT_X = (-34.7, 54.3)
OUT_Y = (-28.4, 33.6)
OUT_R = 3.0
FLOOR = 0.6            # floor top above the ledge
RIM_W = 1.6
RIM_H = 3.4            # rim top above the ledge
BOARD_H = 3.78         # boss top (underside of the board) above the ledge
BOSS_LOW = (7.3, 2.18)  # diameter, top above the ledge
BOSS_TOP_D = 5.6
HOLES = [(sx * 29.0, sy * 24.5) for sx in (-1, 1) for sy in (-1, 1)]
M25_CLEAR = 3.0
M25_HEAD_D = 5.7
M25_UNDER_HEAD = 2.2   # plastic under the screw head, as on the stock bottom,
                       # so the stock M2.5 x 6 screws still reach the shell
SD_NOTCH = ((-40.0, -30.9), (-14.0, 20.0))   # wider than the Pi 3 and Pi 4 notches;
                                             # limited by the tab pads
GPIO_NOTCH = ((-28.5, 29.1), (31.1, 40.0))

# Slab and tab
SLAB_T = 3.0
SLAB_X = (-54.0, 56.8)
SLAB_Y = (-31.1, 36.9)
SLAB_R = 4.0
TAB_X = -45.0                    # 8.7 mm beyond the SD end of the shell
TAB_Y = (2.92 - 25.0, 2.92 + 25.0)  # 50 mm apart, centred on the case's width
TAB_PAD_D = 14.0
TAB_T = 5.5                      # a 1/4"-20 x 3/8" screw enters the monitor 4.0 mm
QUARTER_CLEAR = 6.8
FORK_ROOT_R = 2.0
EDGE_BREAK = 0.8

# Position on the monitor (frame of edge-pi-mount.FCStd): SD end and tab
# toward the centre, USB end to the left seen from behind, ports side up.
ON_MONITOR = Placement(Vector(TAB_X, 2.92, 0), Rotation(Vector(0, 0, 1), 180))


def rbox(x, y, z, r):
    box = Part.makeBox(x[1] - x[0], y[1] - y[0], z[1] - z[0],
                       Vector(x[0], y[0], z[0]))
    if not r:
        return box
    vertical = [e for e in box.Edges
                if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
    return box.makeFillet(r, vertical)


def cyl(d, z0, z1, x, y):
    return Part.makeCylinder(d / 2.0, z1 - z0, Vector(x, y, z0))


def build():
    t = SLAB_T
    top = t + BOARD_H
    envelope = rbox(OUT_X, OUT_Y, (t, top), OUT_R)

    insert = rbox(OUT_X, OUT_Y, (t, t + FLOOR), OUT_R)
    ring = rbox(OUT_X, OUT_Y, (t, t + RIM_H), OUT_R).cut(
        rbox((OUT_X[0] + RIM_W, OUT_X[1] - RIM_W),
             (OUT_Y[0] + RIM_W, OUT_Y[1] - RIM_W),
             (t - 1, top + 1), max(OUT_R - RIM_W, 0.5)))
    insert = insert.fuse(ring)
    for x, y in HOLES:
        boss = cyl(BOSS_LOW[0], t, t + BOSS_LOW[1], x, y).fuse(
            cyl(BOSS_TOP_D, t, top, x, y))
        insert = insert.fuse(boss.common(envelope))
    for nx, ny in (SD_NOTCH, GPIO_NOTCH):
        insert = insert.cut(rbox(nx, ny, (t, top + 1), 0))

    slab = rbox(SLAB_X, SLAB_Y, (0, t), SLAB_R)
    slab = slab.cut(rbox((SLAB_X[0] - 1, SD_NOTCH[0][1]), SD_NOTCH[1],
                         (-1, t + 1), 0))   # open fork: no slab under the card

    def fork_corners(x):
        return [e for e in slab.Edges
                if abs(e.Vertexes[0].Point.z - e.Vertexes[-1].Point.z) > 1e-6
                and abs(e.Vertexes[0].Point.x - x) < 1e-6
                and SD_NOTCH[1][0] - 1e-6 <= e.Vertexes[0].Point.y <= SD_NOTCH[1][1] + 1e-6]
    slab = slab.makeFillet(SLAB_R, fork_corners(SLAB_X[0]))        # arm tips
    slab = slab.makeFillet(FORK_ROOT_R, fork_corners(SD_NOTCH[0][1]))  # fork root
    # Break the top edges of the fork, where fingers reach for the card.
    top_inner = [e for e in slab.Edges
                 if all(abs(v.Point.z - t) < 1e-6 for v in e.Vertexes)
                 and e.BoundBox.XMax < SD_NOTCH[0][1] + 1e-6
                 and e.BoundBox.YMin > SD_NOTCH[1][0] - SLAB_R - 1e-6
                 and e.BoundBox.YMax < SD_NOTCH[1][1] + SLAB_R + 1e-6]
    slab = slab.makeChamfer(EDGE_BREAK, top_inner)
    for y in TAB_Y:
        slab = slab.fuse(cyl(TAB_PAD_D, 0, TAB_T, TAB_X, y))

    body = slab.fuse(insert)
    for y in TAB_Y:
        body = body.cut(cyl(QUARTER_CLEAR, -1, TAB_T + 1, TAB_X, y))
    for x, y in HOLES:
        body = body.cut(cyl(M25_CLEAR, -1, top + 1, x, y))
        body = body.cut(cyl(M25_HEAD_D, -1, top - M25_UNDER_HEAD, x, y))
    return body.removeSplitter()


def open_document():
    """The open EdgePiMount document, else the saved one, else a new one.
    A new one gets Corsair's model of the monitor if it has been downloaded."""
    if "EdgePiMount" in FreeCAD.listDocuments():
        return FreeCAD.getDocument("EdgePiMount")
    if os.path.exists(FCSTD):
        return FreeCAD.openDocument(FCSTD)
    doc = FreeCAD.newDocument("EdgePiMount")
    if os.path.exists(EDGE_STEP):
        shape = Part.Shape()
        shape.read(EDGE_STEP)
        mon = doc.addObject("Part::Feature", "XeneonEdge")
        mon.Shape = shape
        # Corsair's frame to ours: origin at the centre of the back, +X right
        # seen from behind, +Y up, +Z away from the monitor.
        mon.Placement = Placement(Vector(64.24, 24.55, -5.85),
                                  Rotation(Vector(1, 0, 0), 180))
    doc.saveAs(FCSTD)
    return doc


body = build()
doc = open_document()
obj = doc.getObject("FlircBottom") or doc.addObject("Part::Feature", "FlircBottom")
obj.Shape = body
obj.Placement = ON_MONITOR
doc.recompute()
doc.save()

os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
body.exportStep(os.path.join(HERE, "out", "flirc-bottom.step"))
body.exportStl(os.path.join(HERE, "out", "flirc-bottom.stl"))

bb = body.BoundBox
print("valid:", body.isValid(), "solids:", len(body.Solids),
      "volume cm3: %.1f" % (body.Volume / 1000))
print("extent x %.1f..%.1f y %.1f..%.1f z %.1f..%.1f"
      % (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax))
mon = doc.getObject("XeneonEdge")
if mon:
    placed = obj.Shape
    print("interference with monitor mm3: %.2f" % placed.common(mon.Shape).Volume)
    for y in TAB_Y:
        p = ON_MONITOR.multVec(Vector(TAB_X, y, 0))
        pin = Part.makeCylinder(2.0, 4.0, Vector(p.x, p.y, -4.0))
        print("tab hole at monitor (%.2f, %.2f): monitor material in a 4 mm pin below it: %.3f mm3"
              % (p.x, p.y, pin.common(mon.Shape).Volume))
    pb = placed.BoundBox
    print("on monitor: X %.1f..%.1f Y %.1f..%.1f" % (pb.XMin, pb.XMax, pb.YMin, pb.YMax))
