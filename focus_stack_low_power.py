#!/usr/bin/env python3
"""
Focus Stacking - Low Power High Efficiency Version
=================================================

低算力高效版焦点堆叠实现，针对算力消耗进行优化：

算力消耗分析：
1. 图像对齐 (ECC算法) - 高算力消耗 O(N²) - 优化为简单模板匹配
2. 小波变换 - 极高算力消耗 O(N log N) - 简化为拉普拉斯算子
3. 焦点测量 (Tenengrad) - 中等算力消耗 O(N) - 优化为简单梯度
4. 图像合并 - 中等算力消耗 O(N) - 保持原算法
5. 深度图生成 (Guo算法) - 高算力消耗 O(N³) - 简化为最大值选择
6. 灰度转换 (PCA) - 高算力消耗 O(N²) - 简化为固定权重
7. 去噪 - 中等算力消耗 O(N) - 简化或跳过
8. 像素重分配 - 低算力消耗 O(N) - 保持原算法

优化策略：
- 跳过复杂的小波变换，使用简单的拉普拉斯算子
- 简化图像对齐，使用模板匹配替代ECC
- 使用固定权重灰度转换替代PCA
- 简化焦点测量算法
- 减少不必要的平滑和滤波操作
"""

import cv2
import numpy as np
import argparse
import os
import sys
from typing import List, Tuple, Optional
import logging
import time
import warnings
warnings.filterwarnings('ignore')

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LowPowerImageAligner:
    """低算力图像对齐类 - 使用模板匹配替代ECC"""
    
    def align_images(self, images: List[np.ndarray], reference_idx: int = -1) -> List[np.ndarray]:
        """简化的图像对齐"""
        if len(images) < 2:
            return images
        
        # 选择参考图像
        if reference_idx < 0:
            reference_idx = len(images) // 2
        reference_idx = min(reference_idx, len(images) - 1)
        
        aligned_images = [None] * len(images)
        aligned_images[reference_idx] = images[reference_idx].copy()
        
        # 转换为灰度图进行对齐
        ref_gray = cv2.cvtColor(images[reference_idx], cv2.COLOR_BGR2GRAY)
        
        for i, img in enumerate(images):
            if i == reference_idx:
                continue
            
            src_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 使用简单的模板匹配进行对齐
            aligned = self._simple_align(src_gray, ref_gray, img)
            aligned_images[i] = aligned
            
        return aligned_images
    
    def _simple_align(self, src_gray: np.ndarray, ref_gray: np.ndarray, src_color: np.ndarray) -> np.ndarray:
        """简化的图像对齐 - 使用相位相关"""
        try:
            # 使用相位相关进行对齐
            h, w = src_gray.shape
            
            # 转换为浮点数
            src_float = src_gray.astype(np.float32)
            ref_float = ref_gray.astype(np.float32)
            
            # 计算相位相关
            src_fft = np.fft.fft2(src_float)
            ref_fft = np.fft.fft2(ref_float)
            
            # 计算互相关
            cross_power_spectrum = (src_fft * np.conj(ref_fft)) / (np.abs(src_fft * np.conj(ref_fft)) + 1e-8)
            correlation = np.fft.ifft2(cross_power_spectrum)
            correlation = np.real(correlation)
            
            # 找到最大相关位置
            max_loc = np.unravel_index(np.argmax(correlation), correlation.shape)
            
            # 计算偏移量
            dy = max_loc[0] if max_loc[0] < h//2 else max_loc[0] - h
            dx = max_loc[1] if max_loc[1] < w//2 else max_loc[1] - w
            
            # 如果偏移量太大，使用原始图像
            if abs(dx) > w//4 or abs(dy) > h//4:
                logger.warning(f"偏移量过大 ({dx}, {dy})，使用原始图像")
                return src_color.copy()
            
            # 应用偏移
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            aligned = cv2.warpAffine(src_color, M, (w, h))
            
            return aligned
            
        except Exception as e:
            logger.warning(f"相位相关对齐失败，使用原始图像: {e}")
            return src_color.copy()


