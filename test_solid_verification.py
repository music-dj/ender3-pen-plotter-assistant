import sys
import io
import os
import numpy as np
import cv2

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from ui.app_window import AppWindow
from core.solid_vectorizer import SolidVectorizer
from core.stl_exporter import STLExporter

def run_tests():
    print("--- Test 1: Window Instantiation & TkinterDnD ---")
    app = AppWindow()
    app.update()
    print("AppWindow initialized with TkinterDnD version:", app.TkdndVersion)

    print("--- Test 2: Solid Vectorizer (0.2mm) ---")
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.circle(mask, (50, 50), 30, 255, -1)
    cv2.circle(mask, (50, 50), 10, 0, -1)  # inner hole

    res = SolidVectorizer.vectorize_to_solid_svg(mask, target_width_mm=100, target_height_mm=100, thickness_mm=0.2)
    svg = res["svg"]
    assert "fill-rule=\"evenodd\"" in svg, "evenodd missing"
    assert "0.20" in svg, "0.20mm thickness missing"
    print("Solid SVG generated with evenodd and 0.2mm thickness. Stats:", res["stats"])

    print("--- Test 3: 3D STL Exporter (0.2mm) ---")
    stl_file = "test_check_0.2mm.stl"
    count = STLExporter.export_binary_stl(mask, stl_file, 100, 100, 0.2)
    assert os.path.exists(stl_file), "STL not created"
    size = os.path.getsize(stl_file)
    print(f"STL exported successfully with {count} triangles ({size} bytes)!")
    os.remove(stl_file)

    print("--- Test 4: Drag and Drop Event Handling ---")
    class FakeDropEvent:
        data = "{test_fake.png}"

    test_img = np.ones((50, 50, 3), dtype=np.uint8) * 200
    cv2.imwrite("test_fake.png", test_img)
    app.on_drop_event(FakeDropEvent())
    app.update()
    print("Fake drop processed successfully!")
    os.remove("test_fake.png")

    app.destroy()
    print("\n✅ All 3D Solid & Drag and Drop tests PASSED with zero errors!")

if __name__ == "__main__":
    run_tests()
