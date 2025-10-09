Python Overview
更新时间：
2025-02-20
下载文档
VSOA is the abbreviation of Vehicle SOA presented by ACOINFO, VSOA provides a reliable, Real-Time SOA (Service Oriented Architecture) framework, this framework has multi-language and multi-environment implementation, developers can use this framework to build a distributed service model.

VSOA includes the following features:

Support resource tagging of unified URL
Support URL matching subscribe and publish model
Support Real-Time Remote Procedure Call
Support parallel multiple command sequences
Support reliable and unreliable data publishing and datagram
Support multi-channel full-duplex high speed parallel data streams
Support network QoS control
Easily implement server fault-tolerant design
Supports multiple language bindings
Support work queue mechanism
Support TLS encrypted connection
Support client robot
VSOA is a dual-channel communication protocol, using both TCP and UDP, among which the API marked with quick uses the UDP channel. The quick channel is used for high-frequency data update channels. Due to the high data update frequency, the requirements for communication reliability are not strict. It should be noted that UDP channel cannot pass through NAT network, so please do not use quick channel in NAT network.

The total url and payload length of the VSOA data packet cannot exceed 256KBytes - 20Bytes and 65507Bytes - 20Bytes on quick channel, so if you need to send a large amount of data, you can use the VSOA data stream.

User can use the following code to import the vsoa module.


import vsoa
Python minimum version requirement 3.10, recommended >= 3.12.

VSOA Server Class
vsoa.Server(info: dict | str = '', passwd: str = '', raw: bool = False)
info This server information.
passwd This server password.
raw Whether RPC and DATAGRAM payload.param automatically perform JSON parsing.
Returns: VSOA server object.
Create a VSOA server.


server = vsoa.Server('VSOA python server')
VSOA Server Object
server.clients() -> list[RemoteClient]
Returns: List of clients.
Get list of clients currently connected to this server.


for cli in server.clients():
	print(cli.id) # Print remote client ID
server.address() -> tuple[str, int]
Returns: Server address tuple.
Get the server address currently bound to this server. Exception will be thrown when the server is not started.


addr, port = server.address()
server.passwd(passwd: str = '')
passwd New password.
Set a new password for the server, None or '' mean no password.

NOTICE: The password is just a string without any secure encryption, therefore, it is only a relatively simple security management.

server.getpeercert(binary: bool = False) -> dict | None
binary information format,Default False.
Get the peer certificate information.

When binary is set to True, the method returns the certificate in binary form, which can be used in specific situations where the certificate data needs to be saved intact and passed to other underlying functions that may require input in binary format for further processing.

When binary is set to False, this method returns a data structure of type dict that contains many details about the certificate,commonly as follows:

"version" Version number of the certificate.
"serialNumber" Serial number of certificate.
"subject" Certificate subject information.
"issuer" Certificate issuer information.
"notBefore" Start validity period of the certificate.
"notAfter" Expiration date of the certificate.
There are also some other information such as public key related information, extension information, etc. Different certificates may have more detailed content in these aspects.

server.publish(url: str, payload: vsoa.Payload | dict = None, quick: bool = False) -> bool
url Publish URL.
payload Payload data.
quick Whether to use quick mode.
Returns: Whether publish is successful.
Publish a message, all clients subscribed to this URL will receive this message. If a large number of high-frequency releases are required and delivery is not guaranteed, the quick parameter can be set to True.

The payload object contains the following members:

param: {object | dict | list | str | bytes | bytearray} Parameters of this RPC request. Optional.
data {bytes | bytearray} Data for this publish. Optional.
URL matching: URL uses '/' as a separator, for example: '/a/b/c', if the client subscribes to '/a/', the server publish '/a', '/a/b' or '/a/b/c' message, the client will be received.


server.publish('/a/b/c')
server.publish('/a/b/c', { 'param': { 'hello': 'hello' } })
server.publish('/a/b/c', { 'param': { 'hello': 'hello' }, 'data': bytes([1, 2, 3]) })

# Or
server.publish('/a/b/c', vsoa.Payload({ 'hello': 'hello' }))
server.publish('/a/b/c', vsoa.Payload({ 'hello': 'hello' }, bytes([1, 2, 3])))
**NOTICE：**The URL must start with '/', otherwise an exception will be generated.

server.is_subscribed(url: str) -> bool
url Publish URL.
Returns: Whether the specified URL is subscribed by clients.
Whether the specified URL is subscribed. When the return value is True, it means that the specified URL is subscribed by at least one client.

