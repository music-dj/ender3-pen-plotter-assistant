"""
Verification Test for v1.2 updates:
1. Safe park at (0,0) on Pause + Audio Beep Chime + Z-Hop on Resume.
2. Tab reordering: Settings is Tab 2, Preview is Tab 3.
3. Fix zoom-out bug during recoloring (preserve_view).
4. Save and Open drawing projects (.plotproj) with full color layers intact.
5. App version 1.2 and modern icon assets.
"""
import os
import time
import shapely.geometry as sg
from core.version import APP_VERSION, APP_TITLE
from core.project_manager import ProjectManager
from core.serial_printer import SerialPrinter
from ui.app_window import AppWindow

def test_version_and_assets():
    print("=" * 50)
    print(f"TEST 1: Version Verification (Currently {APP_VERSION}) and Icon Assets")
    print("=" * 50)
    assert float(APP_VERSION) >= 1.4, f"Expected version >= 1.4, got {APP_VERSION}"
    print(f"App Version verified: v{APP_VERSION} ({APP_TITLE})")

    ico_path = os.path.join("assets", "app_icon.ico")
    png_path = os.path.join("assets", "app_icon.png")
    assert os.path.exists(ico_path), "assets/app_icon.ico must exist!"
    assert os.path.exists(png_path), "assets/app_icon.png must exist!"
    print(f"Icon assets exist: ICO ({os.path.getsize(ico_path)} bytes), PNG ({os.path.getsize(png_path)} bytes)")
    print("✅ TEST 1 PASSED: Version v1.3 & Icon assets verified!\n")

def test_tab_reordering():
    print("=" * 50)
    print("TEST 2: Tab Order (Settings = Tab 2, Preview = Tab 3)")
    print("=" * 50)
    app = AppWindow()
    app.withdraw()

    # In customtkinter, tabs are stored in _tab_dict
    tab_names = list(app.tabview._tab_dict.keys())
    print("Registered Tab Order in AppWindow:")
    for idx, name in enumerate(tab_names, 1):
        print(f"  Tab {idx}: {name}")

    assert tab_names[0] == "🎨 التصميم والمجسم 3D", "Tab 1 must be Design!"
    assert tab_names[1] == "⚙️ إعدادات التقطيع والطباعة", "Tab 2 must be Settings!"
    assert tab_names[2] == "📐 معاينة السلايس (ورقة A5)", "Tab 3 must be Slicer Preview!"
    assert tab_names[3] == "🖨️ الاتصال بالطابعة والتحكم المباشر", "Tab 4 must be Printer!"

    app.destroy()
    print("✅ TEST 2 PASSED: Tab order verified (Settings is Tab 2, Preview is Tab 3)!\n")

def test_preserve_zoom_on_coloring():
    print("=" * 50)
    print("TEST 3: Preserve Zoom and Pan on Coloring (No Auto Zoom-Out)")
    print("=" * 50)
    app = AppWindow()
    app.withdraw()
    preview_tab = app.slicer_preview_tab

    # Simulate user zooming and panning into fine details
    preview_tab.base_scale = 3.0
    preview_tab.zoom = 2.5
    preview_tab.pan_x = 120.5
    preview_tab.pan_y = 85.0

    dummy_slice = {
        "ordered_moves": [{"type": "wall", "points": [(10, 10), (20, 20)], "color": "#EF4444"}],
        "color_layers_summary": [{"hex": "#EF4444", "name": "أحمر", "drawn_meters": 0.5}],
        "model_w_mm": 50.0,
        "model_h_mm": 50.0
    }

    # Calling set_slice_result with preserve_view=True (as triggered during recoloring)
    preview_tab.set_slice_result(dummy_slice, preserve_view=True)

    print(f"After recolor slice: zoom={preview_tab.zoom}, pan_x={preview_tab.pan_x}, pan_y={preview_tab.pan_y}")
    assert preview_tab.zoom == 2.5, "Zoom level must be preserved (not reset to 1.0)!"
    assert preview_tab.pan_x == 120.5 and preview_tab.pan_y == 85.0, "Pan position must be preserved!"

    app.destroy()
    print("✅ TEST 3 PASSED: Zoom level and pan position stay 100% locked during recoloring!\n")

