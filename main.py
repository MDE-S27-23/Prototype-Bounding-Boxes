"""Tobacco Vision v3: rotation/perspective-aware seedling image analysis."""

import argparse
from pathlib import Path
import cv2

import config
from excel_export import export_excel
from grid_detection import detect_grid, grid_from_dimensions
from leaf_analysis import analyze_cells
from rectification import rectify_image, select_corners
from visualization import draw_grid_overlay, draw_leaf_overlay, show_result_windows


def parse_args():
    p = argparse.ArgumentParser(description='Measure tobacco seedlings in tray photographs.')
    p.add_argument('image', help='Input JPG/PNG')
    p.add_argument('--output-dir', default='output')
    p.add_argument('--cell-pitch-in', type=float, default=None,
                   help='Measured physical center-to-center pitch in inches')
    p.add_argument('--max-dimension', type=int, default=2200,
                   help='Longest image dimension during processing; 0 is invalid')
    p.add_argument('--rotate', default='auto',
                   help='Auto-rotation (default), or an explicit angle in degrees')
    p.add_argument('--corners', nargs=8, type=float, metavar='PX',
                   help='Perspective: four x y original-image pixel pairs, TL TR BR BL')
    p.add_argument('--select-corners', action='store_true',
                   help='Select the four outer grid corners by clicking the image')
    p.add_argument('--rows', type=int, default=None,
                   help='Rows for a manually selected four-corner complete grid')
    p.add_argument('--cols', type=int, default=None,
                   help='Columns for a manually selected four-corner complete grid')
    p.add_argument('--show', action='store_true')
    return p.parse_args()


def main():
    args = parse_args()
    if args.cell_pitch_in is not None:
        if args.cell_pitch_in <= 0:
            raise ValueError('--cell-pitch-in must be positive')
        config.CELL_PITCH_X_IN = config.CELL_PITCH_Y_IN = args.cell_pitch_in
    image_path = Path(args.image)
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f'Unable to load: {image_path}')
    corners = None
    if args.corners:
        corners = [(args.corners[i], args.corners[i+1]) for i in range(0, 8, 2)]
    elif args.select_corners:
        corners = select_corners(image)
    if (args.rows is None) != (args.cols is None):
        raise ValueError('--rows and --cols must be provided together')
    if args.rows is not None and (corners is None or min(args.rows,args.cols) < 2):
        raise ValueError('--rows/--cols require perspective corners and values >= 2')
    out = Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)

    print('[1/4] Straightening image and detecting tray cells...')
    straight, angle, scale, mode = rectify_image(
        image, args.max_dimension, args.rotate, corners)
    if args.rows is not None:
        grid = grid_from_dimensions(straight.shape, args.rows, args.cols)
    else:
        grid = detect_grid(straight)
    if corners is None and abs(angle) > 8 and min(grid.rows, grid.columns) < 9:
        raise RuntimeError('The photo likely contains multiple trays or strong perspective. '
                           'Use --select-corners for ONE tray, and optionally --rows/--cols.')
    grid.rotation_deg = angle
    grid.correction_mode = mode
    grid.image_scale = scale
    print(f'      Correction: {mode}, rotation {angle:+.2f} degrees, scale {scale:.3f}')
    print(f'      Grid: {grid.rows} rows x {grid.columns} cols, '
          f'pitch {grid.pitch_x_px:.2f} x {grid.pitch_y_px:.2f} processed pixels')

    print('[2/4] Segmenting foliage and measuring leaves...')
    cells, leaf_mask, contours = analyze_cells(straight, grid)
    print(f'      Seedling cells: {sum(c.status == "SEEDLING" for c in cells)} / {len(cells)}; '
          f'leaf regions: {sum(len(c.leaves) for c in cells)}')

    print('[3/4] Writing verification pictures...')
    grid_overlay = draw_grid_overlay(straight, grid)
    leaf_overlay = draw_leaf_overlay(straight, cells, contours)
    for name, im in [('rectified_image.jpg', straight),
                     ('grid_overlay.png', grid_overlay),
                     ('leaf_overlay.png', leaf_overlay),
                     ('leaf_mask.png', leaf_mask)]:
        if not cv2.imwrite(str(out/name), im):
            raise OSError(f'Could not write {out/name}')

    print('[4/4] Exporting tray map and measurements...')
    export_excel(out/'tobacco_measurements.xlsx', image_path, grid, cells)
    print(f'Finished: {out.resolve()}')
    if args.show or config.SHOW_WINDOWS:
        show_result_windows(grid_overlay,leaf_mask,leaf_overlay)


if __name__ == '__main__':
    main()
