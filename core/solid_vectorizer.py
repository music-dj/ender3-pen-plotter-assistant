"""
Solid Vectorization Engine for 3D Printing & Slicing.
Converts raster images into solid filled SVG shapes with accurate hole handling (evenodd).
"""
import cv2
import numpy as np
from typing import List, Tuple, Dict, Any

class SolidVectorizer:
    @staticmethod
    def vectorize_to_solid_svg(
        binary_img: np.ndarray,
        target_width_mm: float = 150.0,
        target_height_mm: float = 150.0,
        thickness_mm: float = 0.2,
        epsilon: float = 0.8,
        fill_color: str = "#222222"
    ) -> Dict[str, Any]:
        """
        Extracts all outer contours and internal holes and builds a solid-filled SVG
        using fill-rule='evenodd' for direct use in 3D slicers (Cura, Bambu Studio, PrusaSlicer).
        """
        h, w = binary_img.shape
        if h == 0 or w == 0:
            return {"svg": "", "contours": [], "stats": {"contours": 0, "points": 0}}

        # Find all contours with hierarchical relationships (outer perimeters and inner cutouts/holes)
        contours, hierarchy = cv2.findContours(binary_img, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)

        if not contours:
            return {"svg": "", "contours": [], "stats": {"contours": 0, "points": 0}}

        scale_x = target_width_mm / w
        scale_y = target_height_mm / h

        path_segments = []
        total_points = 0
        simplified_contours = []

        for cnt in contours:
            if cv2.contourArea(cnt) < 4:  # Filter out tiny noise artifacts
                continue

            approx = cv2.approxPolyDP(cnt, epsilon, closed=True)
            pts = [pt[0] for pt in approx]
            if len(pts) < 3:
                continue

            total_points += len(pts)
            simplified_contours.append(pts)

            # Build SVG subpath 'M x y L x y ... Z'
            subpath_parts = []
            for i, (px, py) in enumerate(pts):
                mx = px * scale_x
                my = py * scale_y
                if i == 0:
                    subpath_parts.append(f"M {mx:.3f} {my:.3f}")
                else:
                    subpath_parts.append(f"L {mx:.3f} {my:.3f}")
            subpath_parts.append("Z")
            path_segments.append(" ".join(subpath_parts))

        compound_path = " ".join(path_segments)

        svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:slic3r="http://slic3r.org/namespaces/slic3r"
     xmlns:bambu="http://bambulab.com/namespaces/bambu"
     version="1.1"
     width="{target_width_mm:.2f}mm"
     height="{target_height_mm:.2f}mm"
     viewBox="0 0 {target_width_mm:.2f} {target_height_mm:.2f}">
<!--
  3D Printable Solid Model
  Target Physical Dimensions: {target_width_mm:.2f}mm x {target_height_mm:.2f}mm
  Target 3D Thickness (Extrusion Height): {thickness_mm:.2f}mm
  Slicer Infill: Solid filled body with evenodd holes
-->
<g id="solid_body" slic3r:extrusion_height="{thickness_mm:.2f}" bambu:height="{thickness_mm:.2f}">
  <path d="{compound_path}"
        fill="{fill_color}"
        fill-rule="evenodd"
        stroke="none" />
</g>
</svg>"""

        return {
            "svg": svg_content,
            "contours": simplified_contours,
            "stats": {
                "contours": len(simplified_contours),
                "points": total_points
            }
        }
