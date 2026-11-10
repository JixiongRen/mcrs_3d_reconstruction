"""Offline figures and live display rendering; no camera access."""
import time

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np


def save_plots(out, rgb_image, ir_image, rgb_curve, ir_curve, accepted, rejected):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, image, curve, modality in zip(axes, (rgb_image, ir_image), (rgb_curve, ir_curve), ("rgb", "ir")):
        ax.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if modality == "rgb" else image, cmap="gray")
        ax.plot(curve[:, 0], curve[:, 1], color="lime", lw=1, label="automatic centerline")
        points = np.array([a[modality] for a in accepted])
        if len(points):
            ax.scatter(points[::3, 0], points[::3, 1], s=10, c="red", label="accepted matches")
        if modality == "rgb" and rejected:
            points = rgb_curve[[r["rgb_index"] for r in rejected]]
            ax.scatter(points[:, 0], points[:, 1], s=9, c="orange", label="unmatched / rejected")
        lo, hi = curve.min(axis=0)-35, curve.max(axis=0)+35
        ax.set(xlim=(lo[0], hi[0]), ylim=(min(image.shape[0], hi[1]), max(0, lo[1])), title=modality.upper(), xlabel="u [px]", ylabel="v [px]")
        ax.legend(fontsize=8)
    fig.suptitle("Automatic extraction and matching: no manual point inputs; orange points not reconstructed")
    fig.tight_layout()
    fig.savefig(out / "automatic_matches.png", dpi=150)
    plt.close(fig)
    if not accepted:
        return
    xyz = np.array([a["xyz_mm"] for a in accepted])
    indices = np.array([a["rgb_index"] for a in accepted])
    groups = np.split(np.arange(len(xyz)), np.flatnonzero(np.diff(indices) > 1)+1)
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(221, projection="3d")
    for group in groups:
        ax.plot(*xyz[group].T, lw=1)
    ax.scatter(*xyz.T, c=indices, cmap="viridis", s=8)
    ax.set(xlabel="X [mm]", ylabel="Y [mm]", zlabel="Z [mm]", title="Raw automatic XYZ; rejected gaps stay open")
    ax.set_box_aspect(np.maximum(np.ptp(xyz, axis=0), 1))
    for subplot, dims in ((222, (0, 1)), (223, (0, 2)), (224, (1, 2))):
        ax = fig.add_subplot(subplot)
        a, b = dims
        for group in groups:
            ax.plot(xyz[group, a], xyz[group, b], lw=1)
        ax.scatter(xyz[:, a], xyz[:, b], c=indices, cmap="viridis", s=8)
        ax.set(xlabel=f"{'XYZ'[a]} [mm]", ylabel=f"{'XYZ'[b]} [mm]")
        if b == 1:
            ax.invert_yaxis()
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=.3)
    fig.suptitle("Exploratory automatic triangulation: no native depth, no 3D smoothing, no accuracy ground truth")
    fig.tight_layout()
    fig.savefig(out / "automatic_3d.png", dpi=150)
    plt.close(fig)


