"""
Centerline and Contour Vectorization Engine for Pen Plotter.
Extracts clean, single-line (skeletonized) paths or contour outlines from binary images.
"""
import numpy as np
import cv2
from skimage.morphology import skeletonize

class Vectorizer:
    @staticmethod
    def extract_contours(binary_img: np.ndarray, epsilon: float = 1.0):
        """
        Extracts standard vector contours (outlines) from binary image.
        Returns a list of polylines: list of list of (x, y).
        """
        contours, _ = cv2.findContours(binary_img, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_KCOS)
        polylines = []
        for cnt in contours:
            if len(cnt) < 2:
                continue
            approx = cv2.approxPolyDP(cnt, epsilon, closed=True)
            pts = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
            if len(pts) >= 2:
                # Close the loop
                pts.append(pts[0])
                polylines.append(pts)
        return polylines

    @staticmethod
    def extract_centerline(binary_img: np.ndarray, epsilon: float = 0.8):
        """
        Extracts single-stroke centerlines using topological skeletonization
        and graph tracing.
        Returns a list of polylines: list of list of (x, y).
        """
        # Convert binary 0/255 to boolean for skimage skeletonize
        bool_img = binary_img > 127
        skeleton = skeletonize(bool_img)
        skel_uint8 = (skeleton.astype(np.uint8)) * 255

        h, w = skel_uint8.shape
        visited = np.zeros((h, w), dtype=bool)
        polylines = []

        # 8-neighbor offsets
        neighbors_offsets = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]

        def get_neighbors(r, c):
            nb = []
            for dr, dc in neighbors_offsets:
                nr, nc = r + dr, c + dc
                if 0 <= nr < h and 0 <= nc < w:
                    if skel_uint8[nr, nc] > 0:
                        nb.append((nr, nc))
            return nb

        # Identify degree of each foreground pixel
        # Degree 1 = endpoint, Degree > 2 = junction, Degree 2 = internal path
        coords = np.argwhere(skel_uint8 > 0)
        if len(coords) == 0:
            return []

        endpoints = []
        internal_points = []
        for r, c in coords:
            deg = len(get_neighbors(r, c))
            if deg == 1:
                endpoints.append((r, c))
            else:
                internal_points.append((r, c))

        # Trace starting from endpoints first
        def trace_path(start_r, start_c):
            path = [(start_c, start_r)]
            visited[start_r, start_c] = True
            curr_r, curr_c = start_r, start_c

            while True:
                nxt = None
                for nr, nc in get_neighbors(curr_r, curr_c):
                    if not visited[nr, nc]:
                        nxt = (nr, nc)
                        break
                if nxt is None:
                    break
                curr_r, curr_c = nxt
                visited[curr_r, curr_c] = True
                path.append((curr_c, curr_r))
            return path

        for r, c in endpoints:
            if not visited[r, c]:
                raw_path = trace_path(r, c)
                if len(raw_path) > 1:
                    polylines.append(raw_path)

        # Trace any remaining cycles/closed loops
        for r, c in internal_points:
            if not visited[r, c]:
                raw_path = trace_path(r, c)
                if len(raw_path) > 1:
                    polylines.append(raw_path)

        # Simplify polylines using Douglas-Peucker (approxPolyDP)
        smooth_polylines = []
        for poly in polylines:
            if len(poly) < 2:
                continue
            np_pts = np.array(poly, dtype=np.int32).reshape((-1, 1, 2))
            approx = cv2.approxPolyDP(np_pts, epsilon, closed=False)
            simplified = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
            if len(simplified) >= 2:
                smooth_polylines.append(simplified)

        return smooth_polylines
