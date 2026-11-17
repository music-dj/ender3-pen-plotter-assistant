"""
SVG Multi-Color Parser and Vectorizer.
Extracts vector paths, polygons, rects, circles from SVG files,
preserves and normalizes element colors (fill & stroke),
and groups shapes into distinct color layers for multi-pen plotting.
"""
import re
import math
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Any, Optional
import shapely.geometry as sg
import shapely.validation
import shapely.affinity
import numpy as np

# Standard color name to HEX mapping
COLOR_MAP = {
    "black": "#000000", "white": "#FFFFFF", "red": "#EF4444", "blue": "#3B82F6",
    "green": "#10B981", "yellow": "#FBBF24", "orange": "#F97316", "purple": "#A855F7",
    "pink": "#EC4899", "cyan": "#06B6D4", "teal": "#14B8A6", "brown": "#78350F",
    "gray": "#6B7280", "grey": "#6B7280", "navy": "#1E3A8A", "maroon": "#7F1D1D",
    "lime": "#84CC16", "gold": "#F59E0B", "silver": "#9CA3AF", "magenta": "#D946EF"
}

ARABIC_COLOR_NAMES = {
    "#000000": "أسود (Black)",
    "#FFFFFF": "أبيض (White)",
    "#EF4444": "أحمر (Red)",
    "#DC2626": "أحمر قاني",
    "#3B82F6": "أزرق (Blue)",
    "#1D4ED8": "أزرق ملكي",
    "#10B981": "أخضر (Green)",
    "#059669": "أخضر زمردي",
    "#FBBF24": "أصفر (Yellow)",
    "#F59E0B": "أصفر ذهبي",
    "#F97316": "برتقالي (Orange)",
    "#EA580C": "برتقالي داكن",
    "#A855F7": "بنفسجي (Purple)",
    "#7C3AED": "أرجواني",
    "#EC4899": "وردي (Pink)",
    "#06B6D4": "سماوي (Cyan)",
    "#78350F": "بني (Brown)",
    "#6B7280": "رمادي (Gray)"
}

