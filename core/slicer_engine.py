"""
G-Code Slicing and Toolpath Engine for Ender 3 Pro & Marlin.
Slices 2D/3D shapes into precise Marlin G-Code following user Cura profile settings:
Supports:
- Multi-color SVG & pen swapping (Tool Change with zero calibration at 0,0 & Z-Hop safety)
- 10 Infill patterns (Cubic, Grid, Lines, Concentric, Crosshatch, Zigzag, Honeycomb, Spiral, Waves, Dots)
- Downscaling detail preservation (never drops thin lines or small features when scaling down)
- Physical line width visualization and custom paper placement (A5 Landscape, etc.)
"""
import math
import numpy as np
import cv2
import shapely.geometry as sg
import shapely.affinity
import shapely.validation
from typing import Dict, Any, List, Tuple, Optional
from core.svg_loader import get_arabic_color_name

class SlicerEngine:
    DEFAULT_SETTINGS = {
        # Quality
        "layer_height": 0.3,
        "initial_layer_height": 0.3,
        "line_width": 0.4,
        # Walls
        "wall_thickness": 0.6,
        "wall_line_count": 2,
        "horizontal_expansion": 0.0,
        # Top/Bottom & Infill
        "infill_density": 20.0,
        "infill_pattern": "Cubic",  # Cubic, Grid, Lines, Concentric, Crosshatch, Zigzag, Honeycomb, Spiral, Waves, Dots
        "top_bottom_thickness": 2.1,
        "top_layers": 7,
        "bottom_layers": 7,
        # Material
        "print_temp": 0.0,       # 0.0 for pen plotting / drawing
        "bed_temp": 0.0,
        "flow": 100.0,
        # Speed (mm/s)
        "print_speed": 50.0,
        "wall_speed": 25.0,
        "infill_speed": 50.0,
        "travel_speed": 150.0,
        "initial_layer_speed": 20.0,
        "z_hop_speed": 5.0,
        # Travel & Retraction
        "enable_retraction": True,
        "retraction_distance": 6.5,
        "retraction_speed": 25.0,
        "enable_z_hop": True,
        "z_hop_height": 1.5,     # Lift pen 1.5mm while traveling
        # Multi-Pen / Color Change
        "enable_pen_swap": True,
        "pen_swap_at_origin": True,
        # Fan & Cooling
        "enable_fan": False,
        "fan_speed": 0,
        # Paper & Bed (Default A5 Landscape 210 x 148 mm)
        "paper_type": "A5_landscape",
        "paper_width_mm": 210.0,
        "paper_height_mm": 148.0,
        "paper_placement": "center",     # "center", "directional", "custom_zero", "center_bed"
        "paper_margin_mm": 15.0,
        "margin_left_mm": 15.0,
        "margin_right_mm": 15.0,
        "margin_bottom_mm": 15.0,
        "margin_top_mm": 15.0,
        "center_horizontally": True,
        "center_vertically": True,
        "center_on_a5": True,
        "start_at_custom_origin": False,
        "bed_size_x": 220.0,
        "bed_size_y": 220.0,
        "center_on_bed": False,
        "enable_corner_crosses": True,   # Draw alignment + crosses in corners before drawing
        "corner_cross_size_mm": 6.0,     # Size of each corner cross in mm
        "extrusion_mode": False          # False = Pen Plotter (No E), True = Extrude Plastic
    }

    @classmethod
    def generate_infill(
        cls,
        interior: sg.Polygon,
        pattern: str,
        spacing: float,
        line_w: float = 0.4
    ) -> List[List[Tuple[float, float]]]:
        """
        Generates infill path segments inside an interior polygon.
        Supports 10 rich patterns for artistic and structural pen plotting.
        """
        if interior.is_empty or interior.area < 0.05 or spacing <= 0.01:
            return []

        lines: List[List[Tuple[float, float]]] = []
        minx, miny, maxx, maxy = interior.bounds
        diag = math.hypot(maxx - minx, maxy - miny)
        cx = (minx + maxx) / 2.0
        cy = (miny + maxy) / 2.0

        if pattern == "Concentric":
            curr = interior
            while not curr.is_empty and curr.area > 0.05:
                geoms = [curr] if curr.geom_type == 'Polygon' else curr.geoms
                for g in geoms:
                    lines.append(list(g.exterior.coords))
                    for hole in g.interiors:
                        lines.append(list(hole.coords))
                try:
                    curr = curr.buffer(-spacing)
                except Exception:
                    break

        elif pattern in ("Lines", "Grid", "Cubic", "Crosshatch"):
            if pattern == "Lines":
                angles = [45.0]
            elif pattern in ("Grid", "Cubic"):
                angles = [45.0, 135.0]
            else:  # Crosshatch (3-way artistic hatching 0°, 60°, 120°)
                angles = [0.0, 60.0, 120.0]

            for angle_deg in angles:
                rad = math.radians(angle_deg)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)
                steps = int(diag / spacing) + 4
                raw_lines = []
                for s in range(-steps, steps + 1):
                    offset = s * spacing
                    px = cx + offset * (-sin_a)
                    py = cy + offset * cos_a
                    p1 = (px - diag * cos_a, py - diag * sin_a)
                    p2 = (px + diag * cos_a, py + diag * sin_a)
                    raw_lines.append(sg.LineString([p1, p2]))

                multi = sg.MultiLineString(raw_lines)
                try:
                    clipped = multi.intersection(interior)
                    if not clipped.is_empty:
                        c_geoms = [clipped] if clipped.geom_type == 'LineString' else (
                            clipped.geoms if hasattr(clipped, 'geoms') else []
                        )
                        for seg in c_geoms:
                            if seg.geom_type == 'LineString' and len(seg.coords) >= 2:
                                lines.append(list(seg.coords))
                except Exception:
                    pass

        elif pattern == "Zigzag":
            # Alternating connected parallel lines (minimizes pen lifts)
            rad = math.radians(45.0)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            steps = int(diag / spacing) + 2
            for idx, s in enumerate(range(-steps, steps + 1)):
                offset = s * spacing
                px = cx + offset * (-sin_a)
                py = cy + offset * cos_a
                p1 = (px - diag * cos_a, py - diag * sin_a)
                p2 = (px + diag * cos_a, py + diag * sin_a)
                line_seg = sg.LineString([p1, p2] if idx % 2 == 0 else [p2, p1])
                try:
                    clipped = line_seg.intersection(interior)
                    if not clipped.is_empty:
                        c_geoms = [clipped] if clipped.geom_type == 'LineString' else (
                            clipped.geoms if hasattr(clipped, 'geoms') else []
                        )
                        for seg in c_geoms:
                            if seg.geom_type == 'LineString' and len(seg.coords) >= 2:
                                lines.append(list(seg.coords))
                except Exception:
                    pass

        elif pattern == "Honeycomb":
            # Hexagonal honeycomb grid
            h_spacing = spacing * 1.5
            v_spacing = spacing * math.sqrt(3)
            hex_lines = []
            x_steps = int((maxx - minx) / h_spacing) + 4
            y_steps = int((maxy - miny) / v_spacing) + 4
            r = spacing * 0.7
            for xi in range(-2, x_steps + 2):
                hx = minx + xi * h_spacing
                for yi in range(-2, y_steps + 2):
                    hy = miny + yi * v_spacing + ((xi % 2) * (v_spacing / 2.0))
                    h_pts = []
                    for k in range(7):
                        ang = math.radians(60 * k)
                        h_pts.append((hx + r * math.cos(ang), hy + r * math.sin(ang)))
                    hex_lines.append(sg.LineString(h_pts))
            multi = sg.MultiLineString(hex_lines)
            try:
                clipped = multi.intersection(interior)
                if not clipped.is_empty:
                    c_geoms = [clipped] if clipped.geom_type == 'LineString' else (
                        clipped.geoms if hasattr(clipped, 'geoms') else []
                    )
                    for seg in c_geoms:
                        if seg.geom_type == 'LineString' and len(seg.coords) >= 2:
                            lines.append(list(seg.coords))
            except Exception:
                pass

        elif pattern == "Spiral":
            # Archimedean spiral from center outwards
            spiral_pts = []
            max_r = diag / 2.0
            b = spacing / (2.0 * math.pi)
            theta_max = max_r / b if b > 0 else 10.0
            step_theta = 0.12
            theta = 0.0
            while theta <= theta_max:
                r_cur = b * theta
                sx = cx + r_cur * math.cos(theta)
                sy = cy + r_cur * math.sin(theta)
                spiral_pts.append((sx, sy))
                theta += step_theta
            if len(spiral_pts) >= 2:
                try:
                    sp_line = sg.LineString(spiral_pts)
                    clipped = sp_line.intersection(interior)
                    if not clipped.is_empty:
                        c_geoms = [clipped] if clipped.geom_type == 'LineString' else (
                            clipped.geoms if hasattr(clipped, 'geoms') else []
                        )
                        for seg in c_geoms:
                            if seg.geom_type == 'LineString' and len(seg.coords) >= 2:
                                lines.append(list(seg.coords))
                except Exception:
                    pass

        elif pattern == "Waves":
            # Smooth sinusoidal wave lines
            steps_y = int((maxy - miny) / spacing) + 4
            wave_lines = []
            amplitude = spacing * 0.35
            freq = (2.0 * math.pi) / (spacing * 3.5)
            for sy in range(-2, steps_y + 2):
                base_y = miny + sy * spacing
                w_pts = []
                x_cur = minx - 5.0
                while x_cur <= maxx + 5.0:
                    y_cur = base_y + amplitude * math.sin(freq * x_cur)
                    w_pts.append((x_cur, y_cur))
                    x_cur += 1.2
                if len(w_pts) >= 2:
                    wave_lines.append(sg.LineString(w_pts))
            multi = sg.MultiLineString(wave_lines)
            try:
                clipped = multi.intersection(interior)
                if not clipped.is_empty:
                    c_geoms = [clipped] if clipped.geom_type == 'LineString' else (
                        clipped.geoms if hasattr(clipped, 'geoms') else []
                    )
                    for seg in c_geoms:
                        if seg.geom_type == 'LineString' and len(seg.coords) >= 2:
                            lines.append(list(seg.coords))
            except Exception:
                pass

        elif pattern == "Dots":
            # Stippling / dot matrix
            steps_x = int((maxx - minx) / spacing) + 2
            steps_y = int((maxy - miny) / spacing) + 2
            dot_size = max(0.15, line_w * 0.4)
            for sx in range(steps_x):
                dx = minx + sx * spacing
                for sy in range(steps_y):
                    dy = miny + sy * spacing
                    pt = sg.Point(dx, dy)
                    if interior.contains(pt):
                        lines.append([(dx, dy), (dx + dot_size, dy)])

        return lines

    @classmethod
    def slice_mask_to_gcode(
        cls,
        mask: np.ndarray,
        target_w_mm: float,
        target_h_mm: float,
        settings: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Slices a binary mask into G-Code with complete detail preservation.
        (Fixes the downscaling bug: small details & thin lines are NEVER deleted).
        """
        cfg = cls.DEFAULT_SETTINGS.copy()
        if settings:
            cfg.update(settings)

        h, w = mask.shape
        if h == 0 or w == 0:
            return {"gcode": "", "lines_count": 0, "estimated_time_s": 0}

        scale_x = target_w_mm / w
        scale_y = target_h_mm / h

        # Find contours with 2-level hierarchy without aggressive erosion
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
        if not contours or hierarchy is None:
            return {"gcode": "", "lines_count": 0, "estimated_time_s": 0}

        # Physical epsilon in mm (fixed physical tolerance, never blows up when downscaling!)
        user_eps = float(cfg.get("epsilon_mm", 0.05))
        epsilon_mm = max(0.02, min(0.15, user_eps))

        h_data = hierarchy[0]
        polygons: List[sg.Polygon] = []
        lines: List[Any] = []

        for idx, cnt in enumerate(contours):
            if h_data[idx][3] != -1:
                continue

            # Convert to physical mm FIRST before approximation
            pts = cnt.reshape(-1, 2).astype(np.float32)
            pts_mm = np.column_stack([pts[:, 0] * scale_x, (h - pts[:, 1]) * scale_y])

            # Single-pixel dot (e.g. dot on Arabic letters, punctuation)
            if len(pts_mm) == 1:
                lines.append(sg.Point(pts_mm[0][0], pts_mm[0][1]))
                continue
            elif len(pts_mm) == 2:
                lines.append(sg.LineString(pts_mm))
                continue

            approx_mm = cv2.approxPolyDP(pts_mm, epsilon_mm, closed=True)
            if len(approx_mm) < 3:
                # Open line, thin stroke, or annotation note: NEVER DROP!
                if len(pts_mm) >= 2:
                    lines.append(sg.LineString(pts_mm))
                continue

            ext_mm = approx_mm.reshape(-1, 2).astype(np.float64)

            holes_mm = []
            child_idx = h_data[idx][2]
            while child_idx != -1:
                h_cnt = contours[child_idx]
                h_pts = h_cnt.reshape(-1, 2).astype(np.float32)
                h_pts_mm = np.column_stack([h_pts[:, 0] * scale_x, (h - h_pts[:, 1]) * scale_y])
                approx_h = cv2.approxPolyDP(h_pts_mm, epsilon_mm, closed=True)
                if len(approx_h) >= 3:
                    holes_mm.append(approx_h.reshape(-1, 2).astype(np.float64))
                elif len(h_pts_mm) >= 2:
                    lines.append(sg.LineString(h_pts_mm))
                child_idx = h_data[child_idx][0]

            poly = sg.Polygon(shell=ext_mm, holes=holes_mm)
            if not poly.is_valid:
                poly = shapely.validation.make_valid(poly)

            # Preserve all valid geometries: polygons, lines, multi-lines
            if poly.geom_type == 'Polygon' and not poly.is_empty and poly.area > 0.0001:
                polygons.append(poly)
            elif poly.geom_type == 'MultiPolygon':
                for p in poly.geoms:
                    if not p.is_empty and p.area > 0.0001:
                        polygons.append(p)
            elif poly.geom_type in ('LineString', 'MultiLineString'):
                lines.append(poly)
            elif poly.geom_type == 'GeometryCollection':
                for g in poly.geoms:
                    if g.geom_type in ('Polygon', 'MultiPolygon') and g.area > 0.0001:
                        polygons.append(g)
                    elif g.geom_type in ('LineString', 'MultiLineString', 'Point'):
                        lines.append(g)
            else:
                # Fallback to direct LineString to guarantee no stroke is ever lost
                if len(pts_mm) >= 2:
                    lines.append(sg.LineString(pts_mm))

        color_layers = {
            "#000000": {
                "hex": "#000000",
                "name": "قلم أساسي (Black)",
                "polygons": polygons,
                "lines": lines
            }
        }

        return cls.slice_color_layers(
            color_layers=color_layers,
            target_w_mm=target_w_mm,
            target_h_mm=target_h_mm,
            settings=cfg
        )

    @classmethod
    def slice_color_masks_to_gcode(
        cls,
        color_masks: Dict[str, np.ndarray],
        target_w_mm: float,
        target_h_mm: float,
        settings: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Extracts polygons and lines from multiple color masks (e.g. from Auto Color Detection
        or interactive coloring studio) and slices each color with pen swap at (0,0).
        """
        cfg = cls.DEFAULT_SETTINGS.copy()
        if settings:
            cfg.update(settings)

        user_eps = float(cfg.get("epsilon_mm", 0.05))
        epsilon_mm = max(0.02, min(0.15, user_eps))

        color_layers: Dict[str, Dict[str, Any]] = {}

        for col_hex, mask in color_masks.items():
            h, w = mask.shape
            if h == 0 or w == 0:
                continue

            scale_x = target_w_mm / w
            scale_y = target_h_mm / h

            contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
            if not contours or hierarchy is None:
                continue

            h_data = hierarchy[0]
            polygons: List[sg.Polygon] = []
            lines: List[Any] = []

            for idx, cnt in enumerate(contours):
                if h_data[idx][3] != -1:
                    continue

                pts = cnt.reshape(-1, 2).astype(np.float32)
                pts_mm = np.column_stack([pts[:, 0] * scale_x, (h - pts[:, 1]) * scale_y])

                if len(pts_mm) == 1:
                    lines.append(sg.Point(pts_mm[0][0], pts_mm[0][1]))
                    continue
                elif len(pts_mm) == 2:
                    lines.append(sg.LineString(pts_mm))
                    continue

                approx_mm = cv2.approxPolyDP(pts_mm, epsilon_mm, closed=True)
                if len(approx_mm) < 3:
                    if len(pts_mm) >= 2:
                        lines.append(sg.LineString(pts_mm))
                    continue

                ext_mm = approx_mm.reshape(-1, 2).astype(np.float64)

                holes_mm = []
                child_idx = h_data[idx][2]
                while child_idx != -1:
                    h_cnt = contours[child_idx]
                    h_pts = h_cnt.reshape(-1, 2).astype(np.float32)
                    h_pts_mm = np.column_stack([h_pts[:, 0] * scale_x, (h - h_pts[:, 1]) * scale_y])
                    approx_h = cv2.approxPolyDP(h_pts_mm, epsilon_mm, closed=True)
                    if len(approx_h) >= 3:
                        holes_mm.append(approx_h.reshape(-1, 2).astype(np.float64))
                    elif len(h_pts_mm) >= 2:
                        lines.append(sg.LineString(h_pts_mm))
                    child_idx = h_data[child_idx][0]

                poly = sg.Polygon(shell=ext_mm, holes=holes_mm)
                if not poly.is_valid:
                    poly = shapely.validation.make_valid(poly)

                if poly.geom_type == 'Polygon' and not poly.is_empty and poly.area > 0.0001:
                    polygons.append(poly)
                elif poly.geom_type == 'MultiPolygon':
                    for p in poly.geoms:
                        if not p.is_empty and p.area > 0.0001:
                            polygons.append(p)
                elif poly.geom_type in ('LineString', 'MultiLineString'):
                    lines.append(poly)
                elif poly.geom_type == 'GeometryCollection':
                    for g in poly.geoms:
                        if g.geom_type in ('Polygon', 'MultiPolygon') and g.area > 0.0001:
                            polygons.append(g)
                        elif g.geom_type in ('LineString', 'MultiLineString', 'Point'):
                            lines.append(g)
                else:
                    if len(pts_mm) >= 2:
                        lines.append(sg.LineString(pts_mm))

            if polygons or lines:
                color_layers[col_hex] = {
                    "hex": col_hex,
                    "name": get_arabic_color_name(col_hex),
                    "polygons": polygons,
                    "lines": lines
                }

        return cls.slice_color_layers(
            color_layers=color_layers,
            target_w_mm=target_w_mm,
            target_h_mm=target_h_mm,
            settings=cfg
        )

    @classmethod
    def slice_color_layers(
        cls,
        color_layers: Dict[str, Dict[str, Any]],
        target_w_mm: float,
        target_h_mm: float,
        settings: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Master Multi-Color & Multi-Pen Plotting Slicing Engine.
        Executes each color layer completely, moves pen to (0,0) at drawing Z-height for calibration,
        inserts user pause, and lifts Z-Hop BEFORE starting the next color to prevent ink drag!
        """
        cfg = cls.DEFAULT_SETTINGS.copy()
        if settings:
            cfg.update(settings)

        # Collect all geometries across all layers to compute collective bounding box
        all_geoms: List[Any] = []
        for col_data in color_layers.values():
            all_geoms.extend(col_data.get("polygons", []))
            all_geoms.extend(col_data.get("lines", []))

        if not all_geoms:
            return {"gcode": "", "lines_count": 0, "estimated_time_s": 0, "ordered_moves": [], "paths": {"walls":[], "infill":[], "travels":[]}}

        all_bounds = [g.bounds for g in all_geoms]
        min_x = min(b[0] for b in all_bounds)
        min_y = min(b[1] for b in all_bounds)
        max_x = max(b[2] for b in all_bounds)
        max_y = max(b[3] for b in all_bounds)
        model_w = max(0.001, max_x - min_x)
        model_h = max(0.001, max_y - min_y)

        # Paper placement offsets & Directional Safety Margins
        paper_w = float(cfg.get("paper_width_mm", 210.0))
        paper_h = float(cfg.get("paper_height_mm", 148.0))
        placement = cfg.get("paper_placement", "directional")

        # Directional margins (Left, Right, Bottom, Top)
        fallback_margin = float(cfg.get("paper_margin_mm", 15.0))
        margin_left = float(cfg.get("margin_left_mm", fallback_margin))
        margin_right = float(cfg.get("margin_right_mm", fallback_margin))
        margin_bottom = float(cfg.get("margin_bottom_mm", fallback_margin))
        margin_top = float(cfg.get("margin_top_mm", fallback_margin))

        # Centering flags
        center_x = cfg.get("center_horizontally", None)
        if center_x is None:
            center_x = (placement == "center") or bool(cfg.get("center_on_a5", True))

        center_y = cfg.get("center_vertically", None)
        if center_y is None:
            center_y = (placement == "center") or bool(cfg.get("center_on_a5", True))

        offset_x = 0.0
        offset_y = 0.0

        if cfg.get("center_on_bed", False) or placement == "center_bed":
            bed_cx = float(cfg.get("bed_size_x", 220.0)) / 2.0
            bed_cy = float(cfg.get("bed_size_y", 220.0)) / 2.0
            offset_x = bed_cx - (min_x + model_w / 2.0)
            offset_y = bed_cy - (min_y + model_h / 2.0)
        elif placement == "custom_zero":
            offset_x = -min_x
            offset_y = -min_y
        else:
            # Horizontal (X) positioning:
            if center_x:
                offset_x = (paper_w - model_w) / 2.0 - min_x
            else:
                offset_x = margin_left - min_x

            # Vertical (Y) positioning:
            if center_y:
                offset_y = (paper_h - model_h) / 2.0 - min_y
            else:
                offset_y = margin_bottom - min_y

        # Translate all polygons and lines by offset
        shifted_layers: Dict[str, Dict[str, Any]] = {}
        for col_hex, col_data in color_layers.items():
            translated_polys = [
                shapely.affinity.translate(p, xoff=offset_x, yoff=offset_y)
                for p in col_data.get("polygons", [])
            ]
            translated_lines = [
                shapely.affinity.translate(l, xoff=offset_x, yoff=offset_y)
                for l in col_data.get("lines", [])
            ]
            shifted_layers[col_hex] = {
                "hex": col_hex,
                "name": col_data.get("name", get_arabic_color_name(col_hex)),
                "polygons": translated_polys,
                "lines": translated_lines
            }

        # Extraction parameters
        line_w = max(0.1, float(cfg["line_width"]))
        wall_count = max(1, int(cfg["wall_line_count"]))
        infill_density = float(cfg["infill_density"])
        infill_pattern = str(cfg["infill_pattern"])
        z_layer = float(cfg["initial_layer_height"])
        z_hop = float(cfg["z_hop_height"]) if cfg["enable_z_hop"] else 0.0

        f_travel = int(cfg["travel_speed"] * 60)
        f_wall = int(cfg["wall_speed"] * 60)
        f_infill = int(cfg["infill_speed"] * 60)
        f_zhop = int(cfg["z_hop_speed"] * 60)
        f_retract = int(cfg["retraction_speed"] * 60)
        retract_dist = float(cfg["retraction_distance"]) if cfg["enable_retraction"] else 0.0

        is_extrusion = bool(cfg.get("extrusion_mode", False)) or (float(cfg["print_temp"]) > 50.0)

        # Build G-Code header
        gcode: List[str] = []
        gcode.append("; ===========================================")
        gcode.append("; G-Code Generated by 3D Drawing & Multi-Pen Plotter Assistant")
        gcode.append(f"; Dimensions: {model_w:.1f} x {model_h:.1f} mm | Paper: {paper_w:.1f} x {paper_h:.1f} mm")
        gcode.append(f"; Color Layers: {len(shifted_layers)} colors | Line Width: {line_w:.2f} mm")
        gcode.append(f"; Infill: {infill_density:.1f}% ({infill_pattern}) | Walls: {wall_count}")
        gcode.append(f"; Mode: {'Plastic 3D Print' if is_extrusion else 'Pen Plotting / Drawing'}")
        gcode.append("; ===========================================")
        gcode.append("G21 ; Millimeters")
        gcode.append("G90 ; Absolute coordinates")
        if is_extrusion:
            gcode.append("M82 ; Absolute extrusion mode")

        # Initial positioning
        if not cfg.get("start_at_custom_origin", True):
            gcode.append("G28 ; Home all axes")
        gcode.append(f"G1 Z{z_hop:.2f} F{f_zhop} ; Lift to safe travel height")

        total_travel_dist = 0.0
        total_print_dist = 0.0
        total_wall_dist = 0.0
        total_infill_dist = 0.0
        current_x = 0.0
        current_y = 0.0
        e_pos = 0.0

        ordered_moves: List[Dict[str, Any]] = []
        path_records: Dict[str, List[List[Tuple[float, float]]]] = {
            "walls": [],
            "infill": [],
            "travels": []
        }
        color_stats: Dict[str, Dict[str, Any]] = {}

        def travel_to(tx: float, ty: float):
            nonlocal total_travel_dist, current_x, current_y, e_pos
            dist = math.hypot(tx - current_x, ty - current_y)
            if dist > 0.001:
                total_travel_dist += dist
                ordered_moves.append({
                    "type": "travel",
                    "points": [(current_x, current_y), (tx, ty)],
                    "speed": f_travel,
                    "color": "#94a3b8"
                })
                path_records["travels"].append([(current_x, current_y), (tx, ty)])

            if is_extrusion and retract_dist > 0:
                e_pos -= retract_dist
                gcode.append(f"G1 E{e_pos:.4f} F{f_retract} ; Retract")

            if z_hop > 0:
                gcode.append(f"G1 Z{z_layer + z_hop:.2f} F{f_zhop} ; Pen Lift (Z-Hop)")

            gcode.append(f"G0 X{tx:.3f} Y{ty:.3f} F{f_travel} ; Travel move")
            current_x = tx
            current_y = ty

            if z_hop > 0:
                gcode.append(f"G1 Z{z_layer:.2f} F{f_zhop} ; Pen Down")

            if is_extrusion and retract_dist > 0:
                e_pos += retract_dist
                gcode.append(f"G1 E{e_pos:.4f} F{f_retract} ; Unretract")

        def draw_path(pts: List[Tuple[float, float]], speed: int, is_closed: bool = True, kind: str = "wall", color: str = "#000000"):
            nonlocal total_print_dist, total_wall_dist, total_infill_dist, current_x, current_y, e_pos
            if len(pts) < 2:
                return

            travel_to(pts[0][0], pts[0][1])

            drawn_pts = [(pts[0][0], pts[0][1])]
            for pt in pts[1:]:
                dist = math.hypot(pt[0] - current_x, pt[1] - current_y)
                total_print_dist += dist
                if kind == "wall":
                    total_wall_dist += dist
                else:
                    total_infill_dist += dist
                current_x = pt[0]
                current_y = pt[1]
                drawn_pts.append((current_x, current_y))

                if is_extrusion:
                    e_vol = dist * z_layer * line_w * (cfg["flow"] / 100.0)
                    e_inc = e_vol / (math.pi * (0.875 ** 2))
                    e_pos += e_inc
                    gcode.append(f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} E{e_pos:.4f} F{speed}")
                else:
                    gcode.append(f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} F{speed}")

            if is_closed and len(pts) > 2:
                dist = math.hypot(pts[0][0] - current_x, pts[0][1] - current_y)
                total_print_dist += dist
                if kind == "wall":
                    total_wall_dist += dist
                else:
                    total_infill_dist += dist
                current_x = pts[0][0]
                current_y = pts[0][1]
                drawn_pts.append((current_x, current_y))
                if is_extrusion:
                    e_vol = dist * z_layer * line_w * (cfg["flow"] / 100.0)
                    e_inc = e_vol / (math.pi * (0.875 ** 2))
                    e_pos += e_inc
                    gcode.append(f"G1 X{pts[0][0]:.3f} Y{pts[0][1]:.3f} E{e_pos:.4f} F{speed}")
                else:
                    gcode.append(f"G1 X{pts[0][0]:.3f} Y{pts[0][1]:.3f} F{speed}")

            ordered_moves.append({
                "type": kind,
                "kind": kind,
                "points": drawn_pts,
                "speed": speed,
                "width": line_w,
                "color": color
            })
            if kind in ("wall", "corner_cross"):
                path_records["walls"].append(drawn_pts)
            else:
                path_records["infill"].append(drawn_pts)

        # Process each color layer sequentially
        layer_items = list(shifted_layers.items())
        total_layers = len(layer_items)

        # Draw Corner Registration Crosses (+) if enabled
        enable_crosses = bool(cfg.get("enable_corner_crosses", True))
        cross_size = float(cfg.get("corner_cross_size_mm", 6.0))
        cross_half = cross_size / 2.0

        if enable_crosses:
            gcode.append("")
            gcode.append("; ===========================================")
            gcode.append("; CORNER REGISTRATION CROSSES (+) FOR ALIGNMENT")
            gcode.append("; ===========================================")

            corners = [
                ("أسفل يسار (Bottom-Left)", margin_left, margin_bottom),
                ("أسفل يمين (Bottom-Right)", paper_w - margin_right, margin_bottom),
                ("أعلى يمين (Top-Right)", paper_w - margin_right, paper_h - margin_top),
                ("أعلى يسار (Top-Left)", margin_left, paper_h - margin_top)
            ]

            first_pen_color = layer_items[0][0] if layer_items else "#0284c7"

            for c_name, cx, cy in corners:
                gcode.append(f"; Corner Cross (+): {c_name} at ({cx:.1f}, {cy:.1f})")
                # Stroke 1: Horizontal line
                pt_h_start = (cx - cross_half, cy)
                pt_h_end = (cx + cross_half, cy)
                draw_path([pt_h_start, pt_h_end], speed=f_wall, is_closed=False, kind="corner_cross", color=first_pen_color)

                # Stroke 2: Vertical line
                pt_v_start = (cx, cy - cross_half)
                pt_v_end = (cx, cy + cross_half)
                draw_path([pt_v_start, pt_v_end], speed=f_wall, is_closed=False, kind="corner_cross", color=first_pen_color)

        for layer_idx, (col_hex, layer_data) in enumerate(layer_items):
            col_name = layer_data.get("name", col_hex)
            polygons = layer_data.get("polygons", [])
            lines = layer_data.get("lines", [])
            if not polygons and not lines:
                continue

            color_start_dist = total_print_dist
            gcode.append("")
            gcode.append("; -------------------------------------------")
            gcode.append(f"; COLOR LAYER {layer_idx + 1}/{total_layers}: {col_name} ({col_hex})")
            gcode.append("; -------------------------------------------")

            # 1. Generate Walls / Perimeters for polygons in this color
            for poly in polygons:
                curr_poly = poly
                wall_drawn_for_poly = False
                for w_idx in range(wall_count):
                    inset_dist = line_w * (0.5 if w_idx == 0 else 1.0)
                    try:
                        next_poly = curr_poly.buffer(-inset_dist)
                    except Exception:
                        break

                    # Fallback for thin features: if first wall buffer is empty, draw boundary directly!
                    if next_poly.is_empty:
                        if w_idx == 0 and not wall_drawn_for_poly:
                            # Thin feature preservation: NEVER DROP!
                            draw_path(list(poly.exterior.coords), speed=f_wall, is_closed=True, kind="wall", color=col_hex)
                            for hole in poly.interiors:
                                draw_path(list(hole.coords), speed=f_wall, is_closed=True, kind="wall", color=col_hex)
                            wall_drawn_for_poly = True
                        break

                    curr_poly = next_poly
                    geoms = [curr_poly] if curr_poly.geom_type == 'Polygon' else curr_poly.geoms
                    for g in geoms:
                        if g.is_empty:
                            continue
                        draw_path(list(g.exterior.coords), speed=f_wall, is_closed=True, kind="wall", color=col_hex)
                        for hole in g.interiors:
                            draw_path(list(hole.coords), speed=f_wall, is_closed=True, kind="wall", color=col_hex)
                        wall_drawn_for_poly = True

            # 2. Draw direct open lines, handwritten notes, text strokes, and dots
            for geom_line in lines:
                if geom_line.is_empty:
                    continue
                if geom_line.geom_type == 'LineString':
                    coords = list(geom_line.coords)
                    if len(coords) >= 2:
                        draw_path(coords, speed=f_wall, is_closed=False, kind="wall", color=col_hex)
                elif geom_line.geom_type == 'MultiLineString':
                    for sub_line in geom_line.geoms:
                        coords = list(sub_line.coords)
                        if len(coords) >= 2:
                            draw_path(coords, speed=f_wall, is_closed=False, kind="wall", color=col_hex)
                elif geom_line.geom_type == 'Point':
                    # Precise dot / accent mark / stipple
                    travel_to(geom_line.x, geom_line.y)
                    gcode.append(f"G1 Z{z_layer:.2f} F{f_zhop} ; Dot Down")
                    gcode.append(f"G1 Z{z_layer + z_hop:.2f} F{f_zhop} ; Dot Up")
                    ordered_moves.append({
                        "type": "wall",
                        "points": [(geom_line.x, geom_line.y), (geom_line.x + 0.05, geom_line.y)],
                        "speed": f_wall,
                        "width": line_w,
                        "color": col_hex
                    })
                    path_records["walls"].append([(geom_line.x, geom_line.y), (geom_line.x + 0.05, geom_line.y)])

            # 3. Generate Infill for this color (if density > 0)
            if infill_density > 0:
                spacing = line_w / (infill_density / 100.0)
                for poly in polygons:
                    try:
                        interior = poly.buffer(-line_w * wall_count)
                        if interior.is_empty or interior.area < 0.05:
                            continue

                        infill_lines = cls.generate_infill(interior, infill_pattern, spacing, line_w)
                        for seg_coords in infill_lines:
                            draw_path(seg_coords, speed=f_infill, is_closed=False, kind="infill", color=col_hex)
                    except Exception:
                        pass

            color_drawn_m = (total_print_dist - color_start_dist) / 1000.0
            color_stats[col_hex] = {
                "name": col_name,
                "hex": col_hex,
                "drawn_meters": color_drawn_m,
                "polygons_count": len(polygons) + len(lines)
            }

            # PEN SWAP / TOOL CHANGE:
            # "لا تطلب استبدال اللون الا بعد اكمال نقشه اللون الاول"
            # If there is another color following this one:
            if layer_idx < total_layers - 1:
                next_layer_hex, next_layer_data = layer_items[layer_idx + 1]
                next_layer_name = next_layer_data.get("name", next_layer_hex)

                gcode.append("")
                gcode.append("; ===========================================")
                gcode.append(f"; TOOL CHANGE / PEN SWAP: Finished {col_name} -> Next: {next_layer_name}")
                gcode.append("; ===========================================")

                # 1. Lift pen to Z-hop
                gcode.append(f"G1 Z{z_layer + z_hop:.2f} F{f_zhop} ; Pen Lift for swap")

                # 2. Move pen to origin (0, 0)
                gcode.append(f"G0 X0 Y0 F{f_travel} ; Move pen to Origin (0,0) for pen alignment")
                current_x = 0.0
                current_y = 0.0

                # 3. Lower Z to drawing height: "واجعل الزي اكسس هو نفسه الخاص بالرسم حتى لما استبدل القلم بلون اخر استطيع وضعه عند مكانه الصحيح"
                gcode.append(f"G1 Z{z_layer:.2f} F{f_zhop} ; Lower pen to paper level at (0,0) for height calibration")

                # 4. Printer physical buzzer chime alert (M300) and LCD notification
                gcode.append("M300 S1000 P150 ; Printer Buzzer Tone 1")
                gcode.append("G4 P80 ; Dwell 80ms")
                gcode.append("M300 S1500 P150 ; Printer Buzzer Tone 2")
                gcode.append("G4 P80 ; Dwell 80ms")
                gcode.append("M300 S2000 P350 ; Printer Buzzer Tone 3")
                gcode.append(f"M117 Swap to {next_layer_name} ; Display on Marlin LCD")

                # 5. Pause G-Code marker
                gcode.append(f"; TOOL_CHANGE_COLOR: {next_layer_hex} | {next_layer_name}")
                gcode.append(f"M0 Swap Pen to {next_layer_name} ({next_layer_hex}) ; Marlin Pause for pen swap")

                # Record tool change in ordered moves
                ordered_moves.append({
                    "type": "tool_change",
                    "color": next_layer_hex,
                    "color_name": next_layer_name,
                    "prev_color": col_hex,
                    "prev_color_name": col_name,
                    "points": [(0.0, 0.0), (0.0, 0.0)]
                })

                # 5. CRITICAL USER REQUIREMENT:
                # "وعند بدء حركة اللون الجديد لا تنسى عمل زي هوب حتى لا تعمل خط بالقلم"
                gcode.append(f"G1 Z{z_layer + z_hop:.2f} F{f_zhop} ; CRITICAL Z-Hop: Lift new pen BEFORE moving to avoid drag mark!")

        # Footer
        gcode.append("")
        gcode.append("; ===========================================")
        gcode.append("; Plotting Completed Cleanly")
        gcode.append("; ===========================================")
        gcode.append(f"G1 Z{z_layer + z_hop + 10:.2f} F{f_zhop} ; Raise tool away")
        gcode.append("G91 ; Relative positioning")
        gcode.append("G1 Z5 F600 ; Safe raise")
        gcode.append("G90 ; Absolute positioning")
        if not cfg.get("start_at_custom_origin", True):
            gcode.append("G1 X0 Y200 F9000 ; Present build plate")
        gcode.append("M104 S0 ; Extruder heater OFF")
        gcode.append("M140 S0 ; Bed heater OFF")
        gcode.append("M107 ; Fan OFF")
        gcode.append("M84 ; Disable steppers")

        full_gcode = "\n".join(gcode)

        t_print_s = (total_print_dist / (cfg["wall_speed"])) if cfg["wall_speed"] > 0 else 0
        t_travel_s = (total_travel_dist / (cfg["travel_speed"])) if cfg["travel_speed"] > 0 else 0
        total_time_s = t_print_s + t_travel_s + 10.0 + (len(shifted_layers) * 15.0)

        final_min_x = min_x + offset_x
        final_min_y = min_y + offset_y
        final_max_x = max_x + offset_x
        final_max_y = max_y + offset_y

        clearance_left = max(0.0, final_min_x)
        clearance_right = max(0.0, paper_w - final_max_x)
        clearance_bottom = max(0.0, final_min_y)
        clearance_top = max(0.0, paper_h - final_max_y)

        return {
            "gcode": full_gcode,
            "lines_count": len(gcode),
            "estimated_time_s": total_time_s,
            "travel_distance_mm": total_travel_dist,
            "print_distance_mm": total_print_dist,
            "wall_distance_mm": total_wall_dist,
            "infill_distance_mm": total_infill_dist,
            "line_width_mm": line_w,
            "wall_count": wall_count,
            "infill_density": infill_density,
            "infill_pattern": infill_pattern,
            "ordered_moves": ordered_moves,
            "paths": path_records,
            "bounds": (final_min_x, final_min_y, final_max_x, final_max_y),
            "model_w_mm": model_w,
            "model_h_mm": model_h,
            "paper_w_mm": paper_w,
            "paper_h_mm": paper_h,
            "placement": placement,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "clearance_left": clearance_left,
            "clearance_right": clearance_right,
            "clearance_bottom": clearance_bottom,
            "clearance_top": clearance_top,
            "margin_left_mm": margin_left,
            "margin_right_mm": margin_right,
            "margin_bottom_mm": margin_bottom,
            "margin_top_mm": margin_top,
            "center_horizontally": center_x,
            "center_vertically": center_y,
            "raw_color_layers": color_layers,
            "color_layers_summary": list(color_stats.values()),
            "color_layers": shifted_layers
        }

    @classmethod
    def recolor_geometry_at(
        cls,
        color_layers: Dict[str, Dict[str, Any]],
        click_x: float,
        click_y: float,
        offset_x: float,
        offset_y: float,
        new_hex: str,
        max_dist_mm: float = 3.5
    ) -> Optional[Dict[str, Any]]:
        """
        Interactive Coloring Studio Engine:
        Finds the shape or line at (click_x, click_y) on the paper and transfers it
        to the new_hex color layer.
        Returns dict with undo information, or None if no shape was hit.
        """
        model_x = click_x - offset_x
        model_y = click_y - offset_y
        pt = sg.Point(model_x, model_y)

        # 1. Search closed polygons containing the point (Paint Bucket / Flood Fill)
        for col_hex, layer_info in list(color_layers.items()):
            polys = layer_info.get("polygons", [])
            for idx, p in enumerate(polys):
                if p.contains(pt):
                    if col_hex.upper() == new_hex.upper():
                        return None
                    target_p = polys.pop(idx)
                    if new_hex not in color_layers:
                        color_layers[new_hex] = {
                            "hex": new_hex,
                            "name": get_arabic_color_name(new_hex),
                            "polygons": [],
                            "lines": []
                        }
                    color_layers[new_hex]["polygons"].append(target_p)
                    # Clean up empty layer
                    if not polys and not layer_info.get("lines", []):
                        color_layers.pop(col_hex, None)
                    return {
                        "geom": target_p,
                        "type": "polygon",
                        "old_hex": col_hex,
                        "new_hex": new_hex
                    }

        # 2. Search nearest polygon boundary or line within max_dist_mm (Line Brush)
        best_dist = max_dist_mm
        best_hit = None

        for col_hex, layer_info in list(color_layers.items()):
            for idx, p in enumerate(layer_info.get("polygons", [])):
                d = p.exterior.distance(pt)
                if d < best_dist:
                    best_dist = d
                    best_hit = (col_hex, "polygon", idx, p)

            for idx, l in enumerate(layer_info.get("lines", [])):
                d = l.distance(pt)
                if d < best_dist:
                    best_dist = d
                    best_hit = (col_hex, "line", idx, l)

        if best_hit:
            src_col, geom_type, idx, geom = best_hit
            if src_col.upper() == new_hex.upper():
                return None
            if geom_type == "polygon":
                target_g = color_layers[src_col]["polygons"].pop(idx)
            else:
                target_g = color_layers[src_col]["lines"].pop(idx)

            if new_hex not in color_layers:
                color_layers[new_hex] = {
                    "hex": new_hex,
                    "name": get_arabic_color_name(new_hex),
                    "polygons": [],
                    "lines": []
                }
            if geom_type == "polygon":
                color_layers[new_hex]["polygons"].append(target_g)
            else:
                color_layers[new_hex]["lines"].append(target_g)

            # Clean up empty layer
            if not color_layers[src_col].get("polygons", []) and not color_layers[src_col].get("lines", []):
                color_layers.pop(src_col, None)

            return {
                "geom": target_g,
                "type": geom_type,
                "old_hex": src_col,
                "new_hex": new_hex
            }

        return None

    @classmethod
    def parse_gcode_to_toolpaths(cls, gcode_text: str) -> Dict[str, Any]:
        """Parses any G-Code text, extracting move coordinates, speeds, and color pen swaps."""
        ordered_moves: List[Dict[str, Any]] = []
        path_records: Dict[str, List[List[Tuple[float, float]]]] = {"walls": [], "infill": [], "travels": []}

        cur_x = 0.0
        cur_y = 0.0
        cur_z = 0.0
        cur_e = 0.0
        total_print_dist = 0.0
        total_travel_dist = 0.0
        total_wall_dist = 0.0
        total_infill_dist = 0.0

        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')

        current_kind = "wall"
        current_color = "#000000"
        detected_colors: Dict[str, str] = {}

        for raw_line in gcode_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if "; TOOL_CHANGE_COLOR:" in line:
                parts = line.split("TOOL_CHANGE_COLOR:", 1)[1].split("|")
                next_hex = parts[0].strip()
                next_name = parts[1].strip() if len(parts) > 1 else next_hex
                current_color = next_hex
                detected_colors[next_hex] = next_name
                ordered_moves.append({
                    "type": "tool_change",
                    "color": next_hex,
                    "color_name": next_name,
                    "points": [(cur_x, cur_y), (cur_x, cur_y)]
                })

            if "; --- Outer & Inner Walls ---" in line:
                current_kind = "wall"
            elif "; --- Infill Lines ---" in line:
                current_kind = "infill"

            cmd_part = line[:line.index(";")].strip() if ";" in line else line
            if not cmd_part:
                continue

            tokens = cmd_part.split()
            cmd = tokens[0].upper()
            if cmd in ("G0", "G1"):
                new_x = cur_x
                new_y = cur_y
                new_z = cur_z
                new_e = cur_e
                has_x = False
                has_y = False

                for t in tokens[1:]:
                    val_str = t[1:]
                    try:
                        if t.startswith(("X", "x")):
                            new_x = float(val_str)
                            has_x = True
                        elif t.startswith(("Y", "y")):
                            new_y = float(val_str)
                            has_y = True
                        elif t.startswith(("Z", "z")):
                            new_z = float(val_str)
                        elif t.startswith(("E", "e")):
                            new_e = float(val_str)
                    except ValueError:
                        pass

                dist = math.hypot(new_x - cur_x, new_y - cur_y)
                is_travel = (cmd == "G0") or (new_z > 0.5) or (cur_z > 0.5)

                if dist > 0.001 and (has_x or has_y):
                    if is_travel:
                        total_travel_dist += dist
                        ordered_moves.append({
                            "type": "travel",
                            "points": [(cur_x, cur_y), (new_x, new_y)],
                            "color": "#94a3b8"
                        })
                        path_records["travels"].append([(cur_x, cur_y), (new_x, new_y)])
                    else:
                        total_print_dist += dist
                        kind = current_kind
                        if kind == "infill":
                            total_infill_dist += dist
                            path_records["infill"].append([(cur_x, cur_y), (new_x, new_y)])
                        else:
                            total_wall_dist += dist
                            path_records["walls"].append([(cur_x, cur_y), (new_x, new_y)])

                        ordered_moves.append({
                            "type": kind,
                            "points": [(cur_x, cur_y), (new_x, new_y)],
                            "width": 0.4,
                            "color": current_color
                        })

                        min_x = min(min_x, cur_x, new_x)
                        min_y = min(min_y, cur_y, new_y)
                        max_x = max(max_x, cur_x, new_x)
                        max_y = max(max_y, cur_y, new_y)

                cur_x = new_x
                cur_y = new_y
                cur_z = new_z
                cur_e = new_e

        if min_x == float('inf'):
            min_x = min_y = max_x = max_y = 0.0

        model_w = max(0.0, max_x - min_x)
        model_h = max(0.0, max_y - min_y)

        summary = [{"hex": h, "name": n} for h, n in detected_colors.items()]

        return {
            "gcode": gcode_text,
            "lines_count": len(gcode_text.splitlines()),
            "estimated_time_s": (total_print_dist / 50.0) + (total_travel_dist / 150.0) + 10.0,
            "travel_distance_mm": total_travel_dist,
            "print_distance_mm": total_print_dist,
            "wall_distance_mm": total_wall_dist,
            "infill_distance_mm": total_infill_dist,
            "line_width_mm": 0.4,
            "wall_count": 2,
            "infill_density": 20.0,
            "infill_pattern": "Lines",
            "ordered_moves": ordered_moves,
            "paths": path_records,
            "bounds": (min_x, min_y, max_x, max_y),
            "model_w_mm": model_w,
            "model_h_mm": model_h,
            "paper_w_mm": 210.0,
            "paper_h_mm": 148.0,
            "placement": "custom_zero",
            "color_layers_summary": summary
        }
