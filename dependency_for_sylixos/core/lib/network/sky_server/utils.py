'''
@Project ：dependency_for_sylixos 
@File    ：utils.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/25 10:55 
'''
import asyncio
import tempfile


class SkyBackgroundTasks:
    """模仿 FastAPI 的 BackgroundTasks"""

    def __init__(self):
        self.tasks: list[tuple[callable, tuple, dict]] = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))

    async def run(self):
        for func, args, kwargs in self.tasks:
            if asyncio.iscoroutinefunction(func):
                asyncio.create_task(func(*args, **kwargs))
            else:
                asyncio.get_event_loop().run_in_executor(None, func, *args, **kwargs)


class SkyUploadFile:
    """简易上传文件封装"""

    def __init__(self, filename: str, content_type: str = None, file=None):
        self.filename = filename
        self.content_type = content_type or "application/octet-stream"
        if file is None:
            # 默认用临时文件
            self.file = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
        else:
            self.file = file

    async def read(self) -> bytes:
        self.file.seek(0)
        return self.file.read()

    async def write(self, data: bytes):
        self.file.write(data)

    async def close(self):
        self.file.close()


class SkyFile:
    """参数依赖标记：表单中的文件"""
    def __init__(self, default=..., description: str = None):
        self.default = default
        self.description = description


class SkyForm:
    """参数依赖标记：表单中的字段"""
    def __init__(self, default=..., description: str = None):
        self.default = default
        self.description = description