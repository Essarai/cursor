from typing import Any, TypedDict


class Input(TypedDict, total=False):
    api_code: str
    author: str
    org: str
    page: int
    limit: int
    pub_year: str


class Output(TypedDict):
    response: Any
