"""Tobacco Vision v2 - automatic tray grid + leaf measurement + Excel export."""

import argparse
from pathlib import Path

import cv2

import config
from excel_export import export_excel
from grid_detection import detect_grid
from leaf_analysis import analyze_cells
from visualization import draw_grid_overlay, draw_leaf_overlay, show_result_windows


def parse_args():
    parser = argparse.ArgumentParser(description="Analyze tobacco seedlings in a regular tray grid.")
    parser.add_argument("image", help="Path to the tray image")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Folder for overlays and Excel results (default: output)",
    )
    parser.add_argument(
        "--cell-pitch-in",
        type=float,
        default=None,
        help="Override physical center-to-center pitch in BOTH X and Y (inches)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open resizable OpenCV windows after processing",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.cell_pitch_in is not None:
        if args.cell_pitch_in <= 0:
            raise ValueError("--cell-pitch-in must be greater than zero.")
        config.CELL_PITCH_X_IN = args.cell_pitch_in
        config.CELL_PITCH_Y_IN = args.cell_pitch_in

    image_path = Path(args.image)
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] Detecting tray grid...")
    grid = detect_grid(image)
    print(
        f"      Detected {grid.rows} rows x {grid.columns} columns | "
        f"pitch = {grid.pitch_x_px:.1f}px x {grid.pitch_y_px:.1f}px"
    )
    print(
        f"      Scale = {grid.mm_per_px_x:.4f} mm/px (X), "
        f"{grid.mm_per_px_y:.4f} mm/px (Y)"
    )

    print("[2/4] Detecting and measuring leaves...")
    cell_results, leaf_mask, contour_records = analyze_cells(image, grid)
    detected_cells = sum(1 for cell in cell_results if cell.status == "SEEDLING")
    total_leaves = sum(len(cell.leaves) for cell in cell_results)
    print(f"      Seedlings found in {detected_cells} cells; {total_leaves} leaf regions measured.")

    print("[3/4] Saving verification images...")
    grid_overlay = draw_grid_overlay(image, grid)
    leaf_overlay = draw_leaf_overlay(image, cell_results, contour_records)

    grid_path = output_dir / "grid_overlay.png"
    mask_path = output_dir / "leaf_mask.png"
    leaf_path = output_dir / "leaf_overlay.png"
    cv2.imwrite(str(grid_path), grid_overlay)
    cv2.imwrite(str(mask_path), leaf_mask)
    cv2.imwrite(str(leaf_path), leaf_overlay)

    print("[4/4] Writing Excel workbook...")
    workbook_path = output_dir / "tobacco_measurements.xlsx"
    export_excel(workbook_path, image_path, grid, cell_results)

    print("\nFinished.")
    print(f"  Grid overlay:      {grid_path}")
    print(f"  Leaf mask:         {mask_path}")
    print(f"  Leaf overlay:      {leaf_path}")
    print(f"  Excel workbook:    {workbook_path}")

    if args.show or config.SHOW_WINDOWS:
        show_result_windows(grid_overlay, leaf_mask, leaf_overlay)


if __name__ == "__main__":
    main()
