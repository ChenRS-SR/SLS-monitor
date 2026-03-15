/*
 * StreamSDK 1.2
 * Copyright 2017, IRS.cn
 *
 * 获取网络型热像仪流数据的接口库
 * library for grabbing stream data from IIR device
*/

#ifndef STREAMSDK_H_INCLUDED
#define STREAMSDK_H_INCLUDED

#pragma once

#ifdef _WIN32
#ifdef STREAMSDK_EXPORTS
#ifdef __cplusplus
#define STREAMSDK_API extern "C" __declspec(dllexport)
#else
#define STREAMSDK_API __declspec(dllexport)
#endif
#else
#ifdef __cplusplus
#define STREAMSDK_API extern "C" __declspec(dllimport)
#else
#define STREAMSDK_API __declspec(dllexport)
#endif
#endif

#ifndef CALLBACK
#define CALLBACK __stdcall
#endif

#else
#ifdef __cplusplus
#define STREAMSDK_API extern "C"
#else
#define STREAMSDK_API
#endif
#ifndef CALLBACK
#define CALLBACK
#endif
#endif


#ifndef TRUE
#define TRUE 1
#endif

#ifndef FALSE
#define FALSE 0
#endif

#define __IN
#define __OUT
#define __INOUT

#pragma pack(push,8)
enum streamsdk_enum_error_code
{
    STREAMSDK_EC_OK = 0,				/** 函数调用成功 **/
    STREAMSDK_EC_FAIL = 1,				/** 函数调用失败 **/
    STREAMSDK_EC_TIMEOUT = 2,			/** 网络超时 **/
    STREAMSDK_EC_LIMIT,
};

/* StreamSDK 接口
 * StreamSDK Interfaces

 *  返回字符串的函数，调用者在传入buffer指针前，需要分配不小于STREAMSDK_STR_BUFSZ字节的内存空间
 *  Caller should be responsible for allocating enough memory, when passing char * buffers.
    The buffer size should be at least STREAMSDK_STR_BUFSZ bytes, if no other request is specified.
 *  Callback function pointer may be set to NULL to disable callback
 *  
 */
enum streamsdk_enum_buffer
{
    STREAMSDK_STR_BUFSZ = 256,
};

/** 图像像素的颜色格式 **/
enum streamsdk_enum_pix_type
{
    STREAMSDK_PIX_RGB,					/** RGBRGB... 每个像素24位交替排列**/
    STREAMSDK_PIX_Y420,					/** YUV420，Y平面，U平面和V平面 **/
    STREAMSDK_PIX_GRAY,					/** 灰度，每个像素8位 **/
    STREAMSDK_PIX_BGR,					/** BGRBGR... **/
};

/** 帧缓冲区描述 **/
typedef struct streamsdk_st_buffer_
{
    void *			buf_ptr;			/** 帧缓冲区指针 **/
    unsigned int	buf_size;			/** 帧大小 **/
    unsigned int	buf_pts;			/** 帧序列号 **/
} streamsdk_st_buffer;

/** 图像描述 **/
typedef struct streamsdk_st_image_
{
    void *	img_ptr;					/** 图像矩阵指针 **/
    int		img_w;						/** 图像宽度(像素) **/
    int		img_h;						/** 图像高度(像素) **/
    int		img_linesize;				/** 图像行大小(字节) **/
    int		img_pts;					/** 图像序列号 **/
    int		img_type;					/** 图像像素格式, streamsdk_enum_pix_type **/
} streamsdk_st_image;

/** 解码参数描述 **/
typedef struct streamsdk_st_decoder_param_
{
    int		dec_w;						/** 解码宽度(像素) **/
    int		dec_h;						/** 解码高度(像素) **/
    int		pix_type;					/** 图像像素格式, streamsdk_enum_pix_type **/
} streamsdk_st_decoder_param;

typedef struct streamsdk_st_recorder_param_
{
    int		rec_w;
    int		rec_h;
    float	fps;
} streamsdk_st_recorder_param;

typedef struct streamsdk_st_event_
{
    char * event;
    char * id;
    int pts;
    double value;
}streamsdk_st_event;

typedef void * HSTREAM;					/** 流句柄 **/
typedef void * HDECODER;				/** 解码器句柄 **/
typedef void * HRECORDER;				/** 录像器句柄 **/

