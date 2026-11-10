"""Image segmentation: blue catheter and experimental dark-wire candidates."""
import cv2
import numpy as np

from .centerline import centerline, resample


def ir_ridge(image):
    response = np.zeros(image.shape, np.float32)
    for sigma in (3, 4, 5, 6):
        blurred = cv2.GaussianBlur(image.astype(np.float32), (0, 0), sigma)
        xx = cv2.Sobel(blurred, cv2.CV_32F, 2, 0, ksize=3) / 4
        yy = cv2.Sobel(blurred, cv2.CV_32F, 0, 2, ksize=3) / 4
        xy = cv2.Sobel(blurred, cv2.CV_32F, 1, 1, ksize=3) / 4
        root = np.sqrt((xx-yy)**2 + 4*xy**2)
        a, b = (xx+yy-root)/2, (xx+yy+root)/2
        large = np.where(abs(a) > abs(b), a, b)
        small = np.where(abs(a) > abs(b), b, a)
        # Bright ridges have negative transverse curvature and low axial curvature.
        score = np.maximum(-large, 0)*sigma**2
        score *= np.exp(-.5*(small/(abs(large)+1e-6)/.25)**2)
        response = np.maximum(response, score)
    return response


def segment(image, modality):
    if modality == "rgb":
        color = image.astype(np.float32)
        blue = cv2.GaussianBlur(color[:, :, 0]-color[:, :, 2], (0, 0), 1.2)
        score = cv2.morphologyEx(blue, cv2.MORPH_TOPHAT,
                                 cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
        mask = ((score > 9) & (blue > 15)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    else:
        score = ir_ridge(image)
        mask = (score > 2).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count <= 1:
        raise ValueError(f"No {modality} component detected")
    if modality == "ir":
        # A dark tube can create a broad, weak positive-curvature halo. Integrated
        # bright-ridge strength discriminates it better than component area.
        strength = np.bincount(labels.ravel(), weights=score.ravel(), minlength=count)
        strength[stats[:, cv2.CC_STAT_AREA] < 300] = 0
        index = 1 + np.argmax(strength[1:])
    else:
        index = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    if stats[index, cv2.CC_STAT_AREA] < 300:
        raise ValueError(f"No sufficiently large {modality} component")
    return (labels == index).astype(np.uint8), score


def dark_wire_candidates(image, modality):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = cv2.medianBlur(gray, 3 if modality == "rgb" else 5)
    score = ir_ridge(255-gray)
    mask = (score > (5 if modality == "rgb" else 2)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    strength = np.bincount(labels.ravel(), weights=score.ravel(), minlength=count)
    indices = [i for i in np.argsort(strength[1:])[::-1]+1
               if stats[i, cv2.CC_STAT_AREA] >= 150][:8]
    found = []
    for index in indices:
        try:
            path, reason = centerline((labels == index).astype(np.uint8))
            points, arc = resample(path, 5 if modality == "rgb" else 2)
            found.append({"points": points, "arc": arc, "stop": reason})
        except ValueError:
            continue
    return found
