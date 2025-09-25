'''
@Project ：sky_vsoa
@File    ：target_client.py
@IDE     ：PyCharm
@Author  ：Skyrim
@Date    ：2025/8/26 19:45
'''

import core.lib.network.sky_vsoa.vsoa as vsoa
import threading
from typing import Callable, Dict


class TargetClient(object):
    """
    支持vsoa的客户端,可以用来只做一次就返回
    """

    def __init__(self, ):
        self.client = vsoa.Client()

    def __str__(self):
        return self.info

    def __default_on_connect(c: vsoa.Client, connected: bool, info: dict | None) -> None:
        print(f'[client] {"connected" if connected else "disconnected"} info={info}')

    def __default_on_message(c: vsoa.Client, url: str, payload: vsoa.Payload, quick: bool) -> None:
        print(
            f'[client] message url={url} quick={quick} param={payload.param} data_len={0 if not payload.data else len(payload.data)}')

    def __default_on_data(c: vsoa.Client, url: str, payload: vsoa.Payload, quick: bool) -> None:
        print(
            f'[client] datagram url={url} quick={quick} param={payload.param} data_len={0 if not payload.data else len(payload.data)}')

    def build(self, on_connect: Callable = None, on_message: Callable = None, on_data: Callable = None, ):
        if on_connect is not None:
            self.client.onconnect = on_connect
        else:
            self.client.onconnect = self.__default_on_connect
        if on_message is not None:
            self.client.onmessage = on_message
        else:
            self.client.onmessage = self.__default_on_message
        if on_data is not None:
            self.client.ondata = on_data
        else:
            self.client.ondata = self.__default_on_data

    def parse(self, url):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or 80
        path = parsed.path if parsed.path else "/"
        if parsed.query:
            path += "?" + parsed.query
        return host, port, path

    def do_request(self,
                   url: str,
                   payload: Dict = {},
                   callback: Callable = None,
                   timeout: int = 5,
                   ):
        host, port, path = self.parse(url)
        # 连接服务器
        ret = self.client.connect(f'vsoa://{host}:{port}', timeout=timeout)

        if ret == vsoa.Client.CONNECT_ERROR:
            print(f'[client] 连接出错: {ret}')
        elif ret == vsoa.Client.SERVER_NO_RESPONDING:
            print(f'[client] 服务器无响应')
        elif ret == vsoa.Client.SERVER_NOT_FOUND:
            print(f'[client] 服务器未找到')
        elif ret == vsoa.Client.INVALID_RESPONDING:
            print(f'[client] 非法响应')
        elif ret == vsoa.Client.INVALID_PASSWD:
            print(f'[client] 非法密码')
        if ret != vsoa.Client.CONNECT_OK:
            return
        else:
            print(f'[client] 正常连接成功!')
        # 构造请求
        done = threading.Event()
        result_holder = {}

        def __default_callback(c: vsoa.Client, h: vsoa.Header, p: vsoa.Payload):
            result_holder["data"] = {
                "status": h.status,
                "params": p.param,
            }
            done.set()  # 通知主线程：有结果了
            return result_holder["data"]

        cb = callback if callback else __default_callback
        self.client.call(path, payload=payload, callback=cb, timeout=timeout)

        # 启动事件循环
        t = threading.Thread(target=self.client.run, name="vsoa_client_loop", daemon=True)
        t.start()

        # 等待结果，超时返回 None
        if not done.wait(timeout):
            print("[client] timeout waiting for response")
            self.client.close()
            return None

        self.client.close()
        return result_holder.get("data")


if __name__ == '__main__':
    client = TargetClient()
    res = client.do_request(
        'vsoa://192.168.1.218:8080/test',
        payload={'param': {'hello': 'world'}}
    )
    print(res)
