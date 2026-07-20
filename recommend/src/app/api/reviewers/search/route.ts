import { NextResponse } from "next/server";
import { searchReviewers } from "@/lib/cscd";
import { saveSearchReviewers } from "@/lib/reviewer-store";
import type { SearchRequest } from "@/lib/types";
import { applySearchFilters } from "@/lib/utils";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as SearchRequest;
    const keywords = body.keywords;

    if (!keywords?.length) {
      return NextResponse.json({ error: "请至少输入一个关键词" }, { status: 400 });
    }

    const raw = await searchReviewers(keywords);
    const reviewers = applySearchFilters(raw, {
      keywords,
      excludeOrgs: body.excludeOrgs ?? [],
      excludeNames: body.excludeNames ?? [],
      hasEmail: body.hasEmail ?? false,
    });

    let dbSync: Awaited<ReturnType<typeof saveSearchReviewers>> | null = null;
    try {
      // 仅 CSCD 检索成功时入库；保存 API 返回的完整列表，前端二次筛选不写库
      dbSync = await saveSearchReviewers(keywords, raw);
    } catch (dbErr) {
      console.error("[reviewers/search] DB sync failed:", dbErr);
    }

    return NextResponse.json({
      reviewers,
      count: reviewers.length,
      totalFromApi: raw.length,
      dbSync,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "检索失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
