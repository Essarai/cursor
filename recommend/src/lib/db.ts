import mysql from "mysql2/promise";

let pool: mysql.Pool | null = null;

export function getDbPool(): mysql.Pool {
  if (pool) return pool;

  const host = process.env.DB_HOST;
  const user = process.env.DB_USER;
  const password = process.env.DB_PASSWORD;
  const database = process.env.DB_NAME ?? "cscd_recommend";

  if (!host || !user || !password) {
    throw new Error("请配置 DB_HOST / DB_USER / DB_PASSWORD");
  }

  pool = mysql.createPool({
    host,
    user,
    password,
    database,
    charset: "utf8mb4",
    waitForConnections: true,
    connectionLimit: 5,
  });

  return pool;
}

export async function ensureSchema(): Promise<void> {
  const db = getDbPool();

  await db.execute(`
    CREATE TABLE IF NOT EXISTS reviewer_search (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      keywords VARCHAR(500) NOT NULL COMMENT 'CSCD查询关键词(;;分隔)',
      keyword_list JSON NOT NULL COMMENT '关键词数组',
      reviewer_count INT UNSIGNED NOT NULL DEFAULT 0,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审稿人检索记录'
  `);

  await migrateLegacyPeerReviewerTable(db);

  await db.execute(`
    CREATE TABLE IF NOT EXISTS peer_reviewer (
      id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
      cscd_author_id VARCHAR(32) NOT NULL,
      author_name VARCHAR(100) NOT NULL,
      position VARCHAR(200) NULL,
      education VARCHAR(200) NULL,
      resume TEXT NULL,
      keyword TEXT NULL,
      advistor VARCHAR(500) NULL,
      email VARCHAR(200) NULL,
      org VARCHAR(500) NULL,
      academician VARCHAR(100) NULL,
      subject VARCHAR(200) NULL,
      num_allpaper VARCHAR(32) NULL,
      hindex VARCHAR(32) NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      UNIQUE KEY uk_cscd_author_id (cscd_author_id),
      INDEX idx_author_name (author_name),
      INDEX idx_updated_at (updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审稿人/专家（全局去重）'
  `);

  await db.execute(`
    CREATE TABLE IF NOT EXISTS reviewer_search_item (
      search_id BIGINT UNSIGNED NOT NULL,
      cscd_author_id VARCHAR(32) NOT NULL,
      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (search_id, cscd_author_id),
      INDEX idx_cscd_author_id (cscd_author_id),
      CONSTRAINT fk_search_item_search FOREIGN KEY (search_id) REFERENCES reviewer_search(id) ON DELETE CASCADE,
      CONSTRAINT fk_search_item_reviewer FOREIGN KEY (cscd_author_id) REFERENCES peer_reviewer(cscd_author_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检索与专家关联'
  `);
}

async function migrateLegacyPeerReviewerTable(
  db: mysql.Pool
): Promise<void> {
  const [tables] = await db.execute<mysql.RowDataPacket[]>(
    `SELECT TABLE_NAME FROM information_schema.TABLES
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'peer_reviewer'`
  );
  if (!tables.length) return;

  const [columns] = await db.execute<mysql.RowDataPacket[]>(
    `SELECT COLUMN_NAME FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'peer_reviewer' AND COLUMN_NAME = 'search_id'`
  );
  if (!columns.length) return;

  await db.execute(`CREATE TABLE IF NOT EXISTS peer_reviewer_new (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    cscd_author_id VARCHAR(32) NOT NULL,
    author_name VARCHAR(100) NOT NULL,
    position VARCHAR(200) NULL,
    education VARCHAR(200) NULL,
    resume TEXT NULL,
    keyword TEXT NULL,
    advistor VARCHAR(500) NULL,
    email VARCHAR(200) NULL,
    org VARCHAR(500) NULL,
    academician VARCHAR(100) NULL,
    subject VARCHAR(200) NULL,
    num_allpaper VARCHAR(32) NULL,
    hindex VARCHAR(32) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_cscd_author_id (cscd_author_id)
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`);

  await db.execute(`
    INSERT INTO peer_reviewer_new (
      cscd_author_id, author_name, position, education, resume,
      keyword, advistor, email, org, academician, subject, num_allpaper, hindex, created_at
    )
    SELECT
      cscd_author_id, author_name, position, education, resume,
      keyword, advistor, email, org, academician, subject, num_allpaper, hindex, created_at
    FROM peer_reviewer
    ON DUPLICATE KEY UPDATE
      author_name = VALUES(author_name),
      position = VALUES(position),
      education = VALUES(education),
      resume = VALUES(resume),
      keyword = VALUES(keyword),
      advistor = VALUES(advistor),
      email = VALUES(email),
      org = VALUES(org),
      academician = VALUES(academian),
      subject = VALUES(subject),
      num_allpaper = VALUES(num_allpaper),
      hindex = VALUES(hindex),
      updated_at = CURRENT_TIMESTAMP
  `);

  await db.execute(`
    INSERT IGNORE INTO reviewer_search_item (search_id, cscd_author_id)
    SELECT search_id, cscd_author_id FROM peer_reviewer
  `);

  await db.execute("DROP TABLE peer_reviewer");
  await db.execute("RENAME TABLE peer_reviewer_new TO peer_reviewer");
}
