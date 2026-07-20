package com.example.cite.entity.eo;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * Web of Science（WOS）文献引用数据实体，对应表 {@code t_wos_refer}。
 * <p>
 * 字段名为 WOS 导出标准缩写；标题（{@code ti}）几乎全部为英文。
 * 与知网关联键：{@code sn}（ISSN 去横线）+ {@code ti}（精确标题）+ {@code py}（年份）。
 */
@Getter
@Setter
@NoArgsConstructor
@Entity
@Table(name = "t_wos_refer")
public class WosReferEo {

	/** 主键，系统内部 GUID */
	@Id
	@Column(name = "guid", length = 40, nullable = false)
	private String guid;

	/** 对外合作信息 */
	@Column(name = "对外合作", columnDefinition = "mediumtext")
	private String foreignCooperation;

	/** PT - Publication Type，出版物类型（如 J=期刊论文） */
	@Column(name = "PT", columnDefinition = "mediumtext")
	private String pt;

	/** AU - Authors，作者（缩写形式，分号分隔） */
	@Column(name = "AU", columnDefinition = "mediumtext")
	private String au;

	/** BA - Book Authors，图书作者 */
	@Column(name = "BA", columnDefinition = "mediumtext")
	private String ba;

	/** CA - Corporate Authors，团体作者 */
	@Column(name = "CA", columnDefinition = "mediumtext")
	private String ca;

	/** GP - Group Authors，群组作者 */
	@Column(name = "GP", columnDefinition = "mediumtext")
	private String gp;

	/** RI - Researcher ID，研究者 ID */
	@Column(name = "RI", columnDefinition = "mediumtext")
	private String ri;

	/** OI - ORCID Identifier */
	@Column(name = "OI", columnDefinition = "mediumtext")
	private String oi;

	/** BE - Book Editors，图书编者 */
	@Column(name = "BE", columnDefinition = "mediumtext")
	private String be;

	/** Z2 - 丛书信息 */
	@Column(name = "Z2", columnDefinition = "mediumtext")
	private String z2;

	/** TI - Title，文章标题（英文为主，跨库关联键之一） */
	@Column(name = "TI", columnDefinition = "mediumtext")
	private String ti;

	/** X1 - 丛书标题 */
	@Column(name = "X1", columnDefinition = "mediumtext")
	private String x1;

	/** Y1 - 丛书副标题 */
	@Column(name = "Y1", columnDefinition = "mediumtext")
	private String y1;

	/** Z1 - 丛书编者 */
	@Column(name = "Z1", columnDefinition = "mediumtext")
	private String z1;

	/** FT - Foreign Title，外文标题 */
	@Column(name = "FT", columnDefinition = "mediumtext")
	private String ft;

	/** PN - Part Number，分册号 */
	@Column(name = "PN", columnDefinition = "mediumtext")
	private String pn;

	/** AE - Patent Assignee，专利受让人 */
	@Column(name = "AE", columnDefinition = "mediumtext")
	private String ae;

	/** Z3 - 丛书 ISSN */
	@Column(name = "Z3", columnDefinition = "mediumtext")
	private String z3;

	/** SO - Source，来源期刊全名 */
	@Column(name = "SO", columnDefinition = "mediumtext")
	private String so;

	/** S1 - Series Title，丛书名 */
	@Column(name = "S1", columnDefinition = "mediumtext")
	private String s1;

	/** SE - Series Title Abbreviation，丛书缩写 */
	@Column(name = "SE", columnDefinition = "mediumtext")
	private String se;

	/** BS - Book Series Subtitle，丛书副标题 */
	@Column(name = "BS", columnDefinition = "mediumtext")
	private String bs;

	/** VL - Volume，卷号 */
	@Column(name = "VL", columnDefinition = "mediumtext")
	private String vl;

	/** IS_ - Issue，期号 */
	@Column(name = "IS_", columnDefinition = "mediumtext")
	private String isIssue;

	/** SI - Special Issue，特刊标识 */
	@Column(name = "SI", columnDefinition = "mediumtext")
	private String si;

	/** MA - Meeting Abstract，会议摘要编号 */
	@Column(name = "MA", columnDefinition = "mediumtext")
	private String ma;

	/** BP - Beginning Page，起始页码 */
	@Column(name = "BP", columnDefinition = "mediumtext")
	private String bp;

	/** EP - Ending Page，结束页码 */
	@Column(name = "EP", columnDefinition = "mediumtext")
	private String ep;

	/** AR - Article Number，文章编号（无传统页码时使用） */
	@Column(name = "AR", columnDefinition = "mediumtext")
	private String ar;