def test_project_save_and_load():
    print("=" * 50)
    print("TEST 4: Save & Open Project (.plotproj) with Multi-Color Layers")
    print("=" * 50)

    # Build mock multi-color layers
    poly1 = sg.Polygon([(10, 10), (30, 10), (30, 30), (10, 30)])
    poly2 = sg.Polygon([(50, 50), (80, 50), (80, 80), (50, 80)])
    line1 = sg.LineString([(0, 0), (10, 15), (20, 5)])
    dot1 = sg.Point(40, 40)

    original_layers = {
        "#EF4444": {
            "hex": "#EF4444",
            "name": "أحمر",
            "polygons": [poly1],
            "lines": [line1]
        },
        "#3B82F6": {
            "hex": "#3B82F6",
            "name": "أزرق",
            "polygons": [poly2],
            "lines": [dot1]
        }
    }

    project_data = {
        "target_width_mm": 180.0,
        "target_height_mm": 120.0,
        "thickness_mm": 0.3,
        "lock_aspect": True,
        "infill_pattern": "Honeycomb",
        "infill_density": 25.0,
        "paper_preset": "ورقة A5 بالعرض (210 × 148 مم)",
        "paper_placement": "center",
        "paper_margin_mm": 10.0,
        "color_layers": original_layers
    }

    test_file = "test_artwork_v1.2.plotproj"
    ProjectManager.save_project(test_file, project_data)
    assert os.path.exists(test_file), "Project file should be written to disk!"

    # Load back
    loaded = ProjectManager.load_project(test_file)
    assert float(loaded["version"]) >= 1.4
    assert loaded["model_width_mm"] == 180.0
    assert loaded["infill_pattern"] == "Honeycomb"

    restored_layers = loaded["color_layers"]
    assert "#EF4444" in restored_layers and "#3B82F6" in restored_layers
    assert len(restored_layers["#EF4444"]["polygons"]) == 1
    assert len(restored_layers["#EF4444"]["lines"]) == 1
    assert len(restored_layers["#3B82F6"]["lines"]) == 1

    p_restored = restored_layers["#EF4444"]["polygons"][0]
    assert abs(p_restored.area - poly1.area) < 0.001

    if os.path.exists(test_file):
        os.remove(test_file)

    print("✅ TEST 4 PASSED: Complete multi-color drawing project save & load verified!\n")

def test_serial_pause_park_and_beeps():
    print("=" * 50)
    print("TEST 5: Serial Printer Pause Park at (0,0) and Beep Alerts")
    print("=" * 50)
    printer = SerialPrinter()

    # Track commands simulated
    sent_commands = []
    def mock_send(cmd, wait_ok=True, timeout=8.0):
        sent_commands.append(cmd)
        return True
    printer.send_command = mock_send

    # G-code simulation with movement and tool change
    lines = [
        "G90",
        "G1 Z1.50 F600",
        "G1 X50.000 Y50.000 F3000",
        "G1 Z0.30 F300",
        "G1 X60.000 Y50.000 F1500",
        "TOOL_CHANGE_COLOR: #10B981 | أخضر",
        "G1 X70.000 Y50.000 F1500"
    ]

    # Test tool change audio chime on printer buzzer (M300) and PC
    printer.on_tool_change_request = lambda h, n: None
    printer.beep_printer_chime()
    time.sleep(0.3)
    printer._play_beep_chime()
    printer._play_beep(1000, 100)

    # Verify M300 was issued for buzzer
    has_m300_buzzer = any("M300" in c for c in sent_commands)
    print(f"  - Printer buzzer M300 emitted: {has_m300_buzzer}")
    assert has_m300_buzzer, "Printer buzzer M300 must be sent to printer!"

    # Verify SlicerEngine generates M300 in G-code for multi-color pen swap
    from core.slicer_engine import SlicerEngine
    dummy_layers = {
        "#EF4444": {"hex": "#EF4444", "name": "أحمر", "polygons": [sg.Polygon([(0,0),(10,0),(10,10),(0,10)])], "lines": []},
        "#3B82F6": {"hex": "#3B82F6", "name": "أزرق", "polygons": [sg.Polygon([(20,20),(30,20),(30,30),(20,30)])], "lines": []}
    }
    slice_res = SlicerEngine.slice_color_layers(dummy_layers, 50, 50)
    assert "M300 S1000 P150" in slice_res["gcode"], "G-Code must contain M300 buzzer tone 1 for pen swap!"
    assert "M300 S1500 P150" in slice_res["gcode"], "G-Code must contain M300 buzzer tone 2 for pen swap!"
    assert "M300 S2000 P350" in slice_res["gcode"], "G-Code must contain M300 buzzer tone 3 for pen swap!"
    assert "M117 Swap to" in slice_res["gcode"], "G-Code must contain M117 LCD notification for pen swap!"
    print("  - G-Code contains M300 buzzer tones & M117 LCD display: True")

    # Test pause park logic
    import threading
    printer.is_printing = True
    printer._pause_requested = True

    # Resume after 0.3s so the stream worker finishes
    resume_timer = threading.Timer(0.3, printer.resume_print)
    resume_timer.start()

    printer._stream_worker(lines[:5])
    resume_timer.join()

    print("Commands recorded in streaming:")
    has_park_zero = any("G0 X0 Y0" in c for c in sent_commands)
    has_zhop_return = any("Safety Z-Hop" in c or "Safe Lift" in c for c in sent_commands)
    print(f"  - Moved to Pen Swap (0,0): {has_park_zero}")
    print(f"  - Safe Z-Hop executed: {has_zhop_return}")

    assert has_park_zero, "Head must park at (0, 0) on pause!"
    assert has_zhop_return, "Safety Z-Hop must execute on pause and resume!"

    print("✅ TEST 5 PASSED: Printer buzzer M300 + Safe park at (0,0) verified!\n")

if __name__ == "__main__":
    test_version_and_assets()
    test_tab_reordering()
    test_preserve_zoom_on_coloring()
    test_project_save_and_load()
    test_serial_pause_park_and_beeps()
    print("🎉 ALL 5 V1.3 SUITE TESTS PASSED 100%!")
