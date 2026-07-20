from runtime import Args
from typings.get_recommend_Reviewers.get_recommend_Reviewers import Input, Output
import json
import re
import urllib.parse
import urllib.request

"""
Each file needs to export a function named `handler`. This function is the entrance to the Tool.

Parameters:
args: parameters of the entry function.
args.input - input parameters, you can get test input value by args.input.xxx.
args.logger - logger instance used to print logs, injected by runtime.

Remember to fill in input/output in Metadata, it helps LLM to recognize and use tool.

Return:
The return data of the function, which should match the declared output parameters.

Metadata 入参：
  - api_code（必填）：CSCD ApiCode
  - keywords（必填）：检索关键词
"""


def handler(args: Args[Input]) -> Output:
    api_code = getattr(args.input, "api_code", None) or getattr(args.input, "ApiCode", None) or ""
    keywords = args.input.keywords

    parts = re.split(r"[;；,，、\n]+", keywords.strip())
    keyword_str = ";;".join(p.strip() for p in parts if p.strip())

    params = urllib.parse.urlencode({"keywords": keyword_str})
    url = "http://sciencechina.cn/cscdboot/CscdService/getPeerReviewers?" + params
    req = urllib.request.Request(
        url,
        headers={"ApiCode": api_code},
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        response = json.loads(resp.read().decode("utf-8"))

    args.logger.info(json.dumps(response, ensure_ascii=False))

    return {"response": response}
