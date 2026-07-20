package com.example.cite.service;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.example.cite.client.CitationPushClient;
import com.example.cite.config.CitationPushProperties;
import com.example.cite.entity.eo.CitationPushOutboxEo;
import com.example.cite.entity.eo.PushStatus;
import com.example.cite.entity.vo.CitationPushOutboxVo;
import com.example.cite.entity.vo.CitationPushResponseVo;
import com.example.cite.repository.CitationPushOutboxRepository;
import com.example.cite.service.dto.CitationPushBatchResult;
import com.example.cite.service.dto.CitationPushRunResult;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
@RequiredArgsConstructor
public class CitationPushService {

	private static final List<PushStatus> PUSHABLE_STATUSES = List.of(PushStatus.PENDING, PushStatus.FAILED);

	private final CitationPushOutboxRepository outboxRepository;
	private final CitationPushClient pushClient;
	private final CitationPushProperties properties;

	@Transactional
	public CitationPushBatchResult pushNextBatch() {
		List<CitationPushOutboxEo> batch = fetchNextBatch();
		if (batch.isEmpty()) {
			return CitationPushBatchResult.empty();
		}

		List<CitationPushOutboxVo> requestBody = batch.stream()
				.map(CitationPushOutboxVo::fromEo)
				.toList();

		try {
			CitationPushResponseVo response = pushClient.push(requestBody);
			return applyResponse(batch, response);
		}
		catch (Exception ex) {
			log.error("推送批次失败，本批 {} 条: {}", batch.size(), ex.getMessage());
			markBatchFailed(batch, ex.getMessage());
			return CitationPushBatchResult.builder()
					.batchSize(batch.size())
					.successCount(0)
					.failCount(batch.size())
					.build();
		}
	}

	public CitationPushRunResult pushBatches(int maxBatches) {
		int batches = 0;
		int totalPushed = 0;
		int totalSuccess = 0;
		int totalFailed = 0;

		int limit = maxBatches > 0 ? maxBatches : properties.getMaxBatchesPerRun();
		while (batches < limit) {
			CitationPushBatchResult result = pushNextBatch();
			if (result.getBatchSize() == 0) {
				break;
			}
			batches++;
			totalPushed += result.getBatchSize();
			totalSuccess += result.getSuccessCount();
			totalFailed += result.getFailCount();
		}

		long remaining = countRemaining();
		log.info("推送完成: batches={}, pushed={}, success={}, failed={}, remaining={}",
				batches, totalPushed, totalSuccess, totalFailed, remaining);

		return CitationPushRunResult.builder()
				.batches(batches)
				.totalPushed(totalPushed)
				.totalSuccess(totalSuccess)
				.totalFailed(totalFailed)
				.remaining(remaining)
				.build();
	}

	public long countRemaining() {
		return outboxRepository.countByPushStatusInAndRetryCountLessThan(
				PUSHABLE_STATUSES, properties.getMaxRetry());
	}

	private List<CitationPushOutboxEo> fetchNextBatch() {
		PageRequest page = PageRequest.of(0, properties.getBatchSize());
		return outboxRepository.findByPushStatusInAndRetryCountLessThanOrderByIdAsc(
				PUSHABLE_STATUSES, properties.getMaxRetry(), page);
	}

	private CitationPushBatchResult applyResponse(List<CitationPushOutboxEo> batch,
			CitationPushResponseVo response) {
		LocalDateTime now = LocalDateTime.now();
		Map<Long, String> failureMessages = buildFailureMessageMap(response);

		int successCount = 0;
		int failCount = 0;

		for (CitationPushOutboxEo eo : batch) {
			if (failureMessages.containsKey(eo.getId())) {
				eo.setPushStatus(PushStatus.FAILED);
				eo.setLastErrorMsg(truncate(failureMessages.get(eo.getId())));
				eo.setRetryCount(eo.getRetryCount() + 1);
				failCount++;
			}
			else {
				eo.setPushStatus(PushStatus.SUCCESS);
				eo.setLastErrorMsg(null);
				eo.setLastPushTime(now);
				successCount++;
			}
		}

		outboxRepository.saveAll(batch);
		log.info("批次回写完成: batch={}, success={}, failed={}", batch.size(), successCount, failCount);

		return CitationPushBatchResult.builder()
				.batchSize(batch.size())
				.successCount(successCount)
				.failCount(failCount)
				.build();
	}

	private void markBatchFailed(List<CitationPushOutboxEo> batch, String errorMessage) {
		String message = truncate(errorMessage);
		for (CitationPushOutboxEo eo : batch) {
			eo.setPushStatus(PushStatus.FAILED);
			eo.setLastErrorMsg(message);
			eo.setRetryCount(eo.getRetryCount() + 1);
		}
		outboxRepository.saveAll(batch);
	}

	private Map<Long, String> buildFailureMessageMap(CitationPushResponseVo response) {
		if (response == null || response.getFailures() == null || response.getFailures().isEmpty()) {
			return Map.of();
		}

		Map<Long, String> messages = new HashMap<>();
		for (CitationPushOutboxVo failure : response.getFailures()) {
			if (failure.getId() == null) {
				continue;
			}
			String msg = failure.getLastErrorMsg();
			messages.put(failure.getId(), msg != null ? msg : "第三方返回失败");
		}
		return messages;
	}

	private String truncate(String message) {
		if (message == null) {
			return null;
		}
		return message.length() <= 500 ? message : message.substring(0, 500);
	}

}
