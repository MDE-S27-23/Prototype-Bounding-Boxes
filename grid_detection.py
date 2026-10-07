"""Automatic detection of the repeating tray-cell grid."""

import math
from typing import Tuple

import cv2
import numpy as np

import config
from models import GridInfo


def _smooth_1d(values: np.ndarray, kernel_size: int) -> np.ndarray:
    kernel_size = max(3, int(kernel_size))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
    return np.convolve(values.astype(np.float32), kernel, mode="same")


def _auto_pitch_limits(profile_length: int) -> Tuple[int, int]:
    if config.MIN_CELL_PITCH_PX is None:
        min_pitch = int(round(profile_length * config.AUTO_MIN_PITCH_FRACTION))
    else:
        min_pitch = int(config.MIN_CELL_PITCH_PX)

    if config.MAX_CELL_PITCH_PX is None:
        max_pitch = int(round(profile_length * config.AUTO_MAX_PITCH_FRACTION))
    else:
        max_pitch = int(config.MAX_CELL_PITCH_PX)

    min_pitch = max(8, min_pitch)
    max_pitch = min(profile_length // 2, max(max_pitch, min_pitch + 2))
    return min_pitch, max_pitch


def _estimate_pitch_from_autocorrelation(profile: np.ndarray) -> float:
    """Estimate the fundamental repeating distance in a 1D edge profile."""
    smoothed = _smooth_1d(profile, 7)
    centered = smoothed - float(np.mean(smoothed))
    autocorr = np.correlate(centered, centered, mode="full")[len(centered) - 1 :]

    min_pitch, max_pitch = _auto_pitch_limits(len(profile))
    local_peaks = []
    for lag in range(min_pitch + 1, max_pitch):
        if autocorr[lag] >= autocorr[lag - 1] and autocorr[lag] >= autocorr[lag + 1]:
            local_peaks.append(lag)

    if not local_peaks:
        return float(min_pitch + np.argmax(autocorr[min_pitch : max_pitch + 1]))

    strongest = max(float(autocorr[p]) for p in local_peaks)
    # Prefer the smallest strong peak so a 2x or 3x harmonic does not win.
    strong_candidates = [p for p in local_peaks if autocorr[p] >= 0.55 * strongest]
    return float(min(strong_candidates) if strong_candidates else max(local_peaks, key=lambda p: autocorr[p]))


def _find_profile_peaks(profile: np.ndarray, pitch: float) -> np.ndarray:
    smooth_k = max(3, int(round(pitch * 0.08)))
    smoothed = _smooth_1d(profile, smooth_k)

    candidates = np.where(
        (smoothed[1:-1] >= smoothed[:-2]) & (smoothed[1:-1] >= smoothed[2:])
    )[0] + 1

    median = float(np.median(smoothed))
    threshold = median + 0.10 * (float(np.max(smoothed)) - median)
    candidates = [int(i) for i in candidates if smoothed[i] >= threshold]
    candidates.sort(key=lambda i: float(smoothed[i]), reverse=True)

    min_distance = max(3, int(round(pitch * 0.65)))
    kept = []
    for candidate in candidates:
        if all(abs(candidate - previous) >= min_distance for previous in kept):
            kept.append(candidate)

    return np.array(sorted(kept), dtype=np.int32)


def _refine_pitch(profile: np.ndarray, initial_pitch: float) -> float:
    peaks = _find_profile_peaks(profile, initial_pitch)
    if len(peaks) < 3:
        return initial_pitch

    spacings = np.diff(peaks).astype(np.float32)
    valid = spacings[
        (spacings > 0.75 * initial_pitch) & (spacings < 1.25 * initial_pitch)
    ]
    if len(valid) == 0:
        return initial_pitch
    return float(np.median(valid))


def _best_phase(profile: np.ndarray, pitch: float) -> float:
    """Find where the repeating line pattern begins within one pitch period."""
    smoothed = _smooth_1d(profile, max(3, int(round(pitch * 0.06))))
    n = len(smoothed)
    radius = max(1, int(round(pitch * 0.06)))
    edge_ignore = config.PHASE_IGNORE_EDGE_FRACTION * n

    phase_samples = max(80, int(round(pitch * 4)))
    best_score = -np.inf
    best_phase = 0.0

    for phase in np.linspace(0.0, pitch, phase_samples, endpoint=False):
        line_scores = []
        k_min = math.ceil((0 - phase) / pitch)
        k_max = math.floor((n - 1 - phase) / pitch)

        for k in range(k_min, k_max + 1):
            predicted = phase + k * pitch
            if predicted < edge_ignore or predicted > (n - 1 - edge_ignore):
                continue
            i = int(round(predicted))
            lo = max(0, i - radius)
            hi = min(n, i + radius + 1)
            line_scores.append(float(np.max(smoothed[lo:hi])))

        if len(line_scores) >= 3:
            score = float(np.median(line_scores))
            if score > best_score:
                best_score = score
                best_phase = float(phase)

    return best_phase


def _generate_and_refine_lines(profile: np.ndarray, pitch: float, phase: float):
    smoothed = _smooth_1d(profile, max(3, int(round(pitch * 0.06))))
    n = len(smoothed)
    radius = max(2, int(round(pitch * config.GRID_LINE_SEARCH_FRACTION)))

    k_min = math.ceil((0 - phase) / pitch)
    k_max = math.floor((n - 1 - phase) / pitch)

    positions = []
    scores = []
    for k in range(k_min, k_max + 1):
        predicted = phase + k * pitch
        i = int(round(predicted))
        lo = max(0, i - radius)
        hi = min(n, i + radius + 1)
        local_index = lo + int(np.argmax(smoothed[lo:hi]))
        positions.append(local_index)
        scores.append(float(smoothed[local_index]))

    # Remove duplicates created when two predicted lines refine to the same peak.
    dedup_positions = []
    dedup_scores = []
    for position, score in zip(positions, scores):
        if not dedup_positions or position != dedup_positions[-1]:
            dedup_positions.append(position)
            dedup_scores.append(score)
        elif score > dedup_scores[-1]:
            dedup_scores[-1] = score

    return np.array(dedup_positions, dtype=np.int32), np.array(dedup_scores, dtype=np.float32)


def _trim_weak_outer_lines(lines: np.ndarray, scores: np.ndarray):
    """Trim only weak endpoints; never remove weak lines from inside the grid."""
    if len(lines) <= config.MIN_GRID_LINES:
        return lines, scores

    start = 0
    end = len(lines)

    # Recompute the reference as endpoints are removed.
    while end - start > config.MIN_GRID_LINES:
        current_scores = scores[start:end]
        reference = float(np.median(current_scores))
        threshold = config.GRID_EDGE_SCORE_FRACTION * reference

        changed = False
        if scores[start] < threshold:
            start += 1
            changed = True
        if end - start > config.MIN_GRID_LINES and scores[end - 1] < threshold:
            end -= 1
            changed = True
        if not changed:
            break

    return lines[start:end], scores[start:end]


def detect_grid(image: np.ndarray) -> GridInfo:
    """Detect rows/columns and physical scale from the repeating tray pattern."""
    if image is None or image.size == 0:
        raise ValueError("Empty image supplied to detect_grid().")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    grad_x = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    grad_y = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))

    height, width = gray.shape
    y0, y1 = int(0.05 * height), max(int(0.95 * height), int(0.05 * height) + 1)
    x0, x1 = int(0.05 * width), max(int(0.95 * width), int(0.05 * width) + 1)

    # Vertical grid walls create strong X gradients; horizontal walls create Y gradients.
    vertical_profile = np.mean(grad_x[y0:y1, :], axis=0)
    horizontal_profile = np.mean(grad_y[:, x0:x1], axis=1)

    pitch_x = _estimate_pitch_from_autocorrelation(vertical_profile)
    pitch_y = _estimate_pitch_from_autocorrelation(horizontal_profile)
    pitch_x = _refine_pitch(vertical_profile, pitch_x)
    pitch_y = _refine_pitch(horizontal_profile, pitch_y)

    phase_x = _best_phase(vertical_profile, pitch_x)
    phase_y = _best_phase(horizontal_profile, pitch_y)

    x_lines, x_scores = _generate_and_refine_lines(vertical_profile, pitch_x, phase_x)
    y_lines, y_scores = _generate_and_refine_lines(horizontal_profile, pitch_y, phase_y)

    x_lines, _ = _trim_weak_outer_lines(x_lines, x_scores)
    y_lines, _ = _trim_weak_outer_lines(y_lines, y_scores)

    if len(x_lines) < config.MIN_GRID_LINES or len(y_lines) < config.MIN_GRID_LINES:
        raise RuntimeError(
            "Could not detect a reliable tray grid. Try adjusting the pitch limits in config.py."
        )

    # Use median detected line-to-line distance after local refinement.
    measured_pitch_x = float(np.median(np.diff(x_lines)))
    measured_pitch_y = float(np.median(np.diff(y_lines)))

    mm_per_px_x = (config.CELL_PITCH_X_IN * config.MM_PER_INCH) / measured_pitch_x
    mm_per_px_y = (config.CELL_PITCH_Y_IN * config.MM_PER_INCH) / measured_pitch_y

    return GridInfo(
        x_lines=[int(x) for x in x_lines],
        y_lines=[int(y) for y in y_lines],
        pitch_x_px=measured_pitch_x,
        pitch_y_px=measured_pitch_y,
        mm_per_px_x=mm_per_px_x,
        mm_per_px_y=mm_per_px_y,
    )
