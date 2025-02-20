from pathlib import Path
import queue
import time
import cv2
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
import cv2
import numpy as np
from numpy import full, uint8, hstack
from PIL import Image, ImageTk
from os import getcwd, path
from VideoRecording import AudioThread, VideoThread
from infrared_camera import InfraredCamera
from datetime import datetime
import sys
import threading
import pyaudio
import wave
import subprocess
import os
import globals

# 定义一个类来重定向stdout到Tkinter Text控件
class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')

    def flush(self):
        pass  # 需要定义flush方法，但可以不做任何操作

# 
class DualCameraApp:
    def __init__(self, root, sdk_path):
        self.root = root
        self.root.title("双摄像头录制")
        self.root.geometry("1024x768")  # 设置窗口尺寸为1024x768

        self.target_height = 0
        self.target_width = 0
        self.valid_rgb_value = (255,182,193)  # 默认灰度值（RGB三通道）dd
        self.start_time = None  # 用于记录开始录制的时间
        self.elapsed_time = 0  # 已录制时间
        # 默认帧率
        self.frame_rate = 30
        self.recoding_time = None
        # 初始化红外和USB摄像头的变换参数
        self.ir_scale = 1.0
        self.ir_rotation = 0
        self.ir_flip_horizontal = False
        self.ir_flip_vertical = False

        self.usb_scale = 0.5
        self.usb_rotation = 0
        self.usb_flip_horizontal = False
        self.usb_flip_vertical = False

        # 创建一个事件对象，用于线程间通信
        self.event = threading.Event()

        # 创建主框架
        main_frame = tk.Frame(root)
        main_frame.pack(padx=5, pady=5, fill='both', expand=True)
        # 创建视频显示区域
        self.video_label = tk.Label(main_frame)
        self.video_label.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')
        # 创建设置控制区域
        settings_frame = tk.LabelFrame(main_frame, text="设置控制")
        settings_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        # 添加视频格式选择
        format_frame = tk.LabelFrame(settings_frame, text="视频格式")
        format_frame.grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.video_format = tk.StringVar(value="mp4")
        self.mp4_radio = tk.Radiobutton(format_frame, text="MP4", variable=self.video_format, value="mp4")
        self.mp4_radio.pack(anchor='w', padx=2)
        self.avi_radio = tk.Radiobutton(format_frame, text="AVI", variable=self.video_format, value="avi")
        self.avi_radio.pack(anchor='w', padx=2)
        # 添加帧率调整控件
        framerate_frame = tk.LabelFrame(settings_frame, text="帧率调整")
        framerate_frame.grid(row=0, column=1, padx=5, pady=5, sticky='w')
        framerate_label = tk.Label(framerate_frame, text="录制帧率 (FPS):")
        framerate_label.pack(side=tk.LEFT, padx=2)
        self.framerate_scale = tk.Scale(framerate_frame, from_=1, to=30, orient=tk.HORIZONTAL, length=150, command=self.on_framerate_change)
        self.framerate_scale.set(self.frame_rate)  # 设置默认值
        self.framerate_scale.pack(side=tk.LEFT, padx=2)
        # 添加保存路径选择按钮
        save_path_frame = tk.LabelFrame(settings_frame, text="保存路径")
        save_path_frame.grid(row=0, column=2, padx=5, pady=5, sticky='w')
        save_path_label = tk.Label(save_path_frame, text="保存文件夹:")
        save_path_label.pack(side=tk.LEFT, padx=2)
        self.save_path = tk.StringVar()
        self.save_path_entry = tk.Entry(save_path_frame, textvariable=self.save_path, width=30)
        self.save_path_entry.pack(side=tk.LEFT, padx=2)
        self.browse_button = tk.Button(save_path_frame, text="浏览", command=self.browse_save_path)
        self.browse_button.pack(side=tk.LEFT)
        # 添加RGB值输入框
        rgb_value_frame = tk.LabelFrame(settings_frame, text="RGB值输入")
        rgb_value_frame.grid(row=0, column=3, padx=5, pady=5, sticky='w')
        rgb_value_label = tk.Label(rgb_value_frame, text="输入RGB值 (0-255):")
        rgb_value_label.pack(side=tk.LEFT, padx=2)
        self.rgb_value = tk.StringVar(value="255,182,193")  # 默认RGB值为(128, 128, 128)
        self.rgb_value_entry = tk.Entry(rgb_value_frame, textvariable=self.rgb_value, width=15)
        self.rgb_value_entry.pack(side=tk.LEFT, padx=2)
        # 麦克风设备选择
        audio_device_frame = tk.Frame(settings_frame)
        audio_device_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky='ew')
        self.audio_device_label = tk.Label(audio_device_frame, text="选择麦克风设备:")
        self.audio_device_label.pack(side=tk.LEFT, padx=5)
        # 获取可用麦克风设备列表
        self.microphone_devices = self.get_microphone_devices()
        self.audio_device_var = tk.StringVar(value=self.microphone_devices[0] if self.microphone_devices else "未检测到麦克风")
        self.audio_device_menu = tk.OptionMenu(audio_device_frame, self.audio_device_var, *self.microphone_devices)
        self.audio_device_menu.pack(side=tk.LEFT)
        # 添加摄像头控制区域
        camera_controls_frame = tk.LabelFrame(main_frame, text="摄像头控制")
        camera_controls_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        # 在摄像头控制区域内添加红外和USB控制
        self.add_ir_controls(camera_controls_frame)
        self.add_usb_controls(camera_controls_frame)
        # 创建录制控制按钮
        button_frame = tk.Frame(main_frame)
        button_frame.grid(row=3, column=0, padx=5, pady=5, sticky='w')
        self.start_button = tk.Button(button_frame, text="开始录制", command=self.start_recording)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(button_frame, text="停止录制", command=self.stop_recording, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        # 创建录制状态和时间显示
        status_frame = tk.Frame(main_frame)
        status_frame.grid(row=3, column=1, padx=5, pady=5, sticky='e')
        self.recording_status_label = tk.Label(status_frame, text="当前状态: 停止录制", fg="green")
        self.recording_status_label.pack(side=tk.LEFT, padx=5)
        self.recording_time_label = tk.Label(status_frame, text="录制时间: 00:00", font=("Arial", 12))
        self.recording_time_label.pack(side=tk.LEFT, padx=20)
        # 初始化 USB 摄像头
        self.usb_cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # 根据实际情况调整索引
        if not self.usb_cap.isOpened():
            messagebox.showwarning("警告", "未检测到 USB 摄像头")
            self.usb_cap = None
        # 初始化红外摄像头
        try:
            self.ir_camera = InfraredCamera(sdk_path)
        except Exception as e:
            messagebox.showwarning("警告", f"初始化红外摄像头失败: {str(e)}\n左侧画面将显示为蓝色")
            self.ir_camera = None
        self.out = None  # 用于保存录制视频
        self.destroyed = False  # 标志，防止多次调用 destroy

        # 启动视频保存线程
        self.update_thread = threading.Thread(target=self.read_frames_save)
        self.update_thread.daemon = True  
        self.update_thread.start()

        self.last_frame_time = time.time()  # 记录上一次显示帧的时间
        self.frame_period = 1.0 / self.frame_rate  # 每帧的最大允许周期（秒）
        self.frames_skipped = 0  # 记录跳过的帧数
        # # 启动视频流更新
        self.update_frame()

    def get_microphone_devices(self):
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        
        # 存储麦克风设备
        microphone_devices = []
        
        for i in range(device_count):
            device_info = p.get_device_info_by_index(i)
            # 如果设备是输入设备并且支持麦克风
            if device_info['maxInputChannels'] > 0:
                microphone_devices.append(device_info['name'])
        
        p.terminate()
        
        # 返回麦克风设备列表
        return microphone_devices

    def add_ir_controls(self, parent):
        """添加模块一：红外设备控制"""
        ir_control_frame = tk.LabelFrame(parent, text="红外设备控制")
        ir_control_frame.pack(side=tk.LEFT, padx=5, pady=5, fill='both', expand=True)

        # 缩放
        scale_label = tk.Label(ir_control_frame, text="缩放:")
        scale_label.grid(row=0, column=0, padx=5, pady=2, sticky='w')
        self.ir_scale_slider = tk.Scale(ir_control_frame, from_=0.5, to=2.0, resolution=0.1, orient=tk.HORIZONTAL, length=150, command=self.on_ir_scale_change)
        self.ir_scale_slider.set(self.ir_scale)
        self.ir_scale_slider.grid(row=0, column=1, padx=5, pady=2)

        # 旋转
        rotate_label = tk.Label(ir_control_frame, text="旋转:")
        rotate_label.grid(row=1, column=0, padx=5, pady=2, sticky='w')
        self.ir_rotation_var = tk.StringVar(value="0")
        self.ir_rotation_menu = tk.OptionMenu(ir_control_frame, self.ir_rotation_var, "0", "90", "180", "270", command=self.on_ir_rotation_change)
        self.ir_rotation_menu.grid(row=1, column=1, padx=5, pady=2, sticky='w')

        # 翻转
        flip_label = tk.Label(ir_control_frame, text="翻转:")
        flip_label.grid(row=2, column=0, padx=5, pady=2, sticky='w')
        self.ir_flip_h_var = tk.IntVar()
        self.ir_flip_v_var = tk.IntVar()
        self.ir_flip_h_cb = tk.Checkbutton(ir_control_frame, text="水平翻转", variable=self.ir_flip_h_var, command=self.on_ir_flip_change)
        self.ir_flip_h_cb.grid(row=2, column=1, padx=5, pady=2, sticky='w')
        self.ir_flip_v_cb = tk.Checkbutton(ir_control_frame, text="垂直翻转", variable=self.ir_flip_v_var, command=self.on_ir_flip_change)
        self.ir_flip_v_cb.grid(row=2, column=2, padx=5, pady=2, sticky='w')

    def add_usb_controls(self, parent):
        """添加模块二：USB设备控制"""
        usb_control_frame = tk.LabelFrame(parent, text="USB设备控制")
        usb_control_frame.pack(side=tk.LEFT, padx=5, pady=5, fill='both', expand=True)

        # 缩放
        scale_label = tk.Label(usb_control_frame, text="缩放:")
        scale_label.grid(row=0, column=0, padx=5, pady=2, sticky='w')
        self.usb_scale_slider = tk.Scale(usb_control_frame, from_=0.2, to=2.0, resolution=0.1, orient=tk.HORIZONTAL, length=150, command=self.on_usb_scale_change)
        self.usb_scale_slider.set(self.usb_scale)
        self.usb_scale_slider.grid(row=0, column=1, padx=5, pady=2)

        # 旋转
        rotate_label = tk.Label(usb_control_frame, text="旋转:")
        rotate_label.grid(row=1, column=0, padx=5, pady=2, sticky='w')
        self.usb_rotation_var = tk.StringVar(value="0")
        self.usb_rotation_menu = tk.OptionMenu(usb_control_frame, self.usb_rotation_var, "0", "90", "180", "270", command=self.on_usb_rotation_change)
        self.usb_rotation_menu.grid(row=1, column=1, padx=5, pady=2, sticky='w')

        # 翻转
        flip_label = tk.Label(usb_control_frame, text="翻转:")
        flip_label.grid(row=2, column=0, padx=5, pady=2, sticky='w')
        self.usb_flip_h_var = tk.IntVar()
        self.usb_flip_v_var = tk.IntVar()
        self.usb_flip_h_cb = tk.Checkbutton(usb_control_frame, text="水平翻转", variable=self.usb_flip_h_var, command=self.on_usb_flip_change)
        self.usb_flip_h_cb.grid(row=2, column=1, padx=5, pady=2, sticky='w')
        self.usb_flip_v_cb = tk.Checkbutton(usb_control_frame, text="垂直翻转", variable=self.usb_flip_v_var, command=self.on_usb_flip_change)
        self.usb_flip_v_cb.grid(row=2, column=2, padx=5, pady=2, sticky='w')

    def on_ir_scale_change(self, val):
        """实时更新红外画面的缩放比例"""
        self.ir_scale = float(val)
        print(f"红外画面缩放比例已设置为: {self.ir_scale}")

    def on_ir_rotation_change(self, val):
        """实时更新红外画面的旋转角度"""
        self.ir_rotation = int(val)
        print(f"红外画面旋转角度已设置为: {self.ir_rotation}°")

    def on_ir_flip_change(self):
        """实时更新红外画面的翻转状态"""
        self.ir_flip_horizontal = bool(self.ir_flip_h_var.get())
        self.ir_flip_vertical = bool(self.ir_flip_v_var.get())
        print(f"红外画面翻转状态已设置为: 水平={self.ir_flip_horizontal}, 垂直={self.ir_flip_vertical}")

    def on_usb_scale_change(self, val):
        """实时更新USB画面的缩放比例"""
        self.usb_scale = float(val)
        print(f"USB画面缩放比例已设置为: {self.usb_scale}")

    def on_usb_rotation_change(self, val):
        """实时更新USB画面的旋转角度"""
        self.usb_rotation = int(val)
        print(f"USB画面旋转角度已设置为: {self.usb_rotation}°")

    def on_usb_flip_change(self):
        """实时更新USB画面的翻转状态"""
        self.usb_flip_horizontal = bool(self.usb_flip_h_var.get())
        self.usb_flip_vertical = bool(self.usb_flip_v_var.get())
        print(f"USB画面翻转状态已设置为: 水平={self.usb_flip_horizontal}, 垂直={self.usb_flip_vertical}")

    def on_framerate_change(self, val):
        """实时更新帧率值"""
        self.frame_rate = int(float(val))
        print(f"录制帧率已设置为: {self.frame_rate} FPS")

    def on_rgb_value_change(self, *args):
        """实时验证和更新RGB值"""
        rgb_value_str = self.rgb_value.get()
        try:
            rgb_values = tuple(map(int, rgb_value_str.split(',')))
            if len(rgb_values) != 3 or any(not (0 <= val <= 255) for val in rgb_values):
                raise ValueError
            self.valid_rgb_value = rgb_values
            self.rgb_value_entry.config(bg="white")
        except ValueError:
            self.rgb_value_entry.config(bg="red")
            # 如果需要，可以添加额外的提示，如显示错误信息
            # messagebox.showerror("错误", "请输入有效的RGB值 (0-255, 0-255, 0-255)")

    def read_frames_save(self):
        frame_count = 0
        recording_start_time = None
        target_frame_count = 0
        while not self.destroyed:
            target_frame_count = 0
            frame_count = 0
            frame_usb = self._get_usb_frame()
            frame_ir = self._get_ir_frame()
            try:
                globals.frame_queue_display.put((frame_ir, frame_usb), timeout=0.1)
            except queue.Full:
                pass
            # 如果开始录制且is_recording为True，清空frame_queue_save队列
            if recording_start_time is None:
                recording_start_time = time.time()
            current_time = time.time()
            elapsed_time = current_time - recording_start_time
            target_frame_count = int(elapsed_time * self.frame_rate)
            # 更新frame_queue_display队列以self.frame_rate的fps持续更新
            while not self.destroyed and frame_count < target_frame_count:
                frame_usb = self._get_usb_frame()
                frame_ir = self._get_ir_frame()
                try:
                    # 更新frame_queue_display
                    globals.frame_queue_display.put((frame_ir, frame_usb), timeout=0.1)
                    frame_count += 1
                    # 当切换为录制状态时，清空frame_queue_save
                    if globals.allowRecording:
                        # 更新frame_queue_save
                        globals.frame_queue_save.put((frame_ir,frame_usb), timeout=0.1)
                    # 统计实际帧率并动态调整
                    if frame_count % 30 == 0:
                        actual_fps = frame_count / elapsed_time
                        if actual_fps < self.frame_rate * 0.9:
                            # 如果帧率过低，减少处理延迟
                            sleep_time = max(0, sleep_time - 0.001)
                        elif actual_fps > self.frame_rate * 1.1:
                            # `如果帧率过高，增加适当延迟`
                            sleep_time += 0.001
                except queue.Full:
                    # 队列满时，稍等并重试
                    time.sleep(0.001)
                    continue
                # 计算理想的下一帧时间
                next_frame_time = recording_start_time + (frame_count + 1) / self.frame_rate
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def _get_usb_frame(self):
        if self.usb_cap and self.usb_cap.isOpened():
            ret, frame = self.usb_cap.read()
            if ret:
                return frame
        return full((500, 880, 3), (255, 182, 193), dtype=uint8)

    def _get_ir_frame(self):
        if self.ir_camera:
            frame = self.ir_camera.get_latest_frame()
            if frame is not None:
                return frame
        return full((480, 640, 3), (144, 238, 144), dtype=uint8)

    def update_frame(self):
        if not globals.frame_queue_display.empty():
            # 获取帧并进行预处理
            if globals.frame_queue_display.qsize() > 1:
                    globals.frame_queue_display.get()    
            else:  
                # print(f'globals.frame_queue_display.qsize(){globals.frame_queue_display.qsize()}')
                frame_ir, frame_usb = globals.frame_queue_display.get()
                frame_ir = globals.apply_transformations(frame_ir, self.ir_scale, self.ir_rotation, self.ir_flip_horizontal, self.ir_flip_vertical)
                frame_usb = globals.apply_transformations(frame_usb, self.usb_scale, self.usb_rotation, self.usb_flip_horizontal, self.usb_flip_vertical)
                rgb_value = self.valid_rgb_value if hasattr(self, 'valid_rgb_value') else (128, 128, 128)
                frame_ir, frame_usb = globals.resize_frame(frame_ir, frame_usb, rgb_value)
                combined_frame = hstack((frame_ir, frame_usb))
                self.target_width,self.target_height = combined_frame.shape[1],combined_frame.shape[0]

                # 转换颜色从 BGR 到 RGB
                combined_rgb = cv2.cvtColor(combined_frame, cv2.COLOR_BGR2RGB)
                # 转换为 PIL 图像并处理缩放
                img = Image.fromarray(combined_rgb)
                max_width = 1024
                img_width, img_height = img.size

                # 判断图像宽度是否超过 1024px并进行缩放 
                if img_width > max_width:
                    scale_ratio = max_width / img_width
                    new_height = int(img_height * scale_ratio)
                    img = img.resize((max_width, new_height), Image.LANCZOS)

                # 转换为 Tkinter 可显示的图片
                img_tk = ImageTk.PhotoImage(image=img)

                # 只在图像发生变化时才更新
                if not hasattr(self, 'current_img') or self.current_img != img_tk:
                    self.current_img = img_tk
                    self.video_label.img = img_tk  # 保持引用
                    self.video_label.configure(image=img_tk)
            
        # 更新录制时间显示
        if globals.allowRecording:
            self.elapsed_time = time.time() - self.start_time
            minutes, seconds = divmod(int(self.elapsed_time), 60)
            self.recording_time_label.config(text=f"录制时间: {minutes:02}:{seconds:02}")

        # 如果剩余时间大于 0，延迟更新帧
        self.video_label.after(1,self.update_frame)

    def browse_save_path(self):
        """打开文件对话框，让用户选择保存文件夹"""
        folder_path = filedialog.askdirectory(initialdir=getcwd(), title="选择保存文件夹")
        if folder_path:
            self.save_path.set(folder_path)  # 设置保存路径为用户选择的文件夹

    def start_recording(self):
        """开始录制视频"""
        #allowRecording
        if globals.allowRecording:
            messagebox.showwarning("警告", "视频保存中")
            return
        # 检查保存路径是否已选择
        save_folder = self.save_path.get()
        if not save_folder:
            messagebox.showerror("错误", "请先选择保存文件夹")
            return
        # 检查目标分辨率是否有效
        if self.target_width <= 0 or self.target_height <= 0:
            messagebox.showwarning("警告", "无效的分辨率，宽度和高度必须大于 0")
            return
        # 检查RGB值是否有效
        if not hasattr(self, 'valid_rgb_value'):
            messagebox.showerror("错误", "请输入有效的RGB值 (0-255, 0-255, 0-255)")
            return
        
        # 禁用相关控件
        self.disable_controls()

        # 更新状态显示
        globals.set_allowRecording(True)

        self.recording_status_label.config(text="当前状态: 录制中", fg="red")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.start_time = time.time()  # 记录开始时间

        # 启动线程
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.recoding_time = timestamp
        self.audio_thread = AudioThread(self.event, save_folder,self.video_format.get(), 
                                        timestamp, self.audio_device_var.get())
        self.video_thread = VideoThread(
            self.event, save_folder, self.video_format.get(), self.frame_rate, self.target_width, self.target_height, timestamp,
            self.ir_scale, self.ir_rotation, self.ir_flip_horizontal, self.ir_flip_vertical,
            self.usb_scale, self.usb_rotation, self.usb_flip_horizontal, self.usb_flip_vertical
        )
        for t in (self.video_thread, self.audio_thread):
            t.start()

    def stop_recording(self):
        """停止录制视频"""
        if not globals.allowRecording:
            messagebox.showwarning("警告", "当前没有正在录制的视频")
            return
        globals.set_allowRecording(False)
        self.start_time = None

        # 等待线程结束
        if hasattr(self, 'audio_thread') and self.audio_thread:
            self.audio_thread.join()
        if self.video_thread:
            self.video_thread.join()

        globals.frame_queue_save.queue.clear()  # 清空保存队列
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        #开启一个新的线程合并音频和视频
        if self.video_format.get() == "mp4":
            #启用线程执行combine_audio_video合并音频和视频
            self.combine_thread = threading.Thread(target=self.combine_audio_video)
            self.combine_thread.start()

        # 启用相关控件
        self.enable_controls()

        # 重置录制时间显示
        self.recording_time_label.config(text="录制时间: 00:00")

        # 更新状态显示
        self.recording_status_label.config(text="当前状态: 停止录制", fg="green")

    def combine_audio_video(self):
        """合并音频和视频"""
        save_folder = self.save_path.get()
        audio_file = path.join(save_folder, f"temp_audio_{self.recoding_time}.wav")
        video_file = path.join(save_folder, f"recorded_video_{self.recoding_time}.mp4")
        output_file = path.join(save_folder, f"recorded_{self.recoding_time}.mp4")

        # 检查音频和视频文件是否存在
        if not os.path.exists(audio_file):
            messagebox.showerror("错误", f"音频文件不存在: {audio_file}")
            return
        if not os.path.exists(video_file):
            messagebox.showerror("错误", f"视频文件不存在: {video_file}")
            return

        # 使用ffmpeg合并音频和视频
        command = f"ffmpeg -i {video_file} -i {audio_file} -c:v copy -c:a aac -strict experimental -shortest {output_file}"
        try:
            subprocess.run(command, shell=True, check=True)
            # 删除原始音频和视频文件
            os.remove(audio_file)
            os.remove(video_file)
            print(f"音频和视频合并完成: {output_file}")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("错误", f"合并音频和视频失败: {str(e)}")


    def disable_controls(self):
        """禁用录制期间不可修改的控件"""
        # 禁用视频格式选择
        self.avi_radio.config(state=tk.DISABLED)
        self.mp4_radio.config(state=tk.DISABLED)

        # 禁用帧率调整控件
        self.framerate_scale.config(state=tk.DISABLED)

        # 禁用保存路径选择
        self.save_path_entry.config(state=tk.DISABLED)
        self.browse_button.config(state=tk.DISABLED)

        # 禁用RGB值输入框
        self.rgb_value_entry.config(state=tk.DISABLED)

        # 禁用红外设备控制
        self.ir_scale_slider.config(state=tk.DISABLED)
        self.ir_rotation_menu.config(state=tk.DISABLED)
        self.ir_flip_h_cb.config(state=tk.DISABLED)
        self.ir_flip_v_cb.config(state=tk.DISABLED)

        # 禁用USB设备控制
        self.usb_scale_slider.config(state=tk.DISABLED)
        self.usb_rotation_menu.config(state=tk.DISABLED)
        self.usb_flip_h_cb.config(state=tk.DISABLED)
        self.usb_flip_v_cb.config(state=tk.DISABLED)

    def enable_controls(self):
        """启用录制结束后可修改的控件"""
        self.avi_radio.config(state=tk.NORMAL)
        self.mp4_radio.config(state=tk.NORMAL)
        self.framerate_scale.config(state=tk.NORMAL)
        self.save_path_entry.config(state=tk.NORMAL)
        self.browse_button.config(state=tk.NORMAL)
        self.rgb_value_entry.config(state=tk.NORMAL)
        self.ir_scale_slider.config(state=tk.NORMAL)
        self.ir_rotation_menu.config(state=tk.NORMAL)
        self.ir_flip_h_cb.config(state=tk.NORMAL)
        self.ir_flip_v_cb.config(state=tk.NORMAL)
        self.usb_scale_slider.config(state=tk.NORMAL)
        self.usb_rotation_menu.config(state=tk.NORMAL)
        self.usb_flip_h_cb.config(state=tk.NORMAL)
        self.usb_flip_v_cb.config(state=tk.NORMAL)

    def on_closing(self):
        """处理窗口关闭"""
        if globals.allowRecording and self.out:
            self.out.release()
        if self.usb_cap:
            self.usb_cap.release()
        if self.ir_camera:
            try:
                self.ir_camera.destroy()  # 使用正确的释放方法
            except AttributeError:
                print("红外摄像头没有 destroy 方法，跳过释放步骤。")
        self.root.destroy()
  
    def run(self):
        """启动应用程序"""
        # 启动处理队列的定时器
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

# 启动应用
if __name__ == "__main__":
    sdk_filename = "ArmSdk.dll"
    sdk_path = path.join(getcwd(), sdk_filename)
    root = tk.Tk()
    app = DualCameraApp(root, sdk_path)
    app.run()

