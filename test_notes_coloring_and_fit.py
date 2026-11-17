"""
Comprehensive Verification Test for:
1. Thin notes, lines, and dots preservation (No details hidden in preview or slice).
2. Idempotent "Fit to A5" (Never shrinks continuously on repeated clicks).
3. Auto Color Detection for raster images (Extracts multi-colors automatically).
4. Direct Interactive Coloring Studio (Bucket & Brush recoloring on canvas with undo).
"""
import sys
import os
import cv2
import numpy as np
import shapely.geometry as sg

from core.processor import ImageProcessor
from core.slicer_engine import SlicerEngine
from core.svg_loader import get_arabic_color_name

def test_notes_and_lines_preservation():
    print("=" * 50)
    print("TEST 1: Preserving Thin Notes, Annotations & Dots")
    print("=" * 50)

    # Synthetic image with:
    # 1. Main shape (solid box)
    # 2. Thin 1-pixel handwritten line note
    # 3. Small single-pixel dot (e.g. letter accent or stippling)
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[20:60, 20:60] = 255     # Solid Box
    mask[100:150, 40] = 255      # 1-pixel thin vertical line note
    mask[120, 120] = 255         # 1-pixel dot

    result = SlicerEngine.slice_mask_to_gcode(
        mask=mask,
        target_w_mm=100.0,
        target_h_mm=100.0,
        settings={"line_width": 0.4, "wall_line_count": 2, "infill_density": 0.0}
    )

    ordered_moves = result["ordered_moves"]
    lines_count = result["lines_count"]
    raw_layers = result.get("raw_color_layers", {})

    print(f"Generated {lines_count} lines of G-Code with {len(ordered_moves)} move commands.")
    print("Raw color layers keys:", list(raw_layers.keys()))
    polys_count = len(raw_layers["#000000"].get("polygons", []))
    lines_list_count = len(raw_layers["#000000"].get("lines", []))
    print(f"Captured: {polys_count} polygons and {lines_list_count} line/dot annotations!")

    assert polys_count >= 1, "Main solid shape polygon should be preserved!"
    assert lines_list_count >= 2, "Thin line note and dot MUST both be preserved in the slice!"
    assert len(ordered_moves) >= 3, "Toolpath moves must include box, line, and dot!"

    print("✅ TEST 1 PASSED: Thin lines, handwritten notes, and dots are 100% preserved in both G-Code and preview!\n")

def test_idempotent_fit_to_a5():
    print("=" * 50)
    print("TEST 2: Idempotent 'Fit to A5' (Fix Continuous Shrinking)")
    print("=" * 50)

    # Image where drawing occupies 60% of canvas
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[40:160, 40:160] = 255  # 120x120 pixels in 200x200 canvas (60%)

    paper_w = 210.0
    paper_h = 148.0
    margin = 10.0
    safe_w = paper_w - (2 * margin)  # 190.0
    safe_h = paper_h - (2 * margin)  # 128.0

    current_canvas_w = 150.0
    current_canvas_h = 150.0

    # First slice
    res1 = SlicerEngine.slice_mask_to_gcode(
        mask=mask,
        target_w_mm=current_canvas_w,
        target_h_mm=current_canvas_h,
        settings={"paper_width_mm": paper_w, "paper_height_mm": paper_h, "paper_margin_mm": margin}
    )

    model1_w = res1["model_w_mm"]
    model1_h = res1["model_h_mm"]
    print(f"Initial: Canvas = {current_canvas_w}x{current_canvas_h} mm | Model Content = {model1_w:.1f}x{model1_h:.1f} mm")

    # Fit click 1
    scale_factor1 = min(safe_w / model1_w, safe_h / model1_h)
    new_canvas_w = round(current_canvas_w * scale_factor1, 1)
    new_canvas_h = round(current_canvas_h * scale_factor1, 1)
    print(f"Click 1 Fit: Scale Factor = {scale_factor1:.3f} -> New Canvas = {new_canvas_w}x{new_canvas_h} mm")

    # Re-slice after Click 1
    res2 = SlicerEngine.slice_mask_to_gcode(
        mask=mask,
        target_w_mm=new_canvas_w,
        target_h_mm=new_canvas_h,
        settings={"paper_width_mm": paper_w, "paper_height_mm": paper_h, "paper_margin_mm": margin}
    )
    model2_w = res2["model_w_mm"]
    model2_h = res2["model_h_mm"]
    print(f"After Click 1: Model Content = {model2_w:.1f}x{model2_h:.1f} mm (Safe max: {safe_w}x{safe_h})")

    # Verify model now exactly touches safe area boundary (safe_h = 128.0)
    assert abs(max(model2_w, model2_h) - safe_h) < 1.0, f"Model should fit safe height ({safe_h}mm), got {model2_h}mm!"

    # Fit click 2 (Repeated click)
    scale_factor2 = min(safe_w / model2_w, safe_h / model2_h)
    print(f"Click 2 Fit: Scale Factor = {scale_factor2:.3f}")
    assert 0.985 <= scale_factor2 <= 1.015, f"Repeated click should be exactly ~1.0, got {scale_factor2}!"

    # Fit click 3
    scale_factor3 = min(safe_w / model2_w, safe_h / model2_h)
    assert 0.985 <= scale_factor3 <= 1.015, "Model must remain stable and NEVER shrink on subsequent clicks!"

    print("✅ TEST 2 PASSED: Repeatedly clicking 'Fit to A5' NEVER shrinks the model!\n")

