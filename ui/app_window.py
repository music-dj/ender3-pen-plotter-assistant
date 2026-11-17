"""
Main Application Window for 3D Printing & Pen Plotting Assistant (Ender 3 Pro).
Features:
- Tab 1: Design & 3D Watertight Solid STL / SVG with live bed simulation & Drag-and-Drop
- Tab 2: Print & Slicing Settings Profile (Quality, Walls, Speeds, Z-Hop, Temperatures)
- Tab 3: Direct USB Marlin Printer Connection, Jogging, Custom Origin Zeroing, Slicing & Direct Printing
"""
import os
from tkinter import filedialog, messagebox
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image, ImageTk

from core.processor import ImageProcessor
from core.solid_vectorizer import SolidVectorizer
from core.stl_exporter import STLExporter
from core.serial_printer import SerialPrinter
from core.slicer_engine import SlicerEngine
from core.svg_loader import SVGLoader
from core.project_manager import ProjectManager
from core.version import APP_VERSION, APP_TITLE, APP_NAME

from ui.controls_panel import ControlsPanel
from ui.preview_canvas import PreviewCanvas
from ui.settings_tab import SettingsTab
from ui.printer_tab import PrinterTab
from ui.slicer_preview_tab import SlicerPreviewTab

class AppWindow(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()

        # Initialize TkinterDnD extension inside Tkinter
        self.TkdndVersion = TkinterDnD._require(self)

        # Appearance & Window Config
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title(f"برنامج رسم ثلاثي الأبعاد بالطابعة - الإصدار {APP_VERSION} (Ender 3 Pro / Marlin Plotter v{APP_VERSION})")
        self.geometry("1260x860")
        self.minsize(1020, 720)

        # Set Beautiful High-Res Application Icon
        base_dir = os.path.dirname(os.path.dirname(__file__))
        icon_ico = os.path.join(base_dir, "assets", "app_icon.ico")
        icon_png = os.path.join(base_dir, "assets", "app_icon.png")
        if os.path.exists(icon_ico):
            try:
                self.iconbitmap(icon_ico)
            except Exception:
                pass
        if os.path.exists(icon_png):
            try:
                icon_img = ImageTk.PhotoImage(file=icon_png)
                self.iconphoto(True, icon_img)
            except Exception:
                pass

        # Core Services
        self.serial_printer = SerialPrinter()

        # State
        self.current_image_path = None
        self.original_pil_img = None
        self.binary_mask = None
        self.svg_layers = None
        self.is_svg_file = False
        self.img_w = 0
        self.img_h = 0
        self.last_svg_content = ""
        self.active_color_layers = None
        self.color_masks = None

        # Layout: Main Tabview
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self, corner_radius=8)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=8)

        # Create the 4 Tabs in user-requested order:
        # Tab 1: Design & 3D Model
        # Tab 2: Settings (Cura Profile)
        # Tab 3: Slicer Preview (A5 paper)
        # Tab 4: Printer Connection & Control
        self.tab_name_design = "🎨 التصميم والمجسم 3D"
        self.tab_name_settings = "⚙️ إعدادات التقطيع والطباعة"
        self.tab_name_slicer_preview = "📐 معاينة السلايس (ورقة A5)"
        self.tab_name_printer = "🖨️ الاتصال بالطابعة والتحكم المباشر"

        tab_design = self.tabview.add(self.tab_name_design)
        tab_settings = self.tabview.add(self.tab_name_settings)
        tab_slicer = self.tabview.add(self.tab_name_slicer_preview)
        tab_printer = self.tabview.add(self.tab_name_printer)

        # ------------------ TAB 1: DESIGN & 3D MODEL ------------------
        tab_design.grid_columnconfigure(1, weight=1)
        tab_design.grid_rowconfigure(0, weight=1)

        # Left Controls Panel
        self.controls = ControlsPanel(
            tab_design,
            on_change_callback=self.on_controls_changed,
            on_export_svg_callback=self.export_svg,
            on_export_stl_callback=self.export_stl,
            on_open_callback=self.open_file_dialog,
            on_slice_callback=self.on_quick_slice_clicked,
            on_save_project_callback=self.save_project_dialog,
            on_load_project_callback=self.load_project_dialog,
            width=340,
            corner_radius=0
        )
        self.controls.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)

        # Right Main Panel (Preview + Status)
        self.design_main_frame = ctk.CTkFrame(tab_design, corner_radius=0, fg_color="transparent")
        self.design_main_frame.grid(row=0, column=1, sticky="nsew", padx=4, pady=0)
        self.design_main_frame.grid_columnconfigure(0, weight=1)
        self.design_main_frame.grid_rowconfigure(0, weight=1)

        self.preview = PreviewCanvas(self.design_main_frame)
        self.preview.grid(row=0, column=0, sticky="nsew")

        self.status_bar = ctk.CTkLabel(
            self.design_main_frame,
            text=f"✨ {APP_NAME} v{APP_VERSION} جاهز. اسحب وأفلت أي صورة أو مشروع رسم هنا 🧊🎨",
            anchor="w",
            font=("Segoe UI", 11),
            text_color="#94a3b8"
        )
        self.status_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 0))

        # ------------------ TAB 2: PRINT & SLICING SETTINGS ------------------
        tab_settings.grid_columnconfigure(0, weight=1)
        tab_settings.grid_rowconfigure(0, weight=1)

        self.settings_tab = SettingsTab(tab_settings)
        self.settings_tab.grid(row=0, column=0, sticky="nsew")

        # ------------------ TAB 3: SLICER & A5 PAPER PREVIEW ------------------
        tab_slicer.grid_columnconfigure(0, weight=1)
        tab_slicer.grid_rowconfigure(0, weight=1)

        self.slicer_preview_tab = SlicerPreviewTab(
            tab_slicer,
            on_request_slice=lambda: self.slice_current_model(switch_to_preview=True),
            on_send_to_printer=self.send_slice_to_printer,
            on_fit_to_paper=self.on_fit_model_to_paper,
            on_infill_changed=self.on_infill_changed,
            on_color_layers_updated=self.on_color_layers_updated,
            on_save_project=self.save_project_dialog,
            on_open_project=self.open_file_dialog
        )
        self.slicer_preview_tab.grid(row=0, column=0, sticky="nsew")

        # ------------------ TAB 4: PRINTER & DIRECT CONTROL ------------------
        tab_printer.grid_columnconfigure(0, weight=1)
        tab_printer.grid_rowconfigure(0, weight=1)

        self.printer_tab = PrinterTab(
            tab_printer,
            serial_printer=self.serial_printer,
            on_slice_request=self.slice_current_model,
            on_external_gcode_loaded=self.on_external_gcode_loaded
        )
        self.printer_tab.grid(row=0, column=0, sticky="nsew")

        # Set default tab
        self.tabview.set(self.tab_name_design)

        # Register OLE Drag and Drop on design surfaces
        self._setup_dnd()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close_app)

    def _setup_dnd(self):
        surfaces = [
            self,
            self.design_main_frame,
            self.preview,
            self.preview.solid_canvas,
            self.preview.orig_canvas
        ]
        for widget in surfaces:
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self.on_drop_event)
            except Exception as e:
                print(f"Could not register DnD on {widget}: {e}")

    def on_drop_event(self, event):
        if not event.data:
            return

        files = self.tk.splitlist(event.data)
        if not files:
            return

        filepath = files[0]
        filepath = os.path.normpath(filepath.strip("{}"))

        if os.path.isfile(filepath):
            if filepath.lower().endswith(".plotproj"):
                self.load_project_dialog(filepath)
            else:
                self.tabview.set(self.tab_name_design)
                self.load_image(filepath)

    def open_file_dialog(self):
        filetypes = [
            ("Supported Design & Project Files", "*.plotproj;*.svg;*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.tiff"),
            ("Plotter Project Files (.plotproj)", "*.plotproj"),
            ("SVG Vector Files (Multi-Color)", "*.svg"),
            ("Raster Images", "*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.tiff"),
            ("All files", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="اختر ملف تصميم أو مشروع سابق", filetypes=filetypes)
        if chosen:
            if chosen.lower().endswith(".plotproj"):
                self.load_project_dialog(chosen)
            else:
                self.load_image(chosen)

    def load_image(self, filepath: str):
        self.status_bar.configure(text=f"جاري قراءة ومعالجة الملف: {os.path.basename(filepath)}...")
        self.update_idletasks()

        cfg = self.controls.get_config()

        if filepath.lower().endswith(".svg"):
            try:
                self.is_svg_file = True
                self.current_image_path = filepath
                svg_data = SVGLoader.load_svg(
                    filepath,
                    target_w_mm=cfg["target_width_mm"],
                    target_h_mm=cfg["target_height_mm"],
                    preserve_aspect=cfg["lock_aspect"]
                )
                self.svg_layers = svg_data["color_layers"]
                self.last_svg_content = svg_data["svg_content"]
                self.img_w = max(1, int(svg_data["width_mm"]))
                self.img_h = max(1, int(svg_data["height_mm"]))

                # Update height if aspect ratio is preserved
                if cfg["lock_aspect"] and svg_data["width_mm"] > 0:
                    aspect = svg_data["height_mm"] / svg_data["width_mm"]
                    new_h = cfg["target_width_mm"] * aspect
                    self.controls.height_var.set(f"{new_h:.1f}")

                # Update preview canvas with multi-color layers
                self.preview.set_color_layers(self.svg_layers, svg_data["width_mm"], svg_data["height_mm"])
                total_polys = len(svg_data["all_polygons"])
                colors_cnt = len(self.svg_layers)
                self.controls.update_stats(total_polys, colors_cnt)

                self.status_bar.configure(
                    text=f"تم استيراد SVG بنجاح! {colors_cnt} ألوان مكتشفة ({total_polys} مضلع) | جاهز للتقطيع متعدد الأقلام 🎨"
                )
                # Automatically slice and update A5 preview
                self.slice_current_model(switch_to_preview=False)
                return
            except Exception as e:
                messagebox.showerror("خطأ في قراءة ملف SVG", f"تعذر قراءة ملف الـ SVG:\n{e}")
                self.status_bar.configure(text="حدث خطأ أثناء تحميل ملف SVG.")
                return

        # Raster image loading
        self.is_svg_file = False
        self.svg_layers = None
        self.active_color_layers = None
        self.color_masks = None

        try:
            pil_img = Image.open(filepath)
            self.original_pil_img = pil_img.convert("RGB")
            self.current_image_path = filepath
            self.img_w, self.img_h = self.original_pil_img.size

            aspect = self.img_h / self.img_w
            try:
                cur_w = float(self.controls.width_var.get())
                self.controls.height_var.set(f"{cur_w * aspect:.1f}")
            except Exception:
                pass

            self.preview.set_original_image(self.original_pil_img)
            self.process_image()

        except Exception as e:
            messagebox.showerror("خطأ في قراءة الصورة", f"تعذر فتح الصورة:\n{e}")
            self.status_bar.configure(text="حدث خطأ أثناء تحميل الصورة.")

    def on_controls_changed(self, update_height_from_aspect: bool = False):
        if not self.current_image_path:
            return

        cfg = self.controls.get_config()
        if (cfg["lock_aspect"] or update_height_from_aspect) and self.img_w > 0:
            aspect = self.img_h / self.img_w
            new_h = cfg["target_width_mm"] * aspect
            self.controls.height_var.set(f"{new_h:.1f}")

        if self.is_svg_file:
            self.load_image(self.current_image_path)
        else:
            self.process_image()

    def process_image(self):
        if not self.current_image_path:
            return

        if self.is_svg_file:
            return

        cfg = self.controls.get_config()
        self.status_bar.configure(text="جاري استخراج وتجسيم الأشكال المصمتة (Solid Vectors) ⏳...")
        self.update_idletasks()

        try:
            # 1. Preprocessing into solid binary mask (preserves thin notes and strokes)
            self.binary_mask, _ = ImageProcessor.load_and_preprocess(
                self.current_image_path,
                threshold_val=cfg["threshold"],
                invert=cfg["invert"],
                denoise=False
            )

            # Auto-detect colors if image contains multiple colors
            self.color_masks = ImageProcessor.extract_color_masks(
                self.current_image_path,
                max_colors=5,
                threshold_val=cfg["threshold"],
                invert=cfg["invert"]
            )

            # 2. Vectorize to Solid SVG with evenodd holes
            result = SolidVectorizer.vectorize_to_solid_svg(
                binary_img=self.binary_mask,
                target_width_mm=cfg["target_width_mm"],
                target_height_mm=cfg["target_height_mm"],
                thickness_mm=cfg["thickness_mm"],
                epsilon=cfg.get("epsilon_mm", 0.3)
            )

            self.last_svg_content = result["svg"]
            stats = result["stats"]

            # 3. Update preview canvas with solid 3D bed simulation
            self.preview.set_solid_mask(self.binary_mask)
            self.controls.update_stats(stats["contours"], stats["points"])

            th = cfg["thickness_mm"]
            w = cfg["target_width_mm"]
            h = cfg["target_height_mm"]
            self.status_bar.configure(
                text=f"تم التجسيم بنجاح! الأبعاد: {w:.1f}x{h:.1f} مم | سمك Z: {th:.2f} مم | مجسم ناعم مانع للتسرب جاهز للطباعة 🧊"
            )

        except Exception as e:
            messagebox.showerror("خطأ أثناء المعالجة", f"فشلت معالجة المجسم:\n{e}")
            self.status_bar.configure(text="فشلت عملية المعالجة.")

        except Exception as e:
            messagebox.showerror("خطأ أثناء المعالجة", f"فشلت معالجة المجسم:\n{e}")
            self.status_bar.configure(text="فشلت عملية المعالجة.")

    def export_svg(self):
        if not self.last_svg_content:
            messagebox.showwarning("تنبيه", "يرجى اختيار صورة وتحويلها أولاً قبل التصدير!")
            return

        default_name = "solid_model_3d.svg"
        if self.current_image_path:
            base = os.path.splitext(os.path.basename(self.current_image_path))[0]
            default_name = f"{base}_solid_3d.svg"

        dest_file = filedialog.asksaveasfilename(
            title="حفظ ملف SVG صلب للتقطيع (Slicing)",
            defaultextension=".svg",
            initialfile=default_name,
            filetypes=[("SVG Solid 3D Vector", "*.svg")]
        )
        if dest_file:
            try:
                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write(self.last_svg_content)
                messagebox.showinfo("تم التصدير بنجاح", f"تم حفظ ملف SVG الصلب بنجاح في:\n{dest_file}")
                self.status_bar.configure(text=f"تم تصدير الـ SVG بنجاح إلى: {os.path.basename(dest_file)}")
            except Exception as e:
                messagebox.showerror("خطأ في الحفظ", f"تعذر حفظ الملف:\n{e}")

    def export_stl(self):
        if self.binary_mask is None:
            messagebox.showwarning("تنبيه", "يرجى اختيار صورة وتحويلها أولاً قبل تصدير STL!")
            return

        cfg = self.controls.get_config()
        default_name = "model_3d_watertight.stl"
        if self.current_image_path:
            base = os.path.splitext(os.path.basename(self.current_image_path))[0]
            default_name = f"{base}_watertight_{cfg['thickness_mm']:.1f}mm.stl"

        dest_file = filedialog.asksaveasfilename(
            title="حفظ مجسم STL ثلاثي الأبعاد فائق النعومة (Watertight)",
            defaultextension=".stl",
            initialfile=default_name,
            filetypes=[("3D STL Model", "*.stl")]
        )
        if dest_file:
            try:
                self.status_bar.configure(text="جاري تصدير مجسم ثلاثي الأبعاد مانع للتسرب (Watertight STL)...")
                self.update_idletasks()

                triangles_count = STLExporter.export_watertight_stl(
                    mask=self.binary_mask,
                    filepath=dest_file,
                    target_w_mm=cfg["target_width_mm"],
                    target_h_mm=cfg["target_height_mm"],
                    thickness_mm=cfg["thickness_mm"],
                    epsilon_mm=cfg.get("epsilon_mm", 0.3)
                )

                if triangles_count == 0:
                    messagebox.showwarning("تنبيه", "لم يتم العثور على أشكال صالحة لتصدير STL. تأكد من تباين الصورة.")
                    return

                messagebox.showinfo(
                    "تم تصدير STL فائق الدقة بنجاح 🧊",
                    f"تم إنشاء مجسم ثلاثي الأبعاد حقيقي ناعم ومانع للتسرب (100% Watertight Manifold)!\n\n"
                    f"• الأبعاد: {cfg['target_width_mm']:.1f} × {cfg['target_height_mm']:.1f} مم\n"
                    f"• السمك: {cfg['thickness_mm']:.2f} مم\n"
                    f"• عدد المثلثات: {triangles_count:,}\n\n"
                    f"المسار:\n{dest_file}\n\n"
                    f"تم حل مشكلة الحواف الحادة والثقوب نهائياً. الملف جاهز للتقطيع المباشر في Cura دون أي تشوهات!"
                )
                self.status_bar.configure(text=f"تم تصدير STL مانع للتسرب بنجاح: {os.path.basename(dest_file)} ({triangles_count:,} مثلث)")
            except Exception as e:
                messagebox.showerror("خطأ في تصدير STL", f"تعذر تصدير المجسم:\n{e}")

    def slice_current_model(self, switch_to_preview: bool = False, preserve_view: bool = False) -> str:
        """Slices the currently loaded model (Multi-Color SVG or Raster) using Cura settings."""
        if not self.is_svg_file and self.binary_mask is None and not self.active_color_layers:
            messagebox.showwarning("تنبيه", "يرجى تحميل صورة أو ملف SVG أولاً في تبويب التصميم قبل عمل السلايس!")
            return ""

        cfg = self.controls.get_config()
        slicing_settings = self.settings_tab.get_settings()
        if hasattr(self, 'slicer_preview_tab'):
            slicing_settings.update(self.slicer_preview_tab.get_paper_config())

        self.status_bar.configure(text="جاري عمل سلايس وتوليد كود الطباعة G-Code ⚡...")
        self.update_idletasks()

        try:
            if self.is_svg_file and self.svg_layers and not self.active_color_layers:
                # Master Multi-Color / Multi-Pen Slicing
                res = SlicerEngine.slice_color_layers(
                    color_layers=self.svg_layers,
                    target_w_mm=cfg["target_width_mm"],
                    target_h_mm=cfg["target_height_mm"],
                    settings=slicing_settings
                )
            elif self.active_color_layers:
                # User-colored layers from Interactive Coloring Studio or Project
                res = SlicerEngine.slice_color_layers(
                    color_layers=self.active_color_layers,
                    target_w_mm=cfg["target_width_mm"],
                    target_h_mm=cfg["target_height_mm"],
                    settings=slicing_settings
                )
            elif self.color_masks and len(self.color_masks) > 1:
                # Auto-detected color layers from colored image
                res = SlicerEngine.slice_color_masks_to_gcode(
                    color_masks=self.color_masks,
                    target_w_mm=cfg["target_width_mm"],
                    target_h_mm=cfg["target_height_mm"],
                    settings=slicing_settings
                )
            else:
                # Raster Mask Slicing with downscaling detail preservation & note recovery
                res = SlicerEngine.slice_mask_to_gcode(
                    mask=self.binary_mask,
                    target_w_mm=cfg["target_width_mm"],
                    target_h_mm=cfg["target_height_mm"],
                    settings=slicing_settings
                )

            # Sync active color layers so recoloring studio can manipulate all shapes/notes!
            if "raw_color_layers" in res:
                self.active_color_layers = res["raw_color_layers"]

            # Update SlicerPreviewTab with the new rich slice data, preserving view if requested
            if hasattr(self, 'slicer_preview_tab'):
                self.slicer_preview_tab.set_slice_result(res, preserve_view=preserve_view)

            gcode = res["gcode"]
            lines = res["lines_count"]
            est_time = res["estimated_time_s"]

            mins = int(est_time // 60)
            secs = int(est_time % 60)
            time_str = f"{mins} دقيقة و {secs} ثانية" if mins > 0 else f"{secs} ثانية"

            colors_cnt = len(res.get("color_layers_summary", []))
            colors_info = f" | {colors_cnt} أقلام ملونة 🎨" if colors_cnt > 1 else ""

            self.status_bar.configure(
                text=f"اكتمل السلايس! {lines:,} سطر G-Code{colors_info} | الوقت التقديري: {time_str} | جاهز للطباعة"
            )

            # ALWAYS automatically update PrinterTab with the newly generated G-code!
            if hasattr(self, 'printer_tab') and gcode:
                self.printer_tab.load_gcode_text(gcode)

            if switch_to_preview:
                self.tabview.set(self.tab_name_slicer_preview)

            return gcode

        except Exception as e:
            messagebox.showerror("خطأ في السلايس", f"تعذر إنشاء كود الطباعة:\n{e}")
            return ""

    def on_infill_changed(self, new_pattern: str):
        """Called when infill pattern is changed directly in A5 Slicer Preview Tab."""
        self.settings_tab.var_infill_pattern.set(new_pattern)
        self.slice_current_model(switch_to_preview=True, preserve_view=True)

    def on_quick_slice_clicked(self):
        """Called from Tab 1 to slice and immediately switch to Tab 3 (A5 Slicer Preview)."""
        gcode = self.slice_current_model(switch_to_preview=True, preserve_view=False)
        if gcode:
            self.printer_tab.load_gcode_text(gcode)

    def send_slice_to_printer(self, gcode: str):
        """Called from Tab 3 to send G-code to Printer Tab and switch to it."""
        self.printer_tab.load_gcode_text(gcode)
        self.tabview.set(self.tab_name_printer)

    def on_color_layers_updated(self, updated_layers):
        """Called by SlicerPreviewTab when user clicks a shape or line to recolor it."""
        self.active_color_layers = updated_layers
        # Preserve zoom & pan position so clicking does NOT zoom out!
        gcode = self.slice_current_model(switch_to_preview=True, preserve_view=True)
        if gcode and hasattr(self, 'printer_tab'):
            self.printer_tab.load_gcode_text(gcode)

    def save_project_dialog(self):
        """Saves current multi-color drawing project (.plotproj)."""
        color_layers = self.active_color_layers or self.svg_layers
        if not color_layers and self.binary_mask is None:
            messagebox.showwarning("تنبيه", "لا يوجد رسم حالي لحفظه! يرجى تحميل صورة أو تلوين رسمة أولاً.")
            return

        cfg = self.controls.get_config()
        paper_cfg = self.slicer_preview_tab.get_paper_config() if hasattr(self, 'slicer_preview_tab') else {}
        settings = self.settings_tab.get_settings() if hasattr(self, 'settings_tab') else {}

        # If we have binary mask but no color layers yet, ensure we slice/extract them
        if not color_layers:
            self.slice_current_model()
            color_layers = self.active_color_layers

        default_name = "drawing_project.plotproj"
        if self.current_image_path:
            base = os.path.splitext(os.path.basename(self.current_image_path))[0]
            default_name = f"{base}_project_v{APP_VERSION}.plotproj"

        dest_file = filedialog.asksaveasfilename(
            title="حفظ مشروع الرسم بالألوان (Plotter Project)",
            defaultextension=".plotproj",
            initialfile=default_name,
            filetypes=[
                ("Plotter Project", "*.plotproj"),
                ("JSON Project", "*.json"),
                ("All Files", "*.*")
            ]
        )
        if dest_file:
            try:
                payload = {
                    "target_width_mm": cfg["target_width_mm"],
                    "target_height_mm": cfg["target_height_mm"],
                    "thickness_mm": cfg["thickness_mm"],
                    "lock_aspect": cfg["lock_aspect"],
                    "infill_pattern": settings.get("infill_pattern", "Cubic"),
                    "infill_density": settings.get("infill_density", 20.0),
                    "paper_preset": paper_cfg.get("paper_preset", "ورقة A5 بالعرض (210 × 148 مم)"),
                    "paper_placement": paper_cfg.get("paper_placement", "directional"),
                    "paper_margin_mm": paper_cfg.get("paper_margin_mm", 15.0),
                    "margin_left_mm": paper_cfg.get("margin_left_mm", 15.0),
                    "margin_right_mm": paper_cfg.get("margin_right_mm", 15.0),
                    "margin_bottom_mm": paper_cfg.get("margin_bottom_mm", 15.0),
                    "margin_top_mm": paper_cfg.get("margin_top_mm", 15.0),
                    "center_horizontally": paper_cfg.get("center_horizontally", True),
                    "center_vertically": paper_cfg.get("center_vertically", True),
                    "original_image_path": self.current_image_path or "",
                    "color_layers": color_layers
                }
                ProjectManager.save_project(dest_file, payload)
                messagebox.showinfo("تم الحفظ بنجاح", f"تم حفظ مشروع الرسم بالألوان بنجاح في:\n{dest_file}")
                self.status_bar.configure(text=f"تم حفظ مشروع الرسم: {os.path.basename(dest_file)} بنجاح 💾")
            except Exception as e:
                messagebox.showerror("خطأ في الحفظ", f"تعذر حفظ مشروع الرسم:\n{e}")

    def load_project_dialog(self, filepath: Optional[str] = None):
        """Loads a saved multi-color drawing project (.plotproj)."""
        if not filepath:
            filepath = filedialog.askopenfilename(
                title="فتح مشروع رسم سابق بالألوان",
                filetypes=[
                    ("Plotter Project", "*.plotproj"),
                    ("JSON Project", "*.json"),
                    ("All Files", "*.*")
                ]
            )
        if not filepath or not os.path.isfile(filepath):
            return

        try:
            data = ProjectManager.load_project(filepath)
            self.current_image_path = data.get("original_image_path", filepath)
            w_mm = float(data.get("model_width_mm", 150.0))
            h_mm = float(data.get("model_height_mm", 150.0))
            th_mm = float(data.get("thickness_mm", 0.2))

            self.controls.width_var.set(f"{w_mm:.1f}")
            self.controls.height_var.set(f"{h_mm:.1f}")
            self.controls.thick_var.set(f"{th_mm:.2f}")
            self.controls.lock_aspect_var.set(data.get("lock_aspect", True))

            infill_pat = data.get("infill_pattern", "Cubic")
            if hasattr(self, 'settings_tab'):
                self.settings_tab.var_infill_pattern.set(infill_pat)
            if hasattr(self, 'slicer_preview_tab'):
                self.slicer_preview_tab.var_infill_pattern.set(infill_pat)
                self.slicer_preview_tab.load_paper_config(data)

            self.active_color_layers = data["color_layers"]
            self.svg_layers = data["color_layers"]
            self.is_svg_file = True

            # Update preview canvas
            self.preview.set_color_layers(self.active_color_layers, w_mm, h_mm)
            total_polys = sum(len(l.get("polygons", [])) for l in self.active_color_layers.values())
            colors_cnt = len(self.active_color_layers)
            self.controls.update_stats(total_polys, colors_cnt)

            self.slice_current_model(switch_to_preview=True, preserve_view=False)
            messagebox.showinfo(
                "تم فتح المشروع بنجاح",
                f"تم استعادة المشروع بنجاح مع {colors_cnt} أقلام وألوان محفوظة!\nجاهز للرسم والطباعة فوراً."
            )
            self.status_bar.configure(text=f"تم فتح مشروع الرسم: {os.path.basename(filepath)} ({colors_cnt} ألوان) 🎨")
        except Exception as e:
            messagebox.showerror("خطأ في فتح المشروع", f"تعذر فتح ملف المشروع:\n{e}")

    def on_fit_model_to_paper(self, scale_factor_or_w, new_h: float = None):
        """
        Adjusts model dimensions proportionally to fit neatly within A5 paper and re-slices.
        Fixes continuous shrinking bug: scaling is idempotent and proportional to current canvas.
        """
        if new_h is not None and scale_factor_or_w > 10.0:
            new_w = float(scale_factor_or_w)
            target_h = float(new_h)
        else:
            scale_factor = float(scale_factor_or_w)
            cur_w = float(self.controls.width_var.get())
            cur_h = float(self.controls.height_var.get())
            new_w = round(cur_w * scale_factor, 1)
            target_h = round(cur_h * scale_factor, 1)

        self.controls.width_var.set(f"{new_w:.1f}")
        self.controls.height_var.set(f"{target_h:.1f}")

        # Reset active color layers so they scale to the new physical target width/height
        self.active_color_layers = None

        if self.is_svg_file:
            self.load_image(self.current_image_path)
        else:
            self.process_image()
        self.slice_current_model(switch_to_preview=True)

    def on_external_gcode_loaded(self, gcode_content: str, filename: str):
        """Called when an external G-Code file is loaded in PrinterTab to also show in A5 Preview."""
        if hasattr(self, 'slicer_preview_tab'):
            self.slicer_preview_tab.load_external_gcode(gcode_content, filename)

    def on_close_app(self):
        try:
            if self.serial_printer and self.serial_printer.is_connected:
                self.serial_printer.disconnect()
        except Exception:
            pass
        self.destroy()
