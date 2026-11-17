"""
Pen Plotter Drawing Assistant - Main Application Entry Point.
مساعد الرسم بالقلم عبر الطابعة - تحويل الصور إلى مسارات دقيقة بالمليمتر
"""
import sys
import os

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app_window import AppWindow

def main():
    try:
        app = AppWindow()
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
