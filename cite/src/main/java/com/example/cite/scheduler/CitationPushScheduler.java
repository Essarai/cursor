package com.example.cite.scheduler;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.example.cite.config.CitationPushProperties;
import com.example.cite.service.CitationPushService;
import com.example.cite.service.dto.CitationPushRunResult;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class CitationPushScheduler {

	private final CitationPushProperties properties;
	private final CitationPushService pushService;

	@Scheduled(fixedDelayString = "${cite.push.schedule.fixed-delay:300000}")
	public void scheduledPush() {
		if (!properties.isEnabled()) {
			return;
		}
		CitationPushRunResult result = pushService.pushBatches(properties.getMaxBatchesPerRun());
		if (result.getTotalPushed() > 0) {
			log.info("定时推送: batches={}, pushed={}, remaining={}",
					result.getBatches(), result.getTotalPushed(), result.getRemaining());
		}
	}

}
