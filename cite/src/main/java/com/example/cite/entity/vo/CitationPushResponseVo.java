package com.example.cite.entity.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

/**
 * 引用指标推送 response，记录未能更新成功的出站记录。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CitationPushResponseVo {

	private int total;

	private int successCount;

	private int failCount;

	/** 未更新成功的记录（{@code lastErrorMsg} 填写失败原因） */
	@Builder.Default
	private List<CitationPushOutboxVo> failures = new ArrayList<>();

}
