"""
Print & Slicing Settings Tab for Ender 3 Pro & Marlin.
Matches the user's Cura profile ('super quality ploting - Super Quality - 0.3mm')
with full customization for Quality, Walls, Infill, Speeds, Z-Hop, and Temperatures.
"""
import json
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox

class SettingsTab(ctk.CTkScrollableFrame):
    def __init__(self, master, on_settings_changed=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_settings_changed = on_settings_changed

        self._init_variables()
        self._build_ui()

    def _init_variables(self):
        # Quality
        self.var_layer_height = ctk.StringVar(value="0.3")
        self.var_init_layer_height = ctk.StringVar(value="0.3")
        self.var_line_width = ctk.StringVar(value="0.4")

        # Walls
        self.var_wall_thickness = ctk.StringVar(value="0.6")
        self.var_wall_count = ctk.StringVar(value="2")
        self.var_horizontal_exp = ctk.StringVar(value="0.0")

        # Top/Bottom
        self.var_top_bottom_thick = ctk.StringVar(value="2.1")
        self.var_top_layers = ctk.StringVar(value="7")
        self.var_bottom_layers = ctk.StringVar(value="7")

        # Infill
        self.var_infill_density = ctk.StringVar(value="20.0")
        self.var_infill_pattern = ctk.StringVar(value="Cubic")

        # Material & Temperatures
        self.var_print_temp = ctk.StringVar(value="0.0")
        self.var_bed_temp = ctk.StringVar(value="0.0")
        self.var_flow = ctk.StringVar(value="100.0")

        # Speed
        self.var_print_speed = ctk.StringVar(value="50.0")
        self.var_wall_speed = ctk.StringVar(value="25.0")
        self.var_infill_speed = ctk.StringVar(value="50.0")
        self.var_travel_speed = ctk.StringVar(value="150.0")
        self.var_init_layer_speed = ctk.StringVar(value="20.0")
        self.var_z_hop_speed = ctk.StringVar(value="5.0")

        # Travel & Retraction
        self.var_enable_retraction = ctk.BooleanVar(value=True)
        self.var_retract_dist = ctk.StringVar(value="6.5")
        self.var_retract_speed = ctk.StringVar(value="25.0")
        self.var_enable_z_hop = ctk.BooleanVar(value=True)
        self.var_z_hop_height = ctk.StringVar(value="1.5")

        # Cooling
        self.var_enable_fan = ctk.BooleanVar(value=False)
        self.var_fan_speed = ctk.StringVar(value="0")

        # Bed & Mode
        self.var_bed_x = ctk.StringVar(value="220.0")
        self.var_bed_y = ctk.StringVar(value="220.0")
        self.var_origin_mode = ctk.StringVar(value="custom_zero")  # "custom_zero" or "center"

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))

        title = ctk.CTkLabel(
            header,
            text="⚙️ إعدادات الطباعة والتقطيع (Cura Profile: super quality ploting)",
            font=("Segoe UI", 16, "bold"),
            anchor="e"
        )
        title.pack(side="right")

        desc = ctk.CTkLabel(
            self,
            text="تحكم كامل بجميع متغيرات التقطيع وسرعة وسلوك طابعة Ender 3 Pro مع خيار الرسم البارد بالقلم أو الطباعة بالبلاستيك.",
            font=("Segoe UI", 11),
            text_color="#94a3b8",
            anchor="e"
        )
        desc.pack(fill="x", padx=15, pady=(0, 15))

        # Two-column layout container
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10, pady=5)
        content.grid_columnconfigure((0, 1), weight=1)

        # LEFT COLUMN
        col_left = ctk.CTkFrame(content, fg_color="transparent")
        col_left.grid(row=0, column=0, sticky="nsew", padx=6)

        # RIGHT COLUMN
        col_right = ctk.CTkFrame(content, fg_color="transparent")
        col_right.grid(row=0, column=1, sticky="nsew", padx=6)

        # 1. Quality Card (Col Right)
        self._create_card(
            col_right,
            "📏 الجودة والطبقات (Quality)",
            [
                ("ارتفاع الطبقة (Layer Height mm):", self.var_layer_height),
                ("ارتفاع الطبقة الأولى (Initial Layer Height mm):", self.var_init_layer_height),
                ("عرض خط الرسم (Line Width mm):", self.var_line_width),
            ]
        )

        # 2. Walls Card (Col Right)
        self._create_card(
            col_right,
            "🧱 الجدران والحدود (Walls)",
            [
                ("سمك الجدار (Wall Thickness mm):", self.var_wall_thickness),
                ("عدد خطوط الجدار (Wall Line Count):", self.var_wall_count),
                ("التمدد الأفقي (Horizontal Expansion mm):", self.var_horizontal_exp),
            ]
        )

        # 3. Infill & Top/Bottom Card (Col Right)
        infill_frame = ctk.CTkFrame(col_right, fg_color=("gray85", "gray20"), corner_radius=8)
        infill_frame.pack(fill="x", pady=6)
        ctk.CTkLabel(infill_frame, text="🔷 التعبئة الداخلية والأسطح (Infill)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        self._add_row(infill_frame, "نسبة التعبئة (Infill Density %):", self.var_infill_density)
        
        # Infill Pattern dropdown
        row_pat = ctk.CTkFrame(infill_frame, fg_color="transparent")
        row_pat.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row_pat, text="نمط التعبئة (Infill Pattern):").pack(side="left")
        cmb_pat = ctk.CTkComboBox(
            row_pat,
            values=["Cubic", "Grid", "Lines", "Concentric", "Crosshatch", "Zigzag", "Honeycomb", "Spiral", "Waves", "Dots"],
            variable=self.var_infill_pattern,
            width=135
        )
        cmb_pat.pack(side="right")

        self._add_row(infill_frame, "سمك السطح/القاع (Thickness mm):", self.var_top_bottom_thick)
        self._add_row(infill_frame, "عدد طبقات السطح (Top Layers):", self.var_top_layers)
        self._add_row(infill_frame, "عدد طبقات القاع (Bottom Layers):", self.var_bottom_layers)
        ctk.CTkFrame(infill_frame, height=6, fg_color="transparent").pack()

        # 4. Speeds Card (Col Left)
        self._create_card(
            col_left,
            "⚡ السرعات (Speed mm/s)",
            [
                ("سرعة الطباعة/الرسم (Print Speed):", self.var_print_speed),
                ("سرعة رسم الجدران (Wall Speed):", self.var_wall_speed),
                ("سرعة رسم التعبئة (Infill Speed):", self.var_infill_speed),
                ("سرعة الانتقال السريع (Travel Speed):", self.var_travel_speed),
                ("سرعة الطبقة الأولى (Initial Layer Speed):", self.var_init_layer_speed),
                ("سرعة رفع المحور Z (Z-Hop Speed):", self.var_z_hop_speed),
            ]
        )

        # 5. Travel & Z-Hop Card (Col Left)
        travel_frame = ctk.CTkFrame(col_left, fg_color=("gray85", "gray20"), corner_radius=8)
        travel_frame.pack(fill="x", pady=6)
        ctk.CTkLabel(travel_frame, text="🪶 الانتقال ورفع القلم والسحب (Travel & Z-Hop)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        chk_zhop = ctk.CTkCheckBox(travel_frame, text="تفعيل رفع القلم عند الانتقال (Z Hop When Retracted)", variable=self.var_enable_z_hop)
        chk_zhop.pack(anchor="e", padx=12, pady=4)
        self._add_row(travel_frame, "ارتفاع رفع القلم (Z Hop Height mm):", self.var_z_hop_height)

        chk_ret = ctk.CTkCheckBox(travel_frame, text="تفعيل السحب (Enable Retraction)", variable=self.var_enable_retraction)
        chk_ret.pack(anchor="e", padx=12, pady=4)
        self._add_row(travel_frame, "مسافة السحب (Retraction Distance mm):", self.var_retract_dist)
        self._add_row(travel_frame, "سرعة السحب (Retraction Speed mm/s):", self.var_retract_speed)
        ctk.CTkFrame(travel_frame, height=6, fg_color="transparent").pack()

        # 6. Temperatures & Material (Col Left)
        temp_frame = ctk.CTkFrame(col_left, fg_color=("gray85", "gray20"), corner_radius=8)
        temp_frame.pack(fill="x", pady=6)
        ctk.CTkLabel(temp_frame, text="🔥 الحرارة وسرير الطباعة (Material & Bed)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        self._add_row(temp_frame, "حرارة الفوهة (Printing Temp °C):", self.var_print_temp)
        self._add_row(temp_frame, "حرارة السرير (Bed Temp °C):", self.var_bed_temp)
        self._add_row(temp_frame, "معدل التدفق (Flow %):", self.var_flow)

        note_temp = ctk.CTkLabel(
            temp_frame,
            text="💡 اترك الحرارة 0.0 للرسم البارد بالقلم، أو ضع 200°C للطباعة بالـ PLA.",
            font=("Segoe UI", 10),
            text_color="#38bdf8",
            anchor="e"
        )
        note_temp.pack(anchor="e", padx=12, pady=(0, 8))

        # 7. Coordinates & Origin Mode (Col Right)
        coord_frame = ctk.CTkFrame(col_right, fg_color=("gray85", "gray20"), corner_radius=8)
        coord_frame.pack(fill="x", pady=6)
        ctk.CTkLabel(coord_frame, text="🎯 أبعاد السرير ونقطة البداية (Origin & Bed)", font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        self._add_row(coord_frame, "عرض السرير X (Bed Width mm):", self.var_bed_x)
        self._add_row(coord_frame, "عمق السرير Y (Bed Height mm):", self.var_bed_y)

        # Origin radio buttons
        rad_zero = ctk.CTkRadioButton(
            coord_frame,
            text="الرسم بالنسبة لنقطة الصفر المحددة يدوياً (G92 X0 Y0)",
            variable=self.var_origin_mode,
            value="custom_zero"
        )
        rad_zero.pack(anchor="e", padx=12, pady=4)

        rad_center = ctk.CTkRadioButton(
            coord_frame,
            text="الرسم في منتصف سرير الطابعة تلقائياً (Center on Bed)",
            variable=self.var_origin_mode,
            value="center"
        )
        rad_center.pack(anchor="e", padx=12, pady=(0, 10))

        # Actions Footer
        act_frame = ctk.CTkFrame(self, fg_color="transparent")
        act_frame.pack(fill="x", padx=15, pady=20)

        btn_save = ctk.CTkButton(
            act_frame,
            text="💾 حفظ الإعدادات في ملف",
            command=self.save_preset_dialog,
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=34,
            font=("Segoe UI", 12, "bold")
        )
        btn_save.pack(side="left", padx=5)

        btn_load = ctk.CTkButton(
            act_frame,
            text="📂 استيراد إعدادات",
            command=self.load_preset_dialog,
            fg_color="#475569",
            hover_color="#334155",
            height=34,
            font=("Segoe UI", 12)
        )
        btn_load.pack(side="left", padx=5)

        btn_reset = ctk.CTkButton(
            act_frame,
            text="🔄 استعادة الإعدادات الافتراضية (Super Quality Plotting)",
            command=self.reset_to_default,
            fg_color="#334155",
            hover_color="#1e293b",
            height=34,
            font=("Segoe UI", 12)
        )
        btn_reset.pack(side="right", padx=5)

    def _create_card(self, parent, title, rows):
        frame = ctk.CTkFrame(parent, fg_color=("gray85", "gray20"), corner_radius=8)
        frame.pack(fill="x", pady=6)
        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 12, "bold")).pack(anchor="e", padx=12, pady=(10, 6))
        for label_text, var in rows:
            self._add_row(frame, label_text, var)
        ctk.CTkFrame(frame, height=6, fg_color="transparent").pack()
        return frame

    def _add_row(self, frame, label_text, var):
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        lbl = ctk.CTkLabel(row, text=label_text, font=("Segoe UI", 11))
        lbl.pack(side="left")
        ent = ctk.CTkEntry(row, textvariable=var, width=75, font=("Segoe UI", 11))
        ent.pack(side="right")
        ent.bind("<FocusOut>", lambda e: self._notify_change())
        ent.bind("<Return>", lambda e: self._notify_change())

    def _notify_change(self):
        if self.on_settings_changed:
            self.on_settings_changed(self.get_settings())

    def get_settings(self):
        def _get_f(v, default):
            try:
                return float(v.get())
            except Exception:
                return default

        def _get_i(v, default):
            try:
                return int(float(v.get()))
            except Exception:
                return default

        return {
            "layer_height": _get_f(self.var_layer_height, 0.3),
            "initial_layer_height": _get_f(self.var_init_layer_height, 0.3),
            "line_width": _get_f(self.var_line_width, 0.4),
            "wall_thickness": _get_f(self.var_wall_thickness, 0.6),
            "wall_line_count": _get_i(self.var_wall_count, 2),
            "horizontal_expansion": _get_f(self.var_horizontal_exp, 0.0),
            "top_bottom_thickness": _get_f(self.var_top_bottom_thick, 2.1),
            "top_layers": _get_i(self.var_top_layers, 7),
            "bottom_layers": _get_i(self.var_bottom_layers, 7),
            "infill_density": _get_f(self.var_infill_density, 20.0),
            "infill_pattern": self.var_infill_pattern.get(),
            "print_temp": _get_f(self.var_print_temp, 0.0),
            "bed_temp": _get_f(self.var_bed_temp, 0.0),
            "flow": _get_f(self.var_flow, 100.0),
            "print_speed": _get_f(self.var_print_speed, 50.0),
            "wall_speed": _get_f(self.var_wall_speed, 25.0),
            "infill_speed": _get_f(self.var_infill_speed, 50.0),
            "travel_speed": _get_f(self.var_travel_speed, 150.0),
            "initial_layer_speed": _get_f(self.var_init_layer_speed, 20.0),
            "z_hop_speed": _get_f(self.var_z_hop_speed, 5.0),
            "enable_retraction": self.var_enable_retraction.get(),
            "retraction_distance": _get_f(self.var_retract_dist, 6.5),
            "retraction_speed": _get_f(self.var_retract_speed, 25.0),
            "enable_z_hop": self.var_enable_z_hop.get(),
            "z_hop_height": _get_f(self.var_z_hop_height, 1.5),
            "enable_fan": self.var_enable_fan.get(),
            "fan_speed": _get_i(self.var_fan_speed, 0),
            "bed_size_x": _get_f(self.var_bed_x, 220.0),
            "bed_size_y": _get_f(self.var_bed_y, 220.0),
            "start_at_custom_origin": (self.var_origin_mode.get() == "custom_zero"),
            "center_on_bed": (self.var_origin_mode.get() == "center")
        }

    def reset_to_default(self):
        self.var_layer_height.set("0.3")
        self.var_init_layer_height.set("0.3")
        self.var_line_width.set("0.4")
        self.var_wall_thickness.set("0.6")
        self.var_wall_count.set("2")
        self.var_horizontal_exp.set("0.0")
        self.var_top_bottom_thick.set("2.1")
        self.var_top_layers.set("7")
        self.var_bottom_layers.set("7")
        self.var_infill_density.set("20.0")
        self.var_infill_pattern.set("Cubic")
        self.var_print_temp.set("0.0")
        self.var_bed_temp.set("0.0")
        self.var_flow.set("100.0")
        self.var_print_speed.set("50.0")
        self.var_wall_speed.set("25.0")
        self.var_infill_speed.set("50.0")
        self.var_travel_speed.set("150.0")
        self.var_init_layer_speed.set("20.0")
        self.var_z_hop_speed.set("5.0")
        self.var_enable_retraction.set(True)
        self.var_retract_dist.set("6.5")
        self.var_retract_speed.set("25.0")
        self.var_enable_z_hop.set(True)
        self.var_z_hop_height.set("1.5")
        self.var_enable_fan.set(False)
        self.var_fan_speed.set("0")
        self.var_bed_x.set("220.0")
        self.var_bed_y.set("220.0")
        self.var_origin_mode.set("custom_zero")
        self._notify_change()
        messagebox.showinfo("تمت الاستعادة", "تمت استعادة إعدادات الملف الافتراضي (super quality ploting) بنجاح!")

    def save_preset_dialog(self):
        dest = filedialog.asksaveasfilename(
            title="حفظ ملف إعدادات التقطيع",
            defaultextension=".json",
            initialfile="cura_plotter_profile.json",
            filetypes=[("JSON Settings", "*.json")]
        )
        if dest:
            try:
                data = self.get_settings()
                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo("تم الحفظ", f"تم حفظ ملف الإعدادات في:\n{dest}")
            except Exception as e:
                messagebox.showerror("خطأ", f"تعذر حفظ الملف:\n{e}")

    def load_preset_dialog(self):
        chosen = filedialog.askopenfilename(
            title="اختيار ملف إعدادات",
            filetypes=[("JSON Settings", "*.json")]
        )
        if chosen and os.path.isfile(chosen):
            try:
                with open(chosen, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    attr = f"var_{k}"
                    if hasattr(self, attr):
                        getattr(self, attr).set(str(v))
                self._notify_change()
                messagebox.showinfo("تم التحميل", f"تم استيراد الإعدادات بنجاح من:\n{os.path.basename(chosen)}")
            except Exception as e:
                messagebox.showerror("خطأ", f"تعذر قراءة ملف الإعدادات:\n{e}")
