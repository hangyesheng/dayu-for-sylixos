"""
@Project ：dependency_for_sylixos
@File    ：sky_server.py
@IDE     ：PyCharm
@Author  ：Skyrim
@Date    ：2025/9/25 0:36
"""
import inspect
import asyncio
import os
import json
import re
from urllib.parse import urlparse, parse_qs
from core.lib.network.sky_server.utils import SkyBackgroundTasks, SkyUploadFile
from typing import List, Dict, Any


class HTTPRequest:
    def __init__(
            self, method: str, path: str, version: str, headers: dict, body: bytes
    ):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers
        self.body = body or b""

        parsed = urlparse(path)
        self.url = parsed
        self.route_path = parsed.path
        self.query = {
            k: v[0] if isinstance(v, list) and len(v) == 1 else v
            for k, v in parse_qs(parsed.query).items()
        }

    def json(self, default=None):
        try:
            return json.loads(self.body.decode() or "{}")
        except Exception:
            return default


class HTTPResponse:
    def __init__(self, status_code=200, headers=None, content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = (
            content
            if isinstance(content, (bytes, bytearray))
            else str(content).encode()
        )

    @property
    def text(self):
        try:
            return self.content.decode()
        except Exception:
            return self.content.decode(errors="ignore")

    def json(self, default=None):
        import json

        try:
            return json.loads(self.text or "{}")
        except Exception:
            return default

    def to_bytes(self) -> bytes:
        reason = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            500: "Internal Server Error",
        }.get(self.status_code, "OK")
        headers = {"Content-Length": str(len(self.content)), "Connection": "close"}
        headers.update(self.headers)
        lines = [f"HTTP/1.1 {self.status_code} {reason}"] + [
            f"{k}: {v}" for k, v in headers.items()
        ]
        return ("\r\n".join(lines) + "\r\n\r\n").encode() + self.content


