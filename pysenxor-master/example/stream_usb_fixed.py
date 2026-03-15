# Copyright (C) Meridian Innovation Ltd. Hong Kong, 2020. All rights reserved.
#
import sys
import os
import signal
import time
import logging
import serial
import serial.tools.list_ports
import numpy as np

try:
    import cv2 as cv
except:
    print("Please install OpenCV (or link existing installation)"
          " to see the thermal image")
    exit(1)

from senxor.mi48 import MI48, format_header, format_framestats
from senxor.utils import data_to_frame, remap, cv_filter,\
                         cv_render, RollingAverageFilter,\
                         connect_senxor

# This will enable mi48 logging debug messages
logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))


# Make the a global variable and use it as an instance of the mi48.
# This allows it to be used directly in a signal_handler.
global mi48

# define a signal handler to ensure clean closure upon CTRL+C
# or kill from terminal
def signal_handler(sig, frame):
    """Ensure clean exit in case of SIGINT or SIGTERM"""
    logger.info("Exiting due to SIGINT or SIGTERM")
    if mi48 is not None:
        mi48.stop()
    cv.destroyAllWindows()
    logger.info("Done.")
    sys.exit(0)

# Define the signals that should be handled to ensure clean exit
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def list_all_com_ports():
    """列出所有可用的COM端口"""
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append({
            'device': port.device,
            'description': port.description,
            'vid': getattr(port, 'vid', None),
            'pid': getattr(port, 'pid', None)
        })
    return ports

def find_thermal_cameras():
    """查找可能的热成像摄像头设备"""
    all_ports = list_all_com_ports()
    
    print("所有可用的串口设备:")
    for port in all_ports:
        vid_pid = ""
        if port['vid'] and port['pid']:
            vid_pid = f" (VID:PID = {port['vid']:04X}:{port['pid']:04X})"
        print(f"  - {port['device']}: {port['description']}{vid_pid}")
    
    return all_ports

# Make an instance of the MI48, attaching USB for 
# both control and data interface.
# can try connect_senxor(src='/dev/ttyS3') or similar if default cannot be found
mi48, connected_port, port_names = connect_senxor()

# 检查是否成功连接
if mi48 is None:
    logger.error("未能连接到MI48设备!")
    logger.info("正在查找可能的热成像摄像头设备...")
    
    thermal_cameras = find_thermal_cameras()
    
    if not thermal_cameras:
        logger.error("未发现任何串口设备")
    else:
        logger.info("发现的设备可能需要不同的驱动程序")
        logger.info("请检查:")
        logger.info("1. 设备是否为MI48红外摄像头")
        logger.info("2. 设备驱动是否正确安装")
        logger.info("3. 设备是否正确连接到USB端口")
        
        # 提供一些可能的解决方案
        logger.info("\n可能的解决方案:")
        logger.info("1. 如果您的设备是IR8062，请使用SLS项目中的test脚本")
        logger.info("2. 尝试手动指定端口: connect_senxor(src='COMx')")
        logger.info("3. 检查设备管理器中的VID/PID是否为1046:B002或1046:B020")
    
    sys.exit(1)

# print out camera info
logger.info('Camera info:')
try:
    logger.info(mi48.camera_info)
except AttributeError:
    logger.error("无法获取摄像头信息 - 可能是连接问题")
    sys.exit(1)

# set desired FPS
if len(sys.argv) == 2:
    STREAM_FPS = int(sys.argv[1])
else:
    STREAM_FPS = 15
mi48.set_fps(STREAM_FPS)

# see if filtering is available in MI48 and set it up
mi48.disable_filter(f1=True, f2=True, f3=True)
mi48.set_filter_1(85)
mi48.enable_filter(f1=True, f2=False, f3=False, f3_ks_5=False)
mi48.set_offset_corr(0.0)

mi48.set_sens_factor(100)
mi48.get_sens_factor()

# initiate continuous frame acquisition
with_header = True
mi48.start(stream=True, with_header=with_header)

# change this to false if not interested in the image
GUI = True

# set cv_filter parameters
par = {'blur_ks':3, 'd':5, 'sigmaColor': 27, 'sigmaSpace': 27}

dminav = RollingAverageFilter(N=10)
dmaxav = RollingAverageFilter(N=10)

logger.info("开始读取热成像数据...")
logger.info("按 'q' 键退出程序")

while True:
    data, header = mi48.read()
    if data is None:
        logger.critical('NONE data received instead of GFRA')
        mi48.stop()
        sys.exit(1)

    min_temp = dminav(data.min())  # + 1.5
    max_temp = dmaxav(data.max())  # - 1.5
    frame = data_to_frame(data, (80,62), hflip=False);
    frame = np.clip(frame, min_temp, max_temp)
    filt_uint8 = cv_filter(remap(frame), par, use_median=True,
                           use_bilat=True, use_nlm=False)
    #
    if header is not None:
        logger.debug('  '.join([format_header(header),
                                format_framestats(data)]))
    else:
        logger.debug(format_framestats(data))

    if GUI:
#        cv_render(filt_uint8, resize=(400,310), colormap='ironbow')
        cv_render(filt_uint8, resize=(400,310), colormap='rainbow2')
        # cv_render(remap(frame), resize=(400,310), colormap='rainbow2')
        key = cv.waitKey(1)  # & 0xFF
        if key == ord("q"):
            break
#    time.sleep(1)

# stop capture and quit
mi48.stop()
cv.destroyAllWindows()