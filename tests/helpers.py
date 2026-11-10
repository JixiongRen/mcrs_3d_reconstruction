import numpy as np
from guidewire.stereo import Stereo


def synthetic_stereo():
    intrinsic = {"fx": 600., "fy": 600., "cx": 320., "cy": 240.}
    rotation = np.eye(3).tolist()
    translation = [-14., 0., 0.]
    distortion = {k: 0. for k in ("k1", "k2", "k3", "k4", "k5", "k6", "p1", "p2")}
    calibration = {"ir_intrinsic": intrinsic, "rgb_intrinsic": intrinsic,
                   "rgb_distortion": distortion, "depth_to_rgb_rotation": rotation,
                   "depth_to_rgb_translation": translation, "ir_to_depth_rotation": rotation,
                   "ir_to_depth_translation": [0., 0., 0.]}
    checked = {"ir_distortion": distortion, "ir_to_rgb_rotation": rotation, "ir_to_rgb_translation": translation}
    return Stereo({"calibration": calibration}, checked)
