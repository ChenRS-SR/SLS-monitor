/**
	restc

	REST访问接口库
	REST-api client

	v2.1    2019.1
	v1.0.2	2017.8.21
	v1.0	2015.11.27

**/

#ifndef RESTC_H_INCLUDED
#define RESTC_H_INCLUDED
#pragma once

#include <stdlib.h>

///DLL for Windows
#ifdef _WIN32
#ifdef RESTC_EXPORTS
#ifdef __cplusplus
#define RESTC_API extern "C" __declspec(dllexport)
#else
#define RESTC_API __declspec(dllexport)
#endif
#else
#ifdef __cplusplus
#define RESTC_API extern "C" __declspec(dllimport)
#else
#define RESTC_API __declspec(dllexport)
#endif
#endif ///REST_EXPORTS

///Shared library for Linux
#else
#ifdef __cplusplus
#define RESTC_API extern "C"
#else
#define RESTC_API
#endif
#endif /// _WIN32

#define __IN
#define __OUT
#define __INOUT

typedef void *		RESTC_PTR;
#ifdef _UNICODE
typedef wchar_t		RCHAR;
#else
typedef char	    RCHAR;
#endif
typedef unsigned short PORT_NUM;
typedef RESTC_PTR	RestConn;		/** REST连接句柄 **/
typedef RESTC_PTR	RestHeaders;
#define NullConn     NULL

enum RestcErrorCode{
	EC_OK		= 0,				/** 函数调用成功 **/
	EC_FAIL		= -1,				/** 函数调用失败 **/
	EC_BUFSZ    = -2,				/** 缓冲区错误 **/
	EC_NETWORK  = -3,				/** 网络错误 **/
    EC_NOT_SUPPORTED = -4,
};

/** 全局函数 Global libray functions **/
/** 线程池大小，根据计算机和用户负载来确定所需要的数量，一般与CPU的核心数一致可以发挥最大性能, 在任何流操作前调用方可生效
    Try to set it according to your number of CPU cores so you can
    make use of the whole performace of your computer.  Call before any stream operations initiated **/
RESTC_API void restc_set_thread_num(int num);
RESTC_API void restc_cleanup();
RESTC_API int restc_get_version(__IN unsigned int *,__OUT char * buf,__INOUT size_t * bsz);



/** HTTP头操作 HTTP header operations **/
RESTC_API RestHeaders restc_create_headers();
RESTC_API int restc_destroy_headers(RestHeaders);

RESTC_API int restc_add_header(RestHeaders,__IN const char * key,__IN const char * value);
RESTC_API int restc_get_header_num(RestHeaders);
RESTC_API int restc_get_header(RestHeaders,int idx,__IN char * key,__IN size_t * ksz,__OUT char * value,__INOUT size_t * vsz);
RESTC_API int restc_find_header(RestHeaders,__IN const char * key,__OUT char * value,__INOUT size_t * vsz);

/** 创建连接 restc connection **/
RESTC_API RestConn restc_create_connection(__IN const char * host,PORT_NUM);
RESTC_API RestConn restc_create_usb_connection(PORT_NUM vid,PORT_NUM pid);
RESTC_API int restc_destroy_connection(RestConn);
RESTC_API int restc_set_authroization(__IN const char * user,__IN const char * passwd);
RESTC_API int restc_set_timeout(RestConn,int timeout_ms);

