"""
Crash-proof 64-bit/32-bit Windows Drag & Drop module for Tkinter/CustomTkinter.
Replaces flawed 'windnd' library with proper 64-bit pointer handling and Unicode support.
"""
import sys
import ctypes
from ctypes import wintypes

# Define 64-bit compatible ctypes signatures
if sys.platform == "win32":
    WNDPROC_PROTO = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM
    )

    SetWindowLongPtr = ctypes.windll.user32.SetWindowLongPtrW
    SetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    SetWindowLongPtr.restype = ctypes.c_void_p

    GetWindowLongPtr = ctypes.windll.user32.GetWindowLongPtrW
    GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
    GetWindowLongPtr.restype = ctypes.c_void_p

    CallWindowProc = ctypes.windll.user32.CallWindowProcW
    CallWindowProc.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    CallWindowProc.restype = ctypes.c_ssize_t

    DragAcceptFiles = ctypes.windll.shell32.DragAcceptFiles
    DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]

    DragQueryFileW = ctypes.windll.shell32.DragQueryFileW
    DragQueryFileW.argtypes = [wintypes.WPARAM, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    DragQueryFileW.restype = wintypes.UINT

    DragFinish = ctypes.windll.shell32.DragFinish
    DragFinish.argtypes = [wintypes.WPARAM]

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4

class SafeDnD:
    def __init__(self, tk_widget, callback):
        self.widget = tk_widget
        self.callback = callback
        self.old_wndproc = None
        self._new_wndproc_ref = None
        self._hooked = False

        if sys.platform != "win32":
            return

        try:
            self._install_hook()
        except Exception as e:
            print(f"[SafeDnD] Could not hook window for drag & drop: {e}")

    def _install_hook(self):
        hwnd = self.widget.winfo_id()
        if not hwnd:
            # Try waiting for window to be realized
            self.widget.update_idletasks()
            hwnd = self.widget.winfo_id()

        if not hwnd:
            return

        DragAcceptFiles(hwnd, True)
        self.old_wndproc = GetWindowLongPtr(hwnd, GWL_WNDPROC)

        def _wndproc_handler(hwnd_val, msg, wp, lp):
            if msg == WM_DROPFILES:
                try:
                    file_count = DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
                    dropped_files = []
                    for i in range(file_count):
                        # Query path length
                        buffer_len = DragQueryFileW(wp, i, None, 0) + 1
                        buf = ctypes.create_unicode_buffer(buffer_len)
                        DragQueryFileW(wp, i, buf, buffer_len)
                        dropped_files.append(buf.value)

                    DragFinish(wp)

                    # Dispatch to Tkinter main thread safely using widget.after
                    if dropped_files and self.callback:
                        self.widget.after(0, lambda: self.callback(dropped_files))
                except Exception as ex:
                    print(f"[SafeDnD] Error processing dropped files: {ex}")

            return CallWindowProc(self.old_wndproc, hwnd_val, msg, wp, lp)

        # Keep strong reference to prevent garbage collection of ctypes callback
        self._new_wndproc_ref = WNDPROC_PROTO(_wndproc_handler)
        proc_ptr = ctypes.cast(self._new_wndproc_ref, ctypes.c_void_p)
        SetWindowLongPtr(hwnd, GWL_WNDPROC, proc_ptr)
        self._hooked = True

def hook_dropfiles_safe(widget, callback):
    return SafeDnD(widget, callback)
