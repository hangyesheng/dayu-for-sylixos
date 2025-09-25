from core.lib.common import LOGGER
import socket
from urllib.parse import urlparse, urlencode
import json
from core.lib.network.sky_vsoa import TargetClient

def new_http_request(url: str,
                     method: str = None,
                     timeout: int = 5,
                     body=None,
                     headers: dict = None,
                     cont_type: str = 'application/json'
                     ) -> dict:
    """
    使用原生 socket 实现 HTTP GET/POST 请求
    :param method: "GET" or "POST"
    :param url: 完整 URL，例如 http://127.0.0.1:8000/path
    :param headers: dict 形式的请求头
    :param body: POST 请求体（str 或 dict）
    :param timeout: socket 超时时间
    :return: dict(status_code, headers, body)
    """
    _method = method.upper() if method else "GET"

    parsed = urlparse(url)
    LOGGER.info(parsed)
    host = parsed.hostname
    port = parsed.port or 80
    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += "?" + parsed.query

    # 处理 body
    body_data = ""
    req_headers = {
        "Host": host,
        "User-Agent": "Python-Socket-HTTP/1.0",
        "Connection": "close",
        "Content-Type": cont_type
    }

    if _method == "POST" and body:
        if isinstance(body, dict):
            if req_headers.get("Content-Type") == "application/json":
                body_data = json.dumps(body)
            elif req_headers["Content-Type"] == "application/x-www-form-urlencoded":
                body_data = urlencode(body)
        elif isinstance(body, str):
            body_data = body
            req_headers["Content-Type"] = "text/plain"
        else:
            raise TypeError("body 必须是 str 或 dict")

        req_headers["Content-Length"] = str(len(body_data.encode()))

    if headers:
        req_headers.update(headers)

    # 构造请求报文
    request_line = f"{_method} {path} HTTP/1.1\r\n"
    header_str = "".join([f"{k}: {v}\r\n" for k, v in req_headers.items()])
    request_data = request_line + header_str + "\r\n" + body_data

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
            resp_headers[k.strip()] = v.strip()

    # 构造返回值
    response_dict = {
        "status_code": status_code,
        "headers": resp_headers,
        "body": body_text
    }

    if 200 <= status_code < 300:
        return response_dict
    elif 300 <= status_code < 400:
        LOGGER.info("233")
        # LOGGER.info(f'Redirect maybe, status={status_code}, url={url}')
    else:
        LOGGER.info("bad")
        # LOGGER.warning(f'Get invalid status code {status_code} in request {url}')

    return response_dict


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

if __name__ == '__main__':
    # req = new_http_request("http://127.0.0.1:8000/echo?msg=2333", "GET")
    # req2 = new_http_request("http://127.0.0.1:8000/post_test2", "POST", body={
    #     "name": "2333",
    #     "value": 233
    # })
    # LOGGER.info(f"状态{req}")
    # LOGGER.info(f"状态{req2}")

    req = new_vsoa_request("vsoa://192.168.1.218:8080/test", "GET")
    # req2 = new_vsoa_request("http://127.0.0.1:8000/post_test2", "POST", body={
    #     "name": "2333",
    #     "value": 233
    # })
    LOGGER.info(f"状态{req}")
    # LOGGER.info(f"状态{req2}")
