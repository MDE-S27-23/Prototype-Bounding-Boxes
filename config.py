"""Configuration for Tobacco Vision v2.

The most important calibration values are CELL_PITCH_X_IN and CELL_PITCH_Y_IN.
The software AUTO-DETECTS their spacing in pixels from the image; these values
only tell it how large that detected spacing is in the real world.
"""


# Physical calibration

# For now we assume neighboring cell centers are 1 inch apart in X and Y.
# Change these later if the measured physical pitch is different.
CELL_PITCH_X_IN = 1.0
CELL_PITCH_Y_IN = 1.0
MM_PER_INCH = 25.4

# Automatic grid detection

# Leave as None for automatic limits based on image size. If the detector ever
# locks onto the wrong repeating pattern, these can be set manually in pixels.
MIN_CELL_PITCH_PX = None
MAX_CELL_PITCH_PX = None

# Fraction of image size used when automatic pitch limits are selected.
AUTO_MIN_PITCH_FRACTION = 0.02
AUTO_MAX_PITCH_FRACTION = 0.20

# Edge pixels from the top/bottom or left/right can contain labels, camera UI,
# etc. This fraction is ignored when scoring the best repeating phase.
PHASE_IGNORE_EDGE_FRACTION = 0.03

# Local search radius around each predicted grid line, as a fraction of pitch.
GRID_LINE_SEARCH_FRACTION = 0.08

# Trim very weak lines from only the outside edges of the detected grid.
GRID_EDGE_SCORE_FRACTION = 0.55

# Number of grid lines required in each direction. 3 lines = at least 2 cells.
MIN_GRID_LINES = 3


# Leaf segmentation

# OpenCV hue runs 0..179. These defaults are aimed at green tobacco leaves.
GREEN_H_MIN = 30
GREEN_H_MAX = 95
GREEN_S_MIN = 45
GREEN_V_MIN = 100

# Excess-green threshold: ExG = 2G - R - B.
EXCESS_GREEN_MIN = 30

# Ignore the plastic wall area by shrinking each cell before leaf analysis.
CELL_INSET_FRACTION = 0.12

# Small contour filtering relative to cell area. These scale with resolution.
MIN_LEAF_AREA_FRACTION = 0.0015
MAX_LEAF_AREA_FRACTION = 0.30

# Morphological cleanup kernels. Use odd numbers.
LEAF_OPEN_KERNEL = 3
LEAF_CLOSE_KERNEL = 3

# Experimental separator for leaves that touch each other.
SPLIT_TOUCHING_LEAVES = True
WATERSHED_PEAK_FRACTION = 0.42
MIN_SPLIT_REGION_AREA_FRACTION = 0.0012

# If a plant/leaf touches the analysis ROI boundary, flag it for review.
BOUNDARY_REVIEW_MARGIN_PX = 1

# Display / export

SHOW_WINDOWS = False
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 850

# Draw labels in the grid overlay. On very large trays this can be cluttered;
# set False if you only want the lines and centers.
DRAW_CELL_LABELS = True
