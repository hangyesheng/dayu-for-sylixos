'''
@Project ：dependency_for_sylixos 
@File    ：utils.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/24 15:56 
'''

# FastAPI 栈对照：
# FastAPI -> SkyApp(TargetServer)
# BackgroundTasks -> SkyBackgroundTasks
# UploadFile -> SkyUploadFile
# File -> SkyFile
# Form -> SkyForm
# JSONResponse -> SkyJSONResponse

import asyncio
import typing
from typing import Callable, Awaitable, Any
from .target_server import TargetServer  # 你自己的 vSOA 服务器

P = typing.ParamSpec("P")

class SkyBackgroundTasks:
    """
    简化版私有 BackgroundTask 管理器
    - 支持添加同步/异步任务
    - 支持并发执行
    """
    def __init__(self) -> None:
        self.tasks: list[tuple[Callable[..., Any], tuple, dict]] = []
    def add_task(self, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> None:
        """添加后台任务"""
        self.tasks.append((func, args, kwargs))
    async def run(self) -> None:
        """运行所有任务（并发执行）"""
        coros = []
        for func, args, kwargs in self.tasks:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                coros.append(result)
            else:
                # 包装同步函数为异步
                coros.append(asyncio.to_thread(func, *args, **kwargs))
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)
    def __call__(self) -> Awaitable[None]:
        """允许直接 await tasks()"""
        return self.run()

class SkyUploadFile:
    """
    最简版文件包装，提供与 FastAPI.UploadFile 接近的接口
    """

    def __init__(self, filename: str, content: bytes, content_type: str | None = None) -> None:
        self.filename = filename
        self._content = content or b""
        self.content_type = content_type or "application/octet-stream"

    async def read(self) -> bytes:
        """异步读取文件内容"""
        return self._content

def SkyFile(default: Any = ..., description: str | None = None) -> dict:
    """声明式占位，兼容 FastAPI 的 File(...)，仅用于语义标注"""
    return {"__type__": "file", "default": default, "description": description}

def SkyForm(default: Any = ..., description: str | None = None) -> dict:
    """声明式占位，兼容 FastAPI 的 Form(...)，仅用于语义标注"""
    return {"__type__": "form", "default": default, "description": description}

class SkyJSONResponse(dict):
    """最简 JSONResponse，占位用，等价于返回可序列化字典"""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

class SkyApp:
    """
    最简 vSOA 应用容器，模仿 FastAPI：
    - add_api_route(path, endpoint, methods=[...])
    - start() 启动 vSOA 服务
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, name: str = "sky-app") -> None:
        self._server = TargetServer(host=host, port=port, name=name)

    def add_api_route(self, path: str, endpoint: Callable[..., Any], methods: list[str] | None = None) -> None:
        method = (methods or ["POST"])[0]  # 默认 POST
        self._server.add_route(path, endpoint, method)

    def start(self) -> None:
        self._server.start()


if __name__ == '__main__':
    async def async_job(x: int):
        await asyncio.sleep(1)
        print(f"async done {x}")


    def sync_job(msg: str):
        print(f"sync job: {msg}")


    async def main():
        tasks = SkyBackgroundTasks()
        tasks.add_task(async_job, 1)
        tasks.add_task(sync_job, "hello")
        await tasks()  # 等价于 await tasks.run()


    asyncio.run(main())
