"""Leaf segmentation and measurement inside each detected tray cell."""

from typing import List, Tuple

import cv2
import numpy as np
from openpyxl.utils import get_column_letter

import config
from models import CellResult, GridInfo, LeafMeasurement


def _green_mask(roi: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hsv_mask = cv2.inRange(
        hsv,
        np.array([config.GREEN_H_MIN, config.GREEN_S_MIN, config.GREEN_V_MIN], dtype=np.uint8),
        np.array([config.GREEN_H_MAX, 255, 255], dtype=np.uint8),
    )

    b, g, r = cv2.split(roi.astype(np.int16))
    excess_green = 2 * g - r - b
    exg_mask = (excess_green >= config.EXCESS_GREEN_MIN).astype(np.uint8) * 255

    mask = cv2.bitwise_and(hsv_mask, exg_mask)

    if config.LEAF_OPEN_KERNEL >= 3:
        k = config.LEAF_OPEN_KERNEL
        if k % 2 == 0:
            k += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    if config.LEAF_CLOSE_KERNEL >= 3:
        k = config.LEAF_CLOSE_KERNEL
        if k % 2 == 0:
            k += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    return mask


def _component_contours(mask: np.ndarray, min_area_px: float, max_area_px: float):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [
        c
        for c in contours
        if min_area_px <= cv2.contourArea(c) <= max_area_px and len(c) >= 3
    ]


def _split_component_watershed(
    roi: np.ndarray,
    component_mask: np.ndarray,
    min_region_area_px: float,
) -> List[np.ndarray]:
    """Try to split a touching green component into leaf-shaped regions."""
    if not config.SPLIT_TOUCHING_LEAVES:
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    distance = cv2.distanceTransform(component_mask, cv2.DIST_L2, 5)
    maximum = float(distance.max())
    if maximum <= 0:
        return []

    sure_fg = (distance >= config.WATERSHED_PEAK_FRACTION * maximum).astype(np.uint8) * 255
    peak_count, markers = cv2.connectedComponents(sure_fg)

    # Background + only one foreground peak means there is nothing to split.
    if peak_count <= 2:
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    sure_bg = cv2.dilate(component_mask, kernel, iterations=1)
    unknown = cv2.subtract(sure_bg, sure_fg)

    markers = markers + 1
    markers[unknown > 0] = 0
    watershed_markers = cv2.watershed(roi.copy(), markers.astype(np.int32))

    split_contours = []
    for label in range(2, int(watershed_markers.max()) + 1):
        region = (watershed_markers == label).astype(np.uint8) * 255
        region = cv2.bitwise_and(region, component_mask)
        contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) >= min_region_area_px:
            split_contours.append(contour)

    if len(split_contours) >= 2:
        return split_contours

    contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours


def _get_leaf_contours(roi: np.ndarray, mask: np.ndarray) -> List[np.ndarray]:
    cell_area = float(mask.shape[0] * mask.shape[1])
    min_area = max(3.0, config.MIN_LEAF_AREA_FRACTION * cell_area)
    max_area = config.MAX_LEAF_AREA_FRACTION * cell_area
    min_split_area = max(3.0, config.MIN_SPLIT_REGION_AREA_FRACTION * cell_area)

    components = _component_contours(mask, min_area, max_area)
    result = []

    for component in components:
        component_mask = np.zeros_like(mask)
        cv2.drawContours(component_mask, [component], -1, 255, thickness=-1)

        split = _split_component_watershed(roi, component_mask, min_split_area)
        for contour in split:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                result.append(contour)

    return result


def _contour_touches_boundary(contour: np.ndarray, width: int, height: int) -> bool:
    x, y, w, h = cv2.boundingRect(contour)
    m = config.BOUNDARY_REVIEW_MARGIN_PX
    return x <= m or y <= m or (x + w) >= width - m or (y + h) >= height - m


def _bgr_to_hex(mean_bgr: Tuple[float, float, float]) -> str:
    b, g, r = [int(round(v)) for v in mean_bgr]
    b = max(0, min(255, b))
    g = max(0, min(255, g))
    r = max(0, min(255, r))
    return f"#{r:02X}{g:02X}{b:02X}"


