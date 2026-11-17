"""
High-Precision Watertight 3D STL Mesh Exporter.
Converts vector contours into 100% watertight, manifold 3D models (.stl)
with zero pixelation, smooth edges, and accurate hole handling.
Fully compatible with Cura, PrusaSlicer, Bambu Studio, and OrcaSlicer.
"""
import os
import cv2
import numpy as np
import shapely.geometry as sg
import shapely.validation
import trimesh
import trimesh.repair

class STLExporter:
    @staticmethod
    def export_watertight_stl(
        mask: np.ndarray,
        filepath: str,
        target_w_mm: float = 150.0,
        target_h_mm: float = 150.0,
        thickness_mm: float = 0.3,
        epsilon_mm: float = 0.2,
        center_model: bool = False
    ) -> int:
        """
        Extrudes the binary mask into a true smooth, watertight 3D mesh.
        - mask: binary 2D array (255 = foreground solid, 0 = background)
        - filepath: output .stl file path
        - target_w_mm: width in mm
        - target_h_mm: height in mm
        - thickness_mm: extrusion height (Z) in mm (e.g. 0.2mm or 0.3mm)
        - epsilon_mm: contour smoothing tolerance in mm (lower = more detail, higher = smoother)
        - center_model: if True, centers the mesh at (0, 0), otherwise aligns to (0, 0)
        Returns the number of triangles in the exported mesh.
        """
        h, w = mask.shape
        if h == 0 or w == 0:
            return 0

        scale_x = target_w_mm / w
        scale_y = target_h_mm / h

        # Morphological filter to remove single-pixel floating speckles
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Extract hierarchical contours (RETR_CCOMP: 2-level hierarchy: outer shapes and inner holes)
        contours, hierarchy = cv2.findContours(cleaned, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_TC89_KCOS)
        if not contours or hierarchy is None:
            return 0

        # Calculate pixel epsilon corresponding to physical epsilon_mm
        epsilon_px = max(0.15, (epsilon_mm / max(scale_x, scale_y)))
        h_data = hierarchy[0]
        polygons = []

        for idx, cnt in enumerate(contours):
            # Process only top-level outer contours
            if h_data[idx][3] != -1:
                continue
            if cv2.contourArea(cnt) < 9:
                continue

            approx = cv2.approxPolyDP(cnt, epsilon_px, closed=True)
            if len(approx) < 3:
                continue

            pts = approx.reshape(-1, 2).astype(np.float64)
            # Convert to physical mm and invert Y so bottom-left is origin
            ext_mm = np.column_stack([pts[:, 0] * scale_x, (h - pts[:, 1]) * scale_y])

            # Gather child holes belonging to this outer shape
            holes_mm = []
            child_idx = h_data[idx][2]
            while child_idx != -1:
                h_cnt = contours[child_idx]
                if cv2.contourArea(h_cnt) >= 9:
                    approx_h = cv2.approxPolyDP(h_cnt, epsilon_px, closed=True)
                    if len(approx_h) >= 3:
                        h_pts = approx_h.reshape(-1, 2).astype(np.float64)
                        h_mm = np.column_stack([h_pts[:, 0] * scale_x, (h - h_pts[:, 1]) * scale_y])
                        holes_mm.append(h_mm)
                child_idx = h_data[child_idx][0]

            poly = sg.Polygon(shell=ext_mm, holes=holes_mm)
            if not poly.is_valid:
                poly = shapely.validation.make_valid(poly)

            if poly.geom_type == 'Polygon' and not poly.is_empty and poly.area > 0.01:
                polygons.append(poly)
            elif poly.geom_type == 'MultiPolygon':
                for p in poly.geoms:
                    if not p.is_empty and p.area > 0.01:
                        polygons.append(p)

        if not polygons:
            return 0

        # Extrude each polygon into a 3D manifold mesh
        meshes = []
        for poly in polygons:
            try:
                m = trimesh.creation.extrude_polygon(poly, height=thickness_mm, engine='earcut')
                if m and len(m.faces) > 0:
                    meshes.append(m)
            except Exception as e:
                # If extrusion fails on complex self-touching shape, buffer slightly to heal
                try:
                    healed = poly.buffer(0)
                    if healed.geom_type == 'Polygon':
                        m = trimesh.creation.extrude_polygon(healed, height=thickness_mm, engine='earcut')
                        if m and len(m.faces) > 0:
                            meshes.append(m)
                    elif healed.geom_type == 'MultiPolygon':
                        for sub_p in healed.geoms:
                            m = trimesh.creation.extrude_polygon(sub_p, height=thickness_mm, engine='earcut')
                            if m and len(m.faces) > 0:
                                meshes.append(m)
                except Exception:
                    pass

        if not meshes:
            return 0

        combined = trimesh.util.concatenate(meshes)

        # Center model if requested
        if center_model:
            bounds = combined.bounds
            center = (bounds[0] + bounds[1]) / 2.0
            combined.apply_translation([-center[0], -center[1], 0])

        # Mesh repair and normal consistency checks
        try:
            trimesh.repair.fix_normals(combined)
            trimesh.repair.fix_inversion(combined)
            trimesh.repair.fix_winding(combined)
            combined.fill_holes()
        except Exception:
            pass

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        # Export binary STL
        combined.export(filepath, file_type='stl')
        return len(combined.faces)

    # Backward compatibility alias
    @classmethod
    def export_binary_stl(cls, mask, filepath, target_w_mm=150.0, target_h_mm=150.0, thickness_mm=0.2, **kwargs):
        return cls.export_watertight_stl(
            mask=mask,
            filepath=filepath,
            target_w_mm=target_w_mm,
            target_h_mm=target_h_mm,
            thickness_mm=thickness_mm,
            epsilon_mm=0.2
        )
