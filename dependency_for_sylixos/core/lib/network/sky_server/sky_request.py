"""
@Project ：dependency_for_sylixos
@File    ：sky_request_urllib.py
@IDE     ：PyCharm
@Author  ：Skyrim
@Date    ：2025/9/25
"""

import json
from typing import Any, Optional, Union, BinaryIO, Dict, Tuple
from urllib import request as urllib_request, parse as urllib_parse
from core.lib.network.sky_server.sky_server import HTTPResponse


def sky_request(
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict | str | bytes] = None,
        json_body: Optional[Any] = None,
        files: Optional[dict[str, tuple[str, Union[bytes, BinaryIO], str]]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: float = 5.0,
) -> HTTPResponse:
    """
    基于 urllib 的最简同步 HTTP 客户端
    """
    # 拼接 URL 查询参数
    if params:
        query = urllib_parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"

    req_data: Optional[bytes] = None
    req_headers = headers.copy() if headers else {}

    # body 处理
    if json_body is not None:
        req_data = json.dumps(json_body).encode()
        req_headers["Content-Type"] = "application/json"
    elif files:
        import uuid
        boundary = uuid.uuid4().hex
        lines = []

        # 普通字段
        if data and isinstance(data, dict):
            for k, v in data.items():
                lines.append(f"--{boundary}")
                lines.append(f'Content-Disposition: form-data; name="{k}"')
                lines.append('')
                lines.append(str(v))

        # 文件字段
        for k, (filename, content, content_type) in files.items():
            # 如果是文件对象，自动 read()
            if hasattr(content, "read"):
                content = content.read()
            # 确保是 bytes
            if isinstance(content, str):
                content = content.encode()

            lines.append(f"--{boundary}")
            lines.append(f'Content-Disposition: form-data; name="{k}"; filename="{filename}"')
            lines.append(f"Content-Type: {content_type}")
            lines.append('')
            lines.append(content.decode(errors="ignore") if isinstance(content, bytes) else str(content))

        lines.append(f"--{boundary}--")
        lines.append('')
        req_data = "\r\n".join(lines).encode()
        req_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif isinstance(data, dict):
        req_data = urllib_parse.urlencode(data).encode()
        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif isinstance(data, str):
        req_data = data.encode()
        req_headers["Content-Type"] = "text/plain"
    elif isinstance(data, (bytes, bytearray)):
        req_data = bytes(data)
        req_headers["Content-Type"] = "application/octet-stream"

    req = urllib_request.Request(url, data=req_data, headers=req_headers, method=method.upper())
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read()
            status_code = resp.getcode()
            resp_headers = dict(resp.headers)
    except Exception as e:
        # 网络异常
        status_code = 0
        resp_headers = {}
        resp_body = str(e).encode()

    return HTTPResponse(status_code=status_code, headers=resp_headers, content=resp_body)


# GET/POST 简化
def get(url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None, timeout: float = 5.0):
    return sky_request("GET", url, params=params, headers=headers, timeout=timeout)


def post(url: str, *, data: Optional[dict | str | bytes] = None, json: Optional[Any] = None,
         files: Optional[dict[str, tuple[str, bytes, str]]] = None,
         headers: Optional[dict] = None, timeout: float = 5.0):
    return sky_request("POST", url, data=data, json_body=json, files=files, headers=headers, timeout=timeout)


# 测试
if __name__ == "__main__":
    res = get("http://127.0.0.1:8080")
    print("状态码:", res.status_code)
    print("内容:", res.text)
