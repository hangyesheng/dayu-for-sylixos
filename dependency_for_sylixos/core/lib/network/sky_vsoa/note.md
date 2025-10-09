构建目标：利用 VSOA 完成一个能够无缝兼容 HTTP 协议的通信库

也就是利用 VSOA 实现魔改版本的 HTTP 包

HTTP 请求包括：
POST/GET 方法
URL 寻址
携带 data/json 等数据

实际上是类似 HTTP 语法糖壳了,最后还是会跑在 VSOA 上。

https://docs.acoinfo.com/vsoa/env/dev/sylixos.html#%E6%8E%88%E6%9D%83-vsoa
为了运行 vsoa,需要安装运行库和注册机,python 的话也需要安装 vsoa python 运行库

```python
from vsoa.server import Server

# Create server
server = Server('Hello VSOA')

print('Hello VSOA')

# Server start
server.run('127.0.0.1', 3001)
```

应该需要装一下 sylixos

产品介绍
https://www.acoinfo.com/product/cloud-native/vsoa

使用手册
https://docs.acoinfo.com/vsoa/


发现vsoa纯是socket包装的,因此提供两种方法,
一种是socket实现的http请求,
另一种是利用vsoa实现的http server,并利用vsoa进行请求



最终将思路定为:
1.利用vsoa库实现一个服务器.
2.实现vsoa协议的请求方式
3.利用原生的socket库,实现一个http_request,进行后续的http转换,经测试基本上能够与fastapi交互.


