package com.example.cite.entity.eo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 知网（CNKI）文献引用数据实体，对应表 {@code t_cnki_refer}。
 * <p>
 * 标题以中文为主（约 79% 纯中文、15% 中英混合），与 WOS 关联时需使用英文标题子集。
 */
@Getter
@Setter
@NoArgsConstructor
@Entity
@Table(name = "t_cnki_refer")
public class CnkiReferEo {

	/** 主键，自增 ID */
	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "ID")
	private Integer id;

	/** 期刊名称 */
	@Column(name = "journal", length = 400)
	private String journal;

	/** 期刊标识键 */
	@Column(name = "journal_key", length = 50)
	private String journalKey;

	/** 发表年份 */
	@Column(name = "year", length = 50)
	private String year;

	/** 期号 */
	@Column(name = "issue", length = 100)
	private String issue;

	/** 文章标题（多为中文，部分为英文或中英混合） */
	@Column(name = "title", columnDefinition = "mediumtext")
	private String title;

	/** 作者（分号分隔的字符串） */
	@Column(name = "creator", columnDefinition = "mediumtext")
	private String creator;

	/** 作者机构 */
	@Column(name = "institute", columnDefinition = "mediumtext")
	private String institute;

	/** 摘要 */
	@Column(name = "abstract", columnDefinition = "mediumtext")
	private String abstractText;

	/** 基金资助信息 */
	@Column(name = "fund", columnDefinition = "mediumtext")
	private String fund;

	/** DOI（多为知网自建 DOI，与国际 DOI 通常不一致，不宜用于跨库匹配） */
	@Column(name = "DOI", length = 200)
	private String doi;

	/** 关键词 */
	@Column(name = "keyword", columnDefinition = "mediumtext")
	private String keyword;

	/** 学科分类 */
	@Column(name = "subject", length = 300)
	private String subject;

	/** 知网下载次数 */
	@Column(name = "download_count", length = 100)
	private String downloadCount;

	/** 数据更新时间 */
	@Column(name = "updatetime")
	private LocalDateTime updatetime;

	/** 知网原文链接 */
	@Column(name = "url", columnDefinition = "mediumtext")
	private String url;

	/** 页码 */
	@Column(name = "page", length = 512)
	private String page;

	/** 页数 */
	@Column(name = "pageCounts", length = 128)
	private String pageCounts;

	/** 期刊 ISSN（跨库关联键之一，匹配时需去横线归一化） */
	@Column(name = "ISSN", length = 128)
	private String issn;

	/** 知网文献编码（采集批次内唯一标识） */
	@Column(name = "code", length = 30)
	private String code;

	/** 主题分类 */
	@Column(name = "zt", length = 255)
	private String zt;

	/** 专辑/专题分类 */
	@Column(name = "zj", length = 255)
	private String zj;

	/** 作者结构化 JSON（含姓名、机构等） */
	@Column(name = "au_json", columnDefinition = "mediumtext")
	private String auJson;

	/** 知网被引次数 */
	@Column(name = "citation_num", length = 10)
	private String citationNum;

	/** 期刊被引次数 */
	@Column(name = "citation_qk_num", length = 10)
	private String citationQkNum;

	/** 参考文献数量 */
	@Column(name = "reference_num", length = 10)
	private String referenceNum;

	/** 数据版本号 */
	@Column(name = "version_no", length = 20)
	private String versionNo;

}
