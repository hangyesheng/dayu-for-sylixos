'''
@Project ：sky_vsoa
@File    ：target_server.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/8/26 19:45 
'''

import vsoa
import threading
from typing import Callable
# from core.lib.common import Context, SystemConstant, LOGGER, FileOps
# from core.lib.network import NodeInfo, PortInfo, merge_address, NetworkAPIMethod, NetworkAPIPath, new_http_request
# from core.lib.content import Task
# from core.lib.estimation import TimeEstimator


class TargetServer(object):
    """
    支持vsoa的服务器,会被部署在边缘端.
    """

    def __init__(self,
                 host: str = "localhost",
                 port: int = 2333,
                 name: str = 'demo-server'
                 ):
        self.info = {'name': name, 'version': vsoa.__version__}
        self.server = vsoa.Server(self.info)
        self.host = host
        self.port = port
        self.route_dict = {
            "GET@/TEST": self.info
        }

    def __str__(self):
        return self.info

    def __run(self):
        self.server.run(self.host, self.port)

    def __default_on_client(server: vsoa.Server, cli: vsoa.Server.Client, connected: bool) -> None:
        # 客户端连接/断开回调
        addr = cli.address() if not cli.is_closed() else ('-', 0)
        print(f'[server] client {cli.id} {"connected" if connected else "disconnected"} from {addr}')

    # 处理客户端发送的数据报（包括 quick 与普通）
    def __default_on_data(server: vsoa.Server, cli: vsoa.Server.Client, url: str, payload: vsoa.Payload,
                          quick: bool) -> None:
        # 处理客户端发送的数据报（包括 quick 与普通）
        print(
            f'[server] datagram url={url} quick={quick} param={payload.param} data_len={0 if not payload.data else len(payload.data)}')

    def start(self, on_client: Callable = None, on_data: Callable = None):
        if on_client is not None:
            self.server.onclient = on_client
        else:
            self.server.onclient = self.__default_on_client
        if on_data is not None:
            self.server.ondata = on_data
        else:
            self.server.ondata = self.__default_on_data

        threading.Thread(target=self.__run, name='vsoa_server_demo', daemon=False).start()
        print(f"[INFO] Server started @{self.host}:{self.port} successfully.")

    def decorate(self, func):
        def decorate_func(cli: vsoa.Server.Client, req: vsoa.Request, payload: vsoa.Payload) -> None:
            # 解析参数
            param = payload.param if isinstance(payload.param, dict) else {}
            # 获取结果
            try:
                # 优先传入 param 与 data，兼容需要原始字节数据的处理函数
                res = func(param=param, data=payload.data)
            except TypeError:
                # 兼容只接受解包参数的旧实现
                res = func(**param)
            status = 0 if res is not None else vsoa.parser.VSOA_STATUS_ARGUMENTS
            # 进行回复
            cli.reply(req.seqno, {'param': res}, status=status)

        return decorate_func

    def add_route(self,
                  route: str,
                  func,
                  method
                  ):
        """
        :param route:
        :param func:
        :param method:
        :return:
        """
        if route not in self.route_dict.keys():
            self.route_dict[f"{method}@{route}"] = func
            self.server.command(route)(self.decorate(func))


def test_func(**kwargs):
    return "hello world!"


if __name__ == '__main__':
    server = TargetServer(host="192.168.1.218", port=8080, )
    server.add_route(
        '/test',
        test_func,
        "GET"
    )
    server.start()
