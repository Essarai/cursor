-- =============================================================================
-- 引用指标出站表 + 触发器
-- 数据库: cite
-- 关联键: ISSN(去横线) + 精确标题 + 年份
-- 触发时机: t_cnki_refer / t_wos_refer 的 INSERT、UPDATE
-- =============================================================================

USE cite;

-- -----------------------------------------------------------------------------
-- 1. 出站表
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS t_citation_push_outbox;

CREATE TABLE t_citation_push_outbox (
    id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键，出站任务 ID',
    issn            VARCHAR(128) NOT NULL COMMENT 'ISSN 原始值',
    issn_norm       VARCHAR(64)  NOT NULL COMMENT 'ISSN 去横线归一化',
    title           VARCHAR(2000) NOT NULL COMMENT '文章标题（精确匹配）',
    title_hash      CHAR(64)     AS (SHA2(`title`, 256)) STORED COMMENT '标题 SHA256，用于唯一键',
    year            VARCHAR(16)  NOT NULL COMMENT '发表年份',
    cnki_citation   INT          NULL COMMENT '知网被引次数',
    cnki_download   INT          NULL COMMENT '知网下载次数',
    wos_citation    INT          NULL COMMENT 'WOS 被引次数（优先 Z9，其次 TC）',
    cnki_id         INT          NULL COMMENT '知网源表 t_cnki_refer.ID',
    wos_guid        VARCHAR(40)  NULL COMMENT 'WOS 源表 t_wos_refer.guid',
    sync_source     VARCHAR(16)  NOT NULL COMMENT 'CNKI / WOS / BOTH',
    push_status     VARCHAR(16)  NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING / SUCCESS / FAILED',
    retry_count     INT          NOT NULL DEFAULT 0 COMMENT '已重试次数',
    last_error_msg  VARCHAR(500) NULL COMMENT '最近一次推送失败原因',
    last_push_time  DATETIME     NULL COMMENT '最近一次推送时间',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_article (issn_norm, title_hash, year),
    KEY idx_push_status (push_status),
    KEY idx_cnki_id (cnki_id),
    KEY idx_wos_guid (wos_guid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='引用指标出站推送表';

-- -----------------------------------------------------------------------------
-- 2. 清理旧对象
-- -----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_cnki_refer_ai_outbox;
DROP TRIGGER IF EXISTS trg_cnki_refer_au_outbox;
DROP TRIGGER IF EXISTS trg_wos_refer_ai_outbox;
DROP TRIGGER IF EXISTS trg_wos_refer_au_outbox;
DROP PROCEDURE IF EXISTS sp_outbox_upsert_from_cnki;
DROP PROCEDURE IF EXISTS sp_outbox_upsert_from_wos;

DELIMITER $$

-- -----------------------------------------------------------------------------
-- 3. 知网侧 upsert 存储过程
-- -----------------------------------------------------------------------------
CREATE PROCEDURE sp_outbox_upsert_from_cnki(
    IN p_cnki_id        INT,
    IN p_issn           VARCHAR(128),
    IN p_title          VARCHAR(2000),
    IN p_year           VARCHAR(16),
    IN p_citation_num   VARCHAR(10),
    IN p_download_count VARCHAR(100)
)
proc_cnki: BEGIN
    DECLARE v_issn_norm     VARCHAR(64);
    DECLARE v_cnki_citation INT;
    DECLARE v_cnki_download INT;
    DECLARE v_wos_citation  INT;
    DECLARE v_wos_guid      VARCHAR(40);
    DECLARE v_sync_source   VARCHAR(16);

    IF p_issn IS NULL OR TRIM(p_issn) = ''
       OR p_title IS NULL OR TRIM(p_title) = ''
       OR p_year IS NULL OR TRIM(p_year) = '' THEN
        LEAVE proc_cnki;
    END IF;

    SET v_issn_norm = UPPER(REPLACE(REPLACE(TRIM(p_issn), '-', ''), ' ', ''));

    SET v_cnki_citation = CASE
        WHEN p_citation_num REGEXP '^[0-9]+$' THEN CAST(p_citation_num AS SIGNED)
        ELSE NULL
    END;

    SET v_cnki_download = CASE
        WHEN p_download_count REGEXP '^[0-9]+$' THEN CAST(p_download_count AS SIGNED)
        ELSE NULL
    END;

    SELECT
        w.guid,
        COALESCE(
            CASE WHEN w.Z9 REGEXP '^[0-9]+$' THEN CAST(w.Z9 AS SIGNED) END,
            CASE WHEN w.TC REGEXP '^[0-9]+$' THEN CAST(w.TC AS SIGNED) END
        )
    INTO v_wos_guid, v_wos_citation
    FROM t_wos_refer w
    WHERE UPPER(REPLACE(REPLACE(TRIM(w.SN), '-', ''), ' ', '')) = v_issn_norm
      AND TRIM(w.TI) = TRIM(p_title)
      AND TRIM(w.PY) = TRIM(p_year)
    LIMIT 1;

    SET v_sync_source = IF(v_wos_guid IS NOT NULL, 'BOTH', 'CNKI');

    INSERT INTO t_citation_push_outbox (
        issn, issn_norm, title, year,
        cnki_citation, cnki_download, wos_citation,
        cnki_id, wos_guid, sync_source, push_status, retry_count,
        created_at, updated_at
    ) VALUES (
        TRIM(p_issn), v_issn_norm, TRIM(p_title), TRIM(p_year),
        v_cnki_citation, v_cnki_download, v_wos_citation,
        p_cnki_id, v_wos_guid, v_sync_source, 'PENDING', 0,
        NOW(), NOW()
    )
    ON DUPLICATE KEY UPDATE
        issn            = TRIM(p_issn),
        cnki_citation   = v_cnki_citation,
        cnki_download   = v_cnki_download,
        cnki_id         = p_cnki_id,
        wos_citation    = COALESCE(v_wos_citation, wos_citation),
        wos_guid        = COALESCE(v_wos_guid, wos_guid),
        sync_source     = IF(COALESCE(v_wos_guid, wos_guid) IS NOT NULL, 'BOTH', 'CNKI'),
        push_status     = 'PENDING',
        updated_at      = NOW();
END$$

-- -----------------------------------------------------------------------------
-- 4. WOS 侧 upsert 存储过程
-- -----------------------------------------------------------------------------
CREATE PROCEDURE sp_outbox_upsert_from_wos(
    IN p_wos_guid VARCHAR(40),
    IN p_sn       TEXT,
    IN p_ti       TEXT,
    IN p_py       TEXT,
    IN p_z9       TEXT,
    IN p_tc       TEXT
)
proc_wos: BEGIN
    DECLARE v_issn_norm     VARCHAR(64);
    DECLARE v_wos_citation  INT;
    DECLARE v_cnki_id       INT;
    DECLARE v_cnki_citation INT;
    DECLARE v_cnki_download INT;
    DECLARE v_sync_source   VARCHAR(16);

    IF p_sn IS NULL OR TRIM(p_sn) = ''
       OR p_ti IS NULL OR TRIM(p_ti) = ''
       OR p_py IS NULL OR TRIM(p_py) = '' THEN
        LEAVE proc_wos;
    END IF;

    SET v_issn_norm = UPPER(REPLACE(REPLACE(TRIM(p_sn), '-', ''), ' ', ''));

    SET v_wos_citation = COALESCE(
        CASE WHEN p_z9 REGEXP '^[0-9]+$' THEN CAST(p_z9 AS SIGNED) END,
        CASE WHEN p_tc REGEXP '^[0-9]+$' THEN CAST(p_tc AS SIGNED) END
    );

    SELECT
        c.ID,
        CASE WHEN c.citation_num REGEXP '^[0-9]+$' THEN CAST(c.citation_num AS SIGNED) END,
        CASE WHEN c.download_count REGEXP '^[0-9]+$' THEN CAST(c.download_count AS SIGNED) END
    INTO v_cnki_id, v_cnki_citation, v_cnki_download
    FROM t_cnki_refer c
    WHERE UPPER(REPLACE(REPLACE(TRIM(c.ISSN), '-', ''), ' ', '')) = v_issn_norm
      AND TRIM(c.title) = TRIM(p_ti)
      AND TRIM(c.year) = TRIM(p_py)
    LIMIT 1;

    SET v_sync_source = IF(v_cnki_id IS NOT NULL, 'BOTH', 'WOS');

    INSERT INTO t_citation_push_outbox (
        issn, issn_norm, title, year,
        cnki_citation, cnki_download, wos_citation,
        cnki_id, wos_guid, sync_source, push_status, retry_count,
        created_at, updated_at
    ) VALUES (
        TRIM(p_sn), v_issn_norm, TRIM(p_ti), TRIM(p_py),
        v_cnki_citation, v_cnki_download, v_wos_citation,
        v_cnki_id, p_wos_guid, v_sync_source, 'PENDING', 0,
        NOW(), NOW()
    )
    ON DUPLICATE KEY UPDATE
        issn            = TRIM(p_sn),
        wos_citation    = v_wos_citation,
        wos_guid        = p_wos_guid,
        cnki_citation   = COALESCE(v_cnki_citation, cnki_citation),
        cnki_download   = COALESCE(v_cnki_download, cnki_download),
        cnki_id         = COALESCE(v_cnki_id, cnki_id),
        sync_source     = IF(COALESCE(v_cnki_id, cnki_id) IS NOT NULL, 'BOTH', 'WOS'),
        push_status     = 'PENDING',
        updated_at      = NOW();
END$$

-- -----------------------------------------------------------------------------
-- 5. 知网触发器
-- -----------------------------------------------------------------------------
CREATE TRIGGER trg_cnki_refer_ai_outbox
AFTER INSERT ON t_cnki_refer
FOR EACH ROW
BEGIN
    CALL sp_outbox_upsert_from_cnki(
        NEW.ID, NEW.ISSN, NEW.title, NEW.year,
        NEW.citation_num, NEW.download_count
    );
END$$

CREATE TRIGGER trg_cnki_refer_au_outbox
AFTER UPDATE ON t_cnki_refer
FOR EACH ROW
BEGIN
    IF NOT (
        NEW.ISSN          <=> OLD.ISSN AND
        NEW.title         <=> OLD.title AND
        NEW.year          <=> OLD.year AND
        NEW.citation_num  <=> OLD.citation_num AND
        NEW.download_count <=> OLD.download_count
    ) THEN
        CALL sp_outbox_upsert_from_cnki(
            NEW.ID, NEW.ISSN, NEW.title, NEW.year,
            NEW.citation_num, NEW.download_count
        );
    END IF;
END$$

-- -----------------------------------------------------------------------------
-- 6. WOS 触发器
-- -----------------------------------------------------------------------------
CREATE TRIGGER trg_wos_refer_ai_outbox
AFTER INSERT ON t_wos_refer
FOR EACH ROW
BEGIN
    CALL sp_outbox_upsert_from_wos(
        NEW.guid, NEW.SN, NEW.TI, NEW.PY, NEW.Z9, NEW.TC
    );
END$$

CREATE TRIGGER trg_wos_refer_au_outbox
AFTER UPDATE ON t_wos_refer
FOR EACH ROW
BEGIN
    IF NOT (
        NEW.SN <=> OLD.SN AND
        NEW.TI <=> OLD.TI AND
        NEW.PY <=> OLD.PY AND
        NEW.Z9 <=> OLD.Z9 AND
        NEW.TC <=> OLD.TC
    ) THEN
        CALL sp_outbox_upsert_from_wos(
            NEW.guid, NEW.SN, NEW.TI, NEW.PY, NEW.Z9, NEW.TC
        );
    END IF;
END$$

DELIMITER ;

-- -----------------------------------------------------------------------------
-- 7. 历史数据初始化请单独执行：
--    sql/citation_push_outbox_init.sql
-- 说明：知网源表存在相同 ISSN+标题+年的重复爬虫记录，初始化脚本已做去重。
-- -----------------------------------------------------------------------------
