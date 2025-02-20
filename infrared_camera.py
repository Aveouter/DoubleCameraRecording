# infrared_camera.py

import ctypes
import os
import sys
import numpy as np
import cv2
from ctypes import (
    c_int,
    c_float,
    c_char,
    c_char_p,
    c_void_p,
    POINTER,
    Structure,
    CFUNCTYPE,
    c_short,  # 添加 c_short 的导入
)
import logging

# 初始化日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("infrared_camera.log"),
        logging.StreamHandler()
    ]
)

# 定义 HANDLE_T 类型
HANDLE_T = c_void_p

# 定义枚举 PARAMETER_TYPE 和 IMG_PARAM_TYPE 为整数
PARAMETER_TYPE = c_int
IMG_PARAM_TYPE = c_int

# 定义 FACTORY_VERSION 结构
class FACTORY_VERSION(Structure):
    _fields_ = [
        ("serialNum", ctypes.c_char * 32),
        ("armVersion", ctypes.c_char * 32),
        ("fpgaVersion", ctypes.c_char * 32),
        ("sdkVersion", ctypes.c_char * 32),
    ]

# 定义 OUT_PUT_IR_DATA 结构
class OUT_PUT_IR_DATA(Structure):
    _fields_ = [
        ("width", c_int),
        ("height", c_int),
        ("yuvData", POINTER(ctypes.c_ubyte)),
        ("yuvLength", c_int),
        ("y16Data", POINTER(c_short)),  # 使用已导入的 c_short
        ("y16Length", c_int),
    ]

# 定义回调函数类型
ImageCallBack = CFUNCTYPE(c_int, POINTER(OUT_PUT_IR_DATA), c_void_p)