/** 数据帧回调函数 **/
typedef void (CALLBACK * streamsdk_cb_grabber)(int error,__IN streamsdk_st_buffer * ,__IN void * user_data);
/** 图像帧回调函数 **/
typedef void (CALLBACK * streamsdk_cb_image_grabber)(int error,__IN streamsdk_st_image * ,__IN void * user_data);
/** 事件帧回调函数 **/
typedef void (CALLBACK * streamsdk_cb_event_grabber)(int error,__IN streamsdk_st_event * ,__IN void * user_data);
#pragma pack(pop)

/********** 通用 common **********/
/** 版本号是4个整数，数组需要由调用都分配，
    version number is an array of 4 integers, caller should allocate the array before passing the pointer 
**/
STREAMSDK_API int streamsdk_get_version(__OUT int * ver_no);	
STREAMSDK_API int streamsdk_get_version_str(__OUT char * ver_info);
/** 线程池大小，根据计算机和用户负载来确定所需要的数量，一般与CPU的核心数一致可以发挥最大性能, 在任何流操作前调用方可生效
    Try to set it according to your number of CPU cores so you can 
    make use of the whole performace of your computer.  Call before any stream operations initiated **/
STREAMSDK_API int streamsdk_set_thread_pool_size(int num);	

/********** 流操作 stream operations **********/
/** 线程安全：
      对同一个HSTREAM句柄的不安全
      对不同HSTREAM句柄安全
    数据获取方式:
      同步方式 - 使用 streamsdk_grab_x 函数以阻塞的方式获取
      异步方式 - 向 HSTREAM 句柄提供 streamsdk_cb_x_grabber回调函数指针

**/

/** 创建一个流，获得HSTREAM句柄，需要HSTREAM
    输入：
        link		目标设备IP地址或域名
        port_no		服务端口号
    输出：
        hstream		HSTREAM句柄
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
    备注：
        如果数据流包含H.264压缩视频，见streamsdk_create_h264_decoder
**/
STREAMSDK_API int streamsdk_create_stream(__IN char * link,unsigned short port_no,__OUT HSTREAM *);		

/** 销毁HSTREAM句柄
    输入：
        hstream		HSTREAM句柄
    输出：
        
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_destroy_stream(HSTREAM hstream);

/** 开始流接收，设定数据帧回调函数
    输入:
        hstream				HSTREAM句柄
        path				数据流的URL路径
        max_packet_size		最大帧大小,流接收时分配的缓冲区的大小
        grabber				数据帧回调函数,空(NULL)表示不设定回调函数
        user_data			用户指针，库不会改变其内容，直接在回调函数中返回
    返回:
        成功返回STREAMSDK_EC_OK，网络超时返回STREAMSDK_EC_TIMEOUT，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_start_stream(HSTREAM hstream,__IN char * path,int max_packet_size,streamsdk_cb_grabber grabber,__IN void * user_data);

/** 停止流接收，回调函数在此函数调用成功后将不会被调用
    输入：
        hstream				HSTREAM句柄
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_stop_stream(HSTREAM hstream);

/** 修改回调函数指针
    输入：
        hstream		HSTREAM句柄
        grabber		解码回调函数指针，空(NULL)表示不设定回调函数
        user_data	用户指针，库不会改变其内容，直接在回调函数中返回
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
    备注：
        可在HSTREAM生命期内任意时刻调用
**/
STREAMSDK_API int streamsdk_set_stream_grabber(HSTREAM hstream,streamsdk_cb_grabber grabber,__IN void * user_data); 

/** 获取一个数据帧
    输入：
        hstream		HSTREAM句柄
        buf		    数据缓冲区对像，buf->ptr设定为NULL时，可得到所需要缓冲区大小
        timeout_ms  接收超时为多少毫秒，0表示永不超时
    返回：
        成功返回STREAMSDK_EC_OK，指定时间内未收到数据帧返回STREAMSDK_EC_TIMEOUT,其它返回STREAMSDK_EC_FAIL
    备注：
        获取数据函数会在实际接收到下帧数据前阻塞，或者指定的超时时间已经到了，
        用户需要初始化buf->ptr，为接收到的数据帧分配足够的空间(即 >= buf->buf_size),
**/
STREAMSDK_API int streamsdk_grab_buffer(HSTREAM hstream,__INOUT streamsdk_st_buffer * buf,int timeout_ms);

