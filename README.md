# Tobacco Vision v2

This version separates the project into grid detection, leaf analysis, visualization, and Excel export.

## What it does

1. Automatically finds the repeating center-to-center tray spacing in pixels.
2. Automatically determines the number of rows and columns from the detected grid lines.
3. Assumes the physical center-to-center pitch is **1.0 inch x 1.0 inch** by default.
4. Uses that 1-inch calibration to convert pixels into millimeters.
5. Detects green leaf regions inside each tray cell.
6. Measures each detected leaf region's length, width, area, and average color.
7. Writes an Excel workbook where **Excel A1 corresponds to physical tray row 1 / column 1, B1 to row 1 / column 2, etc.**
8. Saves verification images so you can check the grid and leaf segmentation before trusting the measurements.

## Files

- `main.py` - program entry point
- `config.py` - values you are expected to tune/change
- `grid_detection.py` - automatic grid and center-to-center spacing detection
- `leaf_analysis.py` - green segmentation and leaf measurements
- `excel_export.py` - Excel tray map and detailed measurements
- `visualization.py` - grid/leaf overlay images and optional windows
- `models.py` - small data classes shared by the modules

## Install

From PowerShell or Command Prompt in this folder:

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py "tobacco_tray.jpg" --show
```

Or give the full path to an image:

```powershell
python main.py "C:\Users\Daniel\Pictures\tray_photo.jpg" --show
```

The program creates an `output` folder containing:

- `grid_overlay.png`
- `leaf_mask.png`
- `leaf_overlay.png`
- `tobacco_measurements.xlsx`

## Changing the cell size later

The default physical pitch is set in `config.py`:

```python
CELL_PITCH_X_IN = 1.0
CELL_PITCH_Y_IN = 1.0
```

The spacing **in pixels is always auto-detected**. These settings only say what that detected pitch represents physically.

You can also override both values for one run without editing the file:

```powershell
python main.py "tray_photo.jpg" --cell-pitch-in 0.95 --show
```

## Important calibration note

For accurate millimeter measurements, `CELL_PITCH_X_IN` and `CELL_PITCH_Y_IN` should eventually be the **true physical center-to-center spacing** of neighboring tray cells. If "1 inch" only describes the open soil square and the plastic wall adds extra distance, measure the actual center-to-center pitch and update the values.

## What to inspect first

Always look at `grid_overlay.png` first. If the red/blue grid lines do not line up with the tray walls, do not trust the Excel measurements yet. The grid detector can be tuned in `config.py` without changing the rest of the program.

Next inspect `leaf_mask.png`. White pixels are what the program believes are leaves. The main leaf-tuning values are:

```python
GREEN_H_MIN = 30
GREEN_H_MAX = 95
GREEN_S_MIN = 45
GREEN_V_MIN = 100
EXCESS_GREEN_MIN = 30
```

The sample screenshot is relatively low-resolution and has soil/plastic color variation, so the leaf thresholds will almost certainly be worth tuning again once the controlled, higher-resolution camera images are available.