class SkyHTTPServer:
    def __init__(self, host: str | None = None, port: int | None = None):
        # 支持延迟绑定：host/port 可为 None，启动时从环境变量解析
        self.host = host
        self.port = port
        self._routes: dict[tuple[str, str], callable] = {}
        self._server: asyncio.base_events.Server | None = None

    def route(self, path: str, method: str = "GET"):
        method = method.upper()

        def decorator(func):
            self._routes[(method, path)] = func
            return func

        return decorator

    def add_route(self, path: str, method: str, handler):
        self._routes[(method.upper(), path)] = handler

    def parse_forms_from_request(self, request) -> List[Dict[str, Any]]:
        """
        解析 application/x-www-form-urlencoded 的表单字段
        返回格式: [{ "name": 字段名, "value": 字段值 }, ...]
        """
        content_type = request.headers.get("Content-Type", "")
        if not content_type.startswith("application/x-www-form-urlencoded"):
            return []

        try:
            body_text = request.body.decode(errors="ignore")
            parsed = parse_qs(body_text, keep_blank_values=True)
            return [{"name": k, "value": v[0] if len(v) == 1 else v} for k, v in parsed.items()]
        except Exception:
            return []
        
    def parse_from_forms(self, key: str, forms: List[Dict[str, Any]]) -> Any:
        # 检查是否为空
        if not forms:
            raise ValueError("未收到表单数据")

        # 在 forms 列表中查找 name == key 的项
        data_item = None
        for item in forms:
            if item.get("name") == key:
                data_item = item
                break

        if not data_item:
            raise ValueError(f"未找到名为 {key} 的表单字段")

        # 取出 value 字段, 解析为 JSON
        data_json_str = data_item['value']
        return data_json_str
        
    def parse_data_from_request(self, request) -> Any:
        forms = self.parse_forms_from_request(request=request)
        data_json_str = self.parse_from_forms(key="data", forms=forms)
        data = json.loads(data_json_str)
        return data

    def parse_files_from_request(self, request) -> List[SkyUploadFile]:
        """
        解析 multipart/form-data 请求中的文件，返回内存中的 SkyUploadFile 对象列表
        """
        import re
        content_type = request.headers.get("Content-Type", "")
        match = re.match(r"multipart/form-data;\s*boundary=(.+)", content_type)
        if not match:
            raise ValueError("Missing or invalid Content-Type")

        boundary = match.group(1).encode()
        body = request.body
        parts = body.split(b"--" + boundary)
        files: List[SkyUploadFile] = []

        for part in parts:
            part = part.strip()
            if not part or part == b"--":
                continue

            try:
                head, _, content = part.partition(b"\r\n\r\n")
                content = content.rstrip(b"\r\n")
                head_lines = head.decode(errors="ignore").split("\r\n")

                disposition = next((l for l in head_lines if l.startswith("Content-Disposition")), None)
                if not disposition:
                    continue

                # 提取表单字段名和文件名
                filename_match = re.search(r'filename="([^"]+)"', disposition)
                if not filename_match:
                    continue  # 非文件字段可以跳过
                filename = filename_match.group(1)

                content_type_line = next((l for l in head_lines if l.startswith("Content-Type:")), "")
                content_type_value = content_type_line.split(":", 1)[
                    1].strip() if content_type_line else "application/octet-stream"

                # 封装成 SkyUploadFile
                upload_file = SkyUploadFile(filename=filename, content_type=content_type_value)
                # 写入内容
                upload_file.file.write(content)
                upload_file.file.seek(0)

                files.append(upload_file)

            except Exception as e:
                print(f"[parse_files_from_request] 解析失败: {e}")

        return files

    async def _read_request(self, reader: asyncio.StreamReader) -> HTTPRequest | None:
        try:
            header_data = await reader.readuntil(b"\r\n\r\n")
        except asyncio.IncompleteReadError:
            return None
        except Exception:
            return None

        try:
            header_text = header_data.decode(errors="ignore")
            lines = header_text.split("\r\n")
            request_line = lines[0]
            method, path, version = request_line.split(" ")
            headers = {}
            for line in lines[1:]:
                if not line:
                    continue
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip()] = v.strip()

            content_length = int(headers.get("Content-Length", 0) or 0)
            body = b""
            if content_length > 0:
                body = await reader.readexactly(content_length)
        except Exception:
            return None

        return HTTPRequest(
            method=method, path=path, version=version, headers=headers, body=body
        )

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        req = await self._read_request(reader)
        if not req:
            writer.write(HTTPResponse(400, {"Content-Type": "text/plain"}, b"Bad Request").to_bytes())
            await writer.drain()
            writer.close()
            return

        handler = self._routes.get((req.method.upper(), req.route_path))
        try:
            if handler is None:
                resp = HTTPResponse(404, {"Content-Type": "text/plain"}, b"Not Found")
            else:
                # ==== 参数注入 ====
                sig = inspect.signature(handler)
                bound_args = {}
                bg_tasks = None

                for name, param in sig.parameters.items():
                    anno = param.annotation
                    if anno is HTTPRequest or anno is inspect._empty:
                        bound_args[name] = req
                    elif anno is SkyBackgroundTasks:
                        bg_tasks = SkyBackgroundTasks()
                        bound_args[name] = bg_tasks
                    else:
                        bound_args[name] = None

                # ==== 调用 handler ====
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**bound_args)
                else:
                    result = await asyncio.to_thread(handler, **bound_args)

                # ==== 运行后台任务 ====
                if bg_tasks:
                    await bg_tasks.run()

                # ==== 自动封装 HTTPResponse ====
                if isinstance(result, HTTPResponse):
                    resp = result
                elif isinstance(result, (dict, list)):
                    resp = HTTPResponse(200, {"Content-Type": "application/json"}, json.dumps(result).encode())
                elif isinstance(result, (str, bytes)):
                    resp = HTTPResponse(200, {"Content-Type": "text/plain"}, result)
                else:
                    resp = HTTPResponse(200, {"Content-Type": "text/plain"}, b"")
        except Exception as e:
            resp = HTTPResponse(500, {"Content-Type": "application/json"}, json.dumps({"error": str(e)}).encode())

        writer.write(resp.to_bytes())
        await writer.drain()
        writer.close()

    def configure(self, host: str | None = None, port: int | None = None):
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port

    async def run(self, host: str | None = None, port: int | None = None):
        # 解析优先级：显式参数 > 已配置属性 > 环境变量 > 默认
        rh = host or self.host or os.environ.get("SERVER_HOST") or os.environ.get("HOST") or "0.0.0.0"
        rp_env = (
                os.environ.get("SERVER_PORT")
                or os.environ.get("GUNICORN_PORT")
                or os.environ.get("PORT")
        )
        rp = port or self.port or (int(rp_env) if rp_env else 8080)

        self._server = await asyncio.start_server(
            self._handle_client, rh, rp
        )
        addrs = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        print(f"[SkyHTTPServer] Serving on {addrs}")
        async with self._server:
            await self._server.serve_forever()

    def run_blocking(self, host: str | None = None, port: int | None = None):
        asyncio.run(self.run(host, port))


# 示例：最小可用服务器
async def _example():
    server = SkyHTTPServer(host="0.0.0.0", port=8080)

    @server.route("/", method="GET")
    async def index(req: HTTPRequest):
        return {"message": "hello, async http"}

    @server.route("/echo", method="POST")
    async def echo(req: HTTPRequest):
        data = req.json(default={})
        return 200, {"Content-Type": "application/json"}, json.dumps({"received": data})

    await server.start()


if __name__ == "__main__":
    try:
        asyncio.run(_example())
    except KeyboardInterrupt:
        pass