class LowPowerFocusMeasure:
    """低算力焦点测量类 - 使用改进的拉普拉斯算子"""
    
    def compute(self, img: np.ndarray) -> np.ndarray:
        """改进的焦点测量"""
        # 使用拉普拉斯算子
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        focus_measure = np.abs(laplacian)
        
        # 增强对比度，使焦点差异更明显
        focus_measure = np.power(focus_measure, 1.5)
        
        # 平滑处理，减少噪声影响
        focus_measure = cv2.GaussianBlur(focus_measure, (5, 5), 1.0)
        
        # 归一化到0-1范围
        focus_measure = focus_measure / (np.max(focus_measure) + 1e-8)
        
        return focus_measure


class LowPowerGrayscaleConverter:
    """低算力灰度转换器 - 使用固定权重替代PCA"""
    
    def __init__(self):
        # 使用固定的标准权重，避免PCA计算
        self.weights = np.array([0.114, 0.587, 0.299], dtype=np.float32)  # BGR权重
    
    def convert(self, images: List[np.ndarray]) -> List[np.ndarray]:
        """快速灰度转换"""
        gray_images = []
        
        for img in images:
            if len(img.shape) == 3:
                # 使用固定权重进行快速转换
                gray = np.dot(img.reshape(-1, 3), self.weights).reshape(img.shape[:2])
                gray = np.clip(gray, 0, 255).astype(np.uint8)
            else:
                gray = img.copy()
            gray_images.append(gray)
        
        return gray_images


