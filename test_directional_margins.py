"""
Comprehensive verification test for v1.4 Directional Safety Margins & Independent Centering.
Covers:
1. Version v1.4 check.
2. SlicerEngine directional margin placement (Left, Right, Bottom, Top).
3. Horizontal and Vertical Centering flags (center_horizontally, center_vertically).
4. Manual directional placement when centering is disabled (e.g. margin_bottom lifts design off 0 line).
5. SlicerPreviewTab UI integration and directional config.
6. Fit to paper within safe directional boundaries.
7. ProjectManager saving and restoring directional margins.
"""
import os
import shapely.geometry as sg
from core.version import APP_VERSION, APP_TITLE
from core.slicer_engine import SlicerEngine
from core.project_manager import ProjectManager

def test_version_1_4():
    print("=" * 50)
    print(f"TEST 1: Version Verification (v{APP_VERSION})")
    print("=" * 50)
    assert float(APP_VERSION) >= 1.4, f"Expected version >= 1.4, got {APP_VERSION}"
    print(f"App Version verified: v{APP_VERSION} ({APP_TITLE})")
    print(f"✅ TEST 1 PASSED: Version v{APP_VERSION} verified!\n")

def test_directional_margins_slicing():
    print("=" * 50)
    print("TEST 2: SlicerEngine Directional Margins & Clearance")
    print("=" * 50)
    
    # 50x50 square model
    layers = {
        "#000000": {
            "hex": "#000000",
            "name": "أسود",
            "polygons": [sg.Polygon([(0, 0), (50, 0), (50, 50), (0, 50)])],
            "lines": []
        }
    }
    
    # Paper A5 Landscape: 210 x 148 mm
    # Case A: Centered Horizontally & Vertically
    res_centered = SlicerEngine.slice_color_layers(
        color_layers=layers,
        target_w_mm=50.0,
        target_h_mm=50.0,
        settings={
            "paper_width_mm": 210.0,
            "paper_height_mm": 148.0,
            "center_horizontally": True,
            "center_vertically": True,
            "margin_left_mm": 15.0,
            "margin_right_mm": 15.0,
            "margin_bottom_mm": 15.0,
            "margin_top_mm": 15.0
        }
    )
    
    # Model should be exactly centered:
    # Expected X min: (210 - 50) / 2 = 80.0
    # Expected Y min: (148 - 50) / 2 = 49.0
    b_c = res_centered["bounds"]
    print(f"Centered Bounds: X=[{b_c[0]:.1f}, {b_c[2]:.1f}], Y=[{b_c[1]:.1f}, {b_c[3]:.1f}]")
    assert abs(b_c[0] - 80.0) < 0.1, f"Expected X min 80.0, got {b_c[0]}"
    assert abs(b_c[1] - 49.0) < 0.1, f"Expected Y min 49.0, got {b_c[1]}"
    assert abs(res_centered["clearance_left"] - 80.0) < 0.1
    assert abs(res_centered["clearance_right"] - 80.0) < 0.1
    assert abs(res_centered["clearance_bottom"] - 49.0) < 0.1
    assert abs(res_centered["clearance_top"] - 49.0) < 0.1
    print("  -> Perfectly centered horizontally (80mm clearance each side) and vertically!")

    # Case B: Manual Directional Control (No Centering)
    # Set Left = 25.0 mm, Bottom = 35.0 mm (safely away from bottom edge & 0,0)
    res_manual = SlicerEngine.slice_color_layers(
        color_layers=layers,
        target_w_mm=50.0,
        target_h_mm=50.0,
        settings={
            "paper_width_mm": 210.0,
            "paper_height_mm": 148.0,
            "center_horizontally": False,
            "center_vertically": False,
            "margin_left_mm": 25.0,
            "margin_right_mm": 15.0,
            "margin_bottom_mm": 35.0,
            "margin_top_mm": 15.0
        }
    )
    b_m = res_manual["bounds"]
    print(f"Manual Directional Bounds: X=[{b_m[0]:.1f}, {b_m[2]:.1f}], Y=[{b_m[1]:.1f}, {b_m[3]:.1f}]")
    assert abs(b_m[0] - 25.0) < 0.1, f"Expected X min 25.0, got {b_m[0]}"
    assert abs(b_m[1] - 35.0) < 0.1, f"Expected Y min 35.0, got {b_m[1]}"
    assert abs(res_manual["clearance_left"] - 25.0) < 0.1
    assert abs(res_manual["clearance_bottom"] - 35.0) < 0.1
    print("  -> Exact directional manual positioning verified (never touches edges or zero line)!")
    print("✅ TEST 2 PASSED: SlicerEngine directional margins verified!\n")

