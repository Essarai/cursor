from runtime import Args
from typings.get_author_info.get_author_info import Input, Output
import json
import urllib.parse
import urllib.request

"""
Each file needs to export a function named `handler`. This function is the entrance to the Tool.

CSCD 接口：GET /searchArticles
Header: ApiCode
参数：
  - api_code（必填）：CSCD ApiCode
  - author（必填）：作者姓名
  - org（选填）：作者机构，用于消歧
  - page（选填）：页码，默认 1
  - limit（选填）：每页条数，最大 50，默认 50
  - pub_year（选填）：出版年，格式 YYYY-YYYY

返回 result 结构：
  - total: 总篇数
  - page: 当前页
  - limit: 每页条数
  - data: 文献列表（含题名、期刊、作者、被引等）
"""


def handler(args: Args[Input]) -> Output:
    api_code = getattr(args.input, "api_code", None) or getattr(args.input, "ApiCode", None) or ""
    author = args.input.author
    org = getattr(args.input, "org", None) or ""
    page = getattr(args.input, "page", None) or 1
    limit = getattr(args.input, "limit", None) or 50
    pub_year = getattr(args.input, "pub_year", None) or ""

    params = {
        "author": author,
        "page": str(page),
        "limit": str(limit),
    }
    if org.strip():
        params["institute"] = org.strip()
    if pub_year.strip():
        params["pubYear"] = pub_year.strip()

    query = urllib.parse.urlencode(params)
    url = "http://sciencechina.cn/cscdboot/CscdService/searchArticles?" + query
    req = urllib.request.Request(
        url,
        headers={"ApiCode": api_code},
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        response = json.loads(resp.read().decode("utf-8"))

    args.logger.info(json.dumps(response, ensure_ascii=False))

    return {"response": response}