server.command(url: str, wq: vsoa:WorkQueue = None) -> callable
url RPC command URL.
wq This command function runs in the specified workqueue.
Server RPC command entry registration decorator.


server = vsoa.Server('VSOA python server')

@server.command('/echo')
def echo(cli, request, payload):
	cli.reply(request.seqno, payload) # echo reply

server.run('0.0.0.0', 3005)
server.sendtimeout(timeout: float, sync_to_clis: bool = True)
timeout Send timeout.
sync_to_clis Whether set send timeout to the connected clients.
Set send timeout, default is 0.1. (100ms), if sync_to_clis is set to True, it will also set the send timeout for already connected clients.

server.run(host: str, port: int, sslopt: dict = None)
host Local address.
port Local port.
sslopt TLS connection options, Optional. Default is None.
Start the server and execute the event loop. This function does not return when no errors occur.

one-way authentication sslopt
server sslopt

def sni_callback(sock, server_hostname, sslcontext):
	return server_hostname

sslopt = {
	'cert': 'server.crt',
	'key': 'server.key',
	'load_default_certs': False,
	'sni_callback': sni_callback,
	'verify_mode': ssl.CERT_REQUIRED,
	'handsake_error_log': True,
	'passwd': None
}
cert Server certificate file path.
key Server private key file path.
load_default_certs Whether to load the default system certificate. When set to True, Python's SSL module attempts to load some of the trusted certificates configured by the system default. if you are connecting to a server that issues certificates using a self-signed certificate or a private CA, you may need to configure additional certificate-related options (such as via ca_cert, etc.) to ensure that the authentication passes.
sni_callback SNI is an extension mechanism in the SSL/TLS protocol that allows the client to indicate to the server at the beginning of the SSL handshake the name of the target server to connect to (usually the domain name).
verify_mode During the establishment of an SSL connection, the client usually needs to verify the validity of the server certificate to ensure that the server it is communicating with is trusted. Python's ssl module provides several different authentication mode options:
ssl.CERT_NONE Indicates that certificate verification is not performed. If you want to connect to a server that issues certificates using a self-signed certificate or a private CA, verify_mode must be ssl.CERT_NONE.
ssl.CERT_REQUIRED Mandatory server certificate verification.
ssl.CERT_OPTIONAL Certificate verification is optional and is optional by default.
handsake_error_log Used to control whether and how to record the error information during the handshake. The default value is False.
passwd Certificate password. Optional.
client sslopt

sslopt = {
	'hostname': '127.0.0.1',
	'load_default_certs': False,
	'ca_cert': 'ca.crt',
	'verify_mode': ssl.CERT_REQUIRED,
	'handsake_error_log': True,
}
hostname The host name or IP address of the server to connect.
load_default_certs Whether to load the default system certificate. When set to True, Python's SSL module attempts to load some of the trusted certificates configured by the system default. if you are connecting to a server that issues certificates using a self-signed certificate or a private CA, you may need to configure additional certificate-related options (such as via ca_cert, etc.) to ensure that the authentication passes.
ca_cert Specifies the certificate file of the certificate Authority (CA) that is used to verify that the server certificate is valid.
verify_mode Same as server sslopt usage.
handsake_error_log Same as server sslopt usage.
bidirectional authentication sslopt
server sslopt

sslopt = {
	'cert': 'server.crt',
	'key': 'server.key',
	'ca_cert': 'ca.crt',
	'load_default_certs': False,
	'sni_callback': sni_callback,
	'verify_mode': ssl.CERT_REQUIRED,
	'handsake_error_log': True,
	'passwd': None
}
bidirectional authentication has one more ca_cert than one-way authentication.

ca_cert When the sslopt dictionary contains the 'ca_cert' key, it means that two-way authentication is required, that is, the server must not only prove its identity to the client, but also verify the identity of the client.
client sslopt

sslopt = {
	'hostname': '127.0.0.1',
	'load_default_certs': True,
	'ca_cert': 'ca.crt',
	'cert': 'client.crt',
	'key': 'client.key',
	'verify_mode': ssl.CERT_REQUIRED,
	'handsake_error_log': True,
	'passwd': None
}
bidirectional authentication has more cert and key than one-way authentication.

cert Client certificate file path.
key Client private key file path.
passwd Certificate password. Optional.
server.onclient
On client connect / disconnect callback.
The server will call this function when the client connects and disconnects.


