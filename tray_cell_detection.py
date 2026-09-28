
# Tobacco Vision
import cv2
import numpy as np



# Load image
image = cv2.imread("tobacco_tray.jpg")

if image is None:
    print("Error: Could not load image.")
    exit()

# Make a copy
output = image.copy()

# Convert image from BGR to HSV

hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

hsv = cv2.GaussianBlur(hsv, (5, 5), 0)


# Detect colorful objects(RGB)

lower_color = np.array([0, 49, 100])
upper_color = np.array([179, 255, 255])

mask = cv2.inRange(
    hsv,
    lower_color,
    upper_color
)

# Clean up the mask

# Remove small noise
open_kernel = cv2.getStructuringElement(
    cv2.MORPH_ELLIPSE,
    (3, 3)
)

mask = cv2.morphologyEx(
    mask,
    cv2.MORPH_OPEN,
    open_kernel,
    iterations=2
)

# Fill small holes in detected objects
close_kernel = cv2.getStructuringElement(
    cv2.MORPH_ELLIPSE,
    (3, 3)
)

mask = cv2.morphologyEx(
    mask,
    cv2.MORPH_CLOSE,
    close_kernel,
    iterations=1
)

# Find contours

contours, _ = cv2.findContours(
    mask,
    cv2.RETR_EXTERNAL,
    cv2.CHAIN_APPROX_SIMPLE
)

detected_objects = []

# Filter contours


for contour in contours:

    # Find contour area
    area = cv2.contourArea(contour)

    # Ignore very small objects/noise
    if area < 400:
        continue

    # Get normal bounding box
    x, y, w, h = cv2.boundingRect(contour)

    # Ignore objects touching the edge of the image
    if (
        x <= 2 or
        y <= 2 or
        x + w >= image.shape[1] - 2 or
        y + h >= image.shape[0] - 2
    ):
        continue

    detected_objects.append(contour)

# Sort objects from top to bottom

detected_objects.sort(
    key=lambda c: cv2.boundingRect(c)[1]
)

# Bounding box settings

# Amount of extra space around EACH side of the object
padding = 0

object_number = 1

# Draw bounding boxes

for contour in detected_objects:

    # Create rotated rectangle around object
    rect = cv2.minAreaRect(contour)

    # Get rectangle information
    (center_x, center_y), (width, height), angle = rect

    width = width + (padding * 2)
    height = height + (padding * 2)

    # Create larger rotated rectangle
    larger_rect = (
        (center_x, center_y),
        (width, height),
        angle
    )

    # Get the four corners of the larger rectangle
    box = cv2.boxPoints(larger_rect)
    box = np.intp(box)
    box = np.int32(box)

    # Draw the bounding box


    cv2.polylines(
        output,
        [box],
        True,
        (0, 0, 255),
        8,
        cv2.LINE_AA
    )

    # Draw object number
   

    cv2.putText(
        output,
        str(object_number),
        (int(center_x) - 7, int(center_y) + 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 0),
        2,
        cv2.LINE_AA
    )

    object_number += 1

# Print number of detected objects

print("Objects detected:", object_number - 1)


cv2.namedWindow(
    "Detection Mask",
    cv2.WINDOW_NORMAL
)

cv2.namedWindow(
    "Tobacco Vision Object Detection",
    cv2.WINDOW_NORMAL
)

# Starting window sizes
cv2.resizeWindow(
    "Detection Mask",
    900,
    700
)

cv2.resizeWindow(
    "Tobacco Vision Object Detection",
    1000,
    750
)

# Display images

cv2.imshow(
    "Detection Mask",
    mask
)

cv2.imshow(
    "Tobacco Vision Object Detection",
    output
)

cv2.waitKey(0)

cv2.destroyAllWindows()