class InfraredCamera:
    def __init__(self, sdk_path, module_name="MyModule"):
        """
        初始化红外摄像头

        :param sdk_path: SDK 动态链接库的路径
        :param module_name: 模块名称
        """
        # 检查SDK路径
        if not os.path.exists(sdk_path):
            logging.error(f"SDK 动态链接库未找到: {sdk_path}")
            raise FileNotFoundError(f"SDK 动态链接库未找到: {sdk_path}")

        # 加载动态链接库
        try:
            self.sdk = ctypes.CDLL(sdk_path)
            logging.info(f"成功加载SDK动态链接库: {sdk_path}")
        except OSError as e:
            logging.error(f"加载SDK失败: {str(e)}")
            raise e

        # 定义函数原型
        self._define_functions()

        # 创建模组实例
        try:
            self.handle = self.sdk.CreateModuleInstance(module_name.encode('utf-8'))
            if not self.handle:
                logging.error("创建模组实例失败")
                raise Exception("创建模组实例失败")
            logging.info("成功创建模组实例")
        except Exception as e:
            logging.error(f"创建模组实例失败: {str(e)}")
            raise e

        # 定义回调函数
        self.latest_frame = None
        self.callback = ImageCallBack(self.image_callback)

        # 注册回调函数
        scale_time = 1.0  # 不缩放
        try:
            result = self.sdk.RegisterImgCallBack(self.handle, self.callback, None, c_float(scale_time))
            if result != 0:
                self.sdk.DestroyModuleInstance(self.handle)
                logging.error("注册图像回调函数失败")
                raise Exception("注册图像回调函数失败")
            logging.info("成功注册图像回调函数")
        except AttributeError as e:
            logging.error(f"RegisterImgCallBack 函数不存在: {str(e)}")
            self.sdk.DestroyModuleInstance(self.handle)
            raise e
        except Exception as e:
            logging.error(f"注册图像回调函数失败: {str(e)}")
            self.sdk.DestroyModuleInstance(self.handle)
            raise e

    def _define_functions(self):
        """定义SDK函数的参数类型和返回类型"""
        try:
            # CreateModuleInstance
            self.sdk.CreateModuleInstance.argtypes = [c_char_p]
            self.sdk.CreateModuleInstance.restype = HANDLE_T

            # DestroyModuleInstance
            self.sdk.DestroyModuleInstance.argtypes = [HANDLE_T]
            self.sdk.DestroyModuleInstance.restype = None

            # RegisterImgCallBack
            self.sdk.RegisterImgCallBack.argtypes = [HANDLE_T, ImageCallBack, c_void_p, c_float]
            self.sdk.RegisterImgCallBack.restype = c_int

            # FactoryVersion
            self.sdk.FactoryVersion.argtypes = [HANDLE_T, POINTER(FACTORY_VERSION)]
            self.sdk.FactoryVersion.restype = c_int

            # MeasureBodyTemp
            self.sdk.MeasureBodyTemp.argtypes = [HANDLE_T, c_float, c_float, POINTER(c_float)]
            self.sdk.MeasureBodyTemp.restype = c_int

            # MeasureTempByY16
            self.sdk.MeasureTempByY16.argtypes = [HANDLE_T, c_short, POINTER(c_float)]
            self.sdk.MeasureTempByY16.restype = c_int

            # ImageParamsControl
            self.sdk.ImageParamsControl.argtypes = [HANDLE_T, IMG_PARAM_TYPE, ctypes.c_void_p]
            self.sdk.ImageParamsControl.restype = c_int

            # MeasureParamsControl
            self.sdk.MeasureParamsControl.argtypes = [HANDLE_T, PARAMETER_TYPE, ctypes.c_void_p]
            self.sdk.MeasureParamsControl.restype = c_int

            # 其他需要使用的 SDK 函数根据需求定义

            logging.info("成功定义SDK函数原型")
        except AttributeError as e:
            logging.error(f"定义SDK函数原型失败: {str(e)}")
            raise e

    def image_callback(self, callBackData_ptr, param):
        """
        图像回调函数

        :param callBackData_ptr: 指向OUT_PUT_IR_DATA结构的指针
        :param param: 传递的参数（未使用）
        :return: 整数状态码
        """
        try:
            callBackData = callBackData_ptr.contents
            width = callBackData.width
            height = callBackData.height

            if callBackData.y16Data and callBackData.y16Length > 0:
                # 将 Y16 数据转换为 NumPy 数组
                y16_array = np.ctypeslib.as_array(callBackData.y16Data, shape=(callBackData.y16Length,))
                try:
                    self.latest_frame = y16_array.reshape((height, width))
                    logging.debug(f"获取到最新帧: {width}x{height}")
                except ValueError as ve:
                    logging.error(f"帧数据重塑失败: {str(ve)}")
                    self.latest_frame = None
            else:
                logging.warning("没有有效的 Y16 数据")
                self.latest_frame = None
            return 0  # 返回GUIDERIR_OK 假设为 0
        except Exception as e:
            logging.error(f"图像回调处理失败: {str(e)}")
            return -1  # 返回错误码

    def get_latest_frame(self):
        """
        获取最新的红外摄像头帧

        :return: 三通道的灰度图像
        """
        if self.latest_frame is not None:
            try:
                # 将温度数据归一化到[0, 255]范围
                temp_normalized = cv2.normalize(self.latest_frame, None, 0, 255, cv2.NORM_MINMAX)

                # 转换为灰度图像（单通道）
                temp_image = temp_normalized.astype(np.uint8)

                # 将单通道灰度图像扩展为三通道
                temp_image = cv2.cvtColor(temp_image, cv2.COLOR_GRAY2BGR)

                return temp_image
            except Exception as e:
                logging.error(f"处理最新帧失败: {str(e)}")
                return np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            return np.zeros((480, 640, 3), dtype=np.uint8)

    def get_factory_version(self):
        """
        获取工厂版本信息

        :return: 字典包含序列号和各版本信息
        """
        factory_info = FACTORY_VERSION()
        try:
            result = self.sdk.FactoryVersion(self.handle, ctypes.byref(factory_info))
            if result == 0:
                version_info = {
                    "serialNum": factory_info.serialNum.decode('utf-8').strip(),
                    "armVersion": factory_info.armVersion.decode('utf-8').strip(),
                    "fpgaVersion": factory_info.fpgaVersion.decode('utf-8').strip(),
                    "sdkVersion": factory_info.sdkVersion.decode('utf-8').strip(),
                }
                logging.info(f"获取工厂版本信息成功: {version_info}")
                return version_info
            else:
                logging.error("获取工厂版本信息失败")
                raise Exception("获取工厂版本信息失败")
        except Exception as e:
            logging.error(f"获取工厂版本信息异常: {str(e)}")
            raise e

    def measure_body_temp(self, surface_temp, envir_temp):
        """
        测量体温

        :param surface_temp: 表面温度
        :param envir_temp: 环境温度
        :return: 体温值
        """
        body_temp = c_float()
        try:
            result = self.sdk.MeasureBodyTemp(
                self.handle,
                c_float(surface_temp),
                c_float(envir_temp),
                ctypes.byref(body_temp)
            )
            if result == 0:
                logging.info(f"测量体温成功: {body_temp.value}°C")
                return body_temp.value
            else:
                logging.error("测量体温失败")
                raise Exception("测量体温失败")
        except Exception as e:
            logging.error(f"测量体温异常: {str(e)}")
            raise e

    def set_image_param(self, param_type, param_value):
        """
        设置成像参数

        :param param_type: 成像参数类型（IMG_PARAM_TYPE 枚举值）
        :param param_value: 参数值，传地址
        :return: 无
        """
        try:
            if isinstance(param_value, str):
                param_bytes = param_value.encode('utf-8') + b'\x00'
                param_ptr = ctypes.c_char_p(param_bytes)
            elif isinstance(param_value, (int, float)):
                if isinstance(param_value, int):
                    param_ptr = ctypes.pointer(ctypes.c_int(param_value))
                else:
                    param_ptr = ctypes.pointer(ctypes.c_float(param_value))
            else:
                raise ValueError("Unsupported parameter type")

            result = self.sdk.ImageParamsControl(
                self.handle,
                IMG_PARAM_TYPE(param_type),
                ctypes.byref(param_ptr.contents)
            )
            if result != 0:
                logging.error(f"设置成像参数失败，参数类型: {param_type}, 值: {param_value}")
                raise Exception("设置成像参数失败")
            logging.info(f"设置成像参数成功，参数类型: {param_type}, 值: {param_value}")
        except Exception as e:
            logging.error(f"设置成像参数异常: {str(e)}")
            raise e

    def set_measure_param(self, param_type, param_value):
        """
        设置测温参数

        :param param_type: 测温参数类型（PARAMETER_TYPE 枚举值）
        :param param_value: 参数值，传地址
        :return: 无
        """
        try:
            if isinstance(param_value, str):
                param_bytes = param_value.encode('utf-8') + b'\x00'
                param_ptr = ctypes.c_char_p(param_bytes)
            elif isinstance(param_value, (int, float)):
                if isinstance(param_value, int):
                    param_ptr = ctypes.pointer(ctypes.c_int(param_value))
                else:
                    param_ptr = ctypes.pointer(ctypes.c_float(param_value))
            else:
                raise ValueError("Unsupported parameter type")

            result = self.sdk.MeasureParamsControl(
                self.handle,
                PARAMETER_TYPE(param_type),
                ctypes.byref(param_ptr.contents)
            )
            if result != 0:
                logging.error(f"设置测温参数失败，参数类型: {param_type}, 值: {param_value}")
                raise Exception("设置测温参数失败")
            logging.info(f"设置测温参数成功，参数类型: {param_type}, 值: {param_value}")
        except Exception as e:
            logging.error(f"设置测温参数异常: {str(e)}")
            raise e

    def destroy(self):
        """
        释放红外摄像头资源
        """
        if self.handle:
            try:
                self.sdk.DestroyModuleInstance(self.handle)
                logging.info("成功释放红外摄像头资源")
                self.handle = None
            except Exception as e:
                logging.error(f"释放红外摄像头资源失败: {str(e)}")
