from datetime import datetime
import os
from pathlib import Path
import threading
import wave

from numpy import hstack
import globals
import time
import cv2
import pyaudio
import queue



class AudioThread(threading.Thread):
    def __init__(self, event, save_folder, selected_format, timestamp,audio_device):
        threading.Thread.__init__(self)
        self.event = event
        self.audio_frames = []
        self.selected_format = selected_format
        # 设置音频录制参数  
        if selected_format == "mp4":
            self.audio_path = str(Path(save_folder) / f"temp_audio_{timestamp}.wav") # 临时音频文件路径
            self.CHUNK = 1024
            self.FORMAT = pyaudio.paInt24  # 使用24位深度提高音频质量
            self.CHANNELS = 2
            self.RATE = 48000    # 48kHz采样率
            # 初始化音频录制
            self.audio = pyaudio.PyAudio()
            
            # 检查是否选择了音频设备
            device_name = audio_device
            if device_name == "未检测到麦克风":
                # 如果没有检测到麦克风,使用系统默认录音设备
                self.device_index = self.audio.get_default_input_device_info()['index']
            else:
                # 根据选择的设备名称查找对应的设备索引
                self.device_index = None
                for i in range(self.audio.get_device_count()):
                    device_info = self.audio.get_device_info_by_index(i)
                    if device_info['name'] == device_name and device_info['maxInputChannels'] > 0:
                        self.device_index = i
                        break
                
                # 如果找不到选择的设备,回退到默认设备
                if self.device_index is None:
                    print(f"警告:找不到选择的音频设备 '{device_name}',使用默认录音设备")
                    self.device_index = self.audio.get_default_input_device_info()['index']

            print(f"使用录音设备: {self.audio.get_device_info_by_index(self.device_index)['name']}")

            # 获取设备的通道数
            device_info = self.audio.get_device_info_by_index(self.device_index)
            self.CHANNELS = device_info['maxInputChannels']

            self.stream = self.audio.open(
                format=self.FORMAT,  
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.CHUNK
            )
            self.wf = wave.open(self.audio_path, 'wb')
            self.wf.setnchannels(self.CHANNELS)
            self.wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            self.wf.setframerate(self.RATE)
            

    def run(self):
        if self.selected_format == "mp4":
            self.event.wait()
            self.event.clear()
            print('初始化完成,开始录音', str(datetime.now()))
            while not self.event.is_set():
                data = self.stream.read(self.CHUNK)
                self.wf.writeframes(data)
            print('录制音频结束', str(datetime.now()))
            self.wf.close()
            self.stream.stop_stream()  # 关闭流
            self.stream.close()
            self.audio.terminate()  # 关闭音频对象
            self.event.set()