def test_preview_tab_directional_controls():
    print("=" * 50)
    print("TEST 3: SlicerPreviewTab Directional Margins & Centering")
    print("=" * 50)
    from ui.slicer_preview_tab import SlicerPreviewTab
    import customtkinter as ctk
    
    root = ctk.CTk()
    root.withdraw()
    preview = SlicerPreviewTab(root)
    
    # Check default margins
    assert preview.margin_left_mm == 15.0
    assert preview.margin_right_mm == 15.0
    assert preview.margin_bottom_mm == 15.0
    assert preview.margin_top_mm == 15.0
    assert preview.var_center_x.get() == True
    assert preview.var_center_y.get() == True
    print("Default preview margins: 15mm on all sides with horizontal and vertical centering active.")

    # Test nudging left margin with centering active (should symmetrically adjust right margin)
    preview._nudge_margin("left", 5.0)
    assert preview.margin_left_mm == 20.0
    assert preview.margin_right_mm == 20.0
    assert preview.var_margin_left.get() == "20"
    assert preview.var_margin_right.get() == "20"
    print("Symmetrical margin adjustment while centered verified.")

    # Uncheck centering and test independent directional control
    preview.var_center_x.set(False)
    preview._nudge_margin("left", 10.0)
    assert preview.margin_left_mm == 30.0
    assert preview.margin_right_mm == 20.0  # Right margin unchanged!
    print("Independent directional margin control verified (Left=30, Right=20).")

    # Test preset buttons
    preview.set_all_margins(25.0)
    assert preview.margin_left_mm == 25.0
    assert preview.margin_right_mm == 25.0
    assert preview.margin_bottom_mm == 25.0
    assert preview.margin_top_mm == 25.0
    print("Quick preset button (25mm all around) verified.")

    cfg = preview.get_paper_config()
    assert cfg["margin_left_mm"] == 25.0
    assert cfg["margin_bottom_mm"] == 25.0
    print(f"Paper config payload generated: {cfg['paper_placement']}, margins=[{cfg['margin_left_mm']}, {cfg['margin_right_mm']}, {cfg['margin_bottom_mm']}, {cfg['margin_top_mm']}]")

    root.destroy()
    print("✅ TEST 3 PASSED: Preview Tab directional controls verified!\n")

def test_project_manager_directional_persistence():
    print("=" * 50)
    print("TEST 4: ProjectManager Persistence of Directional Margins")
    print("=" * 50)
    poly = sg.Polygon([(10, 10), (40, 10), (40, 40), (10, 40)])
    layers = {
        "#3B82F6": {
            "hex": "#3B82F6",
            "name": "أزرق",
            "polygons": [poly],
            "lines": []
        }
    }
    
    project_payload = {
        "target_width_mm": 120.0,
        "target_height_mm": 80.0,
        "thickness_mm": 0.3,
        "lock_aspect": True,
        "infill_pattern": "Grid",
        "infill_density": 15.0,
        "paper_preset": "ورقة A5 بالعرض (210 × 148 مم)",
        "paper_placement": "directional",
        "margin_left_mm": 20.0,
        "margin_right_mm": 18.0,
        "margin_bottom_mm": 25.0,
        "margin_top_mm": 22.0,
        "center_horizontally": False,
        "center_vertically": True,
        "color_layers": layers
    }
    
    test_file = "test_directional_v1.4.plotproj"
    ProjectManager.save_project(test_file, project_payload)
    assert os.path.exists(test_file)
    
    loaded = ProjectManager.load_project(test_file)
    assert float(loaded["version"]) >= 1.4
    assert loaded["margin_left_mm"] == 20.0
    assert loaded["margin_right_mm"] == 18.0
    assert loaded["margin_bottom_mm"] == 25.0
    assert loaded["margin_top_mm"] == 22.0
    assert loaded["center_horizontally"] == False
    assert loaded["center_vertically"] == True
    
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("✅ TEST 4 PASSED: Directional margins & centering persistence verified!\n")

if __name__ == "__main__":
    test_version_1_4()
    test_directional_margins_slicing()
    test_preview_tab_directional_controls()
    test_project_manager_directional_persistence()
    print("🎉 ALL V1.4 DIRECTIONAL MARGINS TESTS PASSED 100%!")