def onclient(cli, conn: bool):
	print('Client:', cli.id, 'connect:', conn)

server.onclient = onclient
server.ondata
On client DATAGRAM data received callback.
The server will call this function when client DATAGRAM data received.


def ondata(cli, url: str, payload: vsoa.Payload, quick: bool):
	print('Client:' cli.id, 'DATARAM URL:', url, 'Payload:', dict(payload), 'Q:', quick)

server.ondata = ondata
server.create_stream(onlink: callable, ondata: callable = None, timeout: float = 5.0) -> vsoa.Server.Stream
onlink Client stream connect / disconnect callback.
ondata Receive client stream data callback.
timeout Wait for client connection timeout, unit seconds, default is 5s.
Create a stream to communicate with the client via stream. During normal communication, onlink will be called twice, once when the connection is successful and once when the connection is disconnected. When the stream wait times out, onlink will only be called once, and the conn parameter is False.

Server:


@server.command('/get_data')
def get_data(cli, request, payload):
	def onlink(stream, conn: bool):
		if conn:
			with open('file') as file:
				stream.send(file.read())

	def ondata(stream, data: bytes):
		print('Received:', len(data))

	stream = server.create_stream(onlink, ondata)
	cli.reply(request.seqno, tunid = stream.tunid)
Client:


client = vsoa.Client()
client.robot(...)

file = None
def onlink(stream, conn: bool):
	if conn:
		file = open('file')
	else:
		if file:
			file.close()
			file = None

def ondata(stream, data: bytes):
	file.write(data)

header, payload, _ = client.fetch('/get_data')
if header and header.tunid > 0
	stream = client.create_stream(header.tunid, onlink, ondata)
VSOA Server Remote Client Object
cli.id
Client ID getter. (int type)

cli.authed
Whether this client has logged in. When a client correctly connects to the server (passed the password check), this property defaults to True. If the server requires other login authentication methods at this time, you can set this property to False, and the client will not be able to receive publish message from current server.


def onclient(cli, conn: bool):
	if conn:
		cli.authed = False # This client can not received publish message

server.onclient = onclient

@server.command('/user_auth')
def user_auth(cli, request, payload):
	if user_check:
		cli.authed = True # This client can received publish message
		cli.reply(...)
	else:
		cli.reply(...)
cli.priority
This property is the client priority getter and setter, the valid range is 0 ~ 7, 0 is the lowest.

cli.close()
Close this client, the client object can no longer be used.

cli.is_closed() -> bool
Determine whether the client has been closed. The reason for closure may be that the client actively closed, the developer called the cli.close() method, or the client connection was disconnected.

cli.address() -> tuple[str, int]
Get client address.


def onclient(cli, conn: bool):
	if conn:
		print('Client:', cli.id, 'connected, address:', cli.address())
	else:
		print('Client:', cli.id, 'lost!')

server.onclient = onclient
cli.is_subscribed(url: str) -> bool
url Publish URL.
Returns: Whether the specified URL is subscribed by this client.
Whether the specified URL is subscribed by this client.

cli.reply(seqno: int, payload: vsoa.Payload | dict = None, status: int = 0, tunid: int = 0) -> bool
seqno Request seqno, should be same as the RPC request.
payload Payload to be replied, may be NULL.
status RPC reply status code, 0 means success
tunid If stream communication exists, the returned stream.tunid.
Client RPC call response. status values include:

Constant	Value
vsoa.parser.VSOA_STATUS_SUCCESS	0
vsoa.parser.VSOA_STATUS_PASSWORD	1
vsoa.parser.VSOA_STATUS_ARGUMENTS	2
vsoa.parser.VSOA_STATUS_INVALID_URL	3
vsoa.parser.VSOA_STATUS_NO_RESPONDING	4
vsoa.parser.VSOA_STATUS_NO_PERMISSIONS	5
vsoa.parser.VSOA_STATUS_NO_MEMORY	6
0 means correct, 128 ~ 255 is the server custom error return value.


p = vsoa.Payload({ 'a': 1 }, bytes([1, 2, 3]))

# Same as:
p = vsoa.Payload()
p.param = { 'a': 1 }
p.data  = bytes([1, 2, 3])

# Same as:
p = { 'param': { 'a': 1 }, 'data': bytes([1, 2, 3]) }