def normalize_color(color_str: Optional[str], default_color: str = "#000000") -> Optional[str]:
    """Normalizes any CSS / SVG color string to a 6-digit uppercase hex '#RRGGBB'."""
    if not color_str or color_str.strip().lower() in ("none", "transparent", ""):
        return None

    c = color_str.strip().lower()

    # Check named colors
    if c in COLOR_MAP:
        return COLOR_MAP[c].upper()

    # Hex short: #rgb -> #rrggbb
    if c.startswith("#"):
        if len(c) == 4:
            c = "#" + "".join([ch * 2 for ch in c[1:]])
        if len(c) == 7:
            return c.upper()

    # rgb(r, g, b)
    rgb_match = re.match(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", c)
    if rgb_match:
        r, g, b = [int(v) for v in rgb_match.groups()]
        return f"#{r:02X}{g:02X}{b:02X}"

    return default_color.upper()

def get_arabic_color_name(hex_color: str) -> str:
    """Returns a friendly Arabic name for a given hex color."""
    hex_clean = hex_color.upper()
    if hex_clean in ARABIC_COLOR_NAMES:
        return ARABIC_COLOR_NAMES[hex_clean]

    # Find closest color in predefined list
    try:
        r1, g1, b1 = int(hex_clean[1:3], 16), int(hex_clean[3:5], 16), int(hex_clean[5:7], 16)
        closest_name = f"لون {hex_clean}"
        min_dist = float('inf')
        for k, name in ARABIC_COLOR_NAMES.items():
            r2, g2, b2 = int(k[1:3], 16), int(k[3:5], 16), int(k[5:7], 16)
            d = math.hypot(r1 - r2, g1 - g2, b1 - b2)
            if d < min_dist:
                min_dist = d
                closest_name = name
        if min_dist < 45:
            return closest_name
    except Exception:
        pass

    return f"لون {hex_clean}"


class SVGLoader:
    """Loads and converts multi-color SVGs into categorized polygons."""

    @classmethod
    def load_svg(
        cls,
        filepath: str,
        target_w_mm: float = 150.0,
        target_h_mm: float = 150.0,
        preserve_aspect: bool = True
    ) -> Dict[str, Any]:
        """
        Parses an SVG file, groups elements by color, and scales to physical mm.
        Returns:
            {
                "color_layers": {
                    "#FF0000": {
                        "name": "أحمر (Red)",
                        "polygons": [sg.Polygon, ...],
                        "paths": [ [(x,y), ...], ... ]
                    },
                    ...
                },
                "all_polygons": [sg.Polygon, ...],
                "bounds": (min_x, min_y, max_x, max_y),
                "width_mm": float,
                "height_mm": float,
                "svg_content": str
            }
        """
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

        try:
            tree = ET.fromstring(raw_content)
        except Exception as e:
            raise ValueError(f"Failed to parse SVG XML: {e}")

        # Clean namespaces from tags
        for elem in tree.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

        # Extract viewBox or dimensions
        view_box = tree.attrib.get("viewBox", "")
        vb_w = None
        vb_h = None
        if view_box:
            parts = [float(v) for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", view_box)]
            if len(parts) >= 4:
                vb_w = parts[2]
                vb_h = parts[3]

        if vb_w is None:
            # Fallback to width/height attributes
            w_str = tree.attrib.get("width", "100")
            h_str = tree.attrib.get("height", "100")
            vb_w = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+)", w_str)[0]) if re.findall(r"[-+]?(?:\d*\.\d+|\d+)", w_str) else 100.0
            vb_h = float(re.findall(r"[-+]?(?:\d*\.\d+|\d+)", h_str)[0]) if re.findall(r"[-+]?(?:\d*\.\d+|\d+)", h_str) else 100.0

        # Collect raw shapes grouped by color
        color_groups: Dict[str, List[List[Tuple[float, float]]]] = {}

        cls._parse_element(tree, inherited_fill="#000000", inherited_stroke=None, color_groups=color_groups)

        # If no shapes found, return empty
        if not color_groups:
            return {
                "color_layers": {},
                "all_polygons": [],
                "bounds": (0, 0, 0, 0),
                "width_mm": 0,
                "height_mm": 0,
                "svg_content": raw_content
            }

        # Calculate raw SVG bounds
        all_pts = []
        for col, path_list in color_groups.items():
            for p in path_list:
                all_pts.extend(p)

        if not all_pts:
            return {
                "color_layers": {},
                "all_polygons": [],
                "bounds": (0, 0, 0, 0),
                "width_mm": 0,
                "height_mm": 0,
                "svg_content": raw_content
            }

        xs = [pt[0] for pt in all_pts]
        ys = [pt[1] for pt in all_pts]
        raw_min_x, raw_max_x = min(xs), max(xs)
        raw_min_y, raw_max_y = min(ys), max(ys)
        raw_w = max(0.001, raw_max_x - raw_min_x)
        raw_h = max(0.001, raw_max_y - raw_min_y)

        # Scale factors to target physical mm
        if preserve_aspect:
            scale = min(target_w_mm / raw_w, target_h_mm / raw_h)
            scale_x = scale
            scale_y = scale
        else:
            scale_x = target_w_mm / raw_w
            scale_y = target_h_mm / raw_h

        # Convert to Shapely polygons per color layer
        # Flip Y so SVG top-left becomes plotter bottom-left front
        color_layers: Dict[str, Dict[str, Any]] = {}
        all_polygons: List[sg.Polygon] = []

        for color_hex, path_list in color_groups.items():
            layer_polys: List[sg.Polygon] = []
            layer_paths_mm: List[List[Tuple[float, float]]] = []

            for path_pts in path_list:
                if len(path_pts) < 3:
                    continue

                # Scale to physical mm and flip Y
                pts_mm = [
                    ((pt[0] - raw_min_x) * scale_x, (raw_max_y - pt[1]) * scale_y)
                    for pt in path_pts
                ]
                layer_paths_mm.append(pts_mm)

                try:
                    poly = sg.Polygon(pts_mm)
                    if not poly.is_valid:
                        poly = shapely.validation.make_valid(poly)

                    if poly.geom_type == 'Polygon' and not poly.is_empty and poly.area > 0.001:
                        layer_polys.append(poly)
                        all_polygons.append(poly)
                    elif poly.geom_type == 'MultiPolygon':
                        for sub_p in poly.geoms:
                            if not sub_p.is_empty and sub_p.area > 0.001:
                                layer_polys.append(sub_p)
                                all_polygons.append(sub_p)
                except Exception:
                    pass

            if layer_polys:
                color_layers[color_hex] = {
                    "hex": color_hex,
                    "name": get_arabic_color_name(color_hex),
                    "polygons": layer_polys,
                    "paths": layer_paths_mm
                }

        # Model bounding box in mm
        final_w = raw_w * scale_x
        final_h = raw_h * scale_y

        return {
            "color_layers": color_layers,
            "all_polygons": all_polygons,
            "bounds": (0, 0, final_w, final_h),
            "width_mm": final_w,
            "height_mm": final_h,
            "svg_content": raw_content
        }

    @classmethod
    def _parse_element(
        cls,
        elem: ET.Element,
        inherited_fill: Optional[str],
        inherited_stroke: Optional[str],
        color_groups: Dict[str, List[List[Tuple[float, float]]]]
    ):
        """Recursively traverses SVG elements, resolves CSS/XML colors, and converts shapes."""
        # Style attribute parsing: style="fill:#ff0000;stroke:#000"
        style_dict = {}
        if "style" in elem.attrib:
            for item in elem.attrib["style"].split(";"):
                if ":" in item:
                    k, v = item.split(":", 1)
                    style_dict[k.strip().lower()] = v.strip()

        elem_fill = style_dict.get("fill", elem.attrib.get("fill", inherited_fill))
        elem_stroke = style_dict.get("stroke", elem.attrib.get("stroke", inherited_stroke))

        # Determine effective color
        norm_fill = normalize_color(elem_fill)
        norm_stroke = normalize_color(elem_stroke)
        active_color = norm_fill if norm_fill else (norm_stroke if norm_stroke else "#000000")

        # Check element tag
        tag = elem.tag.lower()

        if tag == "path":
            d_str = elem.attrib.get("d", "")
            if d_str:
                subpaths = cls.parse_svg_path_d(d_str)
                if active_color not in color_groups:
                    color_groups[active_color] = []
                for sp in subpaths:
                    if len(sp) >= 3:
                        color_groups[active_color].append(sp)

        elif tag in ("polygon", "polyline"):
            pts_str = elem.attrib.get("points", "")
            if pts_str:
                pts = cls._parse_points_string(pts_str)
                if len(pts) >= 3:
                    if active_color not in color_groups:
                        color_groups[active_color] = []
                    color_groups[active_color].append(pts)

        elif tag == "rect":
            try:
                rx = float(elem.attrib.get("x", 0))
                ry = float(elem.attrib.get("y", 0))
                rw = float(elem.attrib.get("width", 0))
                rh = float(elem.attrib.get("height", 0))
                if rw > 0 and rh > 0:
                    pts = [(rx, ry), (rx + rw, ry), (rx + rw, ry + rh), (rx, ry + rh), (rx, ry)]
                    if active_color not in color_groups:
                        color_groups[active_color] = []
                    color_groups[active_color].append(pts)
            except Exception:
                pass

        elif tag == "circle":
            try:
                cx = float(elem.attrib.get("cx", 0))
                cy = float(elem.attrib.get("cy", 0))
                r = float(elem.attrib.get("r", 0))
                if r > 0:
                    pts = cls._make_circle_points(cx, cy, r)
                    if active_color not in color_groups:
                        color_groups[active_color] = []
                    color_groups[active_color].append(pts)
            except Exception:
                pass

        elif tag == "ellipse":
            try:
                cx = float(elem.attrib.get("cx", 0))
                cy = float(elem.attrib.get("cy", 0))
                rx = float(elem.attrib.get("rx", 0))
                ry = float(elem.attrib.get("ry", 0))
                if rx > 0 and ry > 0:
                    pts = cls._make_ellipse_points(cx, cy, rx, ry)
                    if active_color not in color_groups:
                        color_groups[active_color] = []
                    color_groups[active_color].append(pts)
            except Exception:
                pass

        # Recurse children (<g>, etc.)
        for child in elem:
            cls._parse_element(child, inherited_fill=elem_fill, inherited_stroke=elem_stroke, color_groups=color_groups)

    @classmethod
    def _parse_points_string(cls, pts_str: str) -> List[Tuple[float, float]]:
        vals = [float(v) for v in re.findall(r"[-+]?(?:\d*\.\d+|\d+)", pts_str)]
        pts = []
        for i in range(0, len(vals) - 1, 2):
            pts.append((vals[i], vals[i + 1]))
        if pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        return pts

    @classmethod
    def _make_circle_points(cls, cx: float, cy: float, r: float, steps: int = 36) -> List[Tuple[float, float]]:
        pts = []
        for i in range(steps + 1):
            theta = 2.0 * math.pi * (i / steps)
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
        return pts

    @classmethod
    def _make_ellipse_points(cls, cx: float, cy: float, rx: float, ry: float, steps: int = 36) -> List[Tuple[float, float]]:
        pts = []
        for i in range(steps + 1):
            theta = 2.0 * math.pi * (i / steps)
            pts.append((cx + rx * math.cos(theta), cy + ry * math.sin(theta)))
        return pts

    @classmethod
    def parse_svg_path_d(cls, d_str: str, num_bezier_subdivisions: int = 8) -> List[List[Tuple[float, float]]]:
        """Robust SVG path 'd' command tokenizer and linearizer."""
        tokens = re.findall(r'([A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)', d_str)

        paths: List[List[Tuple[float, float]]] = []
        current_path: List[Tuple[float, float]] = []

        cur_x, cur_y = 0.0, 0.0
        start_x, start_y = 0.0, 0.0
        i = 0
        cmd = ''

        while i < len(tokens):
            t = tokens[i]
            if t.isalpha():
                cmd = t
                i += 1
            else:
                if cmd in ('M', 'm'):
                    cmd = 'L' if cmd == 'M' else 'l'

            if cmd in ('M', 'm'):
                is_rel = (cmd == 'm')
                x = (cur_x if is_rel else 0.0) + float(tokens[i])
                y = (cur_y if is_rel else 0.0) + float(tokens[i + 1])
                i += 2
                cur_x, cur_y = x, y
                start_x, start_y = x, y
                if current_path:
                    paths.append(current_path)
                current_path = [(cur_x, cur_y)]

            elif cmd in ('L', 'l'):
                is_rel = (cmd == 'l')
                x = (cur_x if is_rel else 0.0) + float(tokens[i])
                y = (cur_y if is_rel else 0.0) + float(tokens[i + 1])
                i += 2
                cur_x, cur_y = x, y
                current_path.append((cur_x, cur_y))

            elif cmd in ('H', 'h'):
                is_rel = (cmd == 'h')
                cur_x = (cur_x if is_rel else 0.0) + float(tokens[i])
                i += 1
                current_path.append((cur_x, cur_y))

            elif cmd in ('V', 'v'):
                is_rel = (cmd == 'v')
                cur_y = (cur_y if is_rel else 0.0) + float(tokens[i])
                i += 1
                current_path.append((cur_x, cur_y))

            elif cmd in ('C', 'c'):
                is_rel = (cmd == 'c')
                ox = cur_x if is_rel else 0.0
                oy = cur_y if is_rel else 0.0
                x1 = ox + float(tokens[i])
                y1 = oy + float(tokens[i + 1])
                x2 = ox + float(tokens[i + 2])
                y2 = oy + float(tokens[i + 3])
                x = ox + float(tokens[i + 4])
                y = oy + float(tokens[i + 5])
                i += 6

                p0 = (cur_x, cur_y)
                p1 = (x1, y1)
                p2 = (x2, y2)
                p3 = (x, y)
                for step in range(1, num_bezier_subdivisions + 1):
                    u = step / num_bezier_subdivisions
                    bx = ((1 - u) ** 3) * p0[0] + 3 * ((1 - u) ** 2) * u * p1[0] + 3 * (1 - u) * (u ** 2) * p2[0] + (u ** 3) * p3[0]
                    by = ((1 - u) ** 3) * p0[1] + 3 * ((1 - u) ** 2) * u * p1[1] + 3 * (1 - u) * (u ** 2) * p2[1] + (u ** 3) * p3[1]
                    current_path.append((bx, by))
                cur_x, cur_y = x, y

            elif cmd in ('S', 's', 'Q', 'q'):
                is_rel = (cmd in ('s', 'q'))
                ox = cur_x if is_rel else 0.0
                oy = cur_y if is_rel else 0.0
                # Approximate quadratic curve as straight or simple step
                x = ox + float(tokens[i])
                y = oy + float(tokens[i + 1])
                i += 2
                cur_x, cur_y = x, y
                current_path.append((cur_x, cur_y))

            elif cmd in ('A', 'a'):
                # Arc: rx ry rot large_arc sweep x y (7 parameters)
                is_rel = (cmd == 'a')
                ox = cur_x if is_rel else 0.0
                oy = cur_y if is_rel else 0.0
                if i + 6 < len(tokens):
                    x = ox + float(tokens[i + 5])
                    y = oy + float(tokens[i + 6])
                    i += 7
                    cur_x, cur_y = x, y
                    current_path.append((cur_x, cur_y))
                else:
                    i += 1

            elif cmd in ('Z', 'z'):
                if current_path and (cur_x != start_x or cur_y != start_y):
                    current_path.append((start_x, start_y))
                cur_x, cur_y = start_x, start_y
                paths.append(current_path)
                current_path = []

            else:
                i += 1

        if current_path:
            paths.append(current_path)

        return paths