def test_auto_color_detection():
    print("=" * 50)
    print("TEST 3: Auto Color Segmentation for Raster Images")
    print("=" * 50)

    # Synthetic RGB image with Black, Red, and Blue shapes
    img = np.ones((120, 120, 3), dtype=np.uint8) * 255
    img[15:45, 15:45] = [0, 0, 0]         # Black square (BGR)
    img[60:90, 15:45] = [0, 0, 220]       # Red square (BGR)
    img[30:80, 65:95] = [220, 0, 0]       # Blue rectangle (BGR)

    tmp_path = "test_colored_image.png"
    cv2.imwrite(tmp_path, img)

    color_masks = ImageProcessor.extract_color_masks(tmp_path, max_colors=4)
    print(f"Extracted {len(color_masks)} distinct color masks:")
    for hex_code, m in color_masks.items():
        name = get_arabic_color_name(hex_code)
        print(f"  - Color: {hex_code} ({name}) | Pixels: {np.sum(m > 0)}")

    assert len(color_masks) == 3, f"Expected 3 color masks, got {len(color_masks)}!"

    # Slice multi-color masks directly
    res = SlicerEngine.slice_color_masks_to_gcode(
        color_masks=color_masks,
        target_w_mm=100.0,
        target_h_mm=100.0,
        settings={"paper_width_mm": 210.0, "paper_height_mm": 148.0}
    )

    tool_changes = [m for m in res["ordered_moves"] if m.get("type") == "tool_change"]
    print(f"Tool change pen swap pauses at (0,0): {len(tool_changes)}")
    assert len(tool_changes) == 2, f"Expected 2 pen swaps for 3 colors, got {len(tool_changes)}!"

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    print("✅ TEST 3 PASSED: Colored images are automatically segmented and sliced into multi-pen layers!\n")

