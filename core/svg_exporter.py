"""
SVG Generation Engine for Pen Plotters and Printers.
Generates SVG with precise physical dimensions (mm), stroke width < 0.2mm,
and optimized vector paths.
"""
from typing import List, Tuple

class SVGExporter:
    @staticmethod
    def generate_svg(
        polylines: List[List[Tuple[float, float]]],
        img_width: int,
        img_height: int,
        target_width_mm: float = 150.0,
        target_height_mm: float = None,
        stroke_width_mm: float = 0.15,
        stroke_color: str = "#000000"
    ) -> str:
        """
        Converts polylines into an SVG string formatted with physical millimeter units.
        Ensures stroke_width_mm is < 0.2 mm.
        """
        if img_width <= 0 or img_height <= 0:
            return ""

        # Maintain aspect ratio if target_height_mm is not specified
        aspect = img_height / img_width
        if target_height_mm is None or target_height_mm <= 0:
            target_height_mm = target_width_mm * aspect

        # Safety enforce: stroke must be < 0.2mm
        if stroke_width_mm >= 0.2:
            stroke_width_mm = 0.15

        # Scale factor from pixel coordinates to mm
        scale_x = target_width_mm / img_width
        scale_y = target_height_mm / img_height

        path_elements = []
        for poly in polylines:
            if len(poly) < 2:
                continue
            # Build SVG path 'd' attribute
            d_parts = []
            first = True
            for x, y in poly:
                mx = x * scale_x
                my = y * scale_y
                if first:
                    d_parts.append(f"M {mx:.3f} {my:.3f}")
                    first = False
                else:
                    d_parts.append(f"L {mx:.3f} {my:.3f}")

            d_str = " ".join(d_parts)
            path_elements.append(
                f'  <path d="{d_str}" fill="none" stroke="{stroke_color}" '
                f'stroke-width="{stroke_width_mm:.3f}mm" stroke-linecap="round" stroke-linejoin="round" />'
            )

        paths_joined = "\n".join(path_elements)

        svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"
     version="1.1"
     width="{target_width_mm:.2f}mm"
     height="{target_height_mm:.2f}mm"
     viewBox="0 0 {target_width_mm:.2f} {target_height_mm:.2f}">
<!-- Pen Plotter Vector Output: Single-line centerlines with stroke < 0.2mm -->
<g id="pen-layer">
{paths_joined}
</g>
</svg>"""
        return svg_content

    @staticmethod
    def save_svg(filepath: str, svg_content: str):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(svg_content)
