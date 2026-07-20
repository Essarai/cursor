package com.example.cite.entity.eo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 引用指标出站推送表，对应 {@code t_citation_push_outbox}。
 * 由知网 / WOS 爬虫同步时的数据库触发器维护。
 */
@Getter
@Setter
@NoArgsConstructor
@Entity
@Table(name = "t_citation_push_outbox")
public class CitationPushOutboxEo {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "issn", length = 128, nullable = false)
	private String issn;

	@Column(name = "issn_norm", length = 64, nullable = false)
	private String issnNorm;

	@Column(name = "title", nullable = false, columnDefinition = "varchar(2000)")
	private String title;

	@Column(name = "year", length = 16, nullable = false)
	private String year;

	@Column(name = "cnki_citation")
	private Integer cnkiCitation;

	@Column(name = "cnki_download")
	private Integer cnkiDownload;

	@Column(name = "wos_citation")
	private Integer wosCitation;

	@Column(name = "cnki_id")
	private Integer cnkiId;

	@Column(name = "wos_guid", length = 40)
	private String wosGuid;

	@Enumerated(EnumType.STRING)
	@Column(name = "sync_source", length = 16, nullable = false)
	private SyncSource syncSource;

	@Enumerated(EnumType.STRING)
	@Column(name = "push_status", length = 16, nullable = false)
	private PushStatus pushStatus;

	@Column(name = "retry_count", nullable = false)
	private Integer retryCount;

	@Column(name = "last_error_msg", length = 500)
	private String lastErrorMsg;

	@Column(name = "last_push_time")
	private LocalDateTime lastPushTime;

	@Column(name = "created_at", nullable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

}