class Display:
    def __init__(self):
        self.figure = Figure(figsize=(6.4, 7.6), dpi=100, facecolor="white")
        self.canvas = FigureCanvasAgg(self.figure)
        self.ax3 = self.figure.add_subplot(211, projection="3d")
        self.ax2 = self.figure.add_subplot(212)
        self.bounds = None
        self.left = np.zeros((760, 640, 3), np.uint8)
        self.right = np.full((760, 640, 3), 25, np.uint8)

    def update(self, result):
        panels = []
        for name, size in (("rgb", (640, 360)), ("ir", (640, 400))):
            image = result[name].copy()
            if name == "ir":
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            curve = result["curves"].get(name)
            if curve is not None:
                cv2.polylines(image, [np.rint(curve).astype(np.int32)], False, (0, 255, 0), 2)
            for point in result["matches"][::3]:
                cv2.circle(image, tuple(np.rint(point[name]).astype(int)), 4, (0, 0, 255), -1)
            if name == "rgb" and curve is not None:
                for rejection in result["rejections"]:
                    cv2.circle(image, tuple(np.rint(curve[rejection["rgb_index"]]).astype(int)), 3, (0, 170, 255), -1)
            panel = cv2.resize(image, size)
            cv2.rectangle(panel, (0, 0), (640, 29), (20, 20, 20), -1)
            cv2.putText(panel, f"{name.upper()}  green=centerline red=matched orange=unmatched", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .43, (240, 240, 240), 1)
            panels.append(panel)
        self.left = np.vstack(panels)
        self.ax3.clear()
        self.ax2.clear()
        matches = result["matches"]
        if matches:
            xyz = np.array([m["xyz_mm"] for m in matches])
            indices = np.array([m["rgb_index"] for m in matches])
            groups = np.split(np.arange(len(xyz)), np.flatnonzero(np.diff(indices) > 1)+1)
            for group in groups:
                self.ax3.plot(*xyz[group].T, color="teal", lw=1)
                self.ax2.plot(xyz[group, 0], xyz[group, 1], color="teal", lw=1)
            self.ax3.scatter(*xyz.T, s=5, c=indices, cmap="viridis")
            self.ax2.scatter(xyz[:, 0], xyz[:, 1], s=4, c=indices, cmap="viridis")
            lo, hi = xyz.min(axis=0)-5, xyz.max(axis=0)+5
            if self.bounds is None:
                self.bounds = lo, hi
            else:
                self.bounds = np.minimum(self.bounds[0], lo), np.maximum(self.bounds[1], hi)
            lo, hi = self.bounds
            self.ax3.set(xlim=(lo[0], hi[0]), ylim=(hi[1], lo[1]), zlim=(lo[2], hi[2]))
            self.ax3.set_box_aspect(hi-lo)
            self.ax2.set(xlim=(lo[0], hi[0]), ylim=(hi[1], lo[1]))
        else:
            self.ax2.text(.5, .5, "No reliable 3D points\nPrevious shape cleared", ha="center", va="center", transform=self.ax2.transAxes, color="darkred")
        self.ax3.view_init(elev=55, azim=-70)
        self.ax3.set(xlabel="X [mm]", ylabel="Y [mm]", zlabel="Z [mm]", title="3D points - IR camera coordinates")
        self.ax2.set(xlabel="X [mm]", ylabel="Y [mm] (down)", title="Front view - gaps remain open")
        self.ax2.set_aspect("equal", adjustable="box")
        self.ax2.grid(alpha=.25)
        self.figure.subplots_adjust(left=.14, right=.92, bottom=.08, top=.94, hspace=.38)
        self.canvas.draw()
        self.right = cv2.cvtColor(np.asarray(self.canvas.buffer_rgba()), cv2.COLOR_RGBA2BGR)

    def compose(self, result, hz, camera_error=None):
        age = time.monotonic()-result["received_at"] if result else float("inf")
        stale = result is None or age > 3 or camera_error is not None
        right = np.full_like(self.right, 25) if stale else self.right
        if stale:
            cv2.putText(right, "Waiting for fresh results - 3D cleared", (28, 355), cv2.FONT_HERSHEY_SIMPLEX, .62, (0, 180, 255), 1)
        body = np.hstack([self.left, right])
        canvas = cv2.copyMakeBorder(body, 65, 0, 0, 0, cv2.BORDER_CONSTANT, value=(25, 25, 25))
        if result:
            line = f"Target {hz:.1f} Hz | actual {result['actual_hz']:.2f} Hz | {len(result['matches'])} points | compute {result['compute_s']:.2f}s | received age {age:.1f}s | RGB-IR {result['pair_gap_ms']:+.1f} ms"
            detail = "STALE" if stale else ("PARTIAL reconstruction" if result["matches"] else "NO reliable reconstruction")
            if result["errors"]:
                detail += " | " + "; ".join(result["errors"])
        else:
            line, detail = "Waiting for camera frames and first reconstruction...", ""
        cv2.putText(canvas, line, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, .48, (240, 240, 240), 1)
        cv2.putText(canvas, (camera_error or detail)[:145], (10, 45), cv2.FONT_HERSHEY_SIMPLEX, .43, (0, 190, 255), 1)
        cv2.putText(canvas, "Static-scene prototype; streams NOT synchronized | Q/Esc: stop | S: save current pair", (10, 61), cv2.FONT_HERSHEY_SIMPLEX, .39, (185, 185, 185), 1)
        return canvas
