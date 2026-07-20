package com.example.cite.service.dto;

import lombok.Builder;
import lombok.Value;

@Value
@Builder
public class CitationPushBatchResult {

	int batchSize;

	int successCount;

	int failCount;

	public static CitationPushBatchResult empty() {
		return CitationPushBatchResult.builder()
				.batchSize(0)
				.successCount(0)
				.failCount(0)
				.build();
	}

}
