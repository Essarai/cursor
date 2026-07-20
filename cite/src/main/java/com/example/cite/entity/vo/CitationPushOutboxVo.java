package com.example.cite.entity.vo;

import com.example.cite.entity.eo.CitationPushOutboxEo;
import com.example.cite.entity.eo.PushStatus;
import com.example.cite.entity.eo.SyncSource;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 出站推送 request 表单，字段与 {@link CitationPushOutboxEo} 一致。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CitationPushOutboxVo {

	private Long id;

	private String issn;

	private String issnNorm;

	private String title;

	private String year;

	private Integer cnkiCitation;

	private Integer cnkiDownload;

	private Integer wosCitation;

	private Integer cnkiId;

	private String wosGuid;

	private SyncSource syncSource;

	private PushStatus pushStatus;

	private Integer retryCount;

	private String lastErrorMsg;

	private LocalDateTime lastPushTime;

	private LocalDateTime createdAt;

	private LocalDateTime updatedAt;

	public static CitationPushOutboxVo fromEo(CitationPushOutboxEo eo) {
		if (eo == null) {
			return null;
		}
		return CitationPushOutboxVo.builder()
				.id(eo.getId())
				.issn(eo.getIssn())
				.issnNorm(eo.getIssnNorm())
				.title(eo.getTitle())
				.year(eo.getYear())
				.cnkiCitation(eo.getCnkiCitation())
				.cnkiDownload(eo.getCnkiDownload())
				.wosCitation(eo.getWosCitation())
				.cnkiId(eo.getCnkiId())
				.wosGuid(eo.getWosGuid())
				.syncSource(eo.getSyncSource())
				.pushStatus(eo.getPushStatus())
				.retryCount(eo.getRetryCount())
				.lastErrorMsg(eo.getLastErrorMsg())
				.lastPushTime(eo.getLastPushTime())
				.createdAt(eo.getCreatedAt())
				.updatedAt(eo.getUpdatedAt())
				.build();
	}

}
