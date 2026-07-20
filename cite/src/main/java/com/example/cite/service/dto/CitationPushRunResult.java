package com.example.cite.service.dto;

import lombok.Builder;
import lombok.Value;

@Value
@Builder
public class CitationPushRunResult {

	int batches;

	int totalPushed;

	int totalSuccess;

	int totalFailed;

	long remaining;

}