class LowPowerFocusStack:
    """低算力焦点堆叠主类"""
    
    def __init__(self, input_images: List[np.ndarray]):
        self.input_images = input_images
        self.output_image = None
        self.depthmap_image = None
        self.verbose = False
        self.reference_idx = -1
        
        # 初始化低算力组件
        self.image_aligner = LowPowerImageAligner()
        self.focus_measure = LowPowerFocusMeasure()
        self.grayscale_converter = LowPowerGrayscaleConverter()
        
        
        
    def set_verbose(self, verbose: bool):
        """设置详细输出"""
        self.verbose = verbose
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            
    def run(self) -> bool:
        """运行低算力焦点堆叠算法"""
        try:
            if len(self.input_images) < 2:
                logger.error("需要至少2张输入图像")
                return False
            
            start_time = time.time()
            logger.info(f"开始处理 {len(self.input_images)} 张图像 (低算力模式)")
            
            # 2. 简化的图像对齐
            align_start = time.time()
            logger.info("开始简化图像对齐...")
            aligned_images = self.image_aligner.align_images(self.input_images, self.reference_idx)
            align_time = time.time() - align_start
            logger.info(f"图像对齐完成: {align_time:.2f}秒")
            
            # 3. 快速灰度转换
            gray_start = time.time()
            logger.info("快速灰度转换...")
            gray_images = self.grayscale_converter.convert(aligned_images)
            gray_time = time.time() - gray_start
            logger.info(f"灰度转换完成: {gray_time:.2f}秒")
            
            # 4. 简化的焦点测量
            focus_start = time.time()
            logger.info("计算焦点测量...")
            focus_measures = []
            for gray_img in gray_images:
                focus = self.focus_measure.compute(gray_img)
                focus_measures.append(focus)
            focus_time = time.time() - focus_start
            logger.info(f"焦点测量完成: {focus_time:.2f}秒")
            
            # 5. 简化的深度图生成
            depth_start = time.time()
            logger.info("生成简化深度图...")
            self.depthmap_image = self._generate_simple_depthmap(focus_measures)
            depth_time = time.time() - depth_start
            logger.info(f"深度图生成完成: {depth_time:.2f}秒")
            
            # 6. 简化的焦点堆叠
            stack_start = time.time()
            logger.info("执行简化焦点堆叠...")
            self.output_image = self._simple_focus_stack(aligned_images, focus_measures)
            stack_time = time.time() - stack_start
            logger.info(f"焦点堆叠完成: {stack_time:.2f}秒")
            
            total_time = time.time() - start_time
            logger.info(f"总处理时间: {total_time:.2f}秒")
            
            return True
            
        except Exception as e:
            logger.error(f"处理过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _load_images(self) -> List[np.ndarray]:
        """加载输入图像"""
        images = []
        for i, file_path in enumerate(self.input_files):
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                continue
            
            img = cv2.imread(file_path)
            if img is None:
                logger.error(f"无法加载图像: {file_path}")
                continue
            
            # 确保图像尺寸一致
            if i == 0:
                target_size = img.shape[:2]
            else:
                if img.shape[:2] != target_size:
                    img = cv2.resize(img, (target_size[1], target_size[0]))
            
            images.append(img)
            logger.debug(f"加载图像 {i+1}/{len(self.input_files)}: {file_path}")
        
        return images
    
    def _generate_simple_depthmap(self, focus_measures: List[np.ndarray]) -> np.ndarray:
        """生成改进的深度图"""
        if not focus_measures:
            return np.zeros((100, 100), dtype=np.uint8)
        
        h, w = focus_measures[0].shape
        
        # 使用向量化操作提高效率
        focus_matrix = np.stack(focus_measures, axis=2)  # (h, w, num_images)
        best_indices = np.argmax(focus_matrix, axis=2)  # (h, w)
        
        # 映射到0-255范围
        if len(focus_measures) > 1:
            depthmap = (255 * best_indices / (len(focus_measures) - 1)).astype(np.uint8)
        else:
            depthmap = np.zeros((h, w), dtype=np.uint8)
        
        # 对深度图进行轻微平滑，减少噪声
        depthmap = cv2.GaussianBlur(depthmap, (3, 3), 0.5)
        
        return depthmap
    
    def _simple_focus_stack(self, color_images: List[np.ndarray], focus_measures: List[np.ndarray]) -> np.ndarray:
        """改进的焦点堆叠"""
        if not color_images or not focus_measures:
            return np.zeros((100, 100, 3), dtype=np.uint8)
        
        h, w = color_images[0].shape[:2]
        result = np.zeros((h, w, 3), dtype=np.uint8)
        
        # 创建焦点测量矩阵
        focus_matrix = np.stack(focus_measures, axis=2)  # (h, w, num_images)
        
        # 找到每个像素的最佳图像索引
        best_indices = np.argmax(focus_matrix, axis=2)  # (h, w)
        
        # 设置最小焦点阈值，避免选择模糊区域
        max_focus_values = np.max(focus_matrix, axis=2)
        min_threshold = np.percentile(max_focus_values, 10)  # 使用10%分位数作为阈值
        
        # 为每个像素选择最佳图像
        for y in range(h):
            for x in range(w):
                best_idx = best_indices[y, x]
                focus_value = focus_matrix[y, x, best_idx]
                
                # 如果焦点值太低，使用参考图像（通常是中间图像）
                if focus_value < min_threshold:
                    ref_idx = len(color_images) // 2
                    result[y, x] = color_images[ref_idx][y, x]
                else:
                    result[y, x] = color_images[best_idx][y, x]
        
        return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Focus Stacking - Low Power High Efficiency Version')
    parser.add_argument('input_files', nargs='+', help='输入图像文件')
    parser.add_argument('--output', '-o', default='output_low_power.jpg', help='输出文件')
    parser.add_argument('--depthmap', '-d', default='', help='深度图输出文件')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--reference', type=int, default=-1, help='参考图像索引')
    
    args = parser.parse_args()
    
    # 创建LowPowerFocusStack实例
    stack = LowPowerFocusStack()
    stack.set_inputs(args.input_files)
    stack.set_output(args.output)
    stack.set_depthmap(args.depthmap)
    stack.set_verbose(args.verbose)
    stack.reference_idx = args.reference
    
    # 运行算法
    success = stack.run()
    
    if success:
        print(f"\n低算力焦点堆叠完成！结果已保存到: {args.output}")
        if args.depthmap:
            print(f"深度图已保存到: {args.depthmap}")
    else:
        print("\n低算力焦点堆叠失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
