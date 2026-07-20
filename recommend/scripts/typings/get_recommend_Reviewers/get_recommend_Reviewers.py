from typing import Any, TypedDict


class Input(TypedDict, total=False):
    api_code: str
    keywords: str


class Output(TypedDict):
    response: Any