	/** DI - Digital Object Identifier，DOI（国际 DOI，与知网 DOI 体系不同） */
	@Column(name = "DI", columnDefinition = "mediumtext")
	private String di;

	/** D2 - Book DOI，图书 DOI */
	@Column(name = "D2", columnDefinition = "mediumtext")
	private String d2;

	/** EA - Early Access Date，提前在线发表日期 */
	@Column(name = "EA", columnDefinition = "mediumtext")
	private String ea;

	/** SU - Supplement，增刊信息 */
	@Column(name = "SU", columnDefinition = "mediumtext")
	private String su;

	/** PD - Publication Date，出版日期 */
	@Column(name = "PD", columnDefinition = "mediumtext")
	private String pd;

	/** PY - Publication Year，发表年份（跨库关联键之一） */
	@Column(name = "PY", columnDefinition = "mediumtext")
	private String py;

	/** AB - Abstract，摘要 */
	@Column(name = "AB", columnDefinition = "mediumtext")
	private String ab;

	/** X4 - 丛书卷号 */
	@Column(name = "X4", columnDefinition = "mediumtext")
	private String x4;

	/** Y4 - 丛书期号 */
	@Column(name = "Y4", columnDefinition = "mediumtext")
	private String y4;

	/** Z4 - 丛书页码 */
	@Column(name = "Z4", columnDefinition = "mediumtext")
	private String z4;

	/** AK - Author Keywords，作者关键词 */
	@Column(name = "AK", columnDefinition = "mediumtext")
	private String ak;

	/** CT - Conference Title，会议名称 */
	@Column(name = "CT", columnDefinition = "mediumtext")
	private String ct;

	/** CY - Conference Date，会议日期 */
	@Column(name = "CY", columnDefinition = "mediumtext")
	private String cy;

	/** SP - Conference Sponsors，会议主办方 */
	@Column(name = "SP", columnDefinition = "mediumtext")
	private String sp;

	/** CL - Conference Location，会议地点 */
	@Column(name = "CL", columnDefinition = "mediumtext")
	private String cl;

	/** TC - Times Cited（WOS 核心合集），WOS 被引次数 */
	@Column(name = "TC", columnDefinition = "mediumtext")
	private String tc;

	/** Z8 - 被引频次相关扩展字段 */
	@Column(name = "Z8", columnDefinition = "mediumtext")
	private String z8;

	/** ZR - 被引相关扩展字段 */
	@Column(name = "ZR", columnDefinition = "mediumtext")
	private String zr;

	/** ZA - 被引相关扩展字段 */
	@Column(name = "ZA", columnDefinition = "mediumtext")
	private String za;

	/** ZB - 被引相关扩展字段 */
	@Column(name = "ZB", columnDefinition = "mediumtext")
	private String zb;

	/** ZS - 被引相关扩展字段 */
	@Column(name = "ZS", columnDefinition = "mediumtext")
	private String zs;

	/** Z9 - Times Cited, All Databases，全库被引次数（通常作为 WOS 引用指标） */
	@Column(name = "Z9", columnDefinition = "mediumtext")
	private String z9;

	/** U1 - Usage Count (Last 180 Days)，近 180 天使用次数 */
	@Column(name = "U1", columnDefinition = "mediumtext")
	private String u1;

	/** U2 - Usage Count (Since 2013)，2013 年以来使用次数 */
	@Column(name = "U2", columnDefinition = "mediumtext")
	private String u2;

	/** SN - ISSN，国际标准期刊号（跨库关联键之一，匹配时需去横线归一化） */
	@Column(name = "SN", columnDefinition = "mediumtext")
	private String sn;

	/** EI - eISSN，电子版 ISSN */
	@Column(name = "EI", columnDefinition = "mediumtext")
	private String ei;

	/** BN - ISBN，国际标准书号 */
	@Column(name = "BN", columnDefinition = "mediumtext")
	private String bn;

	/** UT - Unique WOS ID，WOS 唯一入藏号（如 WOS:000xxxx） */
	@Column(name = "UT", columnDefinition = "mediumtext")
	private String ut;

	/** PM - PubMed ID */
	@Column(name = "PM", columnDefinition = "mediumtext")
	private String pm;

	/** AF - Author Full Names，作者全名 */
	@Column(name = "AF", columnDefinition = "mediumtext")
	private String af;

	/** BF - Book Authors Full Names，图书作者全名 */
	@Column(name = "BF", columnDefinition = "mediumtext")
	private String bf;

	/** LA - Language，文献语言 */
	@Column(name = "LA", columnDefinition = "mediumtext")
	private String la;

	/** DT - Document Type，文献类型 */
	@Column(name = "DT", columnDefinition = "mediumtext")
	private String dt;

