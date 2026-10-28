# Tobacco Vision v3 — improved segmentation and rotation handling

This is an update of your original v2 project. It runs on Windows with Python, OpenCV, NumPy and openpyxl; it does not require a trained ML model. The 28 supplied tobacco photos were used to test the grid detector. Leaf masks are **automated estimates**, not manually checked ground-truth segmentations.

## Installation

In PowerShell, open this project folder and run:

```powershell
py -m pip install -r requirements.txt
```

If `py` isn't recognized, use `python -m pip install -r requirements.txt` and `python main.py ...` instead.

## Analyze one photograph

```powershell
py main.py "C:\Photos\IMG_8418.JPG" --output-dir "output\IMG_8418" --show
```

The default `--rotate auto` automatically straightens a mildly rotated picture, then detects repeating rows/columns. `--max-dimension 2200` downsizes large photographs to make processing practical. Use `--max-dimension 3200` if you want to retain more detail, at the expense of runtime and memory.

The output folder contains:

- `rectified_image.jpg`: resized and straightened image used for the calculations
- `grid_overlay.png`: detected cell boundaries (inspect **first**)
- `leaf_mask.png`: white means accepted green foliage, black means background
- `leaf_overlay.png`: magenta estimated leaf boundaries, numbered leaf regions; orange markers mean no seedling
- `tobacco_measurements.xlsx`: Tray Map (A1 maps to row 1 column 1), Cell Summary, Leaf Measurements and Metadata

Every leaf has an area in mm², length/width **bounding-box estimates**, and a mean RGB color in HEX. The **total foliage area per cell** comes from the number of accepted green pixels; it is not the sum of uncertain watershed segments. Some touching leaves cannot be reliably identified individually without a trained model or human annotations; review `ESTIMATED_SPLIT` leaves accordingly.

## Calibrating real measurements — important

The default center-to-center tray pitch is still **assumed to be 1.0 inch**. This may NOT be the actual pitch of the photographed trays. Measure adjacent cell centers with a ruler, and enter the true value:

```powershell
py main.py "C:\Photos\IMG_8418.JPG" --cell-pitch-in 0.95
```

Incorrect pitch directly affects reported length/width and squared area. The original pixels and output coordinates are *not the same* when an image is resized or corrected; use `rectified_image.jpg` alongside the coordinate columns.

## Photos shot at a strong angle or containing multiple trays

Simple auto rotation handles **in-plane camera roll**, not severe perspective, cell distortion, multiple trays, or a tray with strong lens distortion. For those photographs, crop/rectify exactly **one** tray using the 4 outer corners of its grid. On a computer with a graphical display:

```powershell
py main.py "C:\Photos\IMG_8426.JPG" --select-corners --show
```

Click in this order: **top-left, top-right, bottom-right, bottom-left** of *one individual tray's outer cell-grid rectangle* (not the wooden frame or the full multi-tray photograph). Press **Enter** to accept or **R** to reset. The grid detector runs on the perspective-corrected image. To specify precisely known rows and columns, add `--rows 12 --cols 12` (change those numbers to the actual count). This divides the selected four corners uniformly; make sure the four corners really represent the outermost grid lines.

Alternatively, pass corner coordinates in **original JPG pixels**:

```powershell
py main.py "tray.jpg" --corners 150 100 1850 80 1890 1770 180 1810 --rows 12 --cols 12
```

These example coordinates are not coordinates for the uploaded images. Four corners can also be used without `--rows/--cols` and the grid detector will estimate the counts itself.

A manually specified rotation angle is also supported: `--rotate -2.5`. The normal default `--rotate auto` is recommended for ordinary overhead photographs.

## Tuning vegetation detection

`config.py` contains these important parameters:

- `GREEN_H_MIN`, `GREEN_H_MAX`, `GREEN_S_MIN`, `GREEN_V_MIN`: HSV leaf gate
- `EXCESS_GREEN_MIN` and `NORMALIZED_EXCESS_GREEN_MIN`: green relative to red/blue (rejects brown soil, grey plastic)
- `CELL_INSET_FRACTION`: mask the tray wall around a cell (too large can crop leaves)
- `MIN_LEAF_AREA_FRACTION` and `MIN_PLANT_AREA_FRACTION`: background noise rejection versus small leaf sensitivity
- `SPLIT_TOUCHING_LEAVES`: enable/disable **estimated** watershed leaf separation

Review representative pictures in different lighting conditions after any threshold changes. The program is designed for dark soil and green tobacco seedlings; green algae/grass, green labels, shadows, leaf overlap, and leaves outside the cell ROI may still require manual review. Dense seedlings and very young plants may require separately tuned settings.

## Validation notes

Checks were performed on the uploaded photos at reduced resolution and on representative full-resolution images. The file `tests/test_pipeline.py` contains basic reproducible automated tests. **No precise accuracy percentage** is claimed because the provided black-and-white mask does not include a verified matching per-pixel annotation for each photo.

For the most dependable results, mount the camera directly overhead with diffuse lighting, consistently align the trays, capture a ruler/calibration marker, and collect a hand-annotated reference set of seedlings to evaluate leaf area and false-positive/negative rates. The oblique `IMG_8426.JPG` shows multiple trays and needs perspective selection for each tray instead of running automatic single-tray analysis directly.

## Analyze a whole folder of photographs

```powershell
py batch_run.py "C:\Photos\Tray Imaging Project" --output-dir "batch_results" --cell-pitch-in 1.0
```

Each image gets its own output subfolder. A failed or multi-tray picture is reported without stopping the remaining images. The physical pitch is still unverified in this example; replace `1.0` with your measured center-to-center pitch.


## Centering the grid on the plastic margins (new)

`grid_detection.py` now refines each detected row/column boundary to the **middle of
its plastic separator/margin**, rather than stopping at the first strong wall edge.
The correction happens *after* auto-rotation or perspective rectification and uses
a median brightness profile across the tray. When a clear separator band cannot
be found, it falls back to the original edge position. This avoids making large,
unsupported shifts for very dark, damaged, or obscured walls.

Settings in `config.py`:

- `CENTER_GRID_LINES_ON_MARGINS = True`: enable/disable margin centering.
- `MARGIN_SEARCH_FRACTION = 0.22`: maximum search distance from the originally detected wall edge, expressed as a fraction of cell pitch.
- `MARGIN_RIDGE_THRESHOLD = 0.53`: fraction of the wall-vs-soil brightness range used to locate both sides of the wall.
- `MARGIN_MIN_CONTRAST = 7.0`: minimum contrast necessary to move a line; otherwise keep the old location.

**Important:** `grid_overlay.png` shows the lines centered on the walls. Those
same coordinates are used to crop each cell for seedling detection and Excel
export. If a photo is extremely skewed, contains multiple trays, or has an
unusual tray wall material, inspect the overlay and manually select corners
when appropriate. The leaf area still requires a measured cell-to-cell
physical pitch for true mm² calibration.

### One-click Windows batch run for the supplied photo folder

The updated `run_example.bat` expects photos here:

`C:\Users\Daniel\Downloads\OneDrive_2026-10-28\Tray Imaging Project`

Double-click it from the extracted project folder. It writes `batch_results`.
If your photo folder moves, change the `PHOTO_DIR` variable in the `.bat` file.
