'''
@Project ：sky_vsoa
@File    ：vsoa_server.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/8/26 15:33 
'''
import threading
import time
import core.lib.network.sky_vsoa.vsoa as vsoa


def main() -> None:
    # 创建服务器，设置基本信息（会在握手时返回给客户端）
    server = vsoa.Server(info={'name': 'demo-server', 'version': vsoa.__version__})

    # 客户端连接/断开回调
    def on_client(cli: vsoa.Server.Client, connected: bool) -> None:
        addr = cli.address() if not cli.is_closed() else ('-', 0)
        print(f'[server] client {cli.id} {"connected" if connected else "disconnected"} from {addr}')

    server.onclient = on_client

    # 处理客户端发送的数据报（包括 quick 与普通）
    def on_data(cli: vsoa.Server.Client, url: str, payload: vsoa.Payload, quick: bool) -> None:
        print(
            f'[server] datagram url={url} quick={quick} param={payload.param} data_len={0 if not payload.data else len(payload.data)}')
        # 将数据原样回送到另一路径，演示服务端主动发送数据报
        # cli.datagram('/udp/echo', {'param': {'from': 'server', 'url': url, 'quick': quick, 'echo_param': payload.param},
        #                            'data': payload.data}, quick)

    server.ondata = on_data

    # 注册一个简单的 RPC：/echo 原样返回
    @server.command('/echo')
    def cmd_echo(cli: vsoa.Server.Client, req: vsoa.Request, payload: vsoa.Payload) -> None:
        print(
            f'[server] rpc /echo method={"SET" if req.method else "GET"} param={payload.param} data_len={0 if not payload.data else len(payload.data)}')
        cli.reply(req.seqno, payload)

    # 注册一个 RPC：/sum 计算两数之和，要求 param 为 {'a': number, 'b': number}
    @server.command('/sum')
    def cmd_sum(cli: vsoa.Server.Client, req: vsoa.Request, payload: vsoa.Payload) -> None:
        param = payload.param if isinstance(payload.param, dict) else {}
        a = param.get('a', 0)
        b = param.get('b', 0)
        try:
            res = float(a) + float(b)
        except Exception:
            res = None
        status = 0 if res is not None else vsoa.parser.VSOA_STATUS_ARGUMENTS
        cli.reply(req.seqno, {'param': {'sum': res}}, status=status)

    # 周期性发布主题消息（客户端可订阅）
    def publisher() -> None:
        while True:
            server.publish('/topic/time', {'param': {'ts': int(time.time())}})
            time.sleep(1.0)

    threading.Thread(target=publisher, name='vsoa_demo_publisher', daemon=True).start()

    # 启动服务器
    print('[server] run at 127.0.0.1:8080')
    server.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