	/** HO - Book Authors Full Names（部分导出格式中的图书作者全名） */
	@Column(name = "HO", columnDefinition = "mediumtext")
	private String ho;

	/** DE - Author Keywords / Descriptors，关键词或叙词 */
	@Column(name = "DE", columnDefinition = "mediumtext")
	private String de;

	/** ID - Keywords Plus，WOS 扩展关键词 */
	@Column(name = "ID", columnDefinition = "mediumtext")
	private String wosId;

	/** C1 - Author Address，作者地址 */
	@Column(name = "C1", columnDefinition = "mediumtext")
	private String c1;

	/** RP - Reprint Address，通讯作者地址 */
	@Column(name = "RP", columnDefinition = "mediumtext")
	private String rp;

	/** EM - Email Address，电子邮箱 */
	@Column(name = "EM", columnDefinition = "mediumtext")
	private String em;

	/** FU - Funding Agency，资助机构 */
	@Column(name = "FU", columnDefinition = "mediumtext")
	private String fu;

	/** FX - Funding Text，资助说明全文 */
	@Column(name = "FX", columnDefinition = "mediumtext")
	private String fx;

	/** CR - Cited References，参考文献列表 */
	@Column(name = "CR", columnDefinition = "mediumtext")
	private String cr;

	/** NR - Number of References，参考文献数量 */
	@Column(name = "NR", columnDefinition = "mediumtext")
	private String nr;

	/** PU - Publisher，出版商 */
	@Column(name = "PU", columnDefinition = "mediumtext")
	private String pu;

	/** PI - Publisher City，出版地城市 */
	@Column(name = "PI", columnDefinition = "mediumtext")
	private String pi;

	/** PA - Publisher Address，出版商地址 */
	@Column(name = "PA", columnDefinition = "mediumtext")
	private String pa;

	/** J9 - Journal Abbreviation（29 字符），期刊缩写 */
	@Column(name = "J9", columnDefinition = "mediumtext")
	private String j9;

	/** JI - ISO Source Abbreviation，ISO 期刊缩写 */
	@Column(name = "JI", columnDefinition = "mediumtext")
	private String ji;

	/** C3 - 作者地址扩展信息 */
	@Column(name = "C3", columnDefinition = "mediumtext")
	private String c3;

	/** DA - Date Added to WOS，入藏 WOS 日期 */
	@Column(name = "DA", columnDefinition = "mediumtext")
	private String da;

	/** DL - Date Published，出版日期 */
	@Column(name = "DL", columnDefinition = "mediumtext")
	private String dl;

	/** GA - Document Delivery Number，文献传递号 */
	@Column(name = "GA", columnDefinition = "mediumtext")
	private String ga;

	/** HC - ESI Highly Cited Paper，ESI 高被引论文标识 */
	@Column(name = "HC", columnDefinition = "mediumtext")
	private String hc;

	/** HP - Hot Paper，热点论文标识 */
	@Column(name = "HP", columnDefinition = "mediumtext")
	private String hp;

	/** OA - Open Access，开放获取标识 */
	@Column(name = "OA", columnDefinition = "mediumtext")
	private String oa;

	/** PG - Page Count，页数 */
	@Column(name = "PG", columnDefinition = "mediumtext")
	private String pg;

	/** SC - Research Areas，研究领域 */
	@Column(name = "SC", columnDefinition = "mediumtext")
	private String sc;

	/** WC - Web of Science Categories，WOS 学科分类 */
	@Column(name = "WC", columnDefinition = "mediumtext")
	private String wc;

	/** WE - 学科相关扩展字段 */
	@Column(name = "WE", columnDefinition = "mediumtext")
	private String we;

	/** FP - Conference Host，会议承办方 */
	@Column(name = "FP", columnDefinition = "mediumtext")
	private String fp;

	/** AU_ALL - 全部作者（合并字符串） */
	@Column(name = "AU_ALL", columnDefinition = "mediumtext")
	private String auAll;

	/** AU_JSON - 作者结构化 JSON */
	@Column(name = "AU_JSON", columnDefinition = "mediumtext")
	private String auJson;

	/** AU_STATUS - 作者信息处理状态 */
	@Column(name = "AU_STATUS")
	private Integer auStatus;

	/** BELONG_UNIT - 所属单位编码 */
	@Column(name = "BELONG_UNIT", length = 2)
	private String belongUnit;

	/** BELONG_COM - 所属公司编码 */
	@Column(name = "BELONG_COM", length = 2)
	private String belongCom;

	/** COLLECT_TIME - 数据采集时间 */
	@Column(name = "COLLECT_TIME")
	private LocalDateTime collectTime;

	/** 检索时使用的查询条件 */
	@Column(name = "查询条件", length = 255)
	private String queryCondition;

}