cli.reply(request.seqno, p)
cli.datagram(url: str, payload: vsoa.Payload | dict = None, quick: bool = False) -> bool
url Specified URL.
payload Payload to be send.
quick Whether to use quick channel.
Send a DATAGRAM data to the specified client.


p = vsoa.Payload(data = bytes([1, 2, 3, 4, 5]))
cli.datagram('/custom/data', p)
cli.keepalive(idle: int)
idle Idle interval time, unit: seconds.
Enable the client TCP keepalive function. If no reply is received for more than three times the idle time, it means the client is breakdown.

cli.sendtimeout(timeout: float)
timeout Packet send timeout.
When sending packet to the client, the sending is considered failed if the timeout period is exceeded. Default: 0.1s.

cli.getpeercert(binary: bool = False) -> dict | None
binary information format,Default False.
Get peer certificate information (When using a TLS connection).

When binary is set to True, the method returns the certificate in binary form, which can be used in specific situations where the certificate data needs to be saved intact and passed to other underlying functions that may require input in binary format for further processing.

When binary is set to False, this method returns a data structure of type dict that contains many details about the certificate,commonly as follows:

"version" Version number of the certificate.
"serialNumber" Serial number of certificate.
"subject" Certificate subject information.
"issuer" Certificate issuer information.
"notBefore" Start the validity period of the certificate.
"notAfter" Expiration date of the certificate.
There is also some other information, such as public key related information, extension information, etc. Different certificates may have more detailed content in these aspects.

cli.onsubscribe
This function is called when the client subscribes to the URLs.


def onsubscribe(cli, url: str | list[str]):
	print('onsubscribe:', url)

cli.onsubscribe = onsubscribe
cli.onunsubscribe
This function is called when the client unsubscribes to the URLs.


def onunsubscribe(cli, url: str | list[str]):
	print('onunsubscribe:', url)

cli.onunsubscribe = onunsubscribe
Server Stream Object
stream.tunid
Get stream tunnel ID.(int type)

stream.connected
Check if stream is connected.(bool type)

stream.close()
Close this stream. will be called automatically when disconnecting.

stream.send(data: bytearray | bytes) -> int
data Data to be sent.
Returns: The actual data length sent.
Send data using stream.

stream.keepalive(idle: int)
idle Idle interval time, unit: seconds.
Enable the stream TCP keepalive function. If no reply is received for more than three times the idle time, it means the stream is breakdown.

stream.sendtimeout(timeout: float)
timeout Packet send timeout, unit: senconds.
When sending packet to the stream, the sending is considered failed if the timeout period is exceeded. Default: block until ready to send.

VSOA Client Class
vsoa.Client(raw: bool = False)
raw Whether publish, RPC and DATAGRAM payload.param automatically perform JSON parsing.
Returns: VSOA client object.

client = vsoa.Client()
VSOA Client Object
client.connected
Whether the current client is connected to the server.(bool type)

client.onconnect
This function is called when this client connects or disconnects from the server.


def onconnect(client, conn: bool, info: str | dict | list)
	if conn:
		print('Connected, server info:', info)
	else:
		print('disconnected')

client.onconnect = onconnect
client.onmessage
On server PUBLISH data received callback.
The client will call this function when server PUBLISH data is received.


def onmessage(client, url: str, payload: vsoa.Payload, quick: bool):
	print('Msg received, url:', url, 'payload:', dict(payload), 'Q:', quick)

client.onmessage = onmessage
client.subscribe('/topic1')
client.ondata
On server DATAGRAM data received callback.
The client will call this function when server DATAGRAM data received.


def ondata(client, url: str, payload: vsoa.Payload, quick: bool):
	print('DATARAM URL:', url, 'Payload:', dict(payload), 'Q:', quick)

client.ondata = ondata
client.close()
Close this client. This client object is no longer allowed to be used.

client.call(url: str, method: str | int = 0, payload: vsoa.Payload | dict = None, callback: callable = None, timeout: float = 60.0) -> bool
url Command URL.
method Request method vsoa.METHOD_GET (0) or vsoa.METHOD_SET (1)
payload RPC payload. This payload will be sent to the VSOA server..
callback Server response callback.
timeout Wait timeout out, unit: seconds, default is 60s.
Returns: Whether request send successfully.

def onreply(client, header: vsoa:Header, payload: vsoa:Payload):
	if header:
		print(dict(header), dict(payload))
	else:
		print('Server no response!')