def _measure_contour(
    contour: np.ndarray,
    roi: np.ndarray,
    global_offset: Tuple[int, int],
    grid: GridInfo,
    leaf_number: int,
) -> LeafMeasurement:
    # Transform contour points into millimeter coordinates before measuring.
    points_px = contour.reshape(-1, 2).astype(np.float32)
    points_mm = points_px.copy()
    points_mm[:, 0] *= grid.mm_per_px_x
    points_mm[:, 1] *= grid.mm_per_px_y
    contour_mm = points_mm.reshape(-1, 1, 2)

    rect_mm = cv2.minAreaRect(contour_mm)
    side_a, side_b = rect_mm[1]
    length_mm = float(max(side_a, side_b))
    width_mm = float(min(side_a, side_b))
    area_mm2 = float(cv2.contourArea(contour_mm))
    area_px = float(cv2.contourArea(contour))

    moments = cv2.moments(contour)
    if moments["m00"] != 0:
        cx_local = moments["m10"] / moments["m00"]
        cy_local = moments["m01"] / moments["m00"]
    else:
        x, y, w, h = cv2.boundingRect(contour)
        cx_local = x + w / 2.0
        cy_local = y + h / 2.0

    contour_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
    cv2.drawContours(contour_mask, [contour], -1, 255, thickness=-1)
    mean_bgr = cv2.mean(roi, mask=contour_mask)[:3]

    quality = "REVIEW_BOUNDARY" if _contour_touches_boundary(contour, roi.shape[1], roi.shape[0]) else "OK"

    return LeafMeasurement(
        leaf_number=leaf_number,
        length_mm=length_mm,
        width_mm=width_mm,
        area_mm2=area_mm2,
        area_px=area_px,
        center_x_px=float(global_offset[0] + cx_local),
        center_y_px=float(global_offset[1] + cy_local),
        mean_bgr=tuple(float(v) for v in mean_bgr),
        mean_hex=_bgr_to_hex(mean_bgr),
        quality_flag=quality,
    )


def analyze_cells(image: np.ndarray, grid: GridInfo):
    results: List[CellResult] = []
    full_leaf_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    contour_records = []

    for row in range(grid.rows):
        for column in range(grid.columns):
            x_left, x_right = grid.x_lines[column], grid.x_lines[column + 1]
            y_top, y_bottom = grid.y_lines[row], grid.y_lines[row + 1]

            cell_w = x_right - x_left
            cell_h = y_bottom - y_top
            inset_x = int(round(cell_w * config.CELL_INSET_FRACTION))
            inset_y = int(round(cell_h * config.CELL_INSET_FRACTION))

            x0 = max(0, x_left + inset_x)
            x1 = min(image.shape[1], x_right - inset_x)
            y0 = max(0, y_top + inset_y)
            y1 = min(image.shape[0], y_bottom - inset_y)

            excel_cell = f"{get_column_letter(column + 1)}{row + 1}"

            if x1 <= x0 or y1 <= y0:
                results.append(
                    CellResult(
                        row=row + 1,
                        column=column + 1,
                        excel_cell=excel_cell,
                        bounds=(x_left, y_top, x_right, y_bottom),
                        status="INVALID_CELL",
                        quality_flag="REVIEW",
                    )
                )
                continue

            roi = image[y0:y1, x0:x1]
            mask = _green_mask(roi)
            full_leaf_mask[y0:y1, x0:x1] = cv2.bitwise_or(full_leaf_mask[y0:y1, x0:x1], mask)

            contours = _get_leaf_contours(roi, mask)
            contours.sort(key=lambda c: cv2.boundingRect(c)[0])

            leaves = []
            for leaf_number, contour in enumerate(contours, start=1):
                leaf = _measure_contour(
                    contour,
                    roi,
                    global_offset=(x0, y0),
                    grid=grid,
                    leaf_number=leaf_number,
                )
                leaves.append(leaf)

                global_contour = contour.copy()
                global_contour[:, 0, 0] += x0
                global_contour[:, 0, 1] += y0
                contour_records.append((row + 1, column + 1, leaf_number, global_contour, leaf))

            status = "SEEDLING" if leaves else "NO_SEEDLING"
            quality = "REVIEW" if any(leaf.quality_flag != "OK" for leaf in leaves) else "OK"
            results.append(
                CellResult(
                    row=row + 1,
                    column=column + 1,
                    excel_cell=excel_cell,
                    bounds=(x_left, y_top, x_right, y_bottom),
                    status=status,
                    leaves=leaves,
                    total_leaf_area_mm2=sum(leaf.area_mm2 for leaf in leaves),
                    quality_flag=quality,
                )
            )

    return results, full_leaf_mask, contour_records
