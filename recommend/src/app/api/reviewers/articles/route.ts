import { NextResponse } from "next/server";
import { fetchAllArticlesByAuthor } from "@/lib/cscd";
import { attachRoles, aggregateByYear } from "@/lib/articles";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const author = searchParams.get("author");
    const institute = searchParams.get("institute") ?? undefined;

    if (!author?.trim()) {
      return NextResponse.json({ error: "缺少 author 参数" }, { status: 400 });
    }

    const { articles, total } = await fetchAllArticlesByAuthor(
      author.trim(),
      institute
    );
    const withRoles = attachRoles(articles, author.trim());
    const byYear = aggregateByYear(withRoles);

    return NextResponse.json({
      articles: withRoles,
      byYear,
      total,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "获取发文失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
