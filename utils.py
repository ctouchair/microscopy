import cv2
import os
import numpy as np
import json
from focus_stack_low_power import LowPowerFocusStack

def stitch_images(images):
    """
    拼接图像函数，支持3x3网格拼接实现400%画幅
    """
    # 创建 Stitcher 对象
    stitcher = cv2.Stitcher_create()

    # 拼接图片
    status, stitched_image = stitcher.stitch(images)

    # 判断拼接是否成功
    if status == cv2.Stitcher_OK:
        return stitched_image
    else:
        return None


def crop_center_expanding_rect(image, target_ratio=4/3):
    """
    从图像中心最大区域开始，按照4:3比例逐渐缩小矩形，当遇到黑边时停止
    
    参数:
    - image_path: 输入图像路径
    - output_path: 输出裁剪图像保存路径
    - target_ratio: 目标宽高比，默认4:3
    """
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 获取图像中心点
    h, w = gray.shape
    center_y, center_x = h // 2, w // 2
    
    real_ratio = w/h
    if real_ratio >= target_ratio:
        max_w = int(center_y*target_ratio)
    else:
        max_w = center_x
    
    best_rect = None
    
    for size_w in range(max_w, 0, -20):  # 每次增加2像素
        rect_width = size_w
        rect_height = int(size_w / target_ratio)
        
        # 计算矩形边界
        left = center_x - rect_width
        right = center_x + rect_width
        top = center_y - rect_height
        bottom = center_y + rect_height
        
        # 检查是否超出图像边界
        if size_w <= 2000  :
            print(f"达到单张图像边界，停止收缩。最终尺寸: {rect_width}x{rect_height}")
            break
        # 检查矩形区域内是否有黑色像素（灰度值为0）
        rect_region = gray[top:bottom+1, left:right+1]
        black_pixels = np.sum(rect_region == 0)
        if black_pixels == 0:
            print(f"遇到黑边，停止扩展。最终尺寸: {rect_width*2}x{rect_height*2}")
            break
        # 更新最佳矩形
        best_rect = (left, top, right, bottom)
    
    # 如果找到了有效矩形，进行裁剪
    if best_rect:
        left, top, right, bottom = best_rect
        # 裁剪原始图像
        cropped = image[top:bottom, left:right]
        return cropped
    else:
        print("未找到合适的矩形区域！")
        return None




def get_translation_shift(points1, points2):
    points1 = np.array(points1)
    points2 = np.array(points2)

    # 计算每个点到另一组所有点的距离
    min_distances = []
    for p1 in points1:
        # 计算 p1 到 points2 中每个点的距离
        distances = np.linalg.norm(points2 - p1, axis=1)
        # 记录最小距离
        min_distances.append(np.min(distances))

    # 找出第一组所有点之间的最小距离
    min_distance = np.min(min_distances)
    return min_distance


def findHomography(image_1_kp, image_2_kp, matches):
    image_1_points = np.zeros((len(matches), 1, 2), dtype=np.float32)
    image_2_points = np.zeros((len(matches), 1, 2), dtype=np.float32)

    for i in range(0,len(matches)):
        image_1_points[i] = image_1_kp[matches[i].queryIdx].pt
        image_2_points[i] = image_2_kp[matches[i].trainIdx].pt


    homography, mask = cv2.findHomography(image_1_points, image_2_points, cv2.RANSAC, ransacReprojThreshold=2.0)

    return homography


def focus_stack(images):
    stack = LowPowerFocusStack(images)
    stack.set_verbose(False)
    success = stack.run()
    if success:
        return stack.output_image, stack.depthmap_image
    else:
        return None, None




def count_cells(image, pixel_size=0.09):
    """
    细胞计数函数
    
    参数:
    - image: 输入图像
    - pixel_size: 每个像素对应的实际尺寸 (μm/pixel)
    
    返回:
    - annotated_image: 标注了细胞的图像
    - cell_count: 细胞数量
    - avg_diameter: 平均细胞直径 (μm)
    """
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 高斯模糊去噪
    blurred = cv2.GaussianBlur(gray, (9, 9), 2)
    
    # 使用霍夫圆检测识别细胞
    circles = cv2.HoughCircles(
        blurred, 
        cv2.HOUGH_GRADIENT, 
        dp=1.2, 
        minDist=30,  # 细胞间最小距离
        param1=50, 
        param2=30, 
        minRadius=10,  # 最小细胞半径
        maxRadius=100  # 最大细胞半径
    )
    
    annotated_image = image.copy()
    cell_count = 0
    total_diameter = 0
    
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        cell_count = len(circles)
        
        # 绘制检测到的细胞
        for i, (x, y, r) in enumerate(circles):
            # 计算实际直径 (μm)
            diameter_um = 2 * r * pixel_size
            total_diameter += diameter_um
            
            # 绘制圆形边界
            cv2.circle(annotated_image, (x, y), r, (0, 255, 0), 2)
            # 绘制中心点
            cv2.circle(annotated_image, (x, y), 2, (0, 0, 255), 3)
            # 添加编号
            cv2.putText(annotated_image, str(i+1), (x-10, y-r-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # 计算平均直径
        avg_diameter = total_diameter / cell_count if cell_count > 0 else 0
        
        # 在图像上添加统计信息
        info_text = f"Cells: {cell_count}, Avg Diameter: {avg_diameter:.1f}um"
        cv2.putText(annotated_image, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(annotated_image, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
        
        print(f"检测到 {cell_count} 个细胞")
        print(f"平均直径: {avg_diameter:.2f} μm")
        
        return annotated_image, cell_count, avg_diameter
    else:
        print("未检测到细胞")
        # 在图像上添加"未检测到细胞"的信息
        cv2.putText(annotated_image, "No cells detected", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return annotated_image, 0, 0.0


def load_fused_perspective_transform(fused_params_json_path='fused_perspective_transform_params.json'):
    """
    使用融合后的单一透视变换矩阵对图像进行变换
    
    Args:
        image_path: 输入图像路径
        fused_params_json_path: 融合参数文件路径
    """
    # 加载融合参数
    try:
        with open(fused_params_json_path, 'r', encoding='utf-8') as f:
            params = json.load(f)
        print(f"✓ 成功加载融合透视变换参数: {fused_params_json_path}")
    except FileNotFoundError:
        print(f"错误: 找不到融合参数文件 {fused_params_json_path}")
        return None
    except Exception as e:
        print(f"错误: 加载融合参数文件失败 - {e}")
        return None

    fused_params = params['fused_perspective_transform']
    fused_matrix = np.array(fused_params['perspective_matrix'], dtype=np.float32)
    output_size = tuple(fused_params['output_size'])
    return fused_matrix, output_size
