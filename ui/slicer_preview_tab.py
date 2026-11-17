"""
Slicer Preview and A5 Paper Simulation Tab for Ender 3 Pro / Marlin Pen Plotter.
Features:
- Multi-color toolpath visualization (renders paths in their actual ink colors)
- Multi-pen swap simulation with origin (0,0) calibration and Z-Hop indicators
- 10 artistic & structural infill patterns with live switching
- Physical line width rendering (0.4mm pen stroke)
- Detailed color layers manager with per-color visibility toggles
- A5 landscape paper boundary (210 x 148 mm), rulers, safe margins, and automatic fit
- Interactive zoom towards mouse, pan, and step-by-step drawing simulation.
"""
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from typing import Optional, Callable, Dict, Any, List, Set
from core.svg_loader import get_arabic_color_name

class SlicerPreviewTab(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_request_slice: Optional[Callable[[], Any]] = None,
        on_send_to_printer: Optional[Callable[[str], None]] = None,
        on_fit_to_paper: Optional[Callable[[float], None]] = None,
        on_infill_changed: Optional[Callable[[str], None]] = None,
        on_color_layers_updated: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_save_project: Optional[Callable[[], None]] = None,
        on_open_project: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.on_request_slice = on_request_slice
        self.on_send_to_printer = on_send_to_printer
        self.on_fit_to_paper = on_fit_to_paper
        self.on_infill_changed = on_infill_changed
        self.on_color_layers_updated = on_color_layers_updated
        self.on_save_project = on_save_project
        self.on_open_project = on_open_project

        # Slicing Data State
        self.slice_data: Optional[Dict[str, Any]] = None
        self.ordered_moves: List[Dict[str, Any]] = []
        self.total_moves_count: int = 0
        self.active_move_idx: int = 0

        # Interactive Coloring Studio State
        self.active_mode: str = "pan"  # "pan" (view/navigate) or "paint" (direct coloring)
        self.active_paint_tool: str = "fill"  # "fill" (paint bucket) or "line" (path brush)
        self.active_paint_color: str = "#EF4444"  # Default red
        self.color_undo_stack: List[Dict[str, Any]] = []

        # Color Layer Visibility
        self.visible_colors: Set[str] = set()

        # Paper Specifications (Default: A5 Landscape 210 x 148 mm)
        self.paper_w_mm = 210.0
        self.paper_h_mm = 148.0
        self.margin_left_mm = 15.0
        self.margin_right_mm = 15.0
        self.margin_bottom_mm = 15.0
        self.margin_top_mm = 15.0
        self.paper_margin_mm = 15.0

        # Canvas Transform & Navigation
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.base_scale = 1.0  # px per mm
        self.drag_start_x = 0
        self.drag_start_y = 0

        # Simulation state
        self.sim_running = False
        self.sim_timer = None
        self.sim_speed_multiplier = 1

        # Control Variables
        self._init_variables()

        # Build UI Layout
        self._build_ui()

    def _init_variables(self):
        # Paper preset
        self.var_paper_preset = ctk.StringVar(value="ورقة A5 بالعرض (210 × 148 مم)")
        self.var_placement = ctk.StringVar(value="توسيط داخل الورقة (Center)")
        self.var_margin = ctk.StringVar(value="15")

        # Directional Safety Margins (Left, Right, Bottom, Top in mm)
        self.var_margin_left = ctk.StringVar(value="15")
        self.var_margin_right = ctk.StringVar(value="15")
        self.var_margin_bottom = ctk.StringVar(value="15")
        self.var_margin_top = ctk.StringVar(value="15")

        # Independent Centering Toggles
        self.var_center_x = ctk.BooleanVar(value=True)  # توسيط أفقي (يمين ويسار)
        self.var_center_y = ctk.BooleanVar(value=True)  # توسيط رأسي (أعلى وأسفل)

        # Infill Pattern (10 patterns)
        self.var_infill_pattern = ctk.StringVar(value="Cubic")

        # Visual Display Toggles
        self.var_show_physical_width = ctk.BooleanVar(value=True)
        self.var_show_walls = ctk.BooleanVar(value=True)
        self.var_show_infill = ctk.BooleanVar(value=True)
        self.var_show_travels = ctk.BooleanVar(value=True)
        self.var_show_grid = ctk.BooleanVar(value=True)
        self.var_show_margins = ctk.BooleanVar(value=True)
        self.var_corner_crosses = ctk.BooleanVar(value=True)  # علامات الزاوية (+) قبل بدء الرسم

        # Simulation
        self.var_sim_progress = ctk.DoubleVar(value=100.0)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)  # Left controls
        self.grid_columnconfigure(1, weight=1)  # Right canvas
        self.grid_rowconfigure(0, weight=1)

        # =========================================================================
        # LEFT CONTROLS PANEL (Scrollable)
        # =========================================================================
        left_panel = ctk.CTkScrollableFrame(self, width=340, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)

        # Header Title
        title_box = ctk.CTkFrame(left_panel, fg_color="transparent")
        title_box.pack(fill="x", padx=10, pady=(10, 6))

        ctk.CTkLabel(
            title_box,
            text="📐 معاينة السلايس ومتعدد الألوان (A5)",
            font=("Segoe UI", 15, "bold"),
            anchor="e"
        ).pack(fill="x")

        ctk.CTkLabel(
            title_box,
            text="معاينة حية للمسارات بألوانها الحقيقية، تبديل الأقلام، وأنماط التعبئة المتنوعة.",
            font=("Segoe UI", 10),
            text_color="#94a3b8",
            wraplength=310,
            justify="right",
            anchor="e"
        ).pack(fill="x", pady=(2, 0))

        # ----------------- CARD 1: Paper Configuration & Directional Margins -----------------
        card_paper = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        card_paper.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            card_paper,
            text="📄 قياس الورقة ومسافات الأمان",
            font=("Segoe UI", 12, "bold"),
            anchor="e"
        ).pack(fill="x", padx=10, pady=(8, 4))

        # Preset selection
        row_preset = ctk.CTkFrame(card_paper, fg_color="transparent")
        row_preset.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_preset, text="نوع الورقة:", font=("Segoe UI", 11)).pack(side="left")
        self.cmb_preset = ctk.CTkComboBox(
            row_preset,
            values=[
                "ورقة A5 بالعرض (210 × 148 مم)",
                "ورقة A5 بالطول (148 × 210 مم)",
                "ورقة A4 بالعرض (297 × 210 مم)",
                "ورقة A4 بالطول (210 × 297 مم)",
                "سرير الطابعة Ender 3 (220 × 220 مم)"
            ],
            variable=self.var_paper_preset,
            command=self._on_paper_preset_changed,
            width=180,
            font=("Segoe UI", 11)
        )
        self.cmb_preset.pack(side="right")

        # Centering Options Box
        box_center = ctk.CTkFrame(card_paper, fg_color=("gray80", "gray25"), corner_radius=6)
        box_center.pack(fill="x", padx=10, pady=(6, 4))

        ctk.CTkLabel(box_center, text="🎯 خيارات التوسيط التلقائي:", font=("Segoe UI", 10, "bold"), anchor="e").pack(fill="x", padx=8, pady=(4, 2))

        row_chk_center = ctk.CTkFrame(box_center, fg_color="transparent")
        row_chk_center.pack(fill="x", padx=8, pady=(0, 4))

        self.chk_center_x = ctk.CTkCheckBox(
            row_chk_center,
            text="توسيط أفقي (يمين/يسار)",
            variable=self.var_center_x,
            command=self._on_centering_toggled,
            font=("Segoe UI", 10, "bold")
        )
        self.chk_center_x.pack(side="right", expand=True, anchor="e")

        self.chk_center_y = ctk.CTkCheckBox(
            row_chk_center,
            text="توسيط رأسي (أعلى/أسفل)",
            variable=self.var_center_y,
            command=self._on_centering_toggled,
            font=("Segoe UI", 10, "bold")
        )
        self.chk_center_y.pack(side="left", expand=True, anchor="w")

        # Directional Margins Control Box
        box_margins = ctk.CTkFrame(card_paper, fg_color=("gray80", "gray25"), corner_radius=6)
        box_margins.pack(fill="x", padx=10, pady=4)

        ctk.CTkLabel(
            box_margins,
            text="🛡️ مسافة الأمان من كل الاتجاهات (مم):",
            font=("Segoe UI", 10, "bold"),
            text_color=("#0284c7", "#38bdf8"),
            anchor="e"
        ).pack(fill="x", padx=8, pady=(4, 2))

        def _make_margin_row(parent, label_text, str_var, key):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=2)
            lbl = ctk.CTkLabel(row, text=label_text, font=("Segoe UI", 10), width=90, anchor="e")
            lbl.pack(side="right", padx=(2, 4))

            btn_p = ctk.CTkButton(row, text="+", width=22, height=22, font=("Segoe UI", 10, "bold"),
                                  command=lambda: self._nudge_margin(key, 1.0))
            btn_p.pack(side="left", padx=1)

            entry = ctk.CTkEntry(row, textvariable=str_var, width=44, height=22, font=("Segoe UI", 10), justify="center")
            entry.pack(side="left", padx=1)
            entry.bind("<Return>", lambda e: self._on_directional_margin_changed(key))
            entry.bind("<FocusOut>", lambda e: self._on_directional_margin_changed(key))

            btn_m = ctk.CTkButton(row, text="-", width=22, height=22, font=("Segoe UI", 10, "bold"),
                                  command=lambda: self._nudge_margin(key, -1.0))
            btn_m.pack(side="left", padx=1)
            return entry

        self.entry_margin_left = _make_margin_row(box_margins, "⬅️ يسار (Left):", self.var_margin_left, "left")
        self.entry_margin_right = _make_margin_row(box_margins, "➡️ يمين (Right):", self.var_margin_right, "right")
        self.entry_margin_bottom = _make_margin_row(box_margins, "⬇️ أسفل (Bottom):", self.var_margin_bottom, "bottom")
        self.entry_margin_top = _make_margin_row(box_margins, "⬆️ أعلى (Top):", self.var_margin_top, "top")

        # Quick safety presets row
        row_quick = ctk.CTkFrame(card_paper, fg_color="transparent")
        row_quick.pack(fill="x", padx=10, pady=(4, 2))

        btn_q15 = ctk.CTkButton(row_quick, text="15 مم", width=46, height=24, font=("Segoe UI", 9, "bold"),
                                fg_color="#334155", hover_color="#1e293b", command=lambda: self.set_all_margins(15.0))
        btn_q15.pack(side="right", padx=1)

        btn_q20 = ctk.CTkButton(row_quick, text="20 مم", width=46, height=24, font=("Segoe UI", 9, "bold"),
                                fg_color="#334155", hover_color="#1e293b", command=lambda: self.set_all_margins(20.0))
        btn_q20.pack(side="right", padx=1)

        btn_q25 = ctk.CTkButton(row_quick, text="25 مم", width=46, height=24, font=("Segoe UI", 9, "bold"),
                                fg_color="#334155", hover_color="#1e293b", command=lambda: self.set_all_margins(25.0))
        btn_q25.pack(side="right", padx=1)

        btn_center_both = ctk.CTkButton(row_quick, text="🎯 توسيط الكل", height=24, font=("Segoe UI", 9, "bold"),
                                        fg_color="#0284c7", hover_color="#0369a1", command=self.center_both_axes)
        btn_center_both.pack(side="left", fill="x", expand=True, padx=1)

        # Fit to Paper Button (Within Safe Margins)
        btn_fit = ctk.CTkButton(
            card_paper,
            text="📐 ملاءمة تلقائية للورقة مع مسافات الأمان",
            command=self.fit_model_to_paper_action,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=("Segoe UI", 11, "bold"),
            height=30
        )
        btn_fit.pack(fill="x", padx=10, pady=(6, 4))

        # Corner Registration Crosses (+) Toggle
        self.chk_corner_crosses = ctk.CTkCheckBox(
            card_paper,
            text="➕ رسم علامات الزاوية (+) للمعايرة قبل البدء",
            variable=self.var_corner_crosses,
            command=self._on_corner_crosses_toggled,
            font=("Segoe UI", 10, "bold"),
            text_color=("#0284c7", "#38bdf8")
        )
        self.chk_corner_crosses.pack(fill="x", padx=10, pady=(2, 8))

        # ----------------- CARD 2: Infill & Visual Options -----------------
        card_view = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        card_view.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            card_view,
            text="🔷 نمط التعبئة (Infill) والعرض",
            font=("Segoe UI", 12, "bold"),
            anchor="e"
        ).pack(fill="x", padx=10, pady=(8, 4))

        # Infill Pattern Dropdown (10 rich patterns)
        row_infill = ctk.CTkFrame(card_view, fg_color="transparent")
        row_infill.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(row_infill, text="شكل الـ Infill:", font=("Segoe UI", 11, "bold")).pack(side="left")
        self.cmb_infill_pat = ctk.CTkComboBox(
            row_infill,
            values=[
                "Cubic",
                "Grid",
                "Lines",
                "Concentric",
                "Crosshatch",
                "Zigzag",
                "Honeycomb",
                "Spiral",
                "Waves",
                "Dots"
            ],
            variable=self.var_infill_pattern,
            command=self._on_infill_pattern_changed,
            width=150,
            font=("Segoe UI", 11)
        )
        self.cmb_infill_pat.pack(side="right")

        # Toggles
        chk_width = ctk.CTkCheckBox(
            card_view,
            text="عرض السمك الحقيقي للخط (Physical Width)",
            variable=self.var_show_physical_width,
            command=self.redraw,
            font=("Segoe UI", 11, "bold"),
            text_color="#38bdf8"
        )
        chk_width.pack(anchor="e", padx=10, pady=4)

        chk_walls = ctk.CTkCheckBox(
            card_view,
            text="خطوط الجدران والحدود (Walls)",
            variable=self.var_show_walls,
            command=self.redraw,
            font=("Segoe UI", 11)
        )
        chk_walls.pack(anchor="e", padx=10, pady=3)

        chk_infill = ctk.CTkCheckBox(
            card_view,
            text="خطوط التعبئة الداخلية (Infill)",
            variable=self.var_show_infill,
            command=self.redraw,
            font=("Segoe UI", 11)
        )
        chk_infill.pack(anchor="e", padx=10, pady=3)

        chk_travels = ctk.CTkCheckBox(
            card_view,
            text="مسارات الانتقال ورفع القلم (Travel / Z-Hop)",
            variable=self.var_show_travels,
            command=self.redraw,
            font=("Segoe UI", 11)
        )
        chk_travels.pack(anchor="e", padx=10, pady=3)

        chk_grid = ctk.CTkCheckBox(
            card_view,
            text="مسطرة وشبكة المليمتر (mm Grid)",
            variable=self.var_show_grid,
            command=self.redraw,
            font=("Segoe UI", 11)
        )
        chk_grid.pack(anchor="e", padx=10, pady=(3, 8))

        # ----------------- CARD 3: Multi-Pen Color Layers -----------------
        self.card_colors = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        self.card_colors.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            self.card_colors,
            text="🎨 طبقات الألوان وتبديل الأقلام",
            font=("Segoe UI", 12, "bold"),
            anchor="e"
        ).pack(fill="x", padx=10, pady=(8, 4))

        self.color_layers_container = ctk.CTkFrame(self.card_colors, fg_color="transparent")
        self.color_layers_container.pack(fill="x", padx=8, pady=(0, 6))

        self.lbl_no_colors = ctk.CTkLabel(
            self.color_layers_container,
            text="قلم واحد (#000000 أسود)",
            font=("Segoe UI", 10),
            text_color="#94a3b8"
        )
        self.lbl_no_colors.pack(fill="x", padx=6, pady=4)

        # ----------------- CARD 4: Simulation & Step Control -----------------
        card_sim = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        card_sim.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            card_sim,
            text="🎮 محاكاة مسار الرسم وتبديل القلم",
            font=("Segoe UI", 12, "bold"),
            anchor="e"
        ).pack(fill="x", padx=10, pady=(8, 2))

        self.lbl_sim_status = ctk.CTkLabel(
            card_sim,
            text="جاهز للمحاكاة (100% مكتمل)",
            font=("Segoe UI", 10),
            text_color="#94a3b8",
            anchor="e"
        )
        self.lbl_sim_status.pack(fill="x", padx=10, pady=(0, 4))

        # Slider
        self.slider_sim = ctk.CTkSlider(
            card_sim,
            from_=0,
            to=100,
            variable=self.var_sim_progress,
            command=self._on_slider_changed
        )
        self.slider_sim.pack(fill="x", padx=10, pady=4)

        # Simulation Buttons
        row_sim_btn = ctk.CTkFrame(card_sim, fg_color="transparent")
        row_sim_btn.pack(fill="x", padx=10, pady=(4, 8))

        self.btn_play = ctk.CTkButton(
            row_sim_btn,
            text="▶️ تشغيل",
            command=self.toggle_simulation,
            fg_color="#10b981",
            hover_color="#059669",
            width=75,
            height=28,
            font=("Segoe UI", 11, "bold")
        )
        self.btn_play.pack(side="left", padx=2)

        btn_reset = ctk.CTkButton(
            row_sim_btn,
            text="⏮️ من البداية",
            command=self.reset_simulation,
            fg_color="#475569",
            hover_color="#334155",
            width=80,
            height=28,
            font=("Segoe UI", 10)
        )
        btn_reset.pack(side="left", padx=2)

        btn_end = ctk.CTkButton(
            row_sim_btn,
            text="⏭️ كاملة",
            command=self.finish_simulation,
            fg_color="#475569",
            hover_color="#334155",
            width=65,
            height=28,
            font=("Segoe UI", 10)
        )
        btn_end.pack(side="left", padx=2)

        # Speed Selector
        row_spd = ctk.CTkFrame(card_sim, fg_color="transparent")
        row_spd.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(row_spd, text="السرعة:", font=("Segoe UI", 10)).pack(side="left")
        for spd_val in [1, 2, 5, 10]:
            btn_s = ctk.CTkButton(
                row_spd,
                text=f"{spd_val}x",
                width=32,
                height=22,
                font=("Segoe UI", 9),
                fg_color="#334155" if spd_val != 1 else "#2563eb",
                command=lambda s=spd_val: self.set_sim_speed(s)
            )
            btn_s.pack(side="left", padx=2)

        # ----------------- CARD 5: Slicing & Fit Statistics -----------------
        self.card_stats = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        self.card_stats.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(
            self.card_stats,
            text="📊 معلومات السلايس ومطابقة A5",
            font=("Segoe UI", 12, "bold"),
            anchor="e"
        ).pack(fill="x", padx=10, pady=(8, 4))

        self.lbl_fit_badge = ctk.CTkLabel(
            self.card_stats,
            text="⚪ لم يتم السلايس بعد",
            font=("Segoe UI", 11, "bold"),
            text_color="#94a3b8",
            anchor="e"
        )
        self.lbl_fit_badge.pack(fill="x", padx=10, pady=2)

        self.lbl_stats_details = ctk.CTkLabel(
            self.card_stats,
            text="• أبعاد الورقة: 210.0 × 148.0 مم\n• أبعاد الرسمة: -\n• عرض الخط: -\n• نمط التعبئة: -\n• زمن الرسم المقدر: -",
            font=("Segoe UI", 10),
            justify="right",
            anchor="e"
        )
        self.lbl_stats_details.pack(fill="x", padx=10, pady=(2, 8))

        # ----------------- CARD 6: Action Buttons -----------------
        card_act = ctk.CTkFrame(left_panel, fg_color="transparent")
        card_act.pack(fill="x", padx=10, pady=(6, 15))

        btn_send_printer = ctk.CTkButton(
            card_act,
            text="🚀 إرسال إلى الطابعة للبدء فوراً",
            command=self.send_to_printer_action,
            fg_color="#107c41",
            hover_color="#0b5c30",
            height=38,
            font=("Segoe UI", 13, "bold")
        )
        btn_send_printer.pack(fill="x", pady=4)

        btn_reslice = ctk.CTkButton(
            card_act,
            text="🔄 إعادة التقطيع وتحديث المسارات",
            command=self.request_reslice_action,
            fg_color="#2b7de9",
            hover_color="#1a64ca",
            height=32,
            font=("Segoe UI", 11, "bold")
        )
        btn_reslice.pack(fill="x", pady=4)

        btn_save_gcode = ctk.CTkButton(
            card_act,
            text="💾 حفظ ملف G-Code",
            command=self.save_gcode_action,
            fg_color="#475569",
            hover_color="#334155",
            height=30,
            font=("Segoe UI", 11)
        )
        btn_save_gcode.pack(fill="x", pady=4)

        row_proj_act = ctk.CTkFrame(card_act, fg_color="transparent")
        row_proj_act.pack(fill="x", pady=4)

        btn_save_proj = ctk.CTkButton(
            row_proj_act,
            text="💾 حفظ الرسمة بالألوان",
            command=self.save_project_action,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            height=30,
            font=("Segoe UI", 10, "bold")
        )
        btn_save_proj.pack(side="right", fill="x", expand=True, padx=2)

        btn_open_proj = ctk.CTkButton(
            row_proj_act,
            text="📂 فتح رسمة بالألوان",
            command=self.open_project_action,
            fg_color="#6366f1",
            hover_color="#4f46e5",
            height=30,
            font=("Segoe UI", 10, "bold")
        )
        btn_open_proj.pack(side="left", fill="x", expand=True, padx=2)

        # =========================================================================
        # RIGHT AREA: Interactive Canvas + Toolbar + Status Bar
        # =========================================================================
        right_container = ctk.CTkFrame(self, fg_color="transparent")
        right_container.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        right_container.grid_columnconfigure(0, weight=1)
        right_container.grid_rowconfigure(2, weight=1)

        # 1. Top Canvas Navigation Toolbar
        toolbar = ctk.CTkFrame(right_container, height=36, fg_color=("gray90", "gray17"), corner_radius=6)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        btn_fit_view = ctk.CTkButton(
            toolbar,
            text="🔍 ملاءمة الورقة",
            width=90,
            height=26,
            font=("Segoe UI", 10),
            command=self.fit_view
        )
        btn_fit_view.pack(side="right", padx=6, pady=4)

        btn_zoom_in = ctk.CTkButton(
            toolbar,
            text="➕ تكبير",
            width=60,
            height=26,
            font=("Segoe UI", 10),
            command=lambda: self.zoom_by(1.25)
        )
        btn_zoom_in.pack(side="right", padx=2, pady=4)

        btn_zoom_out = ctk.CTkButton(
            toolbar,
            text="➖ تصغير",
            width=60,
            height=26,
            font=("Segoe UI", 10),
            command=lambda: self.zoom_by(0.8)
        )
        btn_zoom_out.pack(side="right", padx=2, pady=4)

        btn_zoom_100 = ctk.CTkButton(
            toolbar,
            text="1:1 الحجم الفعلي",
            width=85,
            height=26,
            font=("Segoe UI", 10),
            command=self.zoom_100
        )
        btn_zoom_100.pack(side="right", padx=2, pady=4)

        self.lbl_coord = ctk.CTkLabel(
            toolbar,
            text="X: 0.0 mm | Y: 0.0 mm | التكبير: 100%",
            font=("Consolas", 11),
            text_color="#38bdf8"
        )
        self.lbl_coord.pack(side="left", padx=12, pady=4)

        # 2. Interactive Multi-Color Studio Toolbar (Paint Bucket & Line Brush)
        self.coloring_toolbar = ctk.CTkFrame(right_container, height=38, fg_color=("gray90", "gray17"), corner_radius=6)
        self.coloring_toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        self.seg_mode = ctk.CTkSegmentedButton(
            self.coloring_toolbar,
            values=["🔍 معاينة وتنقل", "🎨 تلوين الطبقات والأقلام"],
            command=self._on_mode_toggled,
            font=("Segoe UI", 10, "bold"),
            height=26
        )
        self.seg_mode.set("🔍 معاينة وتنقل")
        self.seg_mode.pack(side="right", padx=6, pady=4)

        # Paint controls container
        self.paint_controls_frame = ctk.CTkFrame(self.coloring_toolbar, fg_color="transparent")

        # Tool selector: Fill vs Line Brush
        self.seg_tool = ctk.CTkSegmentedButton(
            self.paint_controls_frame,
            values=["🪣 سطل المساحات", "🖌️ فرشاة الخطوط"],
            command=self._on_paint_tool_changed,
            font=("Segoe UI", 10),
            height=24
        )
        self.seg_tool.set("🪣 سطل المساحات")
        self.seg_tool.pack(side="right", padx=4)

        # Palette colors
        palette_colors = [
            ("#000000", "أسود"),
            ("#EF4444", "أحمر"),
            ("#3B82F6", "أزرق"),
            ("#10B981", "أخضر"),
            ("#F59E0B", "أصفر"),
            ("#8B5CF6", "بنفسجي"),
            ("#F97316", "برتقالي"),
            ("#78350F", "بني")
        ]

        self.swatch_buttons = []
        for hex_col, name in palette_colors:
            btn = tk.Button(
                self.paint_controls_frame,
                bg=hex_col,
                width=2,
                height=1,
                relief="solid" if hex_col == self.active_paint_color else "groove",
                bd=2 if hex_col == self.active_paint_color else 1,
                cursor="hand2",
                command=lambda h=hex_col: self.set_paint_color(h)
            )
            btn.pack(side="right", padx=1, pady=4)
            self.swatch_buttons.append((btn, hex_col))

        btn_pick = ctk.CTkButton(
            self.paint_controls_frame,
            text="➕ مخصص",
            width=58,
            height=24,
            font=("Segoe UI", 10),
            command=self._pick_custom_color
        )
        btn_pick.pack(side="right", padx=3)

        self.lbl_active_color = ctk.CTkLabel(
            self.paint_controls_frame,
            text="اللون النشط: أحمر",
            font=("Segoe UI", 10, "bold"),
            text_color=self.active_paint_color
        )
        self.lbl_active_color.pack(side="left", padx=8)

        self.btn_undo_color = ctk.CTkButton(
            self.paint_controls_frame,
            text="↩️ تراجع",
            width=60,
            height=24,
            font=("Segoe UI", 10),
            fg_color="#64748b",
            hover_color="#475569",
            command=self.undo_recolor
        )
        self.btn_undo_color.pack(side="left", padx=2)

        # 3. Main Interactive Tkinter Canvas
        self.canvas = tk.Canvas(
            right_container,
            bg="#13141a",
            highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.grid(row=2, column=0, sticky="nsew")

        # Canvas Event Bindings
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonPress-2>", self._on_mouse_down)
        self.canvas.bind("<B2-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonPress-3>", self._on_mouse_down)
        self.canvas.bind("<B3-Motion>", self._on_mouse_drag)
        self.canvas.bind("<Motion>", self._on_mouse_motion)

        # 4. Bottom Quick Legend Bar
        legend_bar = ctk.CTkFrame(right_container, height=28, fg_color="transparent")
        legend_bar.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        legend_text = (
            "💡 البريفيو بالألوان الحقيقية | اسحب للتحريك | عجلة الماوس للتقريب | "
            "تبديل القلم عند (0, 0) مع رفع Z-Hop لحماية الورقة"
        )
        ctk.CTkLabel(
            legend_bar,
            text=legend_text,
            font=("Segoe UI", 10),
            text_color="#94a3b8"
        ).pack(side="left", padx=6)

    # =========================================================================
    # EVENT HANDLERS & PRESETS
    # =========================================================================
    def _on_paper_preset_changed(self, choice: str):
        if "A5 بالعرض" in choice:
            self.paper_w_mm = 210.0
            self.paper_h_mm = 148.0
        elif "A5 بالطول" in choice:
            self.paper_w_mm = 148.0
            self.paper_h_mm = 210.0
        elif "A4 بالعرض" in choice:
            self.paper_w_mm = 297.0
            self.paper_h_mm = 210.0
        elif "A4 بالطول" in choice:
            self.paper_w_mm = 210.0
            self.paper_h_mm = 297.0
        elif "سرير الطابعة" in choice:
            self.paper_w_mm = 220.0
            self.paper_h_mm = 220.0

        self.fit_view()
        self._update_fit_evaluation()
        self.redraw()

    def _on_centering_toggled(self):
        """Called when horizontal or vertical centering checkbox is toggled."""
        self._update_fit_evaluation()
        self.redraw()
        if self.on_request_slice:
            self.on_request_slice()

    def _on_corner_crosses_toggled(self):
        """Called when corner crosses (+) toggle changes."""
        if self.on_request_slice:
            self.on_request_slice()

    def _on_directional_margin_changed(self, key: str):
        """Validates and updates directional margin from Entry inputs."""
        try:
            if key == "left":
                val = max(0.0, float(self.var_margin_left.get()))
                self.margin_left_mm = val
                if self.var_center_x.get():
                    self.margin_right_mm = val
                    self.var_margin_right.set(f"{val:.0f}")
            elif key == "right":
                val = max(0.0, float(self.var_margin_right.get()))
                self.margin_right_mm = val
                if self.var_center_x.get():
                    self.margin_left_mm = val
                    self.var_margin_left.set(f"{val:.0f}")
            elif key == "bottom":
                val = max(0.0, float(self.var_margin_bottom.get()))
                self.margin_bottom_mm = val
                if self.var_center_y.get():
                    self.margin_top_mm = val
                    self.var_margin_top.set(f"{val:.0f}")
            elif key == "top":
                val = max(0.0, float(self.var_margin_top.get()))
                self.margin_top_mm = val
                if self.var_center_y.get():
                    self.margin_bottom_mm = val
                    self.var_margin_bottom.set(f"{val:.0f}")

            self.paper_margin_mm = self.margin_left_mm
            self._update_fit_evaluation()
            self.redraw()
            if self.on_request_slice:
                self.on_request_slice()
        except ValueError:
            self.var_margin_left.set(f"{self.margin_left_mm:.0f}")
            self.var_margin_right.set(f"{self.margin_right_mm:.0f}")
            self.var_margin_bottom.set(f"{self.margin_bottom_mm:.0f}")
            self.var_margin_top.set(f"{self.margin_top_mm:.0f}")

    def _nudge_margin(self, key: str, delta: float):
        """Increments or decrements a margin by delta millimeters."""
        if key == "left":
            self.margin_left_mm = max(0.0, self.margin_left_mm + delta)
            self.var_margin_left.set(f"{self.margin_left_mm:.0f}")
            if self.var_center_x.get():
                self.margin_right_mm = self.margin_left_mm
                self.var_margin_right.set(f"{self.margin_right_mm:.0f}")
        elif key == "right":
            self.margin_right_mm = max(0.0, self.margin_right_mm + delta)
            self.var_margin_right.set(f"{self.margin_right_mm:.0f}")
            if self.var_center_x.get():
                self.margin_left_mm = self.margin_right_mm
                self.var_margin_left.set(f"{self.margin_left_mm:.0f}")
        elif key == "bottom":
            self.margin_bottom_mm = max(0.0, self.margin_bottom_mm + delta)
            self.var_margin_bottom.set(f"{self.margin_bottom_mm:.0f}")
            if self.var_center_y.get():
                self.margin_top_mm = self.margin_bottom_mm
                self.var_margin_top.set(f"{self.margin_top_mm:.0f}")
        elif key == "top":
            self.margin_top_mm = max(0.0, self.margin_top_mm + delta)
            self.var_margin_top.set(f"{self.margin_top_mm:.0f}")
            if self.var_center_y.get():
                self.margin_bottom_mm = self.margin_top_mm
                self.var_margin_bottom.set(f"{self.margin_bottom_mm:.0f}")

        self.paper_margin_mm = self.margin_left_mm
        self._update_fit_evaluation()
        self.redraw()
        if self.on_request_slice:
            self.on_request_slice()

    def set_all_margins(self, val: float):
        """Sets all 4 directional margins to the given millimeter value."""
        self.margin_left_mm = val
        self.margin_right_mm = val
        self.margin_bottom_mm = val
        self.margin_top_mm = val
        self.paper_margin_mm = val
        self.var_margin_left.set(f"{val:.0f}")
        self.var_margin_right.set(f"{val:.0f}")
        self.var_margin_bottom.set(f"{val:.0f}")
        self.var_margin_top.set(f"{val:.0f}")
        self._update_fit_evaluation()
        self.redraw()
        if self.on_request_slice:
            self.on_request_slice()

    def center_both_axes(self):
        """Enables both horizontal and vertical centering."""
        self.var_center_x.set(True)
        self.var_center_y.set(True)
        self._update_fit_evaluation()
        self.redraw()
        if self.on_request_slice:
            self.on_request_slice()

    def _on_placement_changed(self, choice: str):
        if self.on_request_slice:
            self.on_request_slice()

    def _on_margin_changed(self):
        self._on_directional_margin_changed("left")

    def _on_infill_pattern_changed(self, choice: str):
        if self.on_infill_changed:
            self.on_infill_changed(choice)
        elif self.on_request_slice:
            self.on_request_slice()

    def get_paper_config(self) -> Dict[str, Any]:
        """Returns the paper configuration, directional margins, and infill pattern."""
        center_x = self.var_center_x.get()
        center_y = self.var_center_y.get()

        return {
            "paper_type": "A5_landscape" if (self.paper_w_mm == 210.0 and self.paper_h_mm == 148.0) else "custom",
            "paper_width_mm": self.paper_w_mm,
            "paper_height_mm": self.paper_h_mm,
            "paper_preset": self.var_paper_preset.get(),
            "paper_placement": "directional",
            "paper_margin_mm": self.margin_left_mm,
            "margin_left_mm": self.margin_left_mm,
            "margin_right_mm": self.margin_right_mm,
            "margin_bottom_mm": self.margin_bottom_mm,
            "margin_top_mm": self.margin_top_mm,
            "center_horizontally": center_x,
            "center_vertically": center_y,
            "center_on_a5": (center_x and center_y),
            "enable_corner_crosses": self.var_corner_crosses.get(),
            "infill_pattern": self.var_infill_pattern.get()
        }

    def load_paper_config(self, cfg: Dict[str, Any]):
        """Restores paper and directional margin configuration from project data."""
        if "paper_preset" in cfg:
            preset = cfg["paper_preset"]
            self.var_paper_preset.set(preset)
            self._on_paper_preset_changed(preset)

        if "margin_left_mm" in cfg:
            self.margin_left_mm = float(cfg["margin_left_mm"])
        elif "paper_margin_mm" in cfg:
            self.margin_left_mm = float(cfg["paper_margin_mm"])
        self.var_margin_left.set(f"{self.margin_left_mm:.0f}")

        if "margin_right_mm" in cfg:
            self.margin_right_mm = float(cfg["margin_right_mm"])
        elif "paper_margin_mm" in cfg:
            self.margin_right_mm = float(cfg["paper_margin_mm"])
        self.var_margin_right.set(f"{self.margin_right_mm:.0f}")

        if "margin_bottom_mm" in cfg:
            self.margin_bottom_mm = float(cfg["margin_bottom_mm"])
        elif "paper_margin_mm" in cfg:
            self.margin_bottom_mm = float(cfg["paper_margin_mm"])
        self.var_margin_bottom.set(f"{self.margin_bottom_mm:.0f}")

        if "margin_top_mm" in cfg:
            self.margin_top_mm = float(cfg["margin_top_mm"])
        elif "paper_margin_mm" in cfg:
            self.margin_top_mm = float(cfg["paper_margin_mm"])
        self.var_margin_top.set(f"{self.margin_top_mm:.0f}")

        self.paper_margin_mm = self.margin_left_mm

        if "center_horizontally" in cfg:
            self.var_center_x.set(bool(cfg["center_horizontally"]))
        if "center_vertically" in cfg:
            self.var_center_y.set(bool(cfg["center_vertically"]))
        if "enable_corner_crosses" in cfg:
            self.var_corner_crosses.set(bool(cfg["enable_corner_crosses"]))

        self._update_fit_evaluation()
        self.redraw()

    # =========================================================================
    # DATA INGESTION & DISPLAY
    # =========================================================================
    def set_slice_result(self, result: Dict[str, Any], preserve_view: bool = False):
        """Sets the sliced toolpaths and metadata from SlicerEngine."""
        self.slice_data = result
        self.ordered_moves = result.get("ordered_moves", [])
        self.total_moves_count = len(self.ordered_moves)
        self.active_move_idx = self.total_moves_count

        # Extract all colors and populate color manager
        colors_summary = result.get("color_layers_summary", [])
        self.visible_colors = {item["hex"].upper() for item in colors_summary}
        # Default fallback
        if not self.visible_colors:
            self.visible_colors.add("#000000")

        self._rebuild_color_layers_ui(colors_summary)

        # Sync infill pattern if present in result
        if "infill_pattern" in result:
            self.var_infill_pattern.set(result["infill_pattern"])

        self.var_sim_progress.set(100.0)
        self.lbl_sim_status.configure(
            text=f"اكتمل السلايس: {self.total_moves_count:,} مسار حركة (100%)"
        )

        self._update_fit_evaluation()

        # FIX BUG: Preserve zoom level and panning position when coloring or adjusting!
        # NEVER zoom out automatically when the user is zoomed in coloring details!
        if not preserve_view and (self.pan_x == 0.0 and self.pan_y == 0.0):
            self.fit_view()
        self.redraw()

    def _rebuild_color_layers_ui(self, colors_summary: List[Dict[str, Any]]):
        """Builds interactive list of detected colors with visibility checkboxes."""
        for widget in self.color_layers_container.winfo_children():
            widget.destroy()

        if not colors_summary:
            lbl = ctk.CTkLabel(
                self.color_layers_container,
                text="قلم واحد (#000000 أسود)",
                font=("Segoe UI", 10),
                text_color="#94a3b8"
            )
            lbl.pack(fill="x", padx=6, pady=4)
            return

        for idx, item in enumerate(colors_summary):
            col_hex = item.get("hex", "#000000").upper()
            col_name = item.get("name", get_arabic_color_name(col_hex))
            drawn_m = item.get("drawn_meters", 0.0)

            row = ctk.CTkFrame(self.color_layers_container, fg_color=("gray90", "gray17"), corner_radius=6)
            row.pack(fill="x", pady=2)

            # Color swatch square
            swatch = tk.Label(row, bg=col_hex, width=2, height=1, relief="ridge")
            swatch.pack(side="left", padx=6, pady=4)

            # Details
            dist_str = f" | {drawn_m:.2f} م" if drawn_m > 0 else ""
            txt = f"قلم {idx + 1}: {col_name}{dist_str}"
            lbl_title = ctk.CTkLabel(row, text=txt, font=("Segoe UI", 10, "bold"), anchor="w")
            lbl_title.pack(side="left", fill="x", expand=True)

            # Visibility Checkbox
            var_vis = ctk.BooleanVar(value=True)

            def make_toggle(hex_code, v_var):
                def _toggle():
                    if v_var.get():
                        self.visible_colors.add(hex_code)
                    else:
                        self.visible_colors.discard(hex_code)
                    self.redraw()
                return _toggle

            chk_vis = ctk.CTkCheckBox(
                row,
                text="",
                width=24,
                variable=var_vis,
                command=make_toggle(col_hex, var_vis)
            )
            chk_vis.pack(side="right", padx=6)

    def load_external_gcode(self, gcode_text: str, filename: str = "External G-Code"):
        """Parses and loads external G-Code for multi-color visualization."""
        from core.slicer_engine import SlicerEngine
        parsed = SlicerEngine.parse_gcode_to_toolpaths(gcode_text)
        self.set_slice_result(parsed)

    def _update_fit_evaluation(self):
        """Checks if the sliced drawing fits inside the configured A5 paper."""
        if not self.slice_data:
            self.lbl_fit_badge.configure(
                text="⚪ لم يتم السلايس بعد",
                text_color="#94a3b8"
            )
            self.lbl_stats_details.configure(
                text=f"• أبعاد الورقة: {self.paper_w_mm:.1f} × {self.paper_h_mm:.1f} مم\n• في انتظار تحميل النموذج..."
            )
            return

        model_w = self.slice_data.get("model_w_mm", 0.0)
        model_h = self.slice_data.get("model_h_mm", 0.0)
        line_w = self.slice_data.get("line_width_mm", 0.4)
        wall_cnt = self.slice_data.get("wall_count", 2)
        infill_den = self.slice_data.get("infill_density", 20.0)
        infill_pat = self.slice_data.get("infill_pattern", self.var_infill_pattern.get())
        draw_dist_m = self.slice_data.get("print_distance_mm", 0.0) / 1000.0
        travel_dist_m = self.slice_data.get("travel_distance_mm", 0.0) / 1000.0
        est_time_s = self.slice_data.get("estimated_time_s", 0.0)
        colors_count = len(self.slice_data.get("color_layers_summary", []))

        mins = int(est_time_s // 60)
        secs = int(est_time_s % 60)
        time_str = f"{mins} دقيقة و {secs} ثانية" if mins > 0 else f"{secs} ثانية"

        safe_w = max(5.0, self.paper_w_mm - self.margin_left_mm - self.margin_right_mm)
        safe_h = max(5.0, self.paper_h_mm - self.margin_bottom_mm - self.margin_top_mm)

        cl_l = self.slice_data.get("clearance_left", 0.0)
        cl_r = self.slice_data.get("clearance_right", 0.0)
        cl_b = self.slice_data.get("clearance_bottom", 0.0)
        cl_t = self.slice_data.get("clearance_top", 0.0)

        fits_exact = (model_w <= self.paper_w_mm) and (model_h <= self.paper_h_mm)
        fits_safe = (model_w <= safe_w) and (model_h <= safe_h) and (cl_l >= self.margin_left_mm - 1.0) and (cl_b >= self.margin_bottom_mm - 1.0)

        if fits_safe:
            self.lbl_fit_badge.configure(
                text=f"🟢 ممتازة: داخل حدود الأمان ومبتعدة عن الحواف (يسار {cl_l:.0f} | يمين {cl_r:.0f} | أسفل {cl_b:.0f} | أعلى {cl_t:.0f} مم)",
                text_color="#10b981"
            )
        elif fits_exact:
            self.lbl_fit_badge.configure(
                text="🟡 تتسع داخل الورقة لكنها قريبة جداً من أحد الحواف",
                text_color="#f59e0b"
            )
        else:
            overflow_w = max(0.0, model_w - self.paper_w_mm)
            overflow_h = max(0.0, model_h - self.paper_h_mm)
            overflow_msg = []
            if overflow_w > 0:
                overflow_msg.append(f"العرض زائد {overflow_w:.1f}مم")
            if overflow_h > 0:
                overflow_msg.append(f"الارتفاع زائد {overflow_h:.1f}مم")
            self.lbl_fit_badge.configure(
                text=f"🔴 تنبيه: تتجاوز الورقة ({' | '.join(overflow_msg)})",
                text_color="#ef4444"
            )

        orientation_str = "بالعرض" if self.paper_w_mm >= self.paper_h_mm else "بالطول"
        details = (
            f"• الورقة: {self.paper_w_mm:.1f} × {self.paper_h_mm:.1f} مم ({orientation_str})\n"
            f"• أبعاد الرسمة: {model_w:.1f} × {model_h:.1f} مم\n"
            f"• هوامش الأمان المطلوبة: ⬅️ {self.margin_left_mm:.0f} | ➡️ {self.margin_right_mm:.0f} | ⬇️ {self.margin_bottom_mm:.0f} | ⬆️ {self.margin_top_mm:.0f} مم\n"
            f"• المسافة الفعلية عن الحواف: ⬅️ {cl_l:.1f} | ➡️ {cl_r:.1f} | ⬇️ {cl_b:.1f} | ⬆️ {cl_t:.1f} مم\n"
            f"• الألوان/الأقلام: {max(1, colors_count)} ألوان متباينة\n"
            f"• عرض الخط (Line Width): {line_w:.2f} مم\n"
            f"• الجدران: {wall_cnt} خطوط | التعبئة: {infill_den:.0f}% ({infill_pat})\n"
            f"• مسافة الرسم: {draw_dist_m:.2f} م | الانتقال: {travel_dist_m:.2f} م\n"
            f"• زمن الرسم المقدر: {time_str}"
        )
        self.lbl_stats_details.configure(text=details)

    # =========================================================================
    # VIEW NAVIGATION (Zoom & Pan)
    # =========================================================================
    def fit_view(self):
        """Fits the A5 paper neatly centered within the canvas area."""
        cw = max(100, self.canvas.winfo_width())
        ch = max(100, self.canvas.winfo_height())

        padding = 45
        avail_w = max(50, cw - 2 * padding)
        avail_h = max(50, ch - 2 * padding)

        self.base_scale = min(avail_w / self.paper_w_mm, avail_h / self.paper_h_mm)
        self.zoom = 1.0

        pixel_w = self.paper_w_mm * self.base_scale
        pixel_h = self.paper_h_mm * self.base_scale

        self.pan_x = (cw - pixel_w) / 2.0
        self.pan_y = (ch - pixel_h) / 2.0

        self._update_readout(0, 0)
        self.redraw()

    def zoom_by(self, factor: float):
        cw = self.canvas.winfo_width() / 2.0
        ch = self.canvas.winfo_height() / 2.0
        self._apply_zoom_at(cw, ch, factor)

    def zoom_100(self):
        approx_96dpi = 3.78
        if self.base_scale > 0:
            target_zoom = approx_96dpi / self.base_scale
            self.zoom = max(0.2, min(20.0, target_zoom))
            self.redraw()

    def _apply_zoom_at(self, cx: float, cy: float, factor: float):
        old_scale = self.base_scale * self.zoom
        new_zoom = max(0.15, min(25.0, self.zoom * factor))
        new_scale = self.base_scale * new_zoom

        self.pan_x = cx - (cx - self.pan_x) * (new_scale / old_scale)
        self.pan_y = cy - (cy - self.pan_y) * (new_scale / old_scale)
        self.zoom = new_zoom
        self.redraw()

    # =========================================================================
    # INTERACTIVE COLORING STUDIO ACTIONS
    # =========================================================================
    def _on_mode_toggled(self, mode_str: str):
        if "تلوين" in mode_str:
            self.active_mode = "paint"
            self.paint_controls_frame.pack(side="right", fill="x", expand=True, padx=4)
            self.canvas.config(cursor="pencil")
        else:
            self.active_mode = "pan"
            self.paint_controls_frame.pack_forget()
            self.canvas.config(cursor="crosshair")
        self.redraw()

    def _on_paint_tool_changed(self, tool_str: str):
        if "فرشاة" in tool_str:
            self.active_paint_tool = "line"
        else:
            self.active_paint_tool = "fill"

    def set_paint_color(self, hex_col: str):
        self.active_paint_color = hex_col.upper()
        col_name = get_arabic_color_name(self.active_paint_color)
        self.lbl_active_color.configure(
            text=f"اللون النشط: {col_name}",
            text_color=self.active_paint_color
        )
        for btn, h in self.swatch_buttons:
            if h.upper() == self.active_paint_color:
                btn.config(relief="solid", bd=2)
            else:
                btn.config(relief="groove", bd=1)

    def _pick_custom_color(self):
        from tkinter import colorchooser
        color_tuple = colorchooser.askcolor(
            color=self.active_paint_color,
            title="اختر لون القلم الجديد للتلوين المباشر"
        )
        if color_tuple and color_tuple[1]:
            self.set_paint_color(color_tuple[1])

    def recolor_at_pos(self, mm_x: float, mm_y: float):
        if not self.slice_data or "raw_color_layers" not in self.slice_data:
            return

        raw_layers = self.slice_data.get("raw_color_layers")
        if not raw_layers:
            return

        from core.slicer_engine import SlicerEngine
        offset_x = self.slice_data.get("offset_x", 0.0)
        offset_y = self.slice_data.get("offset_y", 0.0)

        undo_info = SlicerEngine.recolor_geometry_at(
            color_layers=raw_layers,
            click_x=mm_x,
            click_y=mm_y,
            offset_x=offset_x,
            offset_y=offset_y,
            new_hex=self.active_paint_color,
            max_dist_mm=3.5
        )

        if undo_info:
            self.color_undo_stack.append(undo_info)
            if hasattr(self, "lbl_fit_badge"):
                self.lbl_fit_badge.configure(
                    text="⚡ تم تلوين العنصر وتحديث كود الطباعة بالألوان الجديدة تلقائياً!",
                    text_color="#10b981"
                )
            if self.on_color_layers_updated:
                self.on_color_layers_updated(raw_layers)

    def undo_recolor(self):
        if not self.color_undo_stack:
            return
        last_action = self.color_undo_stack.pop()
        geom = last_action["geom"]
        gtype = last_action["type"]
        old_hex = last_action["old_hex"]
        new_hex = last_action["new_hex"]

        if not self.slice_data or "raw_color_layers" not in self.slice_data:
            return
        raw_layers = self.slice_data.get("raw_color_layers", {})

        # Remove from new_hex
        if new_hex in raw_layers:
            key = "polygons" if gtype == "polygon" else "lines"
            if geom in raw_layers[new_hex].get(key, []):
                raw_layers[new_hex][key].remove(geom)
            if not raw_layers[new_hex].get("polygons", []) and not raw_layers[new_hex].get("lines", []):
                raw_layers.pop(new_hex, None)

        # Restore to old_hex
        if old_hex not in raw_layers:
            raw_layers[old_hex] = {
                "hex": old_hex,
                "name": get_arabic_color_name(old_hex),
                "polygons": [],
                "lines": []
            }
        key = "polygons" if gtype == "polygon" else "lines"
        raw_layers[old_hex][key].append(geom)

        if hasattr(self, "lbl_fit_badge"):
            self.lbl_fit_badge.configure(
                text="↩️ تم التراجع وتحديث كود الطباعة بالألوان تلقائياً!",
                text_color="#f59e0b"
            )
        if self.on_color_layers_updated:
            self.on_color_layers_updated(raw_layers)

    def _on_mouse_wheel(self, event):
        factor = 1.15 if event.delta > 0 else (1.0 / 1.15)
        self._apply_zoom_at(event.x, event.y, factor)

    def _on_mouse_down(self, event):
        if self.active_mode == "paint" and event.num == 1:
            scale = self.base_scale * self.zoom
            if scale > 0:
                px0 = self.pan_x
                py1 = self.pan_y + self.paper_h_mm * scale
                mm_x = (event.x - px0) / scale
                mm_y = (py1 - event.y) / scale
                self.recolor_at_pos(mm_x, mm_y)
            return

        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def _on_mouse_drag(self, event):
        if self.active_mode == "paint" and (event.state & 0x0100):  # Button 1 dragged
            if self.active_paint_tool == "line":
                scale = self.base_scale * self.zoom
                if scale > 0:
                    px0 = self.pan_x
                    py1 = self.pan_y + self.paper_h_mm * scale
                    mm_x = (event.x - px0) / scale
                    mm_y = (py1 - event.y) / scale
                    self.recolor_at_pos(mm_x, mm_y)
            return

        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.pan_x += dx
        self.pan_y += dy
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.redraw()

    def _on_mouse_motion(self, event):
        scale = self.base_scale * self.zoom
        if scale <= 0:
            return
        px0 = self.pan_x
        py1 = self.pan_y + self.paper_h_mm * scale

        mm_x = (event.x - px0) / scale
        mm_y = (py1 - event.y) / scale
        self._update_readout(mm_x, mm_y)

    def _update_readout(self, mm_x: float, mm_y: float):
        zoom_pct = int(round(self.zoom * 100))
        self.lbl_coord.configure(
            text=f"X: {mm_x:.1f} mm | Y: {mm_y:.1f} mm | التكبير: {zoom_pct}%"
        )

    def _on_canvas_resize(self, event):
        if self.pan_x == 0.0 and self.pan_y == 0.0:
            self.fit_view()
        else:
            self.redraw()

    # =========================================================================
    # CANVAS DRAWING ENGINE (MULTI-COLOR)
    # =========================================================================
    def redraw(self):
        """Renders the A5 paper boundary, coordinate grid, and multi-color sliced toolpaths."""
        self.canvas.delete("all")

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 30 or ch < 30:
            return

        scale = self.base_scale * self.zoom
        if scale <= 0:
            return

        # Paper Sheet Coordinates on Canvas
        px0 = self.pan_x
        py0 = self.pan_y
        pw = self.paper_w_mm * scale
        ph = self.paper_h_mm * scale
        px1 = px0 + pw
        py1 = py0 + ph

        # 1. Subtle Paper Drop Shadow
        self.canvas.create_rectangle(
            px0 + 5, py0 + 5, px1 + 7, py1 + 7,
            fill="#090a0f", outline=""
        )

        # 2. Crisp White Paper Sheet Surface
        self.canvas.create_rectangle(
            px0, py0, px1, py1,
            fill="#ffffff", outline="#94a3b8", width=1.5
        )

        # 3. Safe Margin Guide Line (Dashed) with Directional Margins
        if self.var_show_margins.get():
            ml = self.margin_left_mm * scale
            mr = self.margin_right_mm * scale
            mb = self.margin_bottom_mm * scale
            mt = self.margin_top_mm * scale

            # Safe boundary rectangle
            self.canvas.create_rectangle(
                px0 + ml, py0 + mt, px1 - mr, py1 - mb,
                outline="#38bdf8", width=1.5, dash=(6, 4)
            )

            # Draw directional margin badges
            if scale >= 0.8:
                if self.margin_left_mm > 0:
                    self.canvas.create_text(
                        px0 + ml / 2.0, (py0 + py1) / 2.0,
                        text=f"{self.margin_left_mm:.0f}mm",
                        fill="#0284c7", font=("Segoe UI", 7, "bold")
                    )
                if self.margin_bottom_mm > 0:
                    self.canvas.create_text(
                        (px0 + px1) / 2.0, py1 - mb / 2.0,
                        text=f"⬇ {self.margin_bottom_mm:.0f}mm",
                        fill="#0284c7", font=("Segoe UI", 7, "bold")
                    )

        # 4. Millimeter Grid & Coordinate Rulers
        if self.var_show_grid.get():
            self._draw_grid_and_rulers(px0, py0, px1, py1, scale)

        # 5. Multi-Color Sliced Toolpaths (Walls, Infill, Travels)
        if self.slice_data and self.ordered_moves:
            self._draw_toolpaths(px0, py1, scale)

        # 6. Dimension Annotations around Paper
        self._draw_dimension_annotations(px0, py0, px1, py1)

        # 7. Coordinate Origin Indicator (0, 0)
        self._draw_origin_indicator(px0, py1, scale)

    def _draw_grid_and_rulers(self, px0, py0, px1, py1, scale):
        """Draws subtle 10mm grid lines and 50mm major markers on the paper."""
        for gx in range(10, int(self.paper_w_mm), 10):
            cx = px0 + gx * scale
            is_major = (gx % 50 == 0)
            col = "#e2e8f0" if not is_major else "#cbd5e1"
            w = 1 if not is_major else 1.2
            self.canvas.create_line(cx, py0, cx, py1, fill=col, width=w)

        for gy in range(10, int(self.paper_h_mm), 10):
            cy = py1 - gy * scale
            is_major = (gy % 50 == 0)
            col = "#e2e8f0" if not is_major else "#cbd5e1"
            w = 1 if not is_major else 1.2
            self.canvas.create_line(px0, cy, px1, cy, fill=col, width=w)

    def _draw_dimension_annotations(self, px0, py0, px1, py1):
        """Draws dimensions along the top and left of the paper."""
        orientation_str = "بالعرض" if self.paper_w_mm >= self.paper_h_mm else "بالطول"
        paper_name = "ورقة A5" if (int(self.paper_w_mm) in (148, 210) and int(self.paper_h_mm) in (148, 210)) else "الورقة"

        self.canvas.create_text(
            (px0 + px1) / 2.0, py0 - 14,
            text=f"◄──────── {paper_name} {orientation_str}: {self.paper_w_mm:.1f} مم ────────►",
            fill="#94a3b8",
            font=("Segoe UI", 10, "bold")
        )

        self.canvas.create_text(
            px0 - 14, (py0 + py1) / 2.0,
            text=f"{self.paper_h_mm:.1f} مم",
            fill="#94a3b8",
            font=("Segoe UI", 10, "bold"),
            angle=90
        )

    def _draw_origin_indicator(self, px0, py1, scale):
        """Draws the (0,0) corner origin with X and Y direction arrows."""
        axis_len = max(20, min(50, int(25 * scale)))
        # X axis (Red)
        self.canvas.create_line(
            px0, py1, px0 + axis_len, py1,
            fill="#ef4444", width=2.5, arrow=tk.LAST
        )
        self.canvas.create_text(
            px0 + axis_len + 8, py1,
            text="X", fill="#ef4444", font=("Segoe UI", 9, "bold")
        )

        # Y axis (Green)
        self.canvas.create_line(
            px0, py1, px0, py1 - axis_len,
            fill="#10b981", width=2.5, arrow=tk.LAST
        )
        self.canvas.create_text(
            px0, py1 - axis_len - 8,
            text="Y", fill="#10b981", font=("Segoe UI", 9, "bold")
        )

        # Origin calibration point (Pen Swap target at 0,0)
        self.canvas.create_oval(
            px0 - 4, py1 - 4, px0 + 4, py1 + 4,
            fill="#0ea5e9", outline="#ffffff", width=1.5
        )
        self.canvas.create_text(
            px0 + 12, py1 + 12,
            text="(0,0) نقطة ضبط القلم",
            fill="#0ea5e9",
            font=("Segoe UI", 8, "bold"),
            anchor="nw"
        )

    def _draw_toolpaths(self, px0: float, py1: float, scale: float):
        """Draws multi-color perimeter walls, infill, and pen swap points."""
        show_phys_width = self.var_show_physical_width.get()
        show_walls = self.var_show_walls.get()
        show_infill = self.var_show_infill.get()
        show_travels = self.var_show_travels.get()

        default_line_w = self.slice_data.get("line_width_mm", 0.4)
        last_drawn_pt = None
        current_pen_color = "#000000"

        limit = min(self.active_move_idx, len(self.ordered_moves))

        for idx in range(limit):
            move = self.ordered_moves[idx]
            mtype = move.get("type", "wall")

            # Handle Pen Swap / Tool Change event
            if mtype == "tool_change":
                new_col = move.get("color", "#EF4444")
                col_name = move.get("color_name", new_col)
                current_pen_color = new_col

                # Draw glowing pen swap marker at Origin (0,0)
                ox = px0
                oy = py1
                self.canvas.create_oval(
                    ox - 8, oy - 8, ox + 8, oy + 8,
                    fill="", outline=new_col, width=2.5
                )
                self.canvas.create_text(
                    ox + 10, oy - 14,
                    text=f"🎨 تبديل القلم إلى: {col_name}",
                    fill=new_col,
                    font=("Segoe UI", 9, "bold"),
                    anchor="w"
                )
                continue

            pts = move.get("points", [])
            if len(pts) < 2:
                continue

            # Color filter
            move_color = move.get("color", "#000000").upper()
            if self.visible_colors and move_color not in self.visible_colors and mtype != "travel":
                continue

            # Visibility toggles
            if mtype == "travel" and not show_travels:
                continue
            if mtype == "wall" and not show_walls:
                continue
            if mtype == "infill" and not show_infill:
                continue

            # Determine pixel stroke width
            move_w = move.get("width", default_line_w)
            stroke_px = max(1.0, move_w * scale) if show_phys_width else 1.0

            # Convert to canvas coordinates
            canvas_coords = []
            for (mx, my) in pts:
                cx = px0 + mx * scale
                cy = py1 - my * scale
                canvas_coords.extend([cx, cy])

            last_drawn_pt = (canvas_coords[-2], canvas_coords[-1])

            # Draw move with its real color
            if mtype == "travel":
                self.canvas.create_line(
                    canvas_coords,
                    fill="#f59e0b",
                    width=max(1.0, stroke_px * 0.7),
                    dash=(3, 3)
                )
            elif mtype == "infill":
                self.canvas.create_line(
                    canvas_coords,
                    fill=move_color,
                    width=stroke_px,
                    capstyle=tk.ROUND,
                    joinstyle=tk.ROUND
                )
            else:  # Wall
                self.canvas.create_line(
                    canvas_coords,
                    fill=move_color,
                    width=stroke_px,
                    capstyle=tk.ROUND,
                    joinstyle=tk.ROUND
                )

        # Draw Glowing Pen Cursor at Current Tip Position
        if last_drawn_pt and self.active_move_idx < self.total_moves_count:
            kx, ky = last_drawn_pt
            cursor_color = current_pen_color if current_pen_color else "#ef4444"
            self.canvas.create_oval(
                kx - 7, ky - 7, kx + 7, ky + 7,
                fill="", outline=cursor_color, width=2
            )
            self.canvas.create_oval(
                kx - 3, ky - 3, kx + 3, ky + 3,
                fill=cursor_color, outline="#ffffff", width=1
            )

    # =========================================================================
    # SIMULATION CONTROLS
    # =========================================================================
    def _on_slider_changed(self, value):
        if not self.total_moves_count:
            return
        target_idx = int((float(value) / 100.0) * self.total_moves_count)
        self.active_move_idx = max(0, min(self.total_moves_count, target_idx))
        pct = (self.active_move_idx / self.total_moves_count) * 100.0 if self.total_moves_count else 0
        self.lbl_sim_status.configure(
            text=f"المسار: {self.active_move_idx:,} من {self.total_moves_count:,} ({pct:.1f}%)"
        )
        self.redraw()

    def toggle_simulation(self):
        if self.sim_running:
            self.pause_simulation()
        else:
            self.start_simulation()

    def start_simulation(self):
        if not self.total_moves_count:
            return

        if self.active_move_idx >= self.total_moves_count:
            self.active_move_idx = 0

        self.sim_running = True
        self.btn_play.configure(text="⏸️ إيقاف مؤقت", fg_color="#ea580c", hover_color="#c2410c")
        self._sim_tick()

    def pause_simulation(self):
        self.sim_running = False
        if self.sim_timer:
            self.after_cancel(self.sim_timer)
            self.sim_timer = None
        self.btn_play.configure(text="▶️ تشغيل", fg_color="#10b981", hover_color="#059669")

    def reset_simulation(self):
        self.pause_simulation()
        self.active_move_idx = 0
        self.var_sim_progress.set(0.0)
        self.lbl_sim_status.configure(
            text=f"المسار: 0 من {self.total_moves_count:,} (0.0%)"
        )
        self.redraw()

    def finish_simulation(self):
        self.pause_simulation()
        self.active_move_idx = self.total_moves_count
        self.var_sim_progress.set(100.0)
        self.lbl_sim_status.configure(
            text=f"المسار: {self.total_moves_count:,} من {self.total_moves_count:,} (100.0%)"
        )
        self.redraw()

    def set_sim_speed(self, multiplier: int):
        self.sim_speed_multiplier = multiplier

    def _sim_tick(self):
        if not self.sim_running:
            return

        step = max(1, int(self.sim_speed_multiplier * 2))
        self.active_move_idx = min(self.total_moves_count, self.active_move_idx + step)

        pct = (self.active_move_idx / self.total_moves_count) * 100.0 if self.total_moves_count else 0
        self.var_sim_progress.set(pct)

        # Check if hitting a tool change
        if self.active_move_idx < self.total_moves_count:
            cur_move = self.ordered_moves[self.active_move_idx]
            if cur_move.get("type") == "tool_change":
                col_name = cur_move.get("color_name", cur_move.get("color", ""))
                self.lbl_sim_status.configure(
                    text=f"🎨 استبدال القلم المطلوب: {col_name} عند نقطة (0, 0)"
                )
            else:
                self.lbl_sim_status.configure(
                    text=f"جاري المحاكاة: {self.active_move_idx:,} / {self.total_moves_count:,} ({pct:.0f}%)"
                )
        else:
            self.lbl_sim_status.configure(
                text=f"اكتملت المحاكاة: {self.total_moves_count:,} مسار حركة (100%)"
            )

        self.redraw()

        if self.active_move_idx >= self.total_moves_count:
            self.pause_simulation()
        else:
            self.sim_timer = self.after(20, self._sim_tick)

    # =========================================================================
    # ACTIONS: FIT TO A5, SEND TO PRINTER, SAVE G-CODE
    # =========================================================================
    def fit_model_to_paper_action(self):
        """Automatically scales the design to comfortably fit inside the paper leaving directional safe margins."""
        if not self.slice_data or not self.on_fit_to_paper:
            messagebox.showinfo("تنبيه", "يرجى تحميل صورة أو ملف SVG أولاً لملائمته للورقة!")
            return

        model_w = self.slice_data.get("model_w_mm", 0.0)
        model_h = self.slice_data.get("model_h_mm", 0.0)
        if model_w <= 0.1 or model_h <= 0.1:
            return

        safe_w = max(10.0, self.paper_w_mm - self.margin_left_mm - self.margin_right_mm)
        safe_h = max(10.0, self.paper_h_mm - self.margin_bottom_mm - self.margin_top_mm)

        scale_factor = min(safe_w / model_w, safe_h / model_h)

        # Fix bug: if model is already comfortably fitted, DO NOT continuously shrink!
        if 0.985 <= scale_factor <= 1.015:
            messagebox.showinfo(
                "ملاءمة الورقة",
                f"النموذج ملائم تماماً داخل هوامش الأمان المحددة ومبتعد عن الحواف.\n"
                f"أبعاد الرسمة الحالية: {model_w:.1f} × {model_h:.1f} مم (لا يحتاج تصغير إضافي)."
            )
            return

        self.on_fit_to_paper(scale_factor)

    def request_reslice_action(self):
        if self.on_request_slice:
            self.on_request_slice()

    def send_to_printer_action(self):
        if not self.slice_data or not self.slice_data.get("gcode"):
            messagebox.showwarning("تنبيه", "لا يوجد كود G-Code جاهز! يرجى عمل سلايس للنموذج أولاً.")
            return

        if self.on_send_to_printer:
            self.on_send_to_printer(self.slice_data["gcode"])

    def save_gcode_action(self):
        if not self.slice_data or not self.slice_data.get("gcode"):
            messagebox.showwarning("تنبيه", "لا يوجد كود G-Code جاهز للتصدير!")
            return

        dest = filedialog.asksaveasfilename(
            title="حفظ كود الطباعة والرسم G-Code",
            defaultextension=".gcode",
            initialfile="plotter_drawing_multicolor_a5.gcode",
            filetypes=[("G-Code File", "*.gcode"), ("Text File", "*.txt"), ("All Files", "*.*")]
        )
        if dest:
            try:
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(self.slice_data["gcode"])
                messagebox.showinfo("تم الحفظ بنجاح", f"تم حفظ كود الـ G-Code في:\n{dest}")
            except Exception as e:
                messagebox.showerror("خطأ في الحفظ", f"تعذر حفظ الملف:\n{e}")

    def save_project_action(self):
        """Triggers project saving with all colors and paper settings."""
        if self.on_save_project:
            self.on_save_project()

    def open_project_action(self):
        """Triggers project opening to restore drawing and all colors."""
        if self.on_open_project:
            self.on_open_project()
