"""Calibration, undistortion, triangulation and reprojection in millimetres."""
import cv2
import numpy as np


class Stereo:
    def __init__(self, metadata, checked_profile):
        c = metadata["calibration"]
        def intrinsic(name):
            a = c[name]
            return np.array([[a["fx"], 0, a["cx"]], [0, a["fy"], a["cy"]], [0, 0, 1.]])
        self.ki, self.kr = intrinsic("ir_intrinsic"), intrinsic("rgb_intrinsic")
        self.dr = np.array([c["rgb_distortion"][k] for k in ("k1", "k2", "p1", "p2", "k3", "k4", "k5", "k6")])
        self.r = np.array(c["depth_to_rgb_rotation"]) @ np.array(c["ir_to_depth_rotation"])
        self.t = np.array(c["depth_to_rgb_rotation"]) @ np.array(c["ir_to_depth_translation"]) + np.array(c["depth_to_rgb_translation"])
        if not all(v == 0 for v in checked_profile["ir_distortion"].values()):
            raise ValueError("Prototype requires the verified rectified IR profile")
        if not (np.allclose(self.r, checked_profile["ir_to_rgb_rotation"]) and
                np.allclose(self.t, checked_profile["ir_to_rgb_translation"])):
            raise ValueError("Saved profile check disagrees with capture calibration")
        tx, ty, tz = self.t
        skew = np.array([[0, -tz, ty], [tz, 0, -tx], [-ty, tx, 0]])
        self.e = skew @ self.r
        self.scale = self.ki[0, 0] / self.kr[0, 0]

    def lines(self, rgb):
        norm = cv2.undistortPoints(rgb[:, None], self.kr, self.dr)[:, 0]
        lines = np.c_[norm, np.ones(len(norm))] @ self.e @ np.linalg.inv(self.ki)
        return lines / np.linalg.norm(lines[:, :2], axis=1)[:, None]

    def triangulate(self, rgb, ir):
        a = cv2.undistortPoints(ir[:, None], self.ki, None)[:, 0]
        b = cv2.undistortPoints(rgb[:, None], self.kr, self.dr)[:, 0]
        h = cv2.triangulatePoints(np.c_[np.eye(3), np.zeros(3)], np.c_[self.r, self.t], a.T, b.T)
        return (h[:3] / h[3]).T

    def reproject(self, xyz):
        ir = cv2.projectPoints(xyz, np.zeros(3), np.zeros(3), self.ki, None)[0][:, 0]
        rgb = cv2.projectPoints(xyz, cv2.Rodrigues(self.r)[0], self.t, self.kr, self.dr)[0][:, 0]
        return rgb, ir
