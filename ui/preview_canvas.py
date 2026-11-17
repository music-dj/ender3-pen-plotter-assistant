"""
Interactive Preview Canvas for 3D Printing Assistant.
Displays the solid filled 3D model simulation on a 3D printer build plate alongside the original image.
"""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np

class PreviewCanvas(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_solid = self.tabview.add("🧊 معاينة المجسم للطباعة (Solid 3D)")
        self.tab_orig = self.tabview.add("🖼️ الصورة الأصلية")
        self.tabview.set("🧊 معاينة المجسم للطباعة (Solid 3D)")

        # Solid 3D Bed Canvas
        self.solid_canvas = tk.Canvas(
            self.tab_solid,
            bg="#18181c",
            highlightthickness=0,
            cursor="hand2"
        )
        self.solid_canvas.pack(fill="both", expand=True)

        # Original Image Canvas
        self.orig_canvas = tk.Canvas(
            self.tab_orig,
            bg="#18181c",
            highlightthickness=0
        )
        self.orig_canvas.pack(fill="both", expand=True)

        # State storage
        self.orig_pil_image = None
        self.binary_mask = None
        self.color_layers = None
        self.img_w = 1
        self.img_h = 1
        self.tk_solid = None
        self.tk_orig = None

        self.solid_canvas.bind("<Configure>", self._on_resize)
        self.orig_canvas.bind("<Configure>", self._on_resize)

    def set_original_image(self, pil_image: Image.Image):
        self.orig_pil_image = pil_image
        self.img_w, self.img_h = pil_image.size
        self._render_original()

    def set_solid_mask(self, binary_mask: np.ndarray):
        self.binary_mask = binary_mask
        self.color_layers = None
        self.img_h, self.img_w = binary_mask.shape
        self._render_solid()

    def set_color_layers(self, color_layers: dict, width_mm: float, height_mm: float):
        self.color_layers = color_layers
        self.binary_mask = None
        self.img_w = max(1, int(round(width_mm * 10)))
        self.img_h = max(1, int(round(height_mm * 10)))
        self._render_solid()

    def _on_resize(self, event=None):
        self._render_solid()
        self._render_original()

    def _render_original(self):
        if not self.orig_pil_image:
            return
        cw = self.orig_canvas.winfo_width()
        ch = self.orig_canvas.winfo_height()
        if cw < 30 or ch < 30:
            return

        scale = min(cw / self.img_w, ch / self.img_h) * 0.90
        nw = max(1, int(self.img_w * scale))
        nh = max(1, int(self.img_h * scale))

        resized = self.orig_pil_image.resize((nw, nh), Image.Resampling.LANCZOS)
        self.tk_orig = ImageTk.PhotoImage(resized)

        self.orig_canvas.delete("all")
        x = (cw - nw) // 2
        y = (ch - nh) // 2
        self.orig_canvas.create_image(x, y, anchor="nw", image=self.tk_orig)

    def _render_solid(self):
        self.solid_canvas.delete("all")
        cw = self.solid_canvas.winfo_width()
        ch = self.solid_canvas.winfo_height()

        if self.binary_mask is None and not self.color_layers:
            self.solid_canvas.create_text(
                cw // 2, ch // 2,
                text="اسحب وأفلت صورتك أو ملف SVG هنا لبدء التحويل للرسم والطباعة 🧊\n(SVG, PNG, JPG, BMP, WebP)",
                fill="#777788",
                font=("Segoe UI", 14, "bold"),
                justify="center"
            )
            return

        if cw < 30 or ch < 30:
            return

        # 3D printer build plate simulation
        scale = min(cw / self.img_w, ch / self.img_h) * 0.88
        nw = max(1, int(self.img_w * scale))
        nh = max(1, int(self.img_h * scale))
        off_x = (cw - nw) // 2
        off_y = (ch - nh) // 2

        # Draw Build Plate grid
        grid_margin = 25
        bx0 = off_x - grid_margin
        by0 = off_y - grid_margin
        bx1 = off_x + nw + grid_margin
        by1 = off_y + nh + grid_margin

        # Bed surface
        self.solid_canvas.create_rectangle(bx0, by0, bx1, by1, fill="#2b2d35", outline="#3f424e", width=2)

        # Draw subtle 3D print grid lines (10mm intervals simulation)
        step = max(20, int(30 * scale))
        for gx in range(bx0, bx1, step):
            self.solid_canvas.create_line(gx, by0, gx, by1, fill="#343741", width=1)
        for gy in range(by0, by1, step):
            self.solid_canvas.create_line(bx0, gy, bx1, gy, fill="#343741", width=1)

        # Draw A5 Landscape Paper boundary simulation (210 x 148 mm outline)
        cx_bed = (bx0 + bx1) / 2.0
        cy_bed = (by0 + by1) / 2.0
        a5_px_w = max(nw + 20, int((nh + 20) * (210.0 / 148.0)))
        a5_px_h = int(a5_px_w / (210.0 / 148.0))
        if a5_px_w < (bx1 - bx0 - 10) and a5_px_h < (by1 - by0 - 10):
            a5_x0 = cx_bed - a5_px_w / 2.0
            a5_y0 = cy_bed - a5_px_h / 2.0
            a5_x1 = cx_bed + a5_px_w / 2.0
            a5_y1 = cy_bed + a5_px_h / 2.0
            self.solid_canvas.create_rectangle(
                a5_x0, a5_y0, a5_x1, a5_y1,
                fill="#323540", outline="#60a5fa", width=1.5, dash=(4, 4)
            )
            self.solid_canvas.create_text(
                a5_x0 + 8, a5_y0 + 12,
                text="📄 ورقة A5 بالعرض (210 × 148 مم)",
                fill="#93c5fd",
                font=("Segoe UI", 9, "bold"),
                anchor="w"
            )

        # If we have multi-color vector layers (from SVG)
        if self.color_layers:
            # Draw shadow
            self.solid_canvas.create_rectangle(
                off_x + 3, off_y + 3, off_x + nw + 3, off_y + nh + 3,
                fill="#1e2026", outline=""
            )
            # Draw each color's paths
            s_poly = nw / max(1.0, float(self.img_w / 10.0))
            for col_hex, col_data in self.color_layers.items():
                polys = col_data.get("polygons", [])
                for poly in polys:
                    # Exterior
                    ext_coords = []
                    for (px, py) in poly.exterior.coords:
                        cx_pt = off_x + (px * s_poly)
                        cy_pt = off_y + (nh - py * s_poly)
                        ext_coords.extend([cx_pt, cy_pt])
                    if len(ext_coords) >= 6:
                        self.solid_canvas.create_polygon(
                            ext_coords, fill=col_hex, outline="#111827", width=1
                        )
                # Render lines, notes, text strokes, and points
                lines = col_data.get("lines", [])
                for line in lines:
                    if line.is_empty:
                        continue
                    if line.geom_type == "LineString":
                        coords = []
                        for (px, py) in line.coords:
                            coords.extend([off_x + (px * s_poly), off_y + (nh - py * s_poly)])
                        if len(coords) >= 4:
                            self.solid_canvas.create_line(coords, fill=col_hex, width=2)
                    elif line.geom_type == "MultiLineString":
                        for sub_line in line.geoms:
                            coords = []
                            for (px, py) in sub_line.coords:
                                coords.extend([off_x + (px * s_poly), off_y + (nh - py * s_poly)])
                            if len(coords) >= 4:
                                self.solid_canvas.create_line(coords, fill=col_hex, width=2)
                    elif line.geom_type == "Point":
                        cx_pt = off_x + (line.x * s_poly)
                        cy_pt = off_y + (nh - line.y * s_poly)
                        self.solid_canvas.create_oval(cx_pt - 2, cy_pt - 2, cx_pt + 2, cy_pt + 2, fill=col_hex, outline="")
        elif self.binary_mask is not None:
            # Build visual solid preview image from binary mask
            rgba = np.zeros((self.img_h, self.img_w, 4), dtype=np.uint8)
            fg_mask = self.binary_mask > 127
            rgba[fg_mask] = [0, 210, 255, 255]

            pil_preview = Image.fromarray(rgba, mode="RGBA")
            resized_solid = pil_preview.resize((nw, nh), Image.Resampling.NEAREST)
            self.tk_solid = ImageTk.PhotoImage(resized_solid)

            # Draw 3D layer shadow
            self.solid_canvas.create_rectangle(
                off_x + 3, off_y + 3, off_x + nw + 3, off_y + nh + 3,
                fill="#1e2026", outline=""
            )
            self.solid_canvas.create_image(off_x, off_y, anchor="nw", image=self.tk_solid)
        self.solid_canvas.create_rectangle(
            off_x + 3, off_y + 3, off_x + nw + 3, off_y + nh + 3,
            fill="#1e2026", outline=""
        )
        self.solid_canvas.create_image(off_x, off_y, anchor="nw", image=self.tk_solid)

        # Label on bed
        self.solid_canvas.create_text(
            bx0 + 10, by1 - 12,
            text="🖥️ Build Plate | طبقة أولى مصمتة بسمك 0.2 مم",
            fill="#8899aa",
            font=("Segoe UI", 9, "bold"),
            anchor="w"
        )
