"""
Core Image Preprocessing Module for Pen Plotter Vectorization.
Prepares raster images for skeletonization and contour tracing.
"""
import cv2
import numpy as np
from PIL import Image

class ImageProcessor:
    @staticmethod
    def is_color_image(img_bgr: np.ndarray, color_diff_threshold: float = 12.0) -> bool:
        """Determines if an image contains distinct color information beyond grayscale."""
        if img_bgr is None or len(img_bgr.shape) < 3:
            return False
        b = img_bgr[:, :, 0].astype(np.float32)
        g = img_bgr[:, :, 1].astype(np.float32)
        r = img_bgr[:, :, 2].astype(np.float32)
        diff = np.mean(np.abs(r - g)) + np.mean(np.abs(r - b)) + np.mean(np.abs(g - b))
        return float(diff) > color_diff_threshold

    @staticmethod
    def load_and_preprocess(image_path: str, threshold_val: int = 128, invert: bool = False, denoise: bool = False):
        """
        Loads an image, converts to grayscale, applies detail-preserving thresholding.
        Returns a binary image where foreground (lines, notes, sketches) is white (255)
        and background is black (0).
        Preserves thin handwriting, dots, and faint pencil notes without washing them out.
        """
        # Read image with unicode path support via cv2.imdecode
        with open(image_path, "rb") as f:
            bytes_data = bytearray(f.read())
        np_arr = np.asarray(bytes_data, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)
        
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")

        # Handle alpha channel if present
        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            # Replace transparent parts with white
            bgr = img[:, :, :3]
            white_bg = np.ones_like(bgr, dtype=np.uint8) * 255
            alpha_factor = alpha[:, :, np.newaxis].astype(np.float32) / 255.0
            img = (bgr * alpha_factor + white_bg * (1 - alpha_factor)).astype(np.uint8)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Gentle denoising only if explicitly requested, avoiding erasing thin notes/pencil
        if denoise:
            gray = cv2.bilateralFilter(gray, 3, 25, 25)

        # Thresholding: preserves fine pencil strokes and handwritten notes
        if threshold_val <= 0:
            # Otsu's automatic thresholding
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, binary = cv2.threshold(gray, threshold_val, 255, cv2.THRESH_BINARY)

        # Usually sketches have black/colored lines on white paper:
        # Invert so lines/strokes are 255 (foreground) and paper is 0 (background)
        if not invert:
            binary = 255 - binary
        else:
            binary = binary.copy()

        return binary, gray

    @classmethod
    def extract_color_masks(cls, image_path: str, max_colors: int = 4, threshold_val: int = 128, invert: bool = False):
        """
        Extracts separate binary masks for each distinct color in a colored image.
        If the image is grayscale or monochrome, returns a single '#000000' layer.
        If the image contains colors (e.g. red notes, blue arrows, black text),
        clusters the foreground into distinct color layers for multi-pen plotting.
        """
        with open(image_path, "rb") as f:
            bytes_data = bytearray(f.read())
        np_arr = np.asarray(bytes_data, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")

        # Ensure 3-channel BGR
        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            bgr = img[:, :, :3]
            white_bg = np.ones_like(bgr, dtype=np.uint8) * 255
            alpha_factor = alpha[:, :, np.newaxis].astype(np.float32) / 255.0
            img_bgr = (bgr * alpha_factor + white_bg * (1 - alpha_factor)).astype(np.uint8)
        elif len(img.shape) == 3:
            img_bgr = img
        else:
            img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        binary_total, _ = cls.load_and_preprocess(image_path, threshold_val=threshold_val, invert=invert)

        # If not a color image, return single primary black mask
        if not cls.is_color_image(img_bgr):
            return {"#000000": binary_total}

        # For color images: cluster foreground pixels into distinct colors
        fg_coords = np.where(binary_total > 127)
        if len(fg_coords[0]) < 100:
            return {"#000000": binary_total}

        fg_pixels = img_bgr[fg_coords].astype(np.float32)
        n_clusters = min(max_colors, max(2, len(fg_pixels) // 500))

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 15, 1.0)
        try:
            ret, labels, centers = cv2.kmeans(fg_pixels, n_clusters, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
            labels = labels.flatten()
            centers = np.uint8(centers)

            color_masks = {}
            h, w = binary_total.shape

            for c_idx in range(n_clusters):
                cluster_pixels_idx = np.where(labels == c_idx)[0]
                if len(cluster_pixels_idx) < 30:  # Ignore tiny noise cluster
                    continue

                b, g, r = centers[c_idx]
                hex_col = f"#{r:02X}{g:02X}{b:02X}"

                # Snap very dark colors to black for clean plotting
                if r < 40 and g < 40 and b < 40:
                    hex_col = "#000000"

                mask_c = np.zeros((h, w), dtype=np.uint8)
                sub_y = fg_coords[0][cluster_pixels_idx]
                sub_x = fg_coords[1][cluster_pixels_idx]
                mask_c[sub_y, sub_x] = 255

                if hex_col in color_masks:
                    color_masks[hex_col] = cv2.bitwise_or(color_masks[hex_col], mask_c)
                else:
                    color_masks[hex_col] = mask_c

            if color_masks:
                return color_masks

        except Exception:
            pass

        return {"#000000": binary_total}
