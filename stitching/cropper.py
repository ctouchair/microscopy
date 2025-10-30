from collections import namedtuple

import cv2 as cv
import numpy as np

from .blender import Blender
from .stitching_error import StitchingError


class Rectangle(namedtuple("Rectangle", "x y width height")):
    __slots__ = ()

    @property
    def area(self):
        return self.width * self.height

    @property
    def corner(self):
        return (self.x, self.y)

    @property
    def size(self):
        return (self.width, self.height)

    @property
    def x2(self):
        return self.x + self.width

    @property
    def y2(self):
        return self.y + self.height

    def times(self, x):
        return Rectangle(*(int(round(i * x)) for i in self))

    def draw_on(self, img, color=(0, 0, 255), size=1):
        if len(img.shape) == 2:
            img = cv.cvtColor(img, cv.COLOR_GRAY2RGB)
        start_point = (self.x, self.y)
        end_point = (self.x2 - 1, self.y2 - 1)
        cv.rectangle(img, start_point, end_point, color, size)
        return img


class Cropper:
    DEFAULT_CROP = True

    def __init__(self, crop=DEFAULT_CROP):
        self.do_crop = crop
        self.overlapping_rectangles = []
        self.cropping_rectangles = []

    def prepare(self, imgs, masks, corners, sizes):
        if self.do_crop:
            mask = self.estimate_panorama_mask(imgs, masks, corners, sizes)
            lir = self.estimate_largest_interior_rectangle(mask)
            corners = self.get_zero_center_corners(corners)
            rectangles = self.get_rectangles(corners, sizes)
            self.overlapping_rectangles = self.get_overlaps(rectangles, lir)
            self.intersection_rectangles = self.get_intersections(
                rectangles, self.overlapping_rectangles
            )

    def crop_images(self, imgs, aspect=1):
        for idx, img in enumerate(imgs):
            yield self.crop_img(img, idx, aspect)

    def crop_img(self, img, idx, aspect=1):
        if self.do_crop:
            intersection_rect = self.intersection_rectangles[idx]
            scaled_intersection_rect = intersection_rect.times(aspect)
            cropped_img = self.crop_rectangle(img, scaled_intersection_rect)
            return cropped_img
        return img

    def crop_rois(self, corners, sizes, aspect=1):
        if self.do_crop:
            scaled_overlaps = [r.times(aspect) for r in self.overlapping_rectangles]
            cropped_corners = [r.corner for r in scaled_overlaps]
            cropped_corners = self.get_zero_center_corners(cropped_corners)
            cropped_sizes = [r.size for r in scaled_overlaps]
            return cropped_corners, cropped_sizes
        return corners, sizes

    @staticmethod
    def estimate_panorama_mask(imgs, masks, corners, sizes):
        _, mask = Blender.create_panorama(imgs, masks, corners, sizes)
        return mask

    def estimate_largest_interior_rectangle(self, mask):
        contours, hierarchy = cv.findContours(mask, cv.RETR_TREE, cv.CHAIN_APPROX_NONE)
        
        if not hierarchy.shape == (1, 1, 4) or not np.all(hierarchy == -1):
            raise StitchingError(
                "Invalid Contour. Run with --no-crop"
            )
        
        # 方法1: 使用距离变换找到最大矩形
        dist_transform = cv.distanceTransform(mask, cv.DIST_L2, 5)
        
        # 找到距离变换的最大值点作为矩形中心候选
        _, max_val, _, max_loc = cv.minMaxLoc(dist_transform)
        
        # 从中心点向外扩展寻找最大矩形
        best_rect = None
        max_area = 0
        
        # 多个候选中心点
        h, w = mask.shape
        centers = [
            (w//2, h//2),  # 中心
            max_loc,       # 距离变换最大值点
            (w//3, h//3), (2*w//3, h//3),  # 其他采样点
            (w//3, 2*h//3), (2*w//3, 2*h//3)
        ]
        
        for cx, cy in centers:
            if mask[cy, cx] == 0:
                continue
                
            # 从中心向四个方向扩展
            left = cx
            while left > 0 and mask[cy, left-1] > 0:
                left -= 1
            
            right = cx
            while right < w-1 and mask[cy, right+1] > 0:
                right += 1
            
            top = cy
            while top > 0 and mask[top-1, cx] > 0:
                top -= 1
            
            bottom = cy
            while bottom < h-1 and mask[bottom+1, cx] > 0:
                bottom += 1
            
            # 验证矩形内所有点都在mask内
            rect_width = right - left + 1
            rect_height = bottom - top + 1
            
            # 尝试不同的矩形大小
            for scale in [1.0, 0.95, 0.9, 0.85, 0.8]:
                w_scaled = int(rect_width * scale)
                h_scaled = int(rect_height * scale)
                
                l = cx - w_scaled // 2
                r = l + w_scaled
                t = cy - h_scaled // 2
                b = t + h_scaled
                
                # 确保在边界内
                if l >= 0 and r < w and t >= 0 and b < h:
                    # 检查矩形内是否全部有效
                    roi = mask[t:b, l:r]
                    if np.all(roi > 0):
                        area = w_scaled * h_scaled
                        if area > max_area:
                            max_area = area
                            best_rect = (l, t, w_scaled, h_scaled)
        
        if best_rect is None:
            # 降级方案: 返回一个保守的小矩形
            h, w = mask.shape
            best_rect = (w//4, h//4, w//2, h//2)
        return Rectangle(*best_rect)


    # def estimate_largest_interior_rectangle(self, mask):
    #     # largestinteriorrectangle is only imported if cropping
    #     # is explicitly desired (needs some time to compile at the first run!)
    #     import largestinteriorrectangle

    #     contours, hierarchy = cv.findContours(mask, cv.RETR_TREE, cv.CHAIN_APPROX_NONE)
    #     if not hierarchy.shape == (1, 1, 4) or not np.all(hierarchy == -1):
    #         raise StitchingError(
    #             "Invalid Contour. Run with --no-crop (using the stitch interface), crop=false (using the stitcher class) or Cropper(False) (using the cropper class)"  # noqa: E501
    #         )
    #     contour = contours[0][:, 0, :]

    #     lir = largestinteriorrectangle.lir(mask > 0, contour)
    #     lir = Rectangle(*lir)
    #     return lir

    @staticmethod
    def get_zero_center_corners(corners):
        min_corner_x = min([corner[0] for corner in corners])
        min_corner_y = min([corner[1] for corner in corners])
        return [(x - min_corner_x, y - min_corner_y) for x, y in corners]

    @staticmethod
    def get_rectangles(corners, sizes):
        rectangles = []
        for corner, size in zip(corners, sizes):
            rectangle = Rectangle(*corner, *size)
            rectangles.append(rectangle)
        return rectangles

    @staticmethod
    def get_overlaps(rectangles, lir):
        return [Cropper.get_overlap(r, lir) for r in rectangles]

    @staticmethod
    def get_overlap(rectangle1, rectangle2):
        x1 = max(rectangle1.x, rectangle2.x)
        y1 = max(rectangle1.y, rectangle2.y)
        x2 = min(rectangle1.x2, rectangle2.x2)
        y2 = min(rectangle1.y2, rectangle2.y2)
        if x2 < x1 or y2 < y1:
            raise StitchingError("Rectangles do not overlap!")
        return Rectangle(x1, y1, x2 - x1, y2 - y1)

    @staticmethod
    def get_intersections(rectangles, overlapping_rectangles):
        return [
            Cropper.get_intersection(r, overlap_r)
            for r, overlap_r in zip(rectangles, overlapping_rectangles)
        ]

    @staticmethod
    def get_intersection(rectangle, overlapping_rectangle):
        x = abs(overlapping_rectangle.x - rectangle.x)
        y = abs(overlapping_rectangle.y - rectangle.y)
        width = overlapping_rectangle.width
        height = overlapping_rectangle.height
        return Rectangle(x, y, width, height)

    @staticmethod
    def crop_rectangle(img, rectangle):
        return img[rectangle.y : rectangle.y2, rectangle.x : rectangle.x2]
