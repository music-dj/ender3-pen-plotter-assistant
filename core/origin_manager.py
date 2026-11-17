"""
Origin Manager for Pen Plotter & 3D Assistant.
Handles persistent saving, loading, and memory of the starting point (X, Y, Z origin).
"""
import os
import json
from typing import Dict, Any

class OriginManager:
    CONFIG_FILE = "saved_origins.json"

    @classmethod
    def get_config_path(cls) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, cls.CONFIG_FILE)

    @classmethod
    def load_origin(cls) -> Dict[str, float]:
        """Loads the saved origin coordinates. Returns default if not yet saved."""
        path = cls.get_config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        "x": float(data.get("x", 0.0)),
                        "y": float(data.get("y", 0.0)),
                        "z": float(data.get("z", 0.0)),
                        "name": str(data.get("name", "نقطة البداية المحفوظة"))
                    }
            except Exception:
                pass
        return {"x": 0.0, "y": 0.0, "z": 0.0, "name": "نقطة البداية الافتراضية (0, 0)"}

    @classmethod
    def save_origin(cls, x: float, y: float, z: float = 0.0, name: str = "نقطة البداية المحفوظة") -> Dict[str, Any]:
        """Persistently saves the origin coordinates to disk. Returns saved dict on success."""
        path = cls.get_config_path()
        payload = {
            "x": round(float(x), 2),
            "y": round(float(y), 2),
            "z": round(float(z), 2),
            "name": str(name)
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return payload
        except Exception as e:
            print(f"Error saving origin: {e}")
            return {}