/********** 解码器操作 decoder operations **********/
/** 线程安全：
      对同一个HDECODER句柄的不安全
      对不同HDECODER句柄安全
**/

/** 创建一个解码器并与HSTREAM指向的流连接
    输入:
        hstream		待解码的流句柄
        param		解码器的参数
    输出:
        hdecoder	解码器句柄
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
    备注：
        HSTREAM句柄在HDECODER未销毁之前被销毁（streamsdk_destroy_stream)是允许的，但这时HDECODER将不会接收到数据
**/
STREAMSDK_API int streamsdk_create_h264_decoder(HSTREAM hstream,__IN streamsdk_st_decoder_param *param,__OUT HDECODER *hdecoder);

/** 销毁解码器 
    输入：
        hdecoder	解码器句柄
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_destroy_h264_decoder(HDECODER hdecoder);

/** 开始解码 
    输入：
        hdecoder	解码器句柄
        grabber		解码回调函数指针,空(NULL)表示不设定回调函数
        user_data	用户指针，库不会改变其内容，直接在回调函数中返回
    输出：
    
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_start_h264_decoder(HDECODER hdecoder,streamsdk_cb_image_grabber grabber,__IN void * user_data);

/** 停止解码，回调函数在此函数调用成功后将不会被调用
    输入：
        hdecoder	HDECODER句柄

    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_stop_h264_decoder(HDECODER hdecoder);

/** 修改回调函数指针
    输入：
        hdecoder	HDECODER句柄
        grabber		解码回调函数指针，空(NULL)表示不设定回调函数
        user_data	用户指针，库不会改变其内容，直接在回调函数中返回
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
    备注：
        可在HDECODER生命期内任意时刻调用
**/
STREAMSDK_API int streamsdk_set_image_grabber(HDECODER hdecoder,streamsdk_cb_image_grabber grabber,__IN void * user_data);

/** 分配图像内存空间
    输入：
        img		    img->ptr 必须是NULL，用户填写图像的结构信息，（可从streamsdk_grab_image获得）
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_create_image(__INOUT streamsdk_st_image * img);

/** 释放图像内存空间
    输入：
        img		    必须是调用streamsdk_create_image创建的图像
    返回：
        成功返回STREAMSDK_EC_OK，其它返回STREAMSDK_EC_FAIL
**/
STREAMSDK_API int streamsdk_destroy_image(__IN streamsdk_st_image * img);

/** 获取一帧图像
    输入：
        hdecoder	HDECODER句柄
        img		    图像对像，img->ptr设定为NULL时，可得到图像的结构信息
                    用于由streamsdk_create_image分配图像缓存空间
        timeout_ms  接收超时为多少毫秒，0表示永不超时
    返回：
        成功返回STREAMSDK_EC_OK，指定时间内未收到图像返回STREAMSDK_EC_TIMEOUT,其它返回STREAMSDK_EC_FAIL
    备注：
        获取图像函数会在实际接收到下帧图像前阻塞，或者指定的超时时间已经到了，用户需要为接收到的图像分配足够的空间，请
        使用streamsdk_create_image分配足够空间，并在不再需要使用图像对像时用streamsdk_destroy_image销毁。
**/
STREAMSDK_API int streamsdk_grab_image(HDECODER hdecoder,__INOUT streamsdk_st_image * img,int timeout_ms);

/***** recorder operations ****/
STREAMSDK_API int streamsdk_create_mp4_recorder(HSTREAM h,__IN char * filename,__IN streamsdk_st_recorder_param *,__OUT HRECORDER *);
STREAMSDK_API int streamsdk_destroy_mp4_recorder(HRECORDER h);
STREAMSDK_API int streamsdk_start_mp4_recorder(HRECORDER h);
STREAMSDK_API int streamsdk_stop_mp4_recorder(HRECORDER h);

/***** event operations ****/
STREAMSDK_API int streamsdk_create_event_decoder(HSTREAM h,__OUT HDECODER *);
STREAMSDK_API int streamsdk_destroy_event_decoder(HDECODER h);
STREAMSDK_API int streamsdk_start_event_decoder(HDECODER h,streamsdk_cb_event_grabber grabber,__IN void * user_data);
STREAMSDK_API int streamsdk_stop_event_decoder(HDECODER h);
STREAMSDK_API int streamsdk_set_event_grabber(HDECODER h,streamsdk_cb_event_grabber grabber,__IN void * user_data);
#endif
