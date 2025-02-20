import queue

from cv2 import INTER_LINEAR, ROTATE_180,ROTATE_90_CLOCKWISE, ROTATE_90_COUNTERCLOCKWISE, rotate, resize, flip
import numpy as np   # 旋转    
# 定义全局变量
allowRecording = False  # or True, depending on your requirement
frame_queue_display = queue.Queue()
frame_queue_save = queue.Queue()

def get_allowRecording():
    global allowRecording
    return allowRecording
    
def set_allowRecording(bbb):
    global allowRecording
    allowRecording = bbb

def apply_transformations(frame, scale, rotation, flip_h, flip_v):
    """应用缩放、旋转和翻转到帧"""
    # 缩放
    if scale != 1.0:
        frame = resize(frame, None, fx=scale, fy=scale, interpolation= INTER_LINEAR)

    # 旋转
    if rotation != 0:
        if rotation == 90:
            frame = rotate(frame, ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            frame = rotate(frame, ROTATE_180)
        elif rotation == 270:
            frame = rotate(frame, ROTATE_90_COUNTERCLOCKWISE)

    # 翻转
    if flip_h and flip_v:
        frame = flip(frame, -1)  # 水平和垂直翻转
    elif flip_h:
        frame = flip(frame, 1)  # 水平翻转
    elif flip_v:
        frame = flip(frame, 0)  # 垂直翻转

    return frame

def resize_frame(frame1, frame2, rgb_value):
    """调整两个图像的大小，将它们的最大宽度和最大高度作为目标，左右填充RGB值"""
    height1, width1, _ = frame1.shape
    height2, width2, _ = frame2.shape

    # 计算目标尺寸（最大高度和最大宽度）
    target_height = max(height1, height2)
    target_width = max(width1, width2)

    # 创建RGB填充背景
    new_frame1 = np.full((target_height, target_width, 3), rgb_value, dtype=np.uint8)
    new_frame2 = np.full((target_height, target_width, 3), rgb_value, dtype=np.uint8)

    # 计算左右填充的大小
    pad_left1 = (target_width - width1) // 2
    pad_right1 = target_width - width1 - pad_left1
    pad_top1 = (target_height - height1) // 2
    pad_bottom1 = target_height - height1 - pad_top1

    pad_left2 = (target_width - width2) // 2
    pad_right2 = target_width - width2 - pad_left2
    pad_top2 = (target_height - height2) // 2
    pad_bottom2 = target_height - height2 - pad_top2

    # 将原图像放入目标尺寸中
    new_frame1[pad_top1:pad_top1 + height1, pad_left1:pad_left1 + width1] = frame1
    new_frame2[pad_top2:pad_top2 + height2, pad_left2:pad_left2 + width2] = frame2

    return new_frame1, new_frame2