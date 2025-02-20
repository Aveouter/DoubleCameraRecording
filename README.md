
# DualCameraRecording

## Overview

**DualCameraRecording** is a Python-based application designed for simultaneous video recording from two different cameras: a USB camera and an infrared camera. This application provides real-time processing and recording with customizable settings such as frame rate, resolution, video format, and camera transformations (scaling, rotation, and flipping). It also allows for the integration of microphone audio, and the ability to merge the video and audio files after recording.

## Features

- Dual camera support: USB and infrared camera input.
- Real-time video processing: Frame scaling, rotation, and flipping.
- Frame rate adjustment: Select from 1 to 30 frames per second.
- Audio recording support from external microphones.
- Save video in multiple formats (MP4, AVI).
- User-friendly GUI with control for video format, frame rate, RGB values, and camera settings.
- Recording control: Start and stop buttons for easy video capture.
- Combine audio and video after recording using FFmpeg.
- Customizable output directory for saving recorded files.

## Installation

### Requirements

- Python 3.x
- Tkinter for GUI
- OpenCV
- Pillow
- PyAudio
- NumPy
- FFmpeg
- Infrared camera SDK (e.g., `ArmSdk.dll`)
  
### Dependencies

Install required Python packages using `pip`:

```bash
pip install opencv-python numpy pyaudio pillow
```

Ensure that you have FFmpeg installed. You can download FFmpeg from [here](https://ffmpeg.org/download.html).

For Infrared Camera SDK, ensure that you have the necessary SDK files (`ArmSdk.dll` or relevant files for your infrared camera) and place them in the project directory.

### Running the Application

To run the application, execute the Python script:

```bash
python dual_camera_recording.py
```

### UI Controls

- **Video Format**: Choose between MP4 or AVI formats.
- **Frame Rate**: Adjust the frame rate from 1 to 30 FPS.
- **Save Path**: Select the folder where the video will be saved.
- **RGB Values**: Input RGB values to control the image tint.
- **Microphone Device**: Choose the input device for audio recording.
- **Camera Control**: Adjust settings for both USB and infrared cameras, including zoom, rotation, and flip options.
- **Start/Stop Recording**: Begin and end video recording.

## How to Use

1. **Select Video Format**: Choose whether to save your video as MP4 or AVI.
2. **Adjust Frame Rate**: Use the slider to adjust the frame rate for the recording.
3. **Set Save Path**: Click the "Browse" button to select the folder where the video will be saved.
4. **Adjust RGB Values**: Optionally adjust the RGB values to modify the color tint of the video.
5. **Microphone Settings**: Choose the microphone device for audio recording.
6. **Camera Controls**: Adjust the USB and infrared camera settings:
   - **Zoom**: Control the scale of the camera input.
   - **Rotation**: Rotate the image (0°, 90°, 180°, 270°).
   - **Flip**: Flip the camera feed horizontally or vertically.
7. **Start Recording**: Click "Start Recording" to begin capturing video and audio. The elapsed time will be displayed.
8. **Stop Recording**: Click "Stop Recording" to finish recording and save the video.
9. **Audio-Video Merging**: After stopping the recording, the application will automatically combine the audio and video files into a single file.

## Troubleshooting

- **No USB Camera Detected**: Ensure your USB camera is properly connected and recognized by the system.
- **No Microphone Detected**: Make sure your microphone is correctly plugged in and recognized by the system. Use the "Audio Device" dropdown to select the correct microphone.
- **Infrared Camera Initialization Failed**: Check if the infrared camera SDK is correctly installed and the `ArmSdk.dll` is in the project directory.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
