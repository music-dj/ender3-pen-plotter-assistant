"""
Direct 3D Printer Connection & Control Tab for Ender 3 Pro (Marlin).
Provides USB serial connection, manual jogging, custom origin zeroing,
Z-Hop pen testing, instant slicing, G-Code streaming, and live Marlin terminal.
"""
import time
import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import Optional, Callable
from core.serial_printer import SerialPrinter

class PrinterTab(ctk.CTkFrame):
    def __init__(
        self,
        master,
        serial_printer: SerialPrinter,
        on_slice_request: Optional[Callable[[], Optional[str]]] = None,
        on_external_gcode_loaded: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.printer = serial_printer
        self.on_slice_request = on_slice_request
        self.on_external_gcode_loaded = on_external_gcode_loaded

        self.loaded_gcode: str = ""
        self.selected_step_mm = 10.0

        # Wire serial printer callbacks
        self.printer.on_log = self._handle_printer_log
        self.printer.on_progress = self._handle_printer_progress
        self.printer.on_status_change = self._handle_printer_status
        self.printer.on_print_finished = self._handle_printer_finished
        self.printer.on_tool_change_request = self._handle_tool_change_request

        self._build_ui()
        self.refresh_ports()

    def _build_ui(self):
        # 3 main columns/sections: Left (Terminal), Center (Print & Slicing), Right (Connection & Jog)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ------------------ RIGHT PANEL: Connection & Motion / Origin ------------------
        right_panel = ctk.CTkScrollableFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=10)

        # 1. Connection Card
        conn_card = ctk.CTkFrame(right_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        conn_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(conn_card, text="🔌 الاتصال بالطابعة عبر USB (Ender 3 Pro)", font=("Segoe UI", 13, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        # Port selection
        row_port = ctk.CTkFrame(conn_card, fg_color="transparent")
        row_port.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row_port, text="منفذ الـ COM:").pack(side="left")
        self.port_combo = ctk.CTkComboBox(row_port, values=["جارٍ البحث..."], width=170)
        self.port_combo.pack(side="left", padx=5)

        btn_refresh = ctk.CTkButton(row_port, text="🔄", width=32, command=self.refresh_ports)
        btn_refresh.pack(side="left")

        # Baudrate
        row_baud = ctk.CTkFrame(conn_card, fg_color="transparent")
        row_baud.pack(fill="x", padx=12, pady=3)
        ctk.CTkLabel(row_baud, text="السرعة (Baud):").pack(side="left")
        self.baud_combo = ctk.CTkComboBox(row_baud, values=["115200", "250000", "57600"], width=110)
        self.baud_combo.set("115200")
        self.baud_combo.pack(side="right")

        # Connect / Disconnect Buttons
        row_btn_conn = ctk.CTkFrame(conn_card, fg_color="transparent")
        row_btn_conn.pack(fill="x", padx=12, pady=(8, 10))

        self.btn_connect = ctk.CTkButton(
            row_btn_conn,
            text="اتصال بالطابعة 🔌",
            command=self.toggle_connection,
            fg_color="#107c41",
            hover_color="#0b5c30",
            font=("Segoe UI", 12, "bold"),
            height=34
        )
        self.btn_connect.pack(fill="x")

        self.lbl_status = ctk.CTkLabel(
            conn_card,
            text="⚪ الحالة: غير متصل",
            font=("Segoe UI", 11),
            text_color="#94a3b8"
        )
        self.lbl_status.pack(anchor="e", padx=12, pady=(0, 8))

        # 2. Origin & Jogging Card
        jog_card = ctk.CTkFrame(right_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        jog_card.pack(fill="x", pady=5)

        ctk.CTkLabel(jog_card, text="📍 تحديد نقطة البداية والتحكم اليدوي", font=("Segoe UI", 13, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        # Step size selector
        step_row = ctk.CTkFrame(jog_card, fg_color="transparent")
        step_row.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(step_row, text="مسافة الخطوة:").pack(side="left")
        self.step_var = ctk.StringVar(value="10mm")
        for st in ["0.1mm", "1mm", "10mm", "50mm"]:
            btn_st = ctk.CTkRadioButton(
                step_row,
                text=st,
                value=st,
                variable=self.step_var,
                command=self._on_step_changed,
                font=("Segoe UI", 10)
            )
            btn_st.pack(side="left", padx=3)

        # Jog Control Pad
        pad_frame = ctk.CTkFrame(jog_card, fg_color="transparent")
        pad_frame.pack(pady=8)

        # Row 1: Y+
        btn_yp = ctk.CTkButton(pad_frame, text="Y+ (خلف)", width=90, height=32, command=lambda: self.jog("Y", 1))
        btn_yp.grid(row=0, column=1, padx=4, pady=3)

        # Row 2: X- / Home / X+
        btn_xm = ctk.CTkButton(pad_frame, text="X- (يسار)", width=90, height=32, command=lambda: self.jog("X", -1))
        btn_xm.grid(row=1, column=0, padx=4, pady=3)

        btn_home_all = ctk.CTkButton(pad_frame, text="🏠 Home", width=75, height=32, fg_color="#475569", command=self.home_all)
        btn_home_all.grid(row=1, column=1, padx=4, pady=3)

        btn_xp = ctk.CTkButton(pad_frame, text="X+ (يمين)", width=90, height=32, command=lambda: self.jog("X", 1))
        btn_xp.grid(row=1, column=2, padx=4, pady=3)

        # Row 3: Y-
        btn_ym = ctk.CTkButton(pad_frame, text="Y- (أمام)", width=90, height=32, command=lambda: self.jog("Y", -1))
        btn_ym.grid(row=2, column=1, padx=4, pady=3)

        # Z Controls (Pen Up / Down)
        z_frame = ctk.CTkFrame(jog_card, fg_color="transparent")
        z_frame.pack(fill="x", padx=12, pady=6)

        btn_zp = ctk.CTkButton(z_frame, text="Z+ رفع القلم ⬆️", width=120, height=32, command=lambda: self.jog("Z", 1))
        btn_zp.pack(side="left", expand=True, padx=4)

        btn_zm = ctk.CTkButton(z_frame, text="Z- إنزال القلم ⬇️", width=120, height=32, command=lambda: self.jog("Z", -1))
        btn_zm.pack(side="right", expand=True, padx=4)

        # PROMINENT: Set Custom Origin (G92 X0 Y0)
        btn_set_origin = ctk.CTkButton(
            jog_card,
            text="🎯 تحديد هذه النقطة كنقطة بداية للرسم (G92 X0 Y0)",
            command=self.set_origin_here,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=("Segoe UI", 12, "bold"),
            height=36
        )
        btn_set_origin.pack(fill="x", padx=12, pady=(8, 4))

        btn_set_origin_z = ctk.CTkButton(
            jog_card,
            text="📍 تصفير كل المحاور بما فيها Z (G92 X0 Y0 Z0)",
            command=lambda: self.set_origin_here(include_z=True),
            fg_color="#334155",
            hover_color="#1e293b",
            font=("Segoe UI", 11),
            height=28
        )
        btn_set_origin_z.pack(fill="x", padx=12, pady=(0, 6))

        # Origin Memory Subcard: Save & Recall Starting Point
        card_origin_mem = ctk.CTkFrame(jog_card, fg_color=("gray80", "gray25"), corner_radius=6)
        card_origin_mem.pack(fill="x", padx=12, pady=(2, 6))

        ctk.CTkLabel(
            card_origin_mem,
            text="📍 ذاكرة نقطة البداية (حفظ واستدعاء):",
            font=("Segoe UI", 10, "bold"),
            text_color=("#0284c7", "#38bdf8"),
            anchor="e"
        ).pack(fill="x", padx=8, pady=(4, 2))

        from core.origin_manager import OriginManager
        init_origin = OriginManager.load_origin()
        self.lbl_saved_origin = ctk.CTkLabel(
            card_origin_mem,
            text=f"النقطة المحفوظة: X={init_origin['x']:.1f} | Y={init_origin['y']:.1f} | Z={init_origin['z']:.1f}",
            font=("Segoe UI", 9),
            text_color="#94a3b8",
            anchor="center"
        )
        self.lbl_saved_origin.pack(fill="x", padx=8, pady=(0, 4))

        row_origin_btns = ctk.CTkFrame(card_origin_mem, fg_color="transparent")
        row_origin_btns.pack(fill="x", padx=6, pady=(0, 6))

        btn_save_origin = ctk.CTkButton(
            row_origin_btns,
            text="💾 تسجيل وحفظ",
            command=self.save_current_origin_action,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=("Segoe UI", 10, "bold"),
            height=28
        )
        btn_save_origin.pack(side="right", expand=True, fill="x", padx=2)

        btn_recall_origin = ctk.CTkButton(
            row_origin_btns,
            text="🎯 استدعاء وذهاب",
            command=self.recall_saved_origin_action,
            fg_color="#107c41",
            hover_color="#0b5c30",
            font=("Segoe UI", 10, "bold"),
            height=28
        )
        btn_recall_origin.pack(side="left", expand=True, fill="x", padx=2)

        # Test Z-Hop / Pen contact button
        btn_test_zhop = ctk.CTkButton(
            jog_card,
            text="🧪 اختبار ملامسة القلم والرفع (Z-Hop Test)",
            command=self.test_pen_zhop,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            font=("Segoe UI", 11, "bold"),
            height=30
        )
        btn_test_zhop.pack(fill="x", padx=12, pady=(0, 6))

        # Test Printer Buzzer (M300) button
        btn_test_buzzer = ctk.CTkButton(
            jog_card,
            text="🔊 اختبار صافرة الطابعة (M300 Buzzer)",
            command=self.test_printer_buzzer,
            fg_color="#4f46e5",
            hover_color="#4338ca",
            font=("Segoe UI", 11, "bold"),
            height=30
        )
        btn_test_buzzer.pack(fill="x", padx=12, pady=(0, 10))

        # ------------------ LEFT PANEL: Slicing, Streaming & Terminal ------------------
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=10)
        left_panel.grid_rowconfigure(2, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        # 1. Slicing & G-Code Actions Card
        slice_card = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        slice_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(slice_card, text="⚡ التقطيع وتجهيز ملف الطباعة", font=("Segoe UI", 13, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        row_slice_btns = ctk.CTkFrame(slice_card, fg_color="transparent")
        row_slice_btns.pack(fill="x", padx=12, pady=4)

        btn_slice = ctk.CTkButton(
            row_slice_btns,
            text="⚡ عمل سلايس للنموذج الحالي",
            command=self.do_slice_current_model,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=("Segoe UI", 12, "bold"),
            height=34
        )
        btn_slice.pack(side="right", expand=True, fill="x", padx=3)

        btn_load_gcode = ctk.CTkButton(
            row_slice_btns,
            text="📂 فتح ملف G-Code",
            command=self.open_gcode_file,
            fg_color="#475569",
            hover_color="#334155",
            font=("Segoe UI", 11),
            height=34
        )
        btn_load_gcode.pack(side="left", padx=3)

        # Info Label
        self.lbl_gcode_info = ctk.CTkLabel(
            slice_card,
            text="لم يتم تجهيز ملف G-Code بعد. اضغط 'عمل سلايس للنموذج الحالي' للبدء.",
            font=("Segoe UI", 11),
            text_color="#94a3b8",
            anchor="e"
        )
        self.lbl_gcode_info.pack(fill="x", padx=12, pady=(2, 8))

        # 2. Print Execution Card
        exec_card = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        exec_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(exec_card, text="🚀 التحكم بالطباعة", font=("Segoe UI", 13, "bold")).pack(anchor="e", padx=12, pady=(10, 6))

        row_exec_btns = ctk.CTkFrame(exec_card, fg_color="transparent")
        row_exec_btns.pack(fill="x", padx=12, pady=4)

        self.btn_start_print = ctk.CTkButton(
            row_exec_btns,
            text="▶️ بدء الطباعة",
            command=self.start_print,
            fg_color="#107c41",
            hover_color="#0b5c30",
            font=("Segoe UI", 13, "bold"),
            height=38
        )
        self.btn_start_print.pack(side="right", expand=True, fill="x", padx=3)

        self.btn_pause_print = ctk.CTkButton(
            row_exec_btns,
            text="⏸️ إيقاف مؤقت",
            command=self.pause_resume_print,
            fg_color="#d97706",
            hover_color="#b45309",
            font=("Segoe UI", 11, "bold"),
            height=38,
            state="disabled"
        )
        self.btn_pause_print.pack(side="right", padx=3)

        self.btn_stop_print = ctk.CTkButton(
            row_exec_btns,
            text="🛑 إيقاف طوارئ",
            command=self.emergency_stop,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=("Segoe UI", 11, "bold"),
            height=38
        )
        self.btn_stop_print.pack(side="left", padx=3)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(exec_card)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=12, pady=(8, 4))

        self.lbl_progress = ctk.CTkLabel(
            exec_card,
            text="جاهز للطباعة. 0%",
            font=("Segoe UI", 10),
            text_color="#94a3b8"
        )
        self.lbl_progress.pack(anchor="center", pady=(0, 4))

        # Pen Swap Notification Card (Displayed automatically when changing colors)
        self.pen_swap_card = ctk.CTkFrame(exec_card, fg_color=("#fef3c7", "#451a03"), corner_radius=8, border_width=2, border_color="#f59e0b")
        # Hidden initially

        self.lbl_pen_swap_title = ctk.CTkLabel(
            self.pen_swap_card,
            text="🎨 حان وقت استبدال القلم!",
            font=("Segoe UI", 12, "bold"),
            text_color=("#92400e", "#fbbf24")
        )
        self.lbl_pen_swap_title.pack(anchor="e", padx=10, pady=(6, 2))

        self.lbl_pen_swap_desc = ctk.CTkLabel(
            self.pen_swap_card,
            text="تم إيقاف الحركة عند (0, 0) على مستوى سطح الورقة:\n1. استبدل القلم واضبط سنه ليلامس الورقة عند نقطة الصفر.\n2. ثبّت القلم جيداً ثم اضغط استمرار لمتابعة الرسم.",
            font=("Segoe UI", 10),
            justify="right",
            anchor="e",
            text_color=("#78350f", "#fef3c7")
        )
        self.lbl_pen_swap_desc.pack(fill="x", padx=10, pady=2)

        self.btn_resume_pen_swap = ctk.CTkButton(
            self.pen_swap_card,
            text="▶️ استمرار بالرسم باللون الجديد",
            command=self.confirm_pen_swap_and_resume,
            fg_color="#107c41",
            hover_color="#0b5c30",
            font=("Segoe UI", 11, "bold"),
            height=32
        )
        self.btn_resume_pen_swap.pack(fill="x", padx=10, pady=(4, 8))

        # 3. Marlin Live Console & Terminal Card
        term_card = ctk.CTkFrame(left_panel, fg_color=("gray85", "gray20"), corner_radius=8)
        term_card.grid(row=2, column=0, sticky="nsew", pady=0)
        term_card.grid_columnconfigure(0, weight=1)
        term_card.grid_rowconfigure(1, weight=1)

        term_header = ctk.CTkFrame(term_card, fg_color="transparent")
        term_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 2))
        ctk.CTkLabel(term_header, text="💻 سجل واستجابة مارلن (Marlin Terminal)", font=("Segoe UI", 11, "bold")).pack(side="right")
        btn_clear = ctk.CTkButton(term_header, text="مسح", width=50, height=22, font=("Segoe UI", 10), command=self.clear_terminal)
        btn_clear.pack(side="left")

        self.txt_terminal = ctk.CTkTextbox(term_card, font=("Consolas", 10), wrap="none")
        self.txt_terminal.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)

        # Terminal Command Entry
        term_input_frame = ctk.CTkFrame(term_card, fg_color="transparent")
        term_input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 8))

        self.entry_cmd = ctk.CTkEntry(term_input_frame, placeholder_text="أدخل أمر G-Code (مثلاً M105, G28, M119)...", font=("Consolas", 11))
        self.entry_cmd.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_cmd.bind("<Return>", lambda e: self.send_manual_cmd())

        btn_send_cmd = ctk.CTkButton(term_input_frame, text="إرسال", width=65, height=28, command=self.send_manual_cmd)
        btn_send_cmd.pack(side="right")

    # --- Connection & Port Logic ---

    def refresh_ports(self):
        ports = SerialPrinter.list_ports()
        if ports:
            port_names = [p[0] for p in ports]
            self.port_combo.configure(values=port_names)
            self.port_combo.set(port_names[0])
            self._handle_printer_log(f"تم العثور على {len(ports)} منفذ تسلسلي.", "info")
        else:
            self.port_combo.configure(values=["لا يوجد منافذ متاحة"])
            self.port_combo.set("لا يوجد منافذ متاحة")

    def toggle_connection(self):
        if self.printer.is_connected:
            self.printer.disconnect()
        else:
            port = self.port_combo.get().strip()
            if not port or "لا يوجد" in port or "جارٍ" in port:
                messagebox.showwarning("تنبيه", "يرجى توصيل كابل الـ USB واختيار المنفذ الصحيح للطابعة!")
                return
            try:
                baud = int(self.baud_combo.get().strip())
            except Exception:
                baud = 115200

            success, msg = self.printer.connect(port, baud)
            if not success:
                messagebox.showerror("فشل الاتصال", msg)

    def _handle_printer_status(self, status: str):
        if status == "connected":
            self.lbl_status.configure(text=f"🟢 متصل: {self.printer.port} ({self.printer.baudrate})", text_color="#10b981")
            self.btn_connect.configure(text="قطع الاتصال ❌", fg_color="#dc2626", hover_color="#b91c1c")
        else:
            self.lbl_status.configure(text="⚪ الحالة: غير متصل", text_color="#94a3b8")
            self.btn_connect.configure(text="اتصال بالطابعة 🔌", fg_color="#107c41", hover_color="#0b5c30")
            self.btn_pause_print.configure(state="disabled", text="⏸️ إيقاف مؤقت")

    # --- Jog & Origin Actions ---

    def _on_step_changed(self):
        val_str = self.step_var.get().replace("mm", "")
        try:
            self.selected_step_mm = float(val_str)
        except Exception:
            self.selected_step_mm = 10.0

    def jog(self, axis: str, direction: int):
        dist = self.selected_step_mm * direction
        speed = 3000 if axis in ("X", "Y") else 300
        self.printer.jog(axis, dist, speed_mm_min=speed)

    def home_all(self):
        self.printer.home("XYZ")

    def set_origin_here(self, include_z: bool = False):
        self.printer.set_origin(set_z=include_z)
        if include_z:
            messagebox.showinfo("تم تحديد الصفر", "تم تحديد الموضع الحالي كنقطة بداية للرسم لجميع المحاور (X=0, Y=0, Z=0) بنجاح!")
        else:
            messagebox.showinfo("تم تحديد الصفر", "تم تحديد الموضع الحالي كنقطة بداية للرسم (X=0, Y=0) بنجاح!\nسيبدأ الرسم من هذه النقطة المحددة.")

    def save_current_origin_action(self):
        saved = self.printer.save_current_origin()
        self.lbl_saved_origin.configure(
            text=f"النقطة المحفوظة: X={saved['x']:.1f} | Y={saved['y']:.1f} | Z={saved['z']:.1f}"
        )
        messagebox.showinfo(
            "تم حفظ نقطة البداية",
            f"تم تسجيل وحفظ نقطة البداية في الذاكرة بنجاح:\n"
            f"• المحور X: {saved['x']:.2f} مم\n"
            f"• المحور Y: {saved['y']:.2f} مم\n"
            f"• المحور Z: {saved['z']:.2f} مم\n\n"
            f"يمكنك استدعاؤها وتحريك الرأس إليها بأمان في أي وقت!"
        )

    def recall_saved_origin_action(self):
        if not self.printer.is_connected:
            messagebox.showwarning("تنبيه", "يرجى الاتصال بالطابعة أولاً لاستدعاء نقطة البداية!")
            return
        success, msg = self.printer.go_to_saved_origin(set_zero=True)
        if success:
            messagebox.showinfo("نقطة البداية", f"تم تحريك رأس الطباعة بأمان إلى النقطة المحفوظة:\n{msg}\nوتم تصفير المحاور (G92 X0 Y0).")
        else:
            messagebox.showerror("خطأ", msg)

    def test_pen_zhop(self):
        self.printer.test_z_hop(hop_height=1.5, draw_height=0.0, speed_mm_min=300)

    def test_printer_buzzer(self):
        """Sends a test chime to the printer's physical buzzer (M300) and plays PC chime."""
        if not self.printer.is_connected:
            messagebox.showwarning("تنبيه", "الطابعة غير متصلة! يرجى الاتصال بالطابعة أولاً لاختبار الصافرة.")
            return
        self.printer.beep_printer_chime()
        self.printer._play_beep_chime()
        self.txt_terminal.insert("end", "🔊 تم إرسال نغمة اختبار الصافرة (M300) إلى الطابعة بنجاح!\n")
        self.txt_terminal.see("end")

    # --- Slicing & File Loading ---

    def do_slice_current_model(self):
        if self.on_slice_request:
            gcode_res = self.on_slice_request()
            if gcode_res:
                self.load_gcode_text(gcode_res)
        else:
            messagebox.showwarning("تنبيه", "يرجى اختيار صورة أولاً في تبويب التصميم لعمل السلايس.")

    def load_gcode_text(self, gcode_content: str):
        self.loaded_gcode = gcode_content
        lines = [line for line in gcode_content.splitlines() if line.strip() and not line.startswith(";")]
        lines_count = len(lines)
        self.lbl_gcode_info.configure(
            text=f"✅ جاهز للطباعة: {lines_count:,} أمر G-Code جاهز للإرسال إلى الطابعة.",
            text_color="#10b981"
        )
        self.progress_bar.set(0.0)
        self.lbl_progress.configure(text=f"جاهز للطباعة. 0 من {lines_count:,} سطر (0.0%)")

    def open_gcode_file(self):
        chosen = filedialog.askopenfilename(
            title="اختر ملف G-Code",
            filetypes=[("G-Code files", "*.gcode;*.gco;*.nc"), ("All files", "*.*")]
        )
        if chosen and os.path.isfile(chosen):
            try:
                with open(chosen, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.load_gcode_text(content)
                if self.on_external_gcode_loaded:
                    self.on_external_gcode_loaded(content, os.path.basename(chosen))
                self._handle_printer_log(f"تم تحميل ملف G-Code بنجاح: {os.path.basename(chosen)}", "info")
            except Exception as e:
                messagebox.showerror("خطأ", f"تعذر قراءة ملف الـ G-Code:\n{e}")

    # --- Print Streaming Controls ---

    def start_print(self):
        if not self.printer.is_connected:
            messagebox.showwarning("تنبيه", "يرجى الاتصال بالطابعة أولاً عبر كابل الـ USB!")
            return
        if not self.loaded_gcode:
            if self.on_slice_request:
                self.do_slice_current_model()
            if not self.loaded_gcode:
                messagebox.showwarning("تنبيه", "يرجى عمل سلايس أو فتح ملف G-Code أولاً!")
                return

        ok = self.printer.start_print(self.loaded_gcode)
        if ok:
            self.btn_start_print.configure(state="disabled")
            self.btn_pause_print.configure(state="normal", text="⏸️ إيقاف مؤقت")

    def pause_resume_print(self):
        if not self.printer.is_printing:
            return
        if self.printer.is_paused:
            self.printer.resume_print()
            self.btn_pause_print.configure(text="⏸️ إيقاف مؤقت", fg_color="#d97706")
        else:
            self.printer.pause_print()
            self.btn_pause_print.configure(text="▶️ استئناف", fg_color="#107c41")

    def emergency_stop(self):
        self.printer.emergency_stop()
        self.btn_start_print.configure(state="normal")
        self.btn_pause_print.configure(state="disabled")
        self.pen_swap_card.pack_forget()

    def _handle_tool_change_request(self, color_hex: str, color_name: str):
        def _show():
            self.pen_swap_card.pack(fill="x", padx=10, pady=6)
            self.lbl_pen_swap_title.configure(
                text=f"🎨 يرجى استبدال القلم إلى: {color_name} ({color_hex})"
            )
            self.btn_pause_print.configure(text="▶️ استئناف", fg_color="#107c41")
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass
        self.after(0, _show)

    def confirm_pen_swap_and_resume(self):
        self.pen_swap_card.pack_forget()
        self.printer.resume_print()
        self.btn_pause_print.configure(text="⏸️ إيقاف مؤقت", fg_color="#d97706")

    def _handle_printer_progress(self, cur: int, total: int, pct: float):
        self.after(0, self._update_progress_ui, cur, total, pct)

    def _update_progress_ui(self, cur: int, total: int, pct: float):
        self.progress_bar.set(pct / 100.0)
        self.lbl_progress.configure(text=f"جاري الطباعة: {cur:,} من {total:,} أمر ({pct:.1f}%)")

    def _handle_printer_finished(self, success: bool, msg: str):
        self.after(0, self._on_print_finished_ui, success, msg)

    def _on_print_finished_ui(self, success: bool, msg: str):
        self.btn_start_print.configure(state="normal")
        self.btn_pause_print.configure(state="disabled", text="⏸️ إيقاف مؤقت")
        if success:
            messagebox.showinfo("اكتملت الطباعة 🎉", "اكتمل تنفيذ مسار الرسم والطباعة بنجاح تام!")
        else:
            messagebox.showwarning("تنبيه", f"توقفت الطباعة:\n{msg}")

    # --- Terminal Log & Manual Commands ---

    def _handle_printer_log(self, msg: str, tag: str = "normal"):
        self.after(0, self._append_terminal, msg, tag)

    def _append_terminal(self, msg: str, tag: str):
        self.txt_terminal.insert("end", msg + "\n")
        self.txt_terminal.see("end")

    def clear_terminal(self):
        self.txt_terminal.delete("1.0", "end")

    def send_manual_cmd(self):
        cmd = self.entry_cmd.get().strip()
        if cmd:
            self.entry_cmd.delete(0, "end")
            self.printer.send_command(cmd)