ret = client.call('/echo', payload = vsoa.Payload({ 'a': 1 }), callback = onreply)
if not ret:
	print('RPC request error!')
This function will return immediately, and the callback will be executed in the client event loop thread. The callback header argument object has the following members:

status Response status.
tunid If it is not 0, it means the server stream tunnel ID.
client.ping(callback: callable = None, timeout: float = 60.0) -> bool
callback Server ping echo callback.
timeout Wait timeout out, unit: seconds, default is 60s.
Returns: Whether request send successfully.
Send a ping request.


def onecho(cli, success: bool):
	print('Ping echo:', success)

client.ping(onecho, 10)
client.subscribe(url: str | list[str], callback: callable = None, timeout: float = 60.0) -> bool
url URL or URL list that needs to be subscribed.
callback This will be called after the subscribe request is successfully accepted by the server and the data is published.
timeout Wait timeout out, unit: seconds, default is 60s.
Returns: Whether request send successfully.
Subscribe to the specified URLs message. When the server publishes matching message, the client can receive this data use onmessage.


def onmessage(client, url: str, payload: vsoa.Payload, quick: bool):
	print('Msg received, url:', url, 'payload:', dict(payload), 'Q:', quick)

client.onmessage = onmessage

client.subscribe('/topic1')
client.subscribe(['/topic2', '/topic3'])
client.unsubscribe(url: str | list[str], callback: callable = None, timeout: float = 60.0) -> bool
url URL or URL list that needs to be unsubscribed.
callback This will be called after the unsubscribe request is successful.
timeout Wait timeout out, unit: seconds, default is 60s.
Returns: Whether request send successfully.
Unsubscribe to the specified URLs message.

client.datagram(url: str, payload: vsoa.Payload | dict = None, quick: bool = False) -> bool
url Specified URL.
payload DATAGRAM payload.
quick Whether to use quick channel.
Returns: Whether send successfully.
Send a DATAGRAM data to server.

client.getpeercert(binary: bool = False) -> dict | None
binary information format, Default False.
Get peer certificate information (When using a TLS connection).

VSOA Client Object Current Thread Loop Mode
client.connect(url: str, passwd: str = '', timeout: float = 10.0, sslopt: dict = None) -> int
url Server URL.
passwd Server password. Optional.
timeout Timeout for connecting to the server, unit: seconds, default is 10s.
sslopt TLS connection options, Optional. Default is None.
Returns: Error code.
Connect to the specified server and return the following code:

Constant	Value
Client.CONNECT_OK	0
Client.CONNECT_ERROR	1
Client.CONNECT_UNREACHABLE	2
Client.SERVER_NOT_FOUND	3
Client.SERVER_NO_RESPONDING	4
Client.INVALID_RESPONDING	5
Client.INVALID_PASSWD	6
Client.SSL_HS_FAILED	7

ret = client.connect('vsoa://192.168.0.1:3005')
if ret:
	print('Connect error:', ret)
client.disconnect()
Disconnect from server.


client.disconnect()

time.sleep(3)

client.connect('vsoa://your_server_name_or_ip:port') # reconnect
client.sendtimeout(timeout: float)
timeout Send timeout, unit: seconds.
Set send timeout, default is 0.5. (500ms)

client.linger(time: int = 0) -> bool
time Socket waiting time.
Returns: Whether socket linger time is set.
Set socket linger time, default is 0.

linger is a method related to sockets. It is used to control the behavior of a socket when it is closed, especially when processing unsent data. When the close() method of a socket is called, the linger option can decide whether to wait for unsent data to finish sending, or simply discard it and close the socket.

client.pendings
Get the number of pending messages. These message types include: RPC, subscribe, unsubscribe, ping. (int type)

client.run()
Run the client event loop. When this function exits normally, it means that the client has disconnected from the server or the client has been closed.


client = vsoa.Client()

while True:
	if client.connect('vsoa://192.168.1.1:3005'):
		time.sleep(1)
	else:
		client.run()
		time.sleep(1)
client.create_stream(tunid: int, onlink: callable, ondata: callable = None, timeout: float = 10.0) -> vsoa.Client.Stream:
tunid Server peer stream tunnel id.
onlink Client stream connect / disconnect callback.
ondata Receive client stream data callback.
timeout Wait for client connection timeout, unit: seconds, default is 10s.
Used in pair with server.create_stream

