package com.example.cite.entity.eo;

/**
 * 触发维护出站记录的数据同步来源。
 */
public enum SyncSource {

	/** 知网爬虫同步 */
	CNKI,

	/** WOS 爬虫同步 */
	WOS,

	/** 知网与 WOS 均参与 */
	BOTH

}