class VideoThread(threading.Thread):
    """
    out 是VideoWriter的实例对象，就是写入视频的方式，第一个参数是存放写入视频的位置，
    第二个是编码方式，帧率，最后是视频的高宽，若录制视频为灰度则加上False
    """

    def __init__(self, event, save_folder, video_format, frame_rate, target_width, target_height, timestamp,
                 ir_scale, ir_rotation, ir_flip_horizontal, ir_flip_vertical,
                 usb_scale, usb_rotation, usb_flip_horizontal, usb_flip_vertical):
        threading.Thread.__init__(self)
        self.event = event
        self.frame_rate = frame_rate
        self.target_width = target_width
        self.target_height = target_height
        self.out = None
        self.save_folder = save_folder
        self.video_format = video_format
        self.ir_scale = ir_scale
        self.ir_rotation = ir_rotation
        self.ir_flip_horizontal = ir_flip_horizontal
        self.ir_flip_vertical = ir_flip_vertical
        self.usb_scale = usb_scale
        self.usb_rotation = usb_rotation
        self.usb_flip_horizontal = usb_flip_horizontal
        self.usb_flip_vertical = usb_flip_vertical
        # print(f"视频 : {video_format}")
        # # 获取时间戳，生成文件名
        file_name = f"recorded_video_{timestamp}.{video_format}"
        file_path = os.path.join(save_folder, file_name)

        # 获取用户选择的帧率
        current_framerate = self.frame_rate
        print(f"当前选择的帧率: {current_framerate} FPS")

        # 根据用户选择的格式来确定编码方式
        selected_format = video_format
        fourcc = cv2.VideoWriter_fourcc(*'XVID') if selected_format == "avi" else cv2.VideoWriter_fourcc(*'mp4v')

        # 根据目标宽度和高度调整视频输出尺寸
        frame_width = self.target_width  # 根据需求调整宽度
        frame_height = self.target_height  # The height remains unchanged to maintain the original aspect ratio of the video

        # 确保目录存在
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)

        # 初始化VideoWriter对象
        self.out = cv2.VideoWriter(file_path, fourcc, self.frame_rate, (frame_width, frame_height))
    
    def run(self):
        print(f'开始录制视频{globals.allowRecording}')
        self.event.set()
        print('初始化完成,开始录屏 %s', str(datetime.now()))
        while globals.allowRecording:
            try:
                frame_ir, frame_usb = globals.frame_queue_save.get(timeout=1)
                frame_ir = globals.apply_transformations(frame_ir, self.ir_scale, self.ir_rotation, self.ir_flip_horizontal, self.ir_flip_vertical)
                frame_usb = globals.apply_transformations(frame_usb, self.usb_scale, self.usb_rotation, self.usb_flip_horizontal, self.usb_flip_vertical)
                rgb_value = self.valid_rgb_value if hasattr(self, 'valid_rgb_value') else (128, 128, 128)
                frame_ir, frame_usb = globals.resize_frame(frame_ir, frame_usb, rgb_value)
                combined_frame = hstack((frame_ir, frame_usb))
                datet = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                font = cv2.FONT_HERSHEY_SIMPLEX
                combined_frame = cv2.putText(combined_frame, datet, (10, 30), font, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA) # 是视频里面显示时间或者文字
                # 保存视频
                self.out.write(combined_frame)
            except queue.Empty:
                time.sleep(0.1)  # Avoid printing too frequently
        self.event.set()
        print('录制视频结束', str(datetime.now()))
        # 释放视频资源
        if self.out:
            self.out.release()
            self.out = None

class VideoMerge(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.cur_path = os.path.abspath(os.path.dirname(__file__))
        self.path = self.cur_path + '\\static\\'
        self.merge_path = self.path + 'merge\\'
        self.Lock = threading.Lock()
        self.need_video_merge = list()
        self.init()

    def init(self):
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        if not os.path.exists(self.merge_path):
            os.mkdir(self.merge_path)

    def run(self):
        while True:
            filename = None
            with self.Lock:
                if len(self.need_video_merge) > 0:
                    filename = self.need_video_merge[0]
            if filename is not None:
                try:
                    audio_filename = self.path + filename + '.mp3'
                    video_filename = self.path + filename + '.avi'
                    merge_filename = self.merge_path + filename + '.avi'
                    audioclip = AudioFileClip(audio_filename)
                    videoclip = VideoFileClip(video_filename)
                    videoclip2 = videoclip.set_audio(audioclip)
                    video = CompositeVideoClip([videoclip2])
                    video.write_videofile(merge_filename, codec='mpeg4', bitrate='2000k') # bitrate 设置比特率，比特率越高， 合并的视频越清晰，视频文件也越大
                    print("删除本地视频,音频文件……")
                    os.remove(video_filename)
                    os.remove(audio_filename)
                    self.need_video_merge.pop(0)
                    print("文件 %s 合并成功" % filename)
                except Exception as e:
                    print("文件 %s 合并失败 %s" % (filename, e))

    def push_list(self, filename):
        with self.Lock:
            self.need_video_merge.append(filename)