VSOA Client Object Robot Loop Mode
client.robot(server: str, passwd: str = '', keepalive: float = 3.0, conn_timeout: float = 10.0, reconn_delay: float = 1.0, sslopt: dict = None)
server Server URL.
passwd Server password.
keepalive How often send vsoa ping to detect whether the connection is good after the connection is successful. In milliseconds, the minimum is 50ms. ping timeout is the same as this value.
conn_timeout Connection timeout, the minimum is 50ms.
reconn_delay Waiting time for reconnection after disconnection.
sslopt TLS connection options, Optional. Default is None.
This function will automatically start a robot thread to handle the client event loop, and will automatically handle broken links.


client = vsoa.Client()
client.robot('vsoa://192.168.1.1:3005') # Automatically create a new thread responsible for the event loop

while True:
	time.sleep(1)

	header, payload, errcode = client.fetch('/echo', payload = { 'param': { 'a': 3 }})
	if header:
		print(dict(header), dict(payload))
	else:
		print('fetch error:', errcode) # `errcode` is same as client connect error code
client.robot_ping_turbo(turbo: float, max_cnt: int = 50) -> bool
turbo Robot ping interval.
max_cnt Maximum attempts (not in use).
Returns: Whether turbo ping is set.
When there is an RPC call pending and data packet loss occurs, and at this time, both the client and the server need to try their best to perform TCP fast retransmission. You can set this turbo parameter, whose minimum value is 25ms. 0 means disable turbo ping.

When turbo ping is enabled, the turbo value must be less than or equal to keepalive in client.robot.

client.fetch(url: str, method: str | int = 0, payload: vsoa.Payload | dict = None, timeout: float = 60.0) -> tuple[vsoa.Header, vsoa.Payload, int]
url Command URL.
method Request method vsoa.METHOD_GET (0) or vsoa.METHOD_SET (1)
payload Request payload.
timeout Wait timeout out.
Returns: Request result and error code.
This function is a synchronous version of client.call, this function is not allowed to be executed in the client event loop thread.

Client Stream Object
stream.connected
Check if stream is connected. (bool type)

stream.close()
Close this stream.

stream.send(data: bytearray | bytes) -> int
data Data to be sent.

Returns: The actual data length sent.

Send data using stream.

stream.keepalive(idle: int)
idle Idle interval time, unit: seconds.
Enable the stream TCP keepalive function. If no reply is received for more than three times the idle time, it means the stream is breakdown.

stream.sendtimeout(timeout: float)
timeout Packet send timeout, unit: seconds.
When sending packet to the stream, the sending is considered failed if the timeout period is exceeded. Default: block until ready to send.

VSOA Client 'Once'
If we only need one RPC request and don't want to maintain a long-term connection with the server, we can use the following operation.

vsoa.fetch(url: str, passwd: str = None, method: str | int = 0, payload: vsoa.Payload | dict = None, timeout: float = 10.0, raw: bool = False, sslopt: dict = None) -> tuple[vsoa.Header, vsoa.Payload, int]
url Request URL.
passwd Server password.
method Request method vsoa.METHOD_GET (0) or vsoa.METHOD_SET (1).
payload Request payload.
timeout Wait timeout out, unit: seconds, default is 10s.
raw Whether to automatically parse JSON payload.param.
sslopt TLS connection options, Optional. Default is None.
Returns: Whether request result and error code.

header, payload, _ = vsoa.fetch('vsoa://192.168.1.1:3001/echo', payload = { 'param': { 'a': 3 }})
if header:
	print(dict(header), dict(payload))
VSOA Position Server
vsoa.Position(onquery: callable)
onquery Client host address query callback.
Returns: Position server object.
Create a position server.


def onquery(search: dict, reply: callable):
	if search['name'] == 'myserver':
		reply({ 'addr': '127.0.0.1', 'port': 3005, 'domain': socket.AF_INET })
	else:
		reply(None)

pserv = vsoa.Position(onquery)

pserv.run('0.0.0.0', 3000) # Position server run, never return
VSOA Position Query
vsoa.pos(addr: str, port: int)
addr Position server IP address.
port Position server port.
This function can specify the position server address used by vsoa.lookup.

vsoa.lookup(name: str, domain: int = -1) -> tuple[str, int]
name Server name.
domain Specify IP protocol family, -1 means any.
Returns: Queryed server address.
Query the specified server address.


addr, port = vsoa.lookup('myserv')
if addr:
	...
