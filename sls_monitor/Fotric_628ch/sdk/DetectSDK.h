/*
 * DetectSDK 1.0
 * Copyright 2016, IRS.cn
 *
 * library for detect iir devices on LAN and event reception
*/

#ifndef DETECTSDK_H_INCLUDED
#define DETECTSDK_H_INCLUDED

#pragma once

#ifdef _WIN32
#ifdef DETECTSDK_EXPORTS
#ifdef __cplusplus
#define DETECTSDK_API extern "C" __declspec(dllexport)
#else
#define DETECTSDK_API __declspec(dllexport)
#endif
#else
#ifdef __cplusplus
#define DETECTSDK_API extern "C" __declspec(dllimport)
#else
#define DETECTSDK_API __declspec(dllexport)
#endif
#endif

#ifndef CALLBACK
#define CALLBACK __stdcall
#endif

#else
#ifdef __cplusplus
#define DETECTSDK_API extern "C"
#else
#define DETECTSDK_API
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


/**** types ****/
enum detectsdk_enum_error_code
{
	DETECTSDK_EC_OK = 0,
	DETECTSDK_EC_FAIL = 1,
	DETECTSDK_EC_LIMIT,
};

/* DetectSDK Interfaces

 *  Caller should be responsible for allocating enough memory, when passing char * buffers.
    The buffer size should be at least DETECTSDK_STR_BUFSZ bytes, if no other request is specified.
 *  Callback function pointer may be set to NULL to disable callback
 */
enum detectsdk_enum_buffer
{
	DETECTSDK_STR_BUFSZ = 256,
};

typedef void * HDETECTOR;
typedef void * HRECEPTOR;

typedef struct detectsdk_st_version_
{
	int version[4];
	char version_tag[16];				///null-terminated string
	char version_build[9];
}detectsdk_st_version;

enum detectsdk_enum_node_status
{
	DETECTSDK_NODE_WANDERING = 0x0001,
};

typedef struct detectsdk_st_node_info_
{
	char node_boot_id[16];
	char node_addr[DETECTSDK_STR_BUFSZ];
	char node_static_addr[DETECTSDK_STR_BUFSZ];
	char node_netmask[DETECTSDK_STR_BUFSZ];		///deprecated, use node_prefix
	char node_gateway[DETECTSDK_STR_BUFSZ];		///not contained in detect reply packets
	char node_dns[DETECTSDK_STR_BUFSZ];			///not contained in detect reply packets
	char node_uuid[16];
	char node_sn[DETECTSDK_STR_BUFSZ];
	char node_model[DETECTSDK_STR_BUFSZ];
	char node_version[DETECTSDK_STR_BUFSZ];
	int node_prefix;
	int node_status;							///detectsdk_enum_node_status
}detectsdk_st_node_info;


typedef void (CALLBACK * detectsdk_cb_device_online)(__IN detectsdk_st_node_info * ,__IN void * user_data);
typedef void (CALLBACK * detectsdk_cb_device_offline)(__IN detectsdk_st_node_info * ,__IN void * user_data);

/**** common ****/
DETECTSDK_API int detectsdk_get_version(__OUT int * ver_no);		/* Version number is an array of 4 integers. */
DETECTSDK_API int detectsdk_get_version_str(__OUT char * ver_info);
DETECTSDK_API int detectsdk_set_thread_pool_size(int num);			/* Call before any operations initiated. */

/**** Detector ****/
DETECTSDK_API int detectsdk_create_detector(__IN char * net_iface,int detect_timeout_ms,__OUT HDETECTOR *);
DETECTSDK_API int detectsdk_destroy_detector(HDETECTOR h);
DETECTSDK_API int detectsdk_start_detector(HDETECTOR h,int detect_interval_ms,detectsdk_cb_device_online cb,__IN void * user);
DETECTSDK_API int detectsdk_stop_detector(HDETECTOR h);
DETECTSDK_API int detectsdk_get_detected_nodes(HDETECTOR h,__OUT detectsdk_st_node_info * node_list,__INOUT int * list_cnt);
DETECTSDK_API int detectsdk_set_device_online_listener(HDETECTOR h,detectsdk_cb_device_online cb,__IN void * user);
DETECTSDK_API int detectsdk_set_device_offline_listener(HDETECTOR h,detectsdk_cb_device_offline cb,__IN void * user);
DETECTSDK_API int detectsdk_refresh(HDETECTOR h);

/**** Node Configuration ****/
/* Only node_boot_id, node_addr,node_prefix, node_gateway,node_dns are used,
   you may put an empty node_addr to switch on DHCP of the remote device,
   input fileds may remain empty to keep their values.
*/
DETECTSDK_API int detectsdk_set_node_interface(__IN char * net_iface
		,int invoke_timeout_ms,__IN detectsdk_st_node_info * node);

/**** fwpack ****/
DETECTSDK_API int detectsdk_fwpack_version(__IN char * filename,__OUT detectsdk_st_version *);

#pragma pack(pop)
#endif
