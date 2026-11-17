"""
Project Manager for Pen Plotter & 3D Assistant.
Handles saving and loading full drawing projects (.plotproj / JSON)
preserving multi-color vector layers, dimensions, and slicing configuration.
"""
import json
import os
import time
from typing import Dict, Any, Optional
import shapely
import shapely.geometry as sg
from core.version import APP_VERSION
from core.svg_loader import get_arabic_color_name

class ProjectManager:
    @staticmethod
    def serialize_color_layers(color_layers: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Converts Shapely polygons, lines, and points to standard WKT strings for JSON storage."""
        serialized = {}
        for col_hex, layer_info in color_layers.items():
            polys_wkt = []
            for p in layer_info.get("polygons", []):
                try:
                    polys_wkt.append(shapely.to_wkt(p))
                except Exception:
                    pass

            lines_wkt = []
            for l in layer_info.get("lines", []):
                try:
                    lines_wkt.append(shapely.to_wkt(l))
                except Exception:
                    pass

            serialized[col_hex] = {
                "hex": col_hex,
                "name": layer_info.get("name", get_arabic_color_name(col_hex)),
                "polygons": polys_wkt,
                "lines": lines_wkt
            }
        return serialized

    @staticmethod
    def deserialize_color_layers(serialized: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Restores Shapely geometries from stored WKT strings."""
        deserialized = {}
        for col_hex, layer_info in serialized.items():
            polys = []
            for wkt_str in layer_info.get("polygons", []):
                try:
                    geom = shapely.from_wkt(wkt_str)
                    if geom.geom_type in ('Polygon', 'MultiPolygon'):
                        polys.append(geom)
                except Exception:
                    pass

            lines = []
            for wkt_str in layer_info.get("lines", []):
                try:
                    geom = shapely.from_wkt(wkt_str)
                    if geom.geom_type in ('LineString', 'MultiLineString', 'Point'):
                        lines.append(geom)
                except Exception:
                    pass

            deserialized[col_hex] = {
                "hex": col_hex,
                "name": layer_info.get("name", get_arabic_color_name(col_hex)),
                "polygons": polys,
                "lines": lines
            }
        return deserialized

    @classmethod
    def save_project(cls, filepath: str, project_data: Dict[str, Any]) -> bool:
        """Saves full project state to a .plotproj file."""
        try:
            color_layers = project_data.get("color_layers", {})
            serialized_layers = cls.serialize_color_layers(color_layers)

            paper_cfg = project_data.get("paper_config", {})
            enable_crosses = project_data.get(
                "enable_corner_crosses",
                paper_cfg.get("enable_corner_crosses", project_data.get("settings", {}).get("enable_corner_crosses", True))
            )

            payload = {
                "app": "Ender 3 Pro Pen Plotter & 3D Assistant",
                "version": APP_VERSION,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model_width_mm": float(project_data.get("target_width_mm", paper_cfg.get("model_width_mm", 150.0))),
                "model_height_mm": float(project_data.get("target_height_mm", paper_cfg.get("model_height_mm", 150.0))),
                "thickness_mm": float(project_data.get("thickness_mm", 0.2)),
                "lock_aspect": bool(project_data.get("lock_aspect", True)),
                "infill_pattern": str(project_data.get("infill_pattern", paper_cfg.get("infill_pattern", "Cubic"))),
                "infill_density": float(project_data.get("infill_density", 20.0)),
                "paper_preset": str(project_data.get("paper_preset", paper_cfg.get("paper_preset", "ورقة A5 بالعرض (210 × 148 مم)"))),
                "paper_placement": str(project_data.get("paper_placement", paper_cfg.get("paper_placement", "توسيط داخل الورقة (Center)"))),
                "paper_margin_mm": float(project_data.get("paper_margin_mm", paper_cfg.get("paper_margin_mm", 15.0))),
                "margin_left_mm": float(project_data.get("margin_left_mm", paper_cfg.get("margin_left_mm", 15.0))),
                "margin_right_mm": float(project_data.get("margin_right_mm", paper_cfg.get("margin_right_mm", 15.0))),
                "margin_bottom_mm": float(project_data.get("margin_bottom_mm", paper_cfg.get("margin_bottom_mm", 15.0))),
                "margin_top_mm": float(project_data.get("margin_top_mm", paper_cfg.get("margin_top_mm", 15.0))),
                "center_horizontally": bool(project_data.get("center_horizontally", paper_cfg.get("center_horizontally", True))),
                "center_vertically": bool(project_data.get("center_vertically", paper_cfg.get("center_vertically", True))),
                "enable_corner_crosses": bool(enable_crosses),
                "original_image_path": str(project_data.get("original_image_path", "")),
                "color_layers": serialized_layers
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"Error saving project to {filepath}: {e}")
            raise e

    @classmethod
    def load_project(cls, filepath: str) -> Dict[str, Any]:
        """Loads and deserializes a .plotproj project file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        serialized_layers = data.get("color_layers", {})
        restored_layers = cls.deserialize_color_layers(serialized_layers)
        data["color_layers"] = restored_layers

        # Construct paper_config sub-dict for convenience
        data["paper_config"] = {
            "paper_preset": data.get("paper_preset", "ورقة A5 بالعرض (210 × 148 مم)"),
            "paper_placement": data.get("paper_placement", "توسيط داخل الورقة (Center)"),
            "paper_margin_mm": data.get("paper_margin_mm", 15.0),
            "margin_left_mm": data.get("margin_left_mm", 15.0),
            "margin_right_mm": data.get("margin_right_mm", 15.0),
            "margin_bottom_mm": data.get("margin_bottom_mm", 15.0),
            "margin_top_mm": data.get("margin_top_mm", 15.0),
            "center_horizontally": data.get("center_horizontally", True),
            "center_vertically": data.get("center_vertically", True),
            "enable_corner_crosses": data.get("enable_corner_crosses", True),
            "infill_pattern": data.get("infill_pattern", "Cubic")
        }
        return data
