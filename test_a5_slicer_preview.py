"""
Dedicated Verification Tests for A5 Slicer Preview and Toolpaths Simulation.
"""
import numpy as np
import cv2
from core.slicer_engine import SlicerEngine
from ui.app_window import AppWindow

def run_tests():
    print("==================================================")
    print("TEST 1: SlicerEngine with A5 Landscape (210x148 mm)")
    print("==================================================")
    # Create test circle mask (50x50 mm equivalent in pixels)
    mask = np.zeros((300, 300), dtype=np.uint8)
    cv2.circle(mask, (150, 150), 100, 255, -1)
    cv2.circle(mask, (150, 150), 35, 0, -1)  # Hole

    settings = {
        "line_width": 0.4,
        "wall_line_count": 2,
        "infill_density": 25.0,
        "infill_pattern": "Grid",
        "paper_type": "A5_landscape",
        "paper_width_mm": 210.0,
        "paper_height_mm": 148.0,
        "paper_placement": "center",
        "center_on_a5": True
    }

    res = SlicerEngine.slice_mask_to_gcode(
        mask=mask,
        target_w_mm=100.0,
        target_h_mm=100.0,
        settings=settings
    )

    assert "ordered_moves" in res
    assert "paths" in res
    assert len(res["paths"]["walls"]) > 0
    assert len(res["paths"]["infill"]) > 0
    assert len(res["paths"]["travels"]) > 0

    # Bounds check centering on A5 (210 x 148 mm)
    min_x, min_y, max_x, max_y = res["bounds"]
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    print(f"Model bounds on paper: X[{min_x:.1f} .. {max_x:.1f}], Y[{min_y:.1f} .. {max_y:.1f}]")
    print(f"Center calculated: ({center_x:.1f}, {center_y:.1f})")
    assert abs(center_x - 105.0) < 1.0, f"Expected center X ~ 105mm, got {center_x}"
    assert abs(center_y - 74.0) < 1.0, f"Expected center Y ~ 74mm, got {center_y}"
    print("✅ TEST 1 PASSED: Centering on A5 landscape (210x148 mm) verified!")

    print("\n==================================================")
    print("TEST 2: External G-Code Parser to Toolpaths")
    print("==================================================")
    sample_gcode = res["gcode"]
    parsed = SlicerEngine.parse_gcode_to_toolpaths(sample_gcode)
    assert len(parsed["ordered_moves"]) > 0
    assert parsed["lines_count"] == len(sample_gcode.splitlines())
    assert parsed["print_distance_mm"] > 0
    print(f"Parsed {len(parsed['ordered_moves'])} moves from {parsed['lines_count']} G-Code lines.")
    print("✅ TEST 2 PASSED: External G-Code parser verified!")

    print("\n==================================================")
    print("TEST 3: AppWindow SlicerPreviewTab Interactive Features")
    print("==================================================")
    app = AppWindow()
    app.update()

    # Load mask and slice
    app.binary_mask = mask
    app.slice_current_model(switch_to_preview=True)

    tab = app.slicer_preview_tab
    assert tab.slice_data is not None
    assert tab.paper_w_mm == 210.0
    assert tab.paper_h_mm == 148.0

    # Test toggles and redraw
    tab.var_show_physical_width.set(True)
    tab.var_show_walls.set(True)
    tab.var_show_infill.set(True)
    tab.var_show_travels.set(True)
    tab.redraw()

    # Test simulation stepping
    tab.start_simulation()
    assert tab.sim_running is True
    tab.pause_simulation()
    assert tab.sim_running is False
    tab.reset_simulation()
    assert tab.active_move_idx == 0
    tab.finish_simulation()
    assert tab.active_move_idx == tab.total_moves_count

    # Test fit to A5 paper callback
    initial_w = float(app.controls.width_var.get())
    tab.fit_model_to_paper_action()
    fitted_w = float(app.controls.width_var.get())
    print(f"Width before fit: {initial_w} mm | Width after fit: {fitted_w} mm")
    # Should fit comfortably within 210mm - 2*10mm = 190mm
    assert fitted_w <= 190.0

    app.destroy()
    print("✅ TEST 3 PASSED: SlicerPreviewTab interactive UI verified!")

    print("\n🎉 ALL A5 SLICER PREVIEW TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
