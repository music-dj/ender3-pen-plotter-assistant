"""
Printer and Export Service for Pen Plotter Assistant.
Provides export to SVG and direct vector printing via HTML/Windows print handler.
"""
import os
import tempfile
import webbrowser

class PrinterService:
    @staticmethod
    def print_svg_vector(svg_content: str, width_mm: float, height_mm: float):
        """
        Creates a temporary vector print harness and opens it directly in the system
        print dialog to ensure 100% vector scale and precision on attached printers.
        """
        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Pen Plotter Direct Print</title>
<style>
    @page {{
        size: {width_mm}mm {height_mm}mm;
        margin: 0;
    }}
    body {{
        margin: 0;
        padding: 0;
        display: flex;
        justify-content: center;
        align-items: center;
        background: #fff;
    }}
    svg {{
        width: {width_mm}mm;
        height: {height_mm}mm;
        display: block;
    }}
</style>
</head>
<body>
{svg_content}
<script>
    window.onload = function() {{
        setTimeout(function() {{
            window.print();
        }}, 400);
    }};
</script>
</body>
</html>"""
        temp_dir = tempfile.gettempdir()
        temp_html = os.path.join(temp_dir, "plotter_direct_print.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        webbrowser.open(f"file://{os.path.abspath(temp_html)}")
        return temp_html
