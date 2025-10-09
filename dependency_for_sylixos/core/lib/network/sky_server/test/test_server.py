'''
@Project ：dependency_for_sylixos 
@File    ：test_server.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/25 10:29 
'''
import time
import json
from core.lib.network.sky_server.sky_server import SkyHTTPServer, HTTPResponse, HTTPRequest
from core.lib.network.sky_server.utils import *


class SkyTestServer:
    def __init__(self):
        self.app = SkyHTTPServer()
        self.app.add_route(
            path='/predict',
            method='GET',
            handler=self.test_handler
        )
        self.app.add_route(
            path='/trans',
            method='POST',
            handler=self.trans_data
        )
        self.app.add_route(
            path='/sleep',
            method='POST',
            handler=self.sleep_task
        )
        self.app.add_route(
            path='/form',
            method='POST',
            handler=self.form_task
        )
        self.app.add_route(
            path='/file',
            method='POST',
            handler=self.file_task
        )

    async def test_handler(self, request):
        return HTTPResponse(content={
            'status': 'success',
            'data': 233
        })

    async def trans_data(self, request: HTTPRequest):
        print(request.json())
        return HTTPResponse(content={
            'status': 'success',
            'data': 233
        })

    async def sleep_task(self, request, backtask: SkyBackgroundTasks):
        print(request.json())
        backtask.add_task(self.sleep_2sec)
        return HTTPResponse(content={
            'status': 'success',
            'data': '成功睡眠'
        })

    async def form_task(self, request):
        form_in_memory = self.app.parse_forms_from_request(request)
        for f in form_in_memory:
            print(f"字段名: {f['name']}, 值: {f['value']}")
        return HTTPResponse(content=json.dumps({
            "status": "success",
            "forms_count": len(form_in_memory)
        }))

    async def file_task(self, request):
        files = self.app.parse_files_from_request(request)
        for f in files:
            print(f.filename, f.content_type)
            content_bytes = await f.read()
            print(content_bytes)
        return HTTPResponse(content=json.dumps({
            "status": "success",
            "files_count": len(files)
        }))

    def sleep_2sec(self):
        time.sleep(2)
        print('2333')
        with open('test_server.jsonl', 'w', encoding='utf-8') as f:
            json.dump({
                'status': 'success',
                'sleep_time': '2',
            }, f)


app = SkyTestServer().app

import os

if __name__ == "__main__":
    asyncio.run(app.run(host="0.0.0.0", port=os.getenv('GUNICORN_PORT', 9200)))
