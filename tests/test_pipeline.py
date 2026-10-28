"""Run from the project folder: python -m unittest discover -s tests -v"""
import unittest
import cv2
import numpy as np

from leaf_analysis import _green_mask, _accepted_plant_mask, _measure_region
from models import GridInfo
from rectification import rectify_image
from grid_detection import detect_grid, grid_from_dimensions, _center_lines_in_margins


class TobaccoTests(unittest.TestCase):
    def test_green_versus_soil_and_grey(self):
        im = np.zeros((90, 240, 3), dtype=np.uint8)
        im[:,:80] = (65, 140, 60)    # leaf green, BGR
        im[:,80:160] = (60, 65, 73)  # soil brown
        im[:,160:] = (90, 90, 90)    # plastic grey
        m = _green_mask(im)
        self.assertGreater(cv2.countNonZero(m[:5,:80]), 200)
        self.assertEqual(cv2.countNonZero(m[:,85:155]),0)
        self.assertEqual(cv2.countNonZero(m[:,165:]),0)

    def test_pixel_exact_area(self):
        r = np.zeros((50,50),np.uint8)
        r[10:20,5:15] = 255
        im = np.full((50,50,3),(55,110,50),np.uint8)
        g = GridInfo([0,50],[0,50],50,50,.2,.3)
        leaf = _measure_region(r,im,(0,0),g,1,False)
        self.assertEqual(leaf.area_px,100)
        self.assertAlmostEqual(leaf.area_mm2,6.)

    def test_rotation_alignment(self):
        # A toy 8-by-9 grid rotated off-axis (independent of sample photos).
        nrows,ncols,pitch=8,9,54
        im = np.full((nrows*pitch,ncols*pitch,3), (35,35,35), np.uint8)
        for y in range(nrows):
            for x in range(ncols):
                xa, ya = x*pitch, y*pitch
                cv2.rectangle(im,(xa,ya),(xa+pitch-1,ya+pitch-1),(90,90,90),3)
                cv2.circle(im,(xa+pitch//2,ya+pitch//2),7,(40,120,45),-1)
        h,w=im.shape[:2]
        rotation=cv2.getRotationMatrix2D((w/2,h/2),9.,1.)
        tilted=cv2.warpAffine(im,rotation,(w,h),borderValue=(35,35,35))
        corrected,ang,_,_ = rectify_image(tilted)
        grid=detect_grid(corrected)
        self.assertLess(abs(abs(ang)-9.),2.)
        self.assertGreaterEqual(grid.rows,6)
        self.assertGreaterEqual(grid.columns,7)

    def test_grid_lines_center_on_divider_margins(self):
        # Simulate uniform 16-pixel-wide bright plastic walls separating
        # dark soil cells. The initial Sobel estimates sit on right edges.
        im = np.full((480, 480), 35, dtype=np.uint8)
        true_centers = np.array([85, 165, 245, 325, 405])
        for x in true_centers:
            im[:, x-8:x+8] = 90
        for y in true_centers:
            im[y-8:y+8, :] = 90
        edge_lines = true_centers + 8
        refined_x = _center_lines_in_margins(im, edge_lines, edge_lines, 'x')
        refined_y = _center_lines_in_margins(im, edge_lines, edge_lines, 'y')
        self.assertLessEqual(np.max(np.abs(refined_x - true_centers)), 2)
        self.assertLessEqual(np.max(np.abs(refined_y - true_centers)), 2)

    def test_margin_fallback_without_visible_wall(self):
        # When no convincing ridge is visible, don't invent a divider.
        im = np.full((300, 300), 45, dtype=np.uint8)
        lines = np.array([45, 105, 165, 225, 285])
        refined = _center_lines_in_margins(im, lines, lines, 'x')
        np.testing.assert_array_equal(refined, lines)

    def test_four_corner_rectification(self):
        im=np.zeros((350,460,3),np.uint8)
        pts=[(40,35),(400,45),(440,320),(60,315)]
        for p in pts: cv2.circle(im,p,5,(255,255,255),-1)
        rect,ang,_,mode=rectify_image(im,corners=pts)
        self.assertEqual(mode,'manual-perspective')
        self.assertEqual(ang,0.)
        g=grid_from_dimensions(rect.shape,8,9)
        self.assertEqual((g.rows,g.columns),(8,9))


if __name__=='__main__':
    unittest.main()
