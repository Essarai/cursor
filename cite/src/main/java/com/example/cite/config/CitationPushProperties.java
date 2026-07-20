package com.example.cite.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import lombok.Data;

@Data
@Component
@ConfigurationProperties(prefix = "cite.push")
public class CitationPushProperties {

	/** 是否启用定时推送 */
	private boolean enabled = false;

	/** 第三方批量接收接口 URL */
	private String url = "";

	/** 每批推送条数 */
	private int batchSize = 200;

	/** 最大重试次数 */
	private int maxRetry = 5;

	/** 单次调度最多连续推送批次数（防止单次任务运行过久） */
	private int maxBatchesPerRun = 10;

	/** 定时任务间隔（毫秒） */
	private long scheduleFixedDelay = 300_000L;

	/** HTTP 连接超时（毫秒） */
	private int connectTimeout = 30_000;

	/** HTTP 读取超时（毫秒） */
	private int readTimeout = 60_000;

}
