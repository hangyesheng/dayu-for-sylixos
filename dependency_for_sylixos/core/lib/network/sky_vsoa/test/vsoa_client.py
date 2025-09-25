'''
@Project ：sky_vsoa
@File    ：vsoa_client.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/8/26 15:33 
'''
import threading
import time
import core.lib.network.sky_vsoa.vsoa as vsoa


def main() -> None:
    cli = vsoa.Client()

    # 连接成功/断开回调
    def on_connect(c: vsoa.Client, connected: bool, info: dict | None) -> None:
        print(f'[client] {"connected" if connected else "disconnected"} info={info}')

    # 订阅消息回调（服务器 publish 和 quick publish 都会走这里）
    def on_message(c: vsoa.Client, url: str, payload: vsoa.Payload, quick: bool) -> None:
        print(
            f'[client] message url={url} quick={quick} param={payload.param} data_len={0 if not payload.data else len(payload.data)}')

    # 接收数据报回调
    def on_data(c: vsoa.Client, url: str, payload: vsoa.Payload, quick: bool) -> None:
        print(
            f'[client] datagram url={url} quick={quick} param={payload.param} data_len={0 if not payload.data else len(payload.data)}')

    cli.onconnect = on_connect
    cli.onmessage = on_message
    cli.ondata = on_data

    # 连接服务器（与 vsoa_server.py 对应）
    ret = cli.connect('sky_vsoa://192.168.1.161:8080', timeout=5)
    print(ret)
    if ret != vsoa.Client.CONNECT_OK:
        print(f'[client] connect failed: {ret}')
        return

    # 订阅服务器周期主题
    ok = cli.subscribe('/topic/time', lambda c, success: print(f'[client] subscribe /topic/time => {success}'))
    if not ok:
        print('[client] subscribe request failed to send')

    # 做一次 RPC：/echo
    def echo_cb(c: vsoa.Client, h: vsoa.Header, p: vsoa.Payload) -> None:
        print(f'[client] rpc /echo reply status={h.status} param={p.param} data_len={0 if not p.data else len(p.data)}')

    cli.call('/echo', method='get', payload={'param': {'hello': 'world'}}, callback=echo_cb, timeout=3)

    # 做一次 RPC：/sum
    def sum_cb(c: vsoa.Client, h: vsoa.Header, p: vsoa.Payload) -> None:
        print(f'[client] rpc /sum reply status={h.status} sum={(p.param or {}).get("sum") if p else None}')

    cli.call('/sum', method='get', payload={'param': {'a': 7, 'b': 35}}, callback=sum_cb, timeout=3)

    # 向服务端发送数据报（quick/udp 与普通/tcp 各发一次）
    cli.datagram('/udp/hello', {'param': {'from': 'client', 'n': 1}})
    # quick 通道需要握手后由服务端返回 udp 端口，connect 已完成此过程
    cli.datagram('/udp/hello', {'param': {'from': 'client', 'n': 2, 'quick': True}}, quick=True)

    # 在后台定时发送 datagram
    def spam() -> None:
        cnt = 0
        while cli.connected and cnt < 5:
            cnt += 1
            cli.datagram('/udp/tick', {'param': {'tick': cnt}}, quick=(cnt % 2 == 0))
            time.sleep(1.0)

    threading.Thread(target=spam, name='vsoa_demo_spam', daemon=True).start()

    # 进入事件循环（阻塞直到断开）
    try:
        cli.run()
    finally:
        cli.close()


if __name__ == '__main__':
    main()
