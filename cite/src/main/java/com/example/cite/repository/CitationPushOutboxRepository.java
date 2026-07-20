package com.example.cite.repository;

import java.util.Collection;
import java.util.List;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import com.example.cite.entity.eo.CitationPushOutboxEo;
import com.example.cite.entity.eo.PushStatus;

public interface CitationPushOutboxRepository extends JpaRepository<CitationPushOutboxEo, Long> {

	List<CitationPushOutboxEo> findByPushStatusInAndRetryCountLessThanOrderByIdAsc(
			Collection<PushStatus> pushStatuses, int maxRetry, Pageable pageable);

	long countByPushStatusInAndRetryCountLessThan(Collection<PushStatus> pushStatuses, int maxRetry);

}