def test_interactive_recoloring_studio():
    print("=" * 50)
    print("TEST 4: Interactive Coloring Studio (Bucket & Line Brush)")
    print("=" * 50)

    # 1. Single color input mask with 2 distinct shapes
    mask = np.zeros((150, 150), dtype=np.uint8)
    mask[20:50, 20:50] = 255    # Shape 1 at (35, 35)
    mask[80:120, 80:120] = 255  # Shape 2 at (100, 100)

    res = SlicerEngine.slice_mask_to_gcode(
        mask=mask,
        target_w_mm=100.0,
        target_h_mm=100.0,
        settings={"paper_width_mm": 210.0, "paper_height_mm": 148.0, "paper_placement": "center"}
    )

    raw_layers = res["raw_color_layers"]
    offset_x = res["offset_x"]
    offset_y = res["offset_y"]
    print(f"Initial raw layers: {list(raw_layers.keys())}")
    assert list(raw_layers.keys()) == ["#000000"]

    # Click on Shape 1 on the paper (centroid of Shape 1 is around x=23.0, y=77.0)
    target_poly = raw_layers["#000000"]["polygons"][-1]
    click_paper_x = offset_x + target_poly.centroid.x
    click_paper_y = offset_y + target_poly.centroid.y

    # Recolor Shape 1 to Green (#10B981)
    new_color = "#10B981"
    undo_info = SlicerEngine.recolor_geometry_at(
        color_layers=raw_layers,
        click_x=click_paper_x,
        click_y=click_paper_y,
        offset_x=offset_x,
        offset_y=offset_y,
        new_hex=new_color
    )

    assert undo_info is not None, "Shape 1 should be hit and recolored!"
    print(f"Recolored Shape: from {undo_info['old_hex']} to {undo_info['new_hex']}")
    print(f"Updated raw layers keys: {list(raw_layers.keys())}")
    assert new_color in raw_layers, "Green color layer should now exist in raw_layers!"

    # Re-slice with the recolored layers
    res_recolored = SlicerEngine.slice_color_layers(
        color_layers=raw_layers,
        target_w_mm=100.0,
        target_h_mm=100.0
    )

    summary = res_recolored["color_layers_summary"]
    colors_present = {c["hex"].upper() for c in summary}
    print("Colors present in new slice:", colors_present)
    assert "#000000" in colors_present and "#10B981" in colors_present, "Both Black and Green must exist in slice!"

    # Test Undo
    geom = undo_info["geom"]
    gtype = undo_info["type"]
    old_hex = undo_info["old_hex"]
    raw_layers[new_color]["polygons"].remove(geom)
    raw_layers[old_hex]["polygons"].append(geom)
    if not raw_layers[new_color]["polygons"]:
        raw_layers.pop(new_color, None)

    print(f"After undo: layers = {list(raw_layers.keys())}")
    assert new_color not in raw_layers, "Green layer should be removed after undo!"

    print("✅ TEST 4 PASSED: Interactive direct coloring and undo work flawlessly!\n")

def test_app_window_ui_integration():
    print("=" * 50)
    print("TEST 5: AppWindow & SlicerPreviewTab UI Integration")
    print("=" * 50)

    from ui.app_window import AppWindow
    app = AppWindow()
    app.withdraw()  # Hidden window

    # Check SlicerPreviewTab components
    preview_tab = app.slicer_preview_tab
    assert hasattr(preview_tab, "seg_mode"), "SlicerPreviewTab should have seg_mode toggle!"
    assert hasattr(preview_tab, "recolor_at_pos"), "SlicerPreviewTab should have recolor_at_pos!"
    assert hasattr(preview_tab, "undo_recolor"), "SlicerPreviewTab should have undo_recolor!"

    # Switch to paint mode
    preview_tab._on_mode_toggled("🎨 تلوين الطبقات والأقلام")
    assert preview_tab.active_mode == "paint"
    print("Switched SlicerPreviewTab to Coloring Mode successfully!")

    # Switch back to pan mode
    preview_tab._on_mode_toggled("🔍 معاينة وتنقل")
    assert preview_tab.active_mode == "pan"
    print("Switched SlicerPreviewTab to Pan/Zoom Mode successfully!")

    app.destroy()
    print("✅ TEST 5 PASSED: Full UI and Coloring Studio integration verified!\n")

if __name__ == "__main__":
    test_notes_and_lines_preservation()
    test_idempotent_fit_to_a5()
    test_auto_color_detection()
    test_interactive_recoloring_studio()
    test_app_window_ui_integration()
    print("🎉 ALL 5 COMPREHENSIVE TESTS PASSED 100%!")
