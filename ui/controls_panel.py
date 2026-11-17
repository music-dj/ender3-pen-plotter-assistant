"""
Controls and Configuration Panel for 3D Printing Assistant.
"""
import customtkinter as ctk

class ControlsPanel(ctk.CTkScrollableFrame):
    def __init__(
        self,
        master,
        on_change_callback,
        on_export_svg_callback,
        on_export_stl_callback,
        on_open_callback,
        on_slice_callback=None,
        on_save_project_callback=None,
        on_load_project_callback=None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.on_change = on_change_callback
        self.on_export_svg = on_export_svg_callback
        self.on_export_stl = on_export_stl_callback
        self.on_open = on_open_callback
        self.on_slice = on_slice_callback
        self.on_save_project = on_save_project_callback
        self.on_load_project = on_load_project_callback

        self._build_ui()

    def _build_ui(self):
        title_lbl = ctk.CTkLabel(
            self,
            text="🎨 إعدادات المجسم والتصميم",
            font=("Segoe UI", 16, "bold"),
            anchor="e"
        )
        title_lbl.pack(fill="x", padx=10, pady=(10, 12))

        # --- Section: Files & Projects ---
        file_box = ctk.CTkFrame(self, fg_color="transparent")
        file_box.pack(fill="x", padx=10, pady=(0, 10))

        btn_open = ctk.CTkButton(
            file_box,
            text="📂 اختيار صورة أو SVG من الجهاز",
            command=self.on_open,
            fg_color="#2b7de9",
            hover_color="#1a64ca",
            height=36,
            font=("Segoe UI", 12, "bold")
        )
        btn_open.pack(fill="x", pady=(0, 4))

        proj_btns = ctk.CTkFrame(file_box, fg_color="transparent")
        proj_btns.pack(fill="x")

        btn_load_proj = ctk.CTkButton(
            proj_btns,
            text="📂 فتح مشروع سابق",
            command=self.on_load_project,
            fg_color="#475569",
            hover_color="#334155",
            height=30,
            font=("Segoe UI", 11)
        )
        btn_load_proj.pack(side="left", fill="x", expand=True, padx=(0, 3))

        btn_save_proj = ctk.CTkButton(
            proj_btns,
            text="💾 حفظ المشروع بالألوان",
            command=self.on_save_project,
            fg_color="#0d9488",
            hover_color="#0f766e",
            height=30,
            font=("Segoe UI", 11, "bold")
        )
        btn_save_proj.pack(side="right", fill="x", expand=True, padx=(3, 0))

        # --- Section: Dimensions (mm) ---
        dim_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        dim_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(dim_frame, text="📏 أبعاد المجسم المادية (mm)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=10, pady=(8, 4))

        # Width
        w_box = ctk.CTkFrame(dim_frame, fg_color="transparent")
        w_box.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(w_box, text="العرض (mm):").pack(side="left")
        self.width_var = ctk.StringVar(value="150")
        self.entry_w = ctk.CTkEntry(w_box, textvariable=self.width_var, width=75)
        self.entry_w.pack(side="right")
        self.entry_w.bind("<Return>", lambda e: self.on_change())
        self.entry_w.bind("<FocusOut>", lambda e: self.on_change())

        # Height
        h_box = ctk.CTkFrame(dim_frame, fg_color="transparent")
        h_box.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(h_box, text="الارتفاع (mm):").pack(side="left")
        self.height_var = ctk.StringVar(value="150")
        self.entry_h = ctk.CTkEntry(h_box, textvariable=self.height_var, width=75)
        self.entry_h.pack(side="right")
        self.entry_h.bind("<Return>", lambda e: self.on_change())
        self.entry_h.bind("<FocusOut>", lambda e: self.on_change())

        # Aspect Ratio Lock Checkbox
        self.lock_aspect_var = ctk.BooleanVar(value=True)
        self.chk_lock = ctk.CTkCheckBox(
            dim_frame,
            text="قفل تناسب الأبعاد (Aspect Ratio)",
            variable=self.lock_aspect_var,
            font=("Segoe UI", 11)
        )
        self.chk_lock.pack(anchor="e", padx=10, pady=6)

        # Dimension Presets
        preset_box = ctk.CTkFrame(dim_frame, fg_color="transparent")
        preset_box.pack(fill="x", padx=10, pady=(0, 8))
        btn_a5 = ctk.CTkButton(preset_box, text="ورقة A5", width=62, height=26, font=("Segoe UI", 10, "bold"), fg_color="#0284c7", hover_color="#0369a1", command=lambda: self.set_preset(190))
        btn_a5.pack(side="left", padx=2)
        btn_bed = ctk.CTkButton(preset_box, text="200mm", width=58, height=26, font=("Segoe UI", 10), command=lambda: self.set_preset(200))
        btn_bed.pack(side="left", padx=2)
        btn_150 = ctk.CTkButton(preset_box, text="150mm", width=58, height=26, font=("Segoe UI", 10), command=lambda: self.set_preset(150))
        btn_150.pack(side="left", padx=2)
        btn_100 = ctk.CTkButton(preset_box, text="100mm", width=58, height=26, font=("Segoe UI", 10), command=lambda: self.set_preset(100))
        btn_100.pack(side="left", padx=2)

        # --- Section: 3D Thickness (Z Height) ---
        thick_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        thick_frame.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(thick_frame, text="🧊 سمك المجسم للطباعة (Z Height)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=10, pady=(8, 2))

        z_box = ctk.CTkFrame(thick_frame, fg_color="transparent")
        z_box.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(z_box, text="السمك ثلاثي الأبعاد (mm):").pack(side="left")
        self.thick_var = ctk.StringVar(value="0.3")
        self.entry_thick = ctk.CTkEntry(z_box, textvariable=self.thick_var, width=75)
        self.entry_thick.pack(side="right")
        self.entry_thick.bind("<Return>", lambda e: self.on_change())
        self.entry_thick.bind("<FocusOut>", lambda e: self.on_change())

        ctk.CTkLabel(
            thick_frame,
            text="✨ 0.3 مم أو 0.2 مم = طبقة أولى مثالية للرسم وملء الفراغات",
            font=("Segoe UI", 10),
            text_color="#10b981"
        ).pack(anchor="e", padx=10, pady=(0, 8))

        # --- Section: Smoothness / Tolerance (Epsilon) ---
        smooth_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        smooth_frame.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(smooth_frame, text="✨ نعومة ودقة الحواف (Smoothing)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=10, pady=(8, 2))
        
        self.smooth_lbl = ctk.CTkLabel(smooth_frame, text="0.30 مم (حواف ناعمة فائقة الدقة)", font=("Segoe UI", 10), text_color="#38bdf8")
        self.smooth_lbl.pack(anchor="e", padx=10)

        self.smooth_slider = ctk.CTkSlider(
            smooth_frame,
            from_=0.1,
            to=1.5,
            number_of_steps=28,
            command=self._on_smooth_slider
        )
        self.smooth_slider.set(0.3)
        self.smooth_slider.pack(fill="x", padx=10, pady=(2, 8))

        # --- Section: Threshold / Contrast ---
        thresh_frame = ctk.CTkFrame(self, fg_color=("gray85", "gray20"))
        thresh_frame.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(thresh_frame, text="🎚️ حساسية التقاط الجسم (Threshold)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=10, pady=(8, 2))

        self.thresh_lbl = ctk.CTkLabel(thresh_frame, text="128", font=("Segoe UI", 11))
        self.thresh_lbl.pack(anchor="e", padx=10)

        self.thresh_slider = ctk.CTkSlider(
            thresh_frame,
            from_=10,
            to=250,
            number_of_steps=48,
            command=self._on_thresh_slider
        )
        self.thresh_slider.set(128)
        self.thresh_slider.pack(fill="x", padx=10, pady=(2, 6))

        self.invert_var = ctk.BooleanVar(value=False)
        self.chk_invert = ctk.CTkCheckBox(
            thresh_frame,
            text="عكس الجسم والخلفية (Invert)",
            variable=self.invert_var,
            font=("Segoe UI", 11),
            command=self.on_change
        )
        self.chk_invert.pack(anchor="e", padx=10, pady=(0, 8))

        # --- Section: Statistics ---
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=10, pady=4)
        self.lbl_stats = ctk.CTkLabel(
            self.stats_frame,
            text="الأشكال المغلقة: 0 | النقاط: 0",
            font=("Segoe UI", 11),
            text_color="gray"
        )
        self.lbl_stats.pack(anchor="center")

        # --- Slicing Quick Action ---
        if self.on_slice:
            btn_slice_quick = ctk.CTkButton(
                self,
                text="⚡ عمل سلايس وإرسال للطباعة",
                command=self.on_slice,
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                height=38,
                font=("Segoe UI", 13, "bold")
            )
            btn_slice_quick.pack(fill="x", padx=10, pady=(10, 4))

        # --- Section: Action Buttons ---
        btn_stl = ctk.CTkButton(
            self,
            text="🧊 تصدير مجسم 3D STL (Watertight)",
            command=self.on_export_stl,
            fg_color="#0078d4",
            hover_color="#005a9e",
            height=38,
            font=("Segoe UI", 13, "bold")
        )
        btn_stl.pack(fill="x", padx=10, pady=(6, 4))

        btn_svg = ctk.CTkButton(
            self,
            text="💾 تصدير SVG صلب للتقطيع",
            command=self.on_export_svg,
            fg_color="#107c41",
            hover_color="#0b5c30",
            height=34,
            font=("Segoe UI", 12, "bold")
        )
        btn_svg.pack(fill="x", padx=10, pady=(4, 20))

    def _on_thresh_slider(self, val):
        self.thresh_lbl.configure(text=f"{int(val)}")
        self.on_change()

    def _on_smooth_slider(self, val):
        self.smooth_lbl.configure(text=f"{val:.2f} مم (حواف ناعمة)")
        self.on_change()

    def set_preset(self, w_val):
        self.width_var.set(str(w_val))
        self.on_change(update_height_from_aspect=True)

    def update_stats(self, shapes_count, points_count):
        self.lbl_stats.configure(text=f"الأشكال المغلقة: {shapes_count} | النقاط: {points_count}")

    def get_config(self):
        try:
            w = float(self.width_var.get())
        except ValueError:
            w = 150.0

        try:
            h = float(self.height_var.get())
        except ValueError:
            h = 150.0

        try:
            th = float(self.thick_var.get())
        except ValueError:
            th = 0.3

        return {
            "target_width_mm": max(10.0, w),
            "target_height_mm": max(10.0, h),
            "lock_aspect": self.lock_aspect_var.get(),
            "thickness_mm": max(0.05, th),
            "threshold": int(self.thresh_slider.get()),
            "invert": self.invert_var.get(),
            "epsilon_mm": float(self.smooth_slider.get())
        }
