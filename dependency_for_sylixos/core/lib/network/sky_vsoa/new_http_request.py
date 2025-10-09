'''
@Project ：sky_vsoa
@File    ：just_do_http_socket.py
@IDE     ：PyCharm
@Author  ：Skyrim
@Date    ：2025/8/26 19:52
'''

# 纯socket实现的

import socket
from urllib.parse import urlparse
from .target_client import TargetClient


def http_request(method: str, url: str, headers: dict = None, body: str = None, timeout: int = 5):
    """
    使用原生 socket 实现 HTTP GET/POST 请求
    :param method: "GET" or "POST"
    :param url: 完整 URL，例如 http://127.0.0.1:8000/path
    :param headers: dict 形式的请求头
    :param body: POST 请求体（str）
    :param timeout: socket 超时时间
    :return: (status_code, response_headers, response_body)
    """
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 80
    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += "?" + parsed.query

    # 构造请求行
    request_line = f"{method} {path} HTTP/1.1\r\n"

    # 默认请求头
    req_headers = {
        "Host": host,
        "User-Agent": "Python-Socket-HTTP/1.0",
        "Connection": "close"
    }
    if headers:
        req_headers.update(headers)

    # 如果是 POST，要带上 Content-Length
    if method == "POST" and body:
        req_headers["Content-Length"] = str(len(body.encode()))

    # 拼接 header 部分
    header_str = "".join([f"{k}: {v}\r\n" for k, v in req_headers.items()])

    # 完整请求报文
    request_data = request_line + header_str + "\r\n"
    if method == "POST" and body:
        request_data += body

    # 建立 TCP 连接
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    sock.sendall(request_data.encode())

    # 接收响应
    response = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
    sock.close()

    # 解析响应
    response_text = response.decode(errors="ignore")
    header_text, _, body_text = response_text.partition("\r\n\r\n")

    # 状态行
    status_line = header_text.splitlines()[0]
    status_code = int(status_line.split()[1])

    # 解析 headers
    resp_headers = {}
    for line in header_text.splitlines()[1:]:
        if ": " in line:
            k, v = line.split(": ", 1)
            resp_headers[k] = v

    return status_code, resp_headers, body_text


def new_vsoa_request(url: str,
                     method: str = None,
                     timeout: int = 5,
                     body: dict | str | None = None,
                     **kwargs,
                     ):
    """
    使用 vsoa 实现类似 http 的请求
    :param url: vsoa url，例如 sky_vsoa://127.0.0.1:8080/echo
    :param method: 模拟 http method, GET/POST (不强制，用于兼容接口)
    :param timeout: 超时时间
    :param body: 请求体，可以是 dict 或 str
    :return: dict {"status": int, "params": dict, "data": optional}
    """
    client = TargetClient()
    # 构造 payload
    payload = {}
    if body:
        if isinstance(body, dict):
            payload = {"param": body}
        elif isinstance(body, str):
            payload = {"param": {"body": body}}
        else:
            raise TypeError("body 必须是 dict 或 str")

    res = client.do_request(
        url,
        payload=payload,
        timeout=timeout
    )

    if res is None:
        LOGGER.info("获取结果不成功")

    return res


# --- 使用示例 ---
if __name__ == "__main__":
    # GET 请求
    status, headers, body = http_request("GET", "http://192.168.48.1:8000/echo?msg=2333")
    print("GET 状态:", status)
    print("GET 响应体:", body[:200], "...\n")

    # # POST 请求
    status, headers, body = http_request("POST", "http://192.168.48.1:8000/raw",
                                         body="name=skyrim&lang=python")
    print("POST 状态:", status)
    print("POST 响应体:", body[:200], "...\n")
