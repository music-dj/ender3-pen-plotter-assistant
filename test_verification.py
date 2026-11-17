"""
Verification script for Pen Plotter Assistant.
Tests end-to-end image preprocessing, skeletonization, contour tracing, and SVG generation.
"""
import os
import sys
import cv2
import numpy as np
import xml.etree.ElementTree as ET

# Force UTF-8 on Windows terminal
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from core.processor import ImageProcessor
from core.skeletonizer import Vectorizer
from core.svg_exporter import SVGExporter

def test_pipeline():
    print("🧪 [Test 1] Creating synthetic test line drawing...")
    # Create a 300x300 image with black lines on white background
    test_img = np.ones((300, 300), dtype=np.uint8) * 255
    cv2.circle(test_img, (150, 150), 80, 0, thickness=3)
    cv2.line(test_img, (50, 150), (250, 150), 0, thickness=3)
    cv2.line(test_img, (150, 50), (150, 250), 0, thickness=3)
    
    test_img_path = "test_sketch.png"
    cv2.imwrite(test_img_path, test_img)
    print("   Created test image:", test_img_path)

    print("🧪 [Test 2] Testing ImageProcessor...")
    binary, gray = ImageProcessor.load_and_preprocess(test_img_path, threshold_val=128, invert=False)
    assert binary.shape == (300, 300), "Shape mismatch"
    assert binary.max() == 255 and binary.min() == 0, "Binary range invalid"
    print("   ImageProcessor: SUCCESS")

    print("🧪 [Test 3] Testing Centerline Skeletonizer...")
    polylines_center = Vectorizer.extract_centerline(binary, epsilon=0.8)
    print(f"   Centerline paths found: {len(polylines_center)}")
    assert len(polylines_center) > 0, "No centerlines extracted!"
    total_points = sum(len(p) for p in polylines_center)
    print(f"   Total skeleton points: {total_points}")
    print("   Skeletonizer: SUCCESS")

    print("🧪 [Test 4] Testing Contour Vectorizer...")
    polylines_contour = Vectorizer.extract_contours(binary, epsilon=1.0)
    print(f"   Contour paths found: {len(polylines_contour)}")
    assert len(polylines_contour) > 0, "No contours extracted!"
    print("   Contour Vectorizer: SUCCESS")

    print("🧪 [Test 5] Testing SVG Generation & Physical Constraints (< 0.2mm)...")
    target_w = 180.0 # mm
    target_h = 180.0 # mm
    stroke_w = 0.15  # mm (< 0.2mm)
    svg_str = SVGExporter.generate_svg(
        polylines=polylines_center,
        img_width=300,
        img_height=300,
        target_width_mm=target_w,
        target_height_mm=target_h,
        stroke_width_mm=stroke_w
    )

    # Verify SVG contains correct stroke width
    assert 'stroke-width="0.150mm"' in svg_str or 'stroke-width="0.15' in svg_str, "Stroke width mismatch!"
    assert f'width="{target_w:.2f}mm"' in svg_str, "Width mm mismatch!"
    assert f'height="{target_h:.2f}mm"' in svg_str, "Height mm mismatch!"

    # Parse XML to verify syntax
    root = ET.fromstring(svg_str)
    assert root.tag.endswith("svg"), "Root element must be svg"
    print("   SVG XML Parsing & <0.2mm Stroke verification: SUCCESS")

    output_svg_path = "test_output.svg"
    SVGExporter.save_svg(output_svg_path, svg_str)
    assert os.path.exists(output_svg_path), "SVG output file was not created"
    file_size = os.path.getsize(output_svg_path)
    print(f"   Saved SVG successfully ({file_size} bytes): {output_svg_path}")

    # Cleanup test files
    if os.path.exists(test_img_path):
        os.remove(test_img_path)
    if os.path.exists(output_svg_path):
        os.remove(output_svg_path)

    print("\n✅ All core tests PASSED successfully!")

if __name__ == "__main__":
    test_pipeline()
