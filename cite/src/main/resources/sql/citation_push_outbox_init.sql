-- =============================================================================
-- 出站表历史数据初始化
-- 前置：已执行 citation_push_outbox.sql（建表 + 触发器）
--
-- 注意：本脚本开头会 TRUNCATE 清空出站表；若 INSERT 失败，表将保持为空。
-- 知网源表存在相同 ISSN+标题+年的重复记录，按 MAX(ID) 去重后写入。
-- =============================================================================

USE cite;

TRUNCATE TABLE t_citation_push_outbox;

INSERT INTO t_citation_push_outbox (
    issn, issn_norm, title, year,
    cnki_citation, cnki_download, wos_citation,
    cnki_id, wos_guid, sync_source, push_status, retry_count,
    created_at, updated_at
)
SELECT
    TRIM(c.ISSN),
    UPPER(REPLACE(REPLACE(TRIM(c.ISSN), '-', ''), ' ', '')),
    TRIM(c.title),
    TRIM(c.year),
    CASE WHEN c.citation_num REGEXP '^[0-9]+$' THEN CAST(c.citation_num AS SIGNED) END,
    CASE WHEN c.download_count REGEXP '^[0-9]+$' THEN CAST(c.download_count AS SIGNED) END,
    COALESCE(
        CASE WHEN w.Z9 REGEXP '^[0-9]+$' THEN CAST(w.Z9 AS SIGNED) END,
        CASE WHEN w.TC REGEXP '^[0-9]+$' THEN CAST(w.TC AS SIGNED) END
    ),
    c.ID,
    w.guid,
    IF(w.guid IS NOT NULL, 'BOTH', 'CNKI'),
    'PENDING',
    0,
    NOW(),
    NOW()
FROM t_cnki_refer c
INNER JOIN (
    SELECT MAX(ID) AS id
    FROM t_cnki_refer
    WHERE ISSN IS NOT NULL AND TRIM(ISSN) != ''
      AND title IS NOT NULL AND TRIM(title) != ''
      AND year IS NOT NULL AND TRIM(year) != ''
    GROUP BY
        UPPER(REPLACE(REPLACE(TRIM(ISSN), '-', ''), ' ', '')),
        TRIM(title),
        TRIM(year)
) latest ON c.ID = latest.id
LEFT JOIN t_wos_refer w
    ON UPPER(REPLACE(REPLACE(TRIM(c.ISSN), '-', ''), ' ', '')) = UPPER(REPLACE(REPLACE(TRIM(w.SN), '-', ''), ' ', ''))
   AND TRIM(c.title) = TRIM(w.TI)
   AND TRIM(c.year) = TRIM(w.PY);

-- 执行后应看到约 5 万行；若为 0 说明 INSERT 未成功
SELECT COUNT(*) AS imported_rows FROM t_citation_push_outbox;