Query order:

Use the position server specified by vsoa.pos()
Use the position server specified by the VSOA_POS_SERVER environment variable.
Use the position server specified by the /etc/vsoa.pos configuration file (C:\Windows\System32\drivers\etc\vsoa.pos on windows)
VSOA Timer
VSOA provides a general timer function, and the timer callback will be executed in the timer service thread.

vsoa.Timer()
Create a timer object.

timer.start(timeout: float, callback: callable, interval: float = 0, args = (), kwargs = {})
timeout Timer timeout seconds must be greater than 0.
callback Timer timeout callback.
interval Periodic interval seconds, 0 means one shot timing.
args Callback arguments.
kwargs Callback keywords arguments.

timer = vsoa.Timer()

def func(a, b, c):
	print('timer!', a, b, c)

# One shot timer, Execute `func` function after 1.5s
timer.start(1.5, func, args = (1, 2, 3))
timer.stop()
Stop a timer. A stopped timer can be started again.

timer.is_started() -> bool
Check whether the timer is timing.

VSOA EventEmitter
vsoa provides an EventEmitter class similar to JSRE and NodeJS to facilitate event subscription.

EventEmitter has two special events new_listener and remove_listener indicating the installation and removal of listener. These events is generated automatically. Developers are not allowed to emit these events.

new_listenerand remove_listener event callback parameters are as follows:

event Event.
listener Event listener.
vsoa.EventEmitter()
Event emitter class, Users class can inherit this class, Create a event object.


class MyClass(vsoa.EventEmitter):
	def __init__(self):
		super().__init__()
		...
event.add_listerner(event, listener: callable)
event Event.
listener When this event occurs, this callback function is executed.
Add a listener for the specified event. The listener function arguments need to be consistent with the parameters generated by the event.


def func():
	print('event catched!')

event = vsoa.EventEmitter()

## Add listener
event.add_listerner('test', func)

## Emit event
event.emit('test')
event.on(event, listener: callable)
Alias ​​of event.add_listerner.

event.once(event: int | str | object, listener: callable) -> None
Similar to event.add_listerner, but the added event listener function will only be executed once.

event.remove_listener(event, listener: callable = None) -> bool
event Event.
listener Need matching listener function.
Delete the previously added event listener. If listener is None, it means deleting all listeners for the specified event.

event.remove_all_listeners(event = None)
event Event.
Delete all listeners for the specified event, event is None means deleting all listeners functions for all events.

event.listener_count(event) -> int
event Event.
Get the number of listeners for the specified event.

event.listeners(event) -> list[callable]
event Event.
Get the listener list of the specified event.

event.emit(event, args = (), kwargs = {}) -> bool
event Event.
args Event arguments.
kwargs Event keyword arguments.
Generate an event, the listener corresponding to this event will be run according to the installation order.


class MyClass(vsoa.EventEmitter):
	def __init__(self):
		super().__init__()
		self.on('test', self.on_test)

	def on_test(self, a, b) -> None:
		print(a, b)

e = MyClass()
e.emit('test', args = (1, 2))
VSOA WorkQueue
VSOA provides an asynchronous work queue function. Users can add job functions to the asynchronous work queue for sequential execution.

vsoa.WorkQueue()
Create a work queue.

wq.add(func: callable, args = (), kwargs = {})
func Work queue job function.
args Function arguments.
kwargs Function keywords arguments.

def hello(count: int):
	print('Hello count:', count)

wq = vsoa.WorkQueue()
wq.add(hello, args = (1,))
wq.add(hello, args = (2,))
wq.add(hello, args = (3,))
The server can use WorkQueue to implement asynchronous command processing to avoid the main loop being blocked for too long.


app = vsoa.Server('hello')
wq  = vsoa.WorkQueue()

@app.command('/hello', wq)
def echo(cli, request, payload):
	cli.reply(request.seqno, payload)

app.run('0.0.0.0', 3005)
wq.add_if_not_queued(func: callable, args = (), kwargs = {}) -> bool
func Work queue job function.
args Function arguments.
kwargs Function keywords arguments.
Returns: Whether add is successful.
Add job if job function not in queued.

wq.delete(func: callable) -> bool
func Work queue job function.
Returns: Whether the deletion is successful.
Delete the specified job that is not being executed in the queue.

wq.is_queued(func: callable) -> bool
func Work queue job function.
Returns: Whether queued.
Whether the specified job is in the queue.