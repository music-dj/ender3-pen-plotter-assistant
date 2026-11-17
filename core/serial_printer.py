"""
Serial Communication and G-Code Streamer for Marlin / 3D Printers (Ender 3 Pro).
Handles USB serial connection, real-time command execution, manual jog,
setting custom origins, and threaded G-Code streaming with pause/resume/cancel.
"""
import time
import threading
from typing import List, Tuple, Optional, Callable
import serial
import serial.tools.list_ports
from core.origin_manager import OriginManager

class SerialPrinter:
    def __init__(self):
        self.ser: Optional[serial.Serial] = None
        self.port: str = ""
        self.baudrate: int = 115200
        self.is_connected: bool = False

        # Head position tracking
        self.current_x: float = 0.0
        self.current_y: float = 0.0
        self.current_z: float = 0.0

        # Streaming state
        self.is_printing: bool = False
        self.is_paused: bool = False
        self._pause_requested: bool = False
        self.stop_requested: bool = False
        self._print_thread: Optional[threading.Thread] = None

        # Lock & sync
        self._serial_lock = threading.Lock()
        self._ok_event = threading.Event()
        self._last_response: str = ""

        # Callbacks
        self.on_log: Optional[Callable[[str, str], None]] = None  # (message, tag/type)
        self.on_progress: Optional[Callable[[int, int, float], None]] = None  # (cur, total, pct)
        self.on_status_change: Optional[Callable[[str], None]] = None
        self.on_print_finished: Optional[Callable[[bool, str], None]] = None  # (success, message)
        self.on_tool_change_request: Optional[Callable[[str, str], None]] = None  # (color_hex, color_name)

        # Background reader
        self._reader_running = False
        self._reader_thread: Optional[threading.Thread] = None

    @staticmethod
    def list_ports() -> List[Tuple[str, str]]:
        """Returns a list of available serial ports [(port_device, description), ...]."""
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            result.append((p.device, f"{p.device}: {p.description}"))
        return result

    def connect(self, port: str, baudrate: int = 115200) -> Tuple[bool, str]:
        """Connects to the specified serial port (e.g. 'COM3', 115200)."""
        if self.is_connected:
            self.disconnect()

        self.port = port
        self.baudrate = baudrate

        try:
            # Ender 3 Pro (CH340/FTDI/Marlin) setup
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
                write_timeout=2.0
            )

            # Toggle DTR to trigger clean reset/connection
            try:
                self.ser.dtr = False
                time.sleep(0.1)
                self.ser.dtr = True
            except Exception:
                pass

            self.is_connected = True
            self._reader_running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

            self._log(f"🔌 تم فتح المنفذ {self.port} بسرعة {self.baudrate}. جاري انتظار استجابة الطابعة...", "info")
            if self.on_status_change:
                self.on_status_change("connected")

            # Send a handshake M105 / M115 after brief delay
            threading.Thread(target=self._handshake, daemon=True).start()
            return True, f"تم الاتصال بالمنفذ {port} بنجاح"

        except Exception as e:
            self.is_connected = False
            self.ser = None
            err_msg = f"فشل الاتصال بالمنفذ {port}: {e}"
            self._log(f"❌ {err_msg}", "error")
            return False, err_msg

    def _handshake(self):
        time.sleep(1.5)
        if self.is_connected:
            self.send_command("M105")  # Request temperature / ping
            self.send_command("M115")  # Firmware info

    def disconnect(self):
        """Disconnects cleanly from the serial port."""
        self.stop_requested = True
        self.is_printing = False
        self.is_paused = False
        self._reader_running = False
        self._ok_event.set()

        with self._serial_lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            self.is_connected = False

        self._log("🔌 تم قطع الاتصال بالطابعة.", "info")
        if self.on_status_change:
            self.on_status_change("disconnected")

    def _log(self, msg: str, tag: str = "normal"):
        if self.on_log:
            try:
                self.on_log(msg, tag)
            except Exception:
                pass

    def _read_loop(self):
        """Continuously reads lines from the printer."""
        while self._reader_running and self.ser and self.ser.is_open:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("latin1", errors="replace").strip()
                if not line:
                    continue

                self._last_response = line
                self._log(f"⬅️ {line}", "recv")

                # Parse M114 coordinates if received
                if "X:" in line and "Y:" in line and "Z:" in line:
                    import re
                    m_coords = re.findall(r'([XYZ]):\s*([-+]?[0-9]*\.?[0-9]+)', line)
                    for ax, val in m_coords:
                        if ax == 'X': self.current_x = float(val)
                        elif ax == 'Y': self.current_y = float(val)
                        elif ax == 'Z': self.current_z = float(val)

                # Marlin sends "ok" when done with previous command
                if "ok" in line.lower():
                    self._ok_event.set()

            except (serial.SerialException, OSError) as e:
                if self._reader_running:
                    self._log(f"⚠️ انقطع الاتصال بالمنفذ: {e}", "error")
                    self.is_connected = False
                    if self.on_status_change:
                        self.on_status_change("disconnected")
                break
            except Exception:
                pass

    def send_command(self, cmd: str, wait_ok: bool = False, timeout: float = 8.0) -> bool:
        """Sends a single G-code command string to the printer."""
        if not self.is_connected or not self.ser or not self.ser.is_open:
            self._log("⚠️ غير متصل بالطابعة!", "error")
            return False

        clean_cmd = cmd.strip()
        if not clean_cmd:
            return True

        self._log(f"➡️ {clean_cmd}", "send")
        self._ok_event.clear()

        try:
            with self._serial_lock:
                self.ser.write((clean_cmd + "\n").encode("ascii", errors="replace"))
                self.ser.flush()

            if wait_ok:
                res = self._ok_event.wait(timeout=timeout)
                return res
            return True
        except Exception as e:
            self._log(f"❌ خطأ أثناء إرسال الأمر '{clean_cmd}': {e}", "error")
            return False

    # --- Interactive Printer Controls ---

    def jog(self, axis: str, distance_mm: float, speed_mm_min: float = 3000):
        """Moves an axis relatively (X, Y, or Z)."""
        axis = axis.upper()
        if axis not in ("X", "Y", "Z"):
            return
        if axis == "X": self.current_x += distance_mm
        elif axis == "Y": self.current_y += distance_mm
        elif axis == "Z": self.current_z += distance_mm

        cmds = [
            "G91",  # Relative positioning
            f"G1 {axis}{distance_mm:.2f} F{int(speed_mm_min)}",
            "G90"   # Absolute positioning
        ]
        for c in cmds:
            self.send_command(c)

    def home(self, axes: str = "XYZ"):
        """Homes specified axes (e.g. 'XYZ', 'XY', 'Z')."""
        axes = axes.upper().strip()
        if "X" in axes: self.current_x = 0.0
        if "Y" in axes: self.current_y = 0.0
        if "Z" in axes: self.current_z = 0.0

        if axes == "XYZ":
            self.send_command("G28")
        else:
            self.send_command(f"G28 {axes}")

    def set_origin(self, set_z: bool = False):
        """Sets the current tool position as the new (0, 0) origin for drawing."""
        if set_z:
            self.send_command("G92 X0 Y0 Z0")
            self.current_x = 0.0
            self.current_y = 0.0
            self.current_z = 0.0
            self._log("📍 تم تحديد الموضع الحالي كنقطة بداية وصفر كامل (X=0, Y=0, Z=0)!", "info")
        else:
            self.send_command("G92 X0 Y0")
            self.current_x = 0.0
            self.current_y = 0.0
            self._log("📍 تم تحديد الموضع الحالي كنقطة بداية (X=0, Y=0)!", "info")

    def save_current_origin(self, name: str = "نقطة البداية الأساسية") -> Dict[str, float]:
        """Saves current head position as the recorded origin."""
        res = OriginManager.save_origin(self.current_x, self.current_y, self.current_z, name=name)
        data = {"x": self.current_x, "y": self.current_y, "z": self.current_z, "name": name}
        self._log(f"💾 تم حفظ نقطة البداية في الذاكرة: (X: {self.current_x:.1f}, Y: {self.current_y:.1f}, Z: {self.current_z:.1f})", "info")
        self.beep_printer_single(1500, 150)
        self._play_beep(1500, 150)
        return data

    def go_to_saved_origin(self, set_zero: bool = True) -> Tuple[bool, str]:
        """Recalls the saved origin, moves the head there with safe Z-hop, and sets (0,0)."""
        if not self.is_connected:
            return False, "الطابعة غير متصلة!"

        saved = OriginManager.load_origin()
        sx = saved["x"]
        sy = saved["y"]
        sz = saved["z"]

        self._log(f"🎯 جاري الانتقال إلى نقطة البداية المحفوظة: (X: {sx:.1f}, Y: {sy:.1f}, Z: {sz:.1f})...", "info")

        try:
            # 1. Safe Z-Hop before moving across bed
            self.send_command("G91")
            self.send_command("G1 Z10 F600 ; Safe Z-Hop for travel to origin")
            self.send_command("G90")

            # 2. Rapid move to saved X, Y
            self.send_command(f"G0 X{sx:.3f} Y{sy:.3f} F3600")

            # 3. Lower to saved Z
            self.send_command(f"G1 Z{sz:.3f} F600")

            # 4. Set origin as (0, 0)
            if set_zero:
                self.send_command("G92 X0 Y0")
                self.current_x = 0.0
                self.current_y = 0.0
            else:
                self.current_x = sx
                self.current_y = sy
            self.current_z = sz

            # 5. Alert tone
            self.beep_printer_single(1200, 200)
            self._play_beep(1200, 180)

            msg = f"وصل الرأس إلى نقطة البداية المحفوظة: (X: {sx:.1f}, Y: {sy:.1f}, Z: {sz:.1f})"
            self._log(f"✅ {msg}", "info")
            return True, msg
        except Exception as e:
            err = f"خطأ أثناء الانتقال لنقطة البداية: {e}"
            self._log(f"❌ {err}", "error")
            return False, err

    def test_z_hop(self, hop_height: float = 1.5, draw_height: float = 0.0, speed_mm_min: float = 300):
        """Tests pen lift and drop to verify paper contact and pressure."""
        threading.Thread(
            target=self._do_test_z_hop,
            args=(hop_height, draw_height, speed_mm_min),
            daemon=True
        ).start()

    def _do_test_z_hop(self, hop_height: float, draw_height: float, speed: float):
        self._log(f"🧪 اختبار رفع القلم: جاري الرفع إلى Z={hop_height} مم...", "info")
        self.send_command("G90")
        self.send_command(f"G1 Z{hop_height:.2f} F{int(speed)}", wait_ok=True, timeout=5.0)
        time.sleep(1.0)
        self._log(f"🧪 إنزال القلم إلى Z={draw_height} مم (ملامسة الورقة)...", "info")
        self.send_command(f"G1 Z{draw_height:.2f} F{int(speed)}", wait_ok=True, timeout=5.0)

    def emergency_stop(self):
        """Sends M112 emergency stop and halts print."""
        self.stop_requested = True
        self.is_printing = False
        self.is_paused = False
        self._ok_event.set()
        self.send_command("M112")
        self._log("🛑 تم تنفيذ إيقاف الطوارئ (M112)! توقفت جميع الحركات.", "error")
        if self.on_print_finished:
            self.on_print_finished(False, "تم إيقاف الطباعة بواسطة أمر الطوارئ M112.")

    # --- G-Code Streaming Engine ---

    def start_print(self, gcode_content: str):
        """Starts streaming G-code lines in a background thread."""
        if not self.is_connected:
            self._log("⚠️ لا يمكن بدء الطباعة: الطابعة غير متصلة!", "error")
            return False
        if self.is_printing:
            self._log("⚠️ الطباعة قيد التشغيل بالفعل!", "warning")
            return False

        lines = [line.strip() for line in gcode_content.splitlines()]
        # Filter comments and empty lines for execution, while preserving tool change markers
        executable_lines = []
        for line in lines:
            if line.startswith("; TOOL_CHANGE_COLOR:"):
                executable_lines.append(line[2:].strip())
                continue

            c_idx = line.find(";")
            if c_idx != -1:
                cmd_part = line[:c_idx].strip()
            else:
                cmd_part = line.strip()
            if cmd_part:
                executable_lines.append(cmd_part)

        if not executable_lines:
            self._log("⚠️ ملف الـ G-Code فارغ ولا يحتوي على أوامر صالحة!", "error")
            return False

        self.is_printing = True
        self.is_paused = False
        self.stop_requested = False

        self._print_thread = threading.Thread(
            target=self._stream_worker,
            args=(executable_lines,),
            daemon=True
        )
        self._print_thread.start()
        return True

    def beep_printer_chime(self):
        """Sends a distinct 3-tone chime sequence directly to the printer buzzer (M300)."""
        def _worker():
            try:
                # Multi-tone melody on printer's physical buzzer (Ender 3 Pro / Marlin LCD)
                self.send_command("M300 S1000 P150")
                time.sleep(0.12)
                self.send_command("M300 S1500 P150")
                time.sleep(0.12)
                self.send_command("M300 S2000 P350")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def beep_printer_single(self, freq: int = 1000, duration_ms: int = 250):
        """Sends a single clean tone to the printer physical buzzer (M300)."""
        def _worker():
            try:
                self.send_command(f"M300 S{freq} P{duration_ms}")
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    @staticmethod
    def _play_beep(freq: int = 1000, duration_ms: int = 250):
        """Emits a single alert tone via PC speaker (Windows)."""
        def _worker():
            try:
                import winsound
                winsound.Beep(freq, duration_ms)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    @staticmethod
    def _play_beep_chime():
        """Emits a multi-tone alert chime (e.g. for pen swap or pause)."""
        def _worker():
            try:
                import winsound
                winsound.Beep(880, 140)
                winsound.Beep(1175, 140)
                winsound.Beep(1480, 260)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def pause_print(self):
        if self.is_printing and not self.is_paused:
            self._pause_requested = True
            self._log("⏸️ تم طلب إيقاف الطباعة مؤقتاً. جاري نقل رأس القلم إلى موضع التبديل (0, 0)...", "warning")

    def resume_print(self):
        if self.is_printing and self.is_paused:
            self.is_paused = False
            self._log("▶️ تم استئناف الطباعة. جاري رفع القلم والعودة لموضع الرسم...", "info")

    def cancel_print(self):
        if self.is_printing:
            self.stop_requested = True
            self.is_paused = False
            self._pause_requested = False
            self._ok_event.set()
            self._log("⏹️ جاري إلغاء الطباعة ورفع رأس الطباعة بأمان...", "warning")
            # Safe raise
            try:
                self.send_command("G91")
                self.send_command("G1 Z10 F600")
                self.send_command("G90")
            except Exception:
                pass

    def _stream_worker(self, lines: List[str]):
        import re
        re_coords = re.compile(r'([XYZ])([-+]?[0-9]*\.?[0-9]+)')

        total = len(lines)
        self._log(f"🚀 بدء تنفيذ الطباعة ({total:,} أمر G-Code)...", "info")

        success = True
        err_reason = ""

        current_x = 0.0
        current_y = 0.0
        current_z = 0.0

        for idx, cmd in enumerate(lines):
            if self.stop_requested:
                success = False
                err_reason = "تم إلغاء عملية الطباعة."
                break

            # Track axis positions for safe park & return
            if cmd.startswith(("G0", "G1", "G2", "G3")):
                for ax, val in re_coords.findall(cmd):
                    if ax == 'X':
                        current_x = float(val)
                    elif ax == 'Y':
                        current_y = float(val)
                    elif ax == 'Z':
                        current_z = float(val)

            # Check for tool change / pen swap event
            if cmd.startswith("TOOL_CHANGE_COLOR:") or cmd.startswith("M0"):
                col_hex = "#EF4444"
                col_name = "قلم جديد"
                if "TOOL_CHANGE_COLOR:" in cmd:
                    parts = cmd.split("TOOL_CHANGE_COLOR:", 1)[1].split("|")
                    col_hex = parts[0].strip()
                    col_name = parts[1].strip() if len(parts) > 1 else col_hex
                elif "Swap Pen to" in cmd:
                    col_name = cmd.split("Swap Pen to", 1)[1].strip()

                # Sound alert: Marlin M300 printer physical buzzer chime + Windows PC sound chime!
                self.beep_printer_chime()
                self._play_beep_chime()

                self.is_paused = True
                self._log(f"🔔 🎨 استبدال القلم المطلوب: {col_name} ({col_hex})! الرأس ينتظر عند (0, 0). اضغط متابعة بعد التركيب.", "warning")
                if self.on_tool_change_request:
                    try:
                        self.on_tool_change_request(col_hex, col_name)
                    except Exception:
                        pass

                while self.is_paused and not self.stop_requested:
                    time.sleep(0.2)
                continue

            # Check if user clicked Pause (Head moves to (0,0) and waits there!)
            if self._pause_requested:
                self._pause_requested = False
                self.is_paused = True
                return_x = current_x
                return_y = current_y
                return_z = current_z

                # 1. Lift pen safely by 10mm so ink doesn't bleed
                self.send_command(f"G1 Z{current_z + 10.0:.2f} F600 ; Safe Lift on Pause", wait_ok=True)
                # 2. Rapid move to pen swap origin (0, 0)
                self.send_command("G0 X0 Y0 F6000 ; Move head to Pen Swap Origin (0,0)", wait_ok=True)
                # 3. Lower at (0, 0) to drawing level for pen alignment
                self.send_command(f"G1 Z{current_z:.2f} F600 ; Lower at (0,0) for pen alignment", wait_ok=True)
                # 4. Sound alert beep on printer physical buzzer and Windows PC
                self.beep_printer_single(1000, 300)
                self._play_beep(1000, 280)

                self._log("⏸️ تم إيقاف الطباعة: رأس القلم ينتظر الآن عند (0, 0) لمعايرة أو استبدال القلم.", "warning")

                # Wait while paused
                while self.is_paused and not self.stop_requested:
                    time.sleep(0.2)

                if self.stop_requested:
                    success = False
                    err_reason = "تم إلغاء عملية الطباعة أثناء التوقف المؤقت."
                    break

                # RESUME ROUTINE:
                self._log("▶️ جاري رفع القلم بـ Z-Hop والعودة لنقطة الرسم بدقة...", "info")
                # 1. CRITICAL Z-Hop before moving away from (0,0) to prevent ink drag line!
                self.send_command(f"G1 Z{current_z + 10.0:.2f} F600 ; Safety Z-Hop before return", wait_ok=True)
                # 2. Rapid return to exact saved position
                self.send_command(f"G0 X{return_x:.3f} Y{return_y:.3f} F6000 ; Return to pause position", wait_ok=True)
                # 3. Lower pen back to drawing level
                self.send_command(f"G1 Z{return_z:.2f} F600 ; Lower pen to resume drawing", wait_ok=True)
                continue

            # Standard pause loop if paused externally
            while self.is_paused and not self.stop_requested:
                time.sleep(0.2)

            if self.stop_requested:
                success = False
                err_reason = "تم إلغاء عملية الطباعة."
                break

            # Send command and wait for 'ok'
            timeout = 30.0 if any(cmd.startswith(h) for h in ("G28", "M109", "M190")) else 8.0
            ok = self.send_command(cmd, wait_ok=True, timeout=timeout)

            if not ok and not self.stop_requested:
                self._log(f"⚠️ تحذير: لم يصل رد 'ok' للأمر: {cmd}", "warning")

            pct = ((idx + 1) / total) * 100.0
            if self.on_progress:
                try:
                    self.on_progress(idx + 1, total, pct)
                except Exception:
                    pass

        self.is_printing = False
        self.is_paused = False
        self._pause_requested = False

        if success and not self.stop_requested:
            self._log("🎉 اكتملت عملية الطباعة بنجاح تام! 100%", "info")
            self.beep_printer_chime()
            self._play_beep_chime()
            if self.on_print_finished:
                self.on_print_finished(True, "اكتملت الطباعة بنجاح!")
        else:
            self._log(f"⏹️ انتهت الطباعة: {err_reason}", "warning")
            if self.on_print_finished:
                self.on_print_finished(False, err_reason)