/** REST操作 REST operations **/
/** 如果连接成功，REST函数将返回HTTP状态码，否则返回负整数
	These functions will return HTTP status code from the server
    when HTTP transaction completes.
      If any network error occur in midst of the transaction,
	it will return a negative integer value in RestcErrorCode.

	关于缓冲区
	所有的操作缓冲区都是由调用都分配空间，一般热像仪指令需要的缓冲区大小为1KB
	You should at least allocate 1KB memory as operation text buffer.
**/
/** REST GET 命令
	输入：
		c		RestConn连接句柄
		path	URL路径
		hdr		额外的HTTP头,可以为空(NULL)
		buf		接收到的正文将返回在此缓冲区中
		bufsz	输入的buf的大小（SDK写入的返回正文数据不会超出此界限，如果接收正文超过bufsz，函数返回EC_BUFSZ）
	输出：
		length	远端返回的正文长度

	返回：
		网络通信正常时返回HTTP状态码，其它情况返回负值
**/
RESTC_API int restc_get(RestConn c,__IN const char * path,RestHeaders hdr,__OUT char * buf,size_t bufsz,__OUT size_t * length);
/** REST PUT 命令
	输入：
		c		RestConn连接句柄
		path	URL路径
		hdr		额外的HTTP头,可以为空(NULL)
		buf		待发送的请求正文，接收到的正文也将返回在此缓冲区中，请求正文内容会被覆盖
		bufsz	输入的buf的大小（SDK写入的返回正文数据不会超出此界限，如果接收正文过大，函数返回EC_BUFSZ）
		length	待发送的请求正文长度
	输出：
		length	远端返回的正文长度

	返回：
		网络通信正常时返回HTTP状态码，其它情况返回负值
**/
RESTC_API int restc_put(RestConn c,__IN const char * path,RestHeaders hdr,__INOUT char * buf,size_t bufsz,__INOUT size_t * length);

/** REST DELETE 命令
	DELETE一般没有正文返回，buf可以为空(NULL)
	输入：
		c		RestConn连接句柄
		path	URL路径
		hdr		额外的HTTP头,可以为空(NULL)
		buf		接收到的正文将返回在此缓冲区中
		bufsz	输入的buf的大小
	输出：
		length	远端返回的正文长度

	返回：
		网络通信正常时返回HTTP状态码，其它情况返回负值
**/
RESTC_API int restc_del(RestConn c,__IN const char * path,RestHeaders hdr,__OUT char * buf,size_t bufsz,__OUT size_t * length);

/** REST POST 命令
	输入：
		c		RestConn连接句柄
		path	URL路径
		hdr		额外的HTTP头,可以为空(NULL)
		buf		待发送的请求正文，接收到的正文也将返回在此缓冲区中，请求正文内容会被覆盖
		bufsz	输入的buf的大小（SDK写入的返回正文数据不会超出此界限，如果接收正文过大，函数返回EC_BUFSZ）
		length	待发送的请求正文长度
	输出：
		length	远端返回的正文长度

	返回：
		网络通信正常时返回HTTP状态码，其它情况返回负值
**/
RESTC_API int restc_post(RestConn c,__IN const char * path,RestHeaders hdr,__INOUT char * buf,size_t bufsz,__INOUT size_t * length);

/** REST POST 命令,上传指定文件
	输入：
		c		RestConn连接句柄
		path	URL路径
		hdr		额外的HTTP头,可以为空(NULL)
		filepath	待上传文件的本地路径
		buf		接收到的正文将返回在此缓冲区中
		bufsz	输入的buf的大小（SDK写入的返回正文数据不会超出此界限，如果接收正文过大，函数返回EC_BUFSZ）
	输出：
		length	远端返回的正文长度

	返回：
		网络通信正常时返回HTTP状态码，其它情况返回负值
**/
RESTC_API int restc_post_file(RestConn c,__IN const char * path,RestHeaders hdr
							  ,__IN const char * filepath,__OUT char * buf,size_t bufsz,__OUT size_t * length);

/** REST POST 命令,上传指定内存数据
	输入：
		c		RestConn连接句柄
		path	URL路径
		hdr		额外的HTTP头,可以为空(NULL)
		send_buf	待上传内存起始指针
		send_sz		上传内存大小
		reply_buf	接收到的正文将返回在此缓冲区中
		reply_sz	输入的buf的大小（SDK写入的返回正文数据不会超出此界限，如果接收正文过大，函数返回EC_BUFSZ）
	输出：
		reply_sz	远端返回的正文长度

	返回：
		网络通信正常时返回HTTP状态码，其它情况返回负值
**/
RESTC_API int restc_post_buffer(RestConn c,__IN const char * path,RestHeaders hdr
							  ,__IN const char * send_buf,size_t send_sz,
							  __OUT char * reply_buf,__INOUT size_t * reply_sz);

RESTC_API int restc_usb_grab(RestConn c,__OUT char * grab_buf,size_t grab_sz);

#endif ///RESTC_H_INCLUDED
