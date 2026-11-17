import unittest
import os
import json
import shapely.geometry as sg
from core.version import APP_VERSION
from core.origin_manager import OriginManager
from core.serial_printer import SerialPrinter
from core.slicer_engine import SlicerEngine
from core.project_manager import ProjectManager

class TestV15Features(unittest.TestCase):
    def test_01_app_version(self):
        """Verify version has been bumped to 1.5."""
        self.assertEqual(APP_VERSION, "1.5")

    def test_02_corner_registration_crosses_enabled(self):
        """Verify 4 corner registration crosses (+) are generated when enabled."""
        poly = sg.box(50, 40, 100, 80)
        color_layers = {
            "#000000": {
                "hex": "#000000",
                "name": "أسود",
                "polygons": [poly],
                "lines": []
            }
        }
        cfg = {
            "paper_width_mm": 210.0,
            "paper_height_mm": 148.0,
            "margin_left_mm": 15.0,
            "margin_right_mm": 15.0,
            "margin_bottom_mm": 15.0,
            "margin_top_mm": 15.0,
            "enable_corner_crosses": True,
            "corner_cross_size_mm": 6.0,
            "center_on_a5": True,
        }
        res = SlicerEngine.slice_color_layers(
            color_layers=color_layers,
            target_w_mm=60.0,
            target_h_mm=50.0,
            settings=cfg
        )
        gcode = res["gcode"]
        self.assertIn("CORNER REGISTRATION CROSSES (+)", gcode)
        self.assertIn("Bottom-Left", gcode)
        self.assertIn("Bottom-Right", gcode)
        self.assertIn("Top-Right", gcode)
        self.assertIn("Top-Left", gcode)
        
        # Verify crosses appear in ordered_moves
        cross_moves = [m for m in res["ordered_moves"] if m.get("kind") == "corner_cross"]
        self.assertGreaterEqual(len(cross_moves), 4)

    def test_03_corner_registration_crosses_disabled(self):
        """Verify crosses are excluded when disabled."""
        poly = sg.box(50, 40, 100, 80)
        color_layers = {
            "#000000": {
                "hex": "#000000",
                "name": "أسود",
                "polygons": [poly],
                "lines": []
            }
        }
        cfg = {
            "paper_width_mm": 210.0,
            "paper_height_mm": 148.0,
            "enable_corner_crosses": False,
        }
        res = SlicerEngine.slice_color_layers(
            color_layers=color_layers,
            target_w_mm=60.0,
            target_h_mm=50.0,
            settings=cfg
        )
        gcode = res["gcode"]
        self.assertNotIn("CORNER REGISTRATION CROSSES (+)", gcode)
        cross_moves = [m for m in res["ordered_moves"] if m.get("kind") == "corner_cross"]
        self.assertEqual(len(cross_moves), 0)

    def test_04_origin_manager_persistence(self):
        """Verify persistent saving and retrieval of printer head origin."""
        # Save custom origin
        saved = OriginManager.save_origin(x=55.5, y=77.2, z=0.3, name="A5 Paper Top-Left")
        self.assertEqual(saved["x"], 55.5)
        self.assertEqual(saved["y"], 77.2)
        self.assertEqual(saved["z"], 0.3)
        self.assertEqual(saved["name"], "A5 Paper Top-Left")

        # Load origin
        loaded = OriginManager.load_origin()
        self.assertAlmostEqual(loaded["x"], 55.5)
        self.assertAlmostEqual(loaded["y"], 77.2)
        self.assertAlmostEqual(loaded["z"], 0.3)
        self.assertEqual(loaded["name"], "A5 Paper Top-Left")

    def test_05_serial_printer_origin_recall(self):
        """Verify SerialPrinter origin recall commands and coordinate tracking."""
        printer = SerialPrinter()
        printer.current_x = 45.0
        printer.current_y = 65.0
        printer.current_z = 0.0

        # Save current position
        saved = printer.save_current_origin(name="Bed Clamp Marker")
        self.assertEqual(saved["x"], 45.0)
        self.assertEqual(saved["y"], 65.0)

        # Mock connected printer to test go_to_saved_origin
        printer.is_connected = True
        sent_commands = []
        printer.send_command = lambda cmd: sent_commands.append(cmd)

        success, msg = printer.go_to_saved_origin(set_zero=True)
        self.assertTrue(success)
        # Check safe Z-Hop + Rapid travel to origin + Lower Z + G92 X0 Y0
        self.assertTrue(any("G92 X0 Y0" in c for c in sent_commands))
        self.assertTrue(any("X45.000 Y65.000" in c for c in sent_commands))

    def test_06_project_manager_multicolor_persistence(self):
        """Verify ProjectManager saves and loads multiple color layers with full fidelity."""
        test_file = "test_multicolor_proj.plotproj"
        try:
            poly_red = sg.box(10, 10, 30, 30)
            poly_blue = sg.box(40, 40, 60, 60)
            payload = {
                "version": APP_VERSION,
                "project_name": "Test Multi-Color Art",
                "settings": {"paper_type": "A5_landscape", "enable_corner_crosses": True},
                "paper_config": {
                    "paper_preset": "ورقة A5 بالعرض (210 × 148 مم)",
                    "margin_left_mm": 18.0,
                    "margin_right_mm": 18.0,
                    "margin_bottom_mm": 18.0,
                    "margin_top_mm": 18.0,
                    "center_horizontally": True,
                    "center_vertically": True,
                    "enable_corner_crosses": True
                },
                "color_layers": {
                    "#EF4444": {
                        "hex": "#EF4444",
                        "name": "أحمر",
                        "polygons": [poly_red],
                        "lines": []
                    },
                    "#3B82F6": {
                        "hex": "#3B82F6",
                        "name": "أزرق",
                        "polygons": [poly_blue],
                        "lines": []
                    }
                }
            }
            ProjectManager.save_project(test_file, payload)
            self.assertTrue(os.path.exists(test_file))

            loaded = ProjectManager.load_project(test_file)
            self.assertIn("color_layers", loaded)
            layers = loaded["color_layers"]
            self.assertIn("#EF4444", layers)
            self.assertIn("#3B82F6", layers)
            self.assertEqual(len(layers["#EF4444"]["polygons"]), 1)
            self.assertEqual(len(layers["#3B82F6"]["polygons"]), 1)
            self.assertEqual(loaded["paper_config"]["enable_corner_crosses"], True)
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

if __name__ == "__main__":
    unittest.main()
