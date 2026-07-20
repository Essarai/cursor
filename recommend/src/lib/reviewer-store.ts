import type { PoolConnection } from "mysql2/promise";
import { normalizeKeywords } from "./cscd";
import { ensureSchema, getDbPool } from "./db";
import type { Reviewer } from "./types";

export interface SaveSearchResult {
  searchId: number;
  savedCount: number;
  insertedCount: number;
  updatedCount: number;
}

function reviewerParams(r: Reviewer) {
  return [
    String(r.id),
    r.authorName ?? "",
    r.position,
    r.education,
    r.resume,
    r.keyword,
    r.advistor,
    r.email,
    r.org,
    r.academician,
    r.subject,
    r.numAllpaper,
    r.hindex,
  ];
}

async function upsertReviewer(
  conn: PoolConnection,
  r: Reviewer
): Promise<"inserted" | "updated"> {
  const params = reviewerParams(r);

  const [result] = await conn.execute(
    `INSERT INTO peer_reviewer (
      cscd_author_id, author_name, position, education, resume,
      keyword, advistor, email, org, academician, subject, num_allpaper, hindex
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON DUPLICATE KEY UPDATE
      author_name = VALUES(author_name),
      position = VALUES(position),
      education = VALUES(education),
      resume = VALUES(resume),
      keyword = VALUES(keyword),
      advistor = VALUES(advistor),
      email = VALUES(email),
      org = VALUES(org),
      academician = VALUES(academician),
      subject = VALUES(subject),
      num_allpaper = VALUES(num_allpaper),
      hindex = VALUES(hindex),
      updated_at = CURRENT_TIMESTAMP`,
    params
  );

  const affected = (result as { affectedRows?: number }).affectedRows ?? 0;
  return affected === 1 ? "inserted" : "updated";
}

/**
 * 仅在 CSCD 检索成功后调用：记录一次搜索，专家按 cscd_author_id 全局去重并更新。
 * 前端二次筛选不会触发此函数。
 */
export async function saveSearchReviewers(
  keywords: string[],
  reviewers: Reviewer[]
): Promise<SaveSearchResult> {
  await ensureSchema();
  const pool = getDbPool();
  const conn = await pool.getConnection();

  let searchId = 0;
  let insertedCount = 0;
  let updatedCount = 0;

  try {
    await conn.beginTransaction();

    const keywordStr = normalizeKeywords(keywords);
    const [searchResult] = await conn.execute(
      `INSERT INTO reviewer_search (keywords, keyword_list, reviewer_count)
       VALUES (?, ?, ?)`,
      [keywordStr, JSON.stringify(keywords), reviewers.length]
    );
    searchId = Number((searchResult as { insertId: number }).insertId);

    for (const reviewer of reviewers) {
      if (!reviewer.id) continue;

      const action = await upsertReviewer(conn, reviewer);
      if (action === "inserted") insertedCount++;
      else updatedCount++;

      await conn.execute(
        `INSERT IGNORE INTO reviewer_search_item (search_id, cscd_author_id)
         VALUES (?, ?)`,
        [searchId, String(reviewer.id)]
      );
    }

    await conn.commit();
  } catch (err) {
    await conn.rollback();
    throw err;
  } finally {
    conn.release();
  }

  return {
    searchId,
    savedCount: reviewers.length,
    insertedCount,
    updatedCount,
  };
}
