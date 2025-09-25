#
# Copyright (c) 2024 ACOAUTO Team.
# All rights reserved.
#
# Detailed license information can be found in the LICENSE file.
#
# File: server.py Vehicle SOA server.
#
# Author: Han.hui <hanhui@acoinfo.com>
#

import core.lib.network.sky_vsoa.vsoa.parser as parser
import core.lib.network.sky_vsoa.vsoa.sockopt as sockopt
import core.lib.network.sky_vsoa.vsoa.interface as interface
import time, struct, threading, socket, select

# VSOA server backlog
VSOA_SERVER_BACKLOG = 32

# Server default send timeout (ms)
SERVER_DEF_SEND_TIMEOUT = 100

# Server default handshake timeout (ms)
SERVER_DEF_HANDSHAKE_TIMEOUT = 5000

# Server timer period (ms)
SERVER_TIMER_PERIOD = 100

# Server Stream
class Stream:
	def __init__(self, server: object, family: int, host: str, onlink: callable, ondata: callable, timeout: float) -> None:
		self.onlink = onlink
		self.ondata = ondata
		self._alive = int(timeout * 1000)

		# Stream socket
		self.__server  = server
		self.__listen  = sockopt.create(family, 'tcp', server = True)
		self.__clisock = None

		# Initialize
		self.__listen.bind((host, 0))
		self.__listen.listen(1)

		# Tunid
		_, self.__tunid = self.__listen.getsockname()

		# Add to server stream list
		with server._lock:
			server._streams.append(self)
			sockopt.event_emit(server._strevt[1])

	# Get tunid
	@property
	def tunid(self) -> int:
		return self.__tunid

	@property
	def connected(self) -> bool:
		return True if self.__clisock else False

	# Get socket need to monitor
	def _sock(self) -> socket.socket:
		return self.__listen if self.__listen else self.__clisock

	# Stream remove
	def __remove(self) -> None:
		with self.__server._lock:
			if self.__listen:
				self.__listen.close()
				self.__listen = None

			if self.__clisock:
				self.__clisock.close()
				self.__clisock = None

			if self in self.__server._streams:
				self.__server._streams.remove(self)

		if callable(self.onlink):
			self.onlink(self, False)

	# Stream event
	def _event(self, sock: socket.socket) -> None:
		conn = False

		with self.__server._lock:
			if sock == self.__listen:
				clistream, _ = self.__listen.accept()
				assert(clistream)
				self.__listen.close()
				self.__listen  = None
				self.__clisock = clistream
				self.__clisock.setblocking(True)
				conn = True

		if conn:
			if callable(self.onlink):
				self.onlink(self, True)
			return

		if sock == self.__clisock:
			try:
				data = self.__clisock.recv(parser.VSOA_MAX_PACKET_LENGTH, sockopt.DWT)
			except:
				data = None

			if data:
				if callable(self.ondata):
					self.ondata(self, data)
			else:
				self.__remove()

	# Close stream (will be called automatically when disconnecting)
	def close(self) -> None:
		with self.__server._lock:
			if self.__clisock:
				sockopt.tcpshutdown(self.__clisock)
				return

		if self.__listen:
			self.__remove()

	# Send data
	def send(self, data: bytearray | bytes) -> int:
		if self.__clisock == None:
			if self.__listen:
				raise Exception('Client not connected')
			else:
				raise Exception('Client has closed')

		return sockopt.tcpsend(self.__clisock, data, len(data))

	# Set client keepalive
	def keepalive(self, idle: int) -> None:
		if self.__clisock:
			sockopt.keepalive(self.__clisock, int(idle))

	# Set send timeout
	def sendtimeout(self, timeout: float) -> None:
		if self.__clisock == None:
			raise Exception('Client not connected')

		self.__clisock.settimeout(timeout)

# Remote Client
class Client:
	def __init__(self, sock: socket.socket, server: object, chost: str, cid: int, raw: bool = False) -> None:
		self.authed = False

		# Protected prop
		self._hsalive = SERVER_DEF_HANDSHAKE_TIMEOUT
		self._qaddr   = None
		self._chost   = chost
		self._prio    = 0
		self._active  = False
		self._onconn  = False

		# Private prop
		self.__close    = False
		self.__cid      = cid
		self.__caddr    = sock.getpeername()
		self.__server   = server
		self.__unpacker = parser.Unpacker(raw = raw)
		self.__subs     : set[str] = set()

		# Socket protected
		self._sock = sock

		# User hooks
		self.onsubscribe   = lambda cli, topics: None
		self.onunsubscribe = lambda cli, topics: None

	# Client finish
	def _finish(self) -> None:
		self._sock.setblocking(True)
		self._sock.close()
		self._sock   = None
		self.__close = True

	# Send packet
	def _psend(self, packer: parser.Packer | bytearray, quick: bool) -> bool:
		total = 0
		if type(packer) == parser.Packer:
			packet, plen = packer.packet()
		else:
			packet = packer
			plen   = len(packet)
		try:
			if quick:
				if self._qaddr:
					self.__server._quick.sendto(packet, sockopt.NO_SIG, self._qaddr)
				total = plen
			else:
				total = sockopt.tcpsend(self._sock, packet, plen)
		except:
			return False
		else:
			return True if total == plen else False

	# Receive packet
	def _precv(self, packet: bytes) -> bool:
		return self.__unpacker.input(packet, self._pinput)

	# Packet input
	def _pinput(self, header: interface.Header, url: str, param: dict | list | bytes, data: bytes, quick: bool = False) -> None:
		ptype = header.type
		if ptype == parser.VSOA_TYPE_NOOP or header.flags & parser.VSOA_FLAG_REPLY:
			return

		packer  = self.__server._packer
		payload = interface.Payload(param, data)

		if not self._active:
			if self.__server._passwd:
				if type(param) == dict and ('passwd' in param) and param['passwd'] == self.__server._passwd:
					self.authed = self._active = True
				else:
					with self.__server._lock:
						packer.header(ptype, parser.VSOA_FLAG_REPLY, parser.VSOA_STATUS_PASSWORD, header.seqno)
						self._psend(packer, False)
					return
			else:
				self.authed = self._active = True

		if ptype == parser.VSOA_TYPE_DATAGRAM:
			self.__server.ondata(self, url, payload, quick)

		elif ptype == parser.VSOA_TYPE_SERVINFO:
			with self.__server._lock:
				if header.flags & parser.VSOA_FLAG_TUNNEL:
					self._qaddr = (self._chost, header.tunid)

				packer.header(ptype, parser.VSOA_FLAG_REPLY, 0, header.seqno)
				packer.payload(None, param = self.__server._info, data = struct.pack('>I', self.__cid))
				self._psend(packer, False)
				self.__server._hssuccess(self)

			if not self._onconn:
				self._onconn = True
				self.__server.onclient(self, True)

		elif ptype == parser.VSOA_TYPE_RPC:
			if not url or not url.startswith('/'):
				with self.__server._lock:
					packer.header(ptype, parser.VSOA_FLAG_REPLY, parser.VSOA_STATUS_ARGUMENTS, header.seqno)
					self._psend(packer, False)
			else:
				func = self.__server._cmdfunc(url)
				if callable(func):
					func(self, interface.Request(url, header.seqno, 1 if header.flags & parser.VSOA_FLAG_SET else 0), payload)
				else:
					with self.__server._lock:
						packer.header(ptype, parser.VSOA_FLAG_REPLY, parser.VSOA_STATUS_INVALID_URL, header.seqno)
						self._psend(packer, False)

		elif ptype == parser.VSOA_TYPE_SUBSCRIBE:
			topics = []
			if url and url.startswith('/'):
				self.__subs.add(url)
				topics.append(url)
				status = 0
			elif url is None and type(param) == list:
				for sub in param:
					if type(sub) == str and sub.startswith('/'):
						self.__subs.add(sub)
						topics.append(url)
				status = 0
			else:
				status = parser.VSOA_STATUS_ARGUMENTS
			with self.__server._lock:
				packer.header(ptype, parser.VSOA_FLAG_REPLY, status, header.seqno)
				self._psend(packer, False)
			if status == 0:
				self.onsubscribe(self, topics)

		elif ptype == parser.VSOA_TYPE_UNSUBSCRIBE:
			topics = []
			if url and url.startswith('/'):
				if url in self.__subs:
					self.__subs.remove(url)
					topics.append(url)
				status = 0
			elif url is None and type(param) == list:
				for sub in param:
					if type(sub) == str and sub.startswith('/') and sub in self.__subs:
						self.__subs.remove(sub)
						topics.append(url)
				status = 0
			else:
				status = parser.VSOA_STATUS_ARGUMENTS
			with self.__server._lock:
				packer.header(ptype, parser.VSOA_FLAG_REPLY, status, header.seqno)
				self._psend(packer, False)
			if status == 0:
				self.onunsubscribe(self, topics)

		elif ptype == parser.VSOA_TYPE_PINGECHO:
			with self.__server._lock:
				packer.header(ptype, parser.VSOA_FLAG_REPLY, 0, header.seqno)
				self._psend(packer, False)

	# client.id
	@property
	def id(self) -> int:
		return self.__cid

	# client.prio
	@property
	def priority(self) -> int:
		return self._prio

	@priority.setter
	def priority(self, nprio: int) -> None:
		if nprio < 0 or nprio > 7:
			raise ValueError('Priority must in 0 ~ 7')

		packer = self.__server._packer
		sockopt.priority(self._sock, nprio)

		with self.__server._lock:
			self._prio = nprio
			prio_list  = self.__server._priocli
			if self in prio_list:
				prio_list.remove(self)
				for i in range(0, len(prio_list)):
					cli = prio_list[i]
					if self._prio > cli._prio:
						prio_list.insert(i, self)
						break
				else:
					prio_list.append(self)

			packer.header(parser.VSOA_TYPE_QOSSETUP, parser.VSOA_FLAG_REPLY, nprio, 0)
			self._psend(packer, False)

	# Client close
	def close(self) -> None:
		sockopt.tcpshutdown(self._sock)
		self.__close = True

	# Get client address
	def address(self) -> tuple[str, int]:
		return self.__caddr

	# Get client whether closed
	def is_closed(self) -> bool:
		return self.__close

	# Whether the specified URL is subscribed.
	def is_subscribed(self, url: str) -> bool:
		if self._active and self.authed:
			for sub in self.__subs:
				if len(sub) == 1 or sub == url:
					return True
				elif sub.endswith('/'):
					sub = sub[0:-1]
					if url.startswith(sub):
						ulen = len(url)
						slen = len(sub)
						if ulen == slen or (ulen > slen and url[slen] == '/'):
							return True
		return False

	# Client reply
	def reply(self, seqno: int, payload: interface.Payload | dict = None, status: int = 0, tunid: int = 0) -> bool:
		if self.__close:
			return False

		packer = self.__server._packer

		with self.__server._lock:
			packer.header(parser.VSOA_TYPE_RPC, parser.VSOA_FLAG_REPLY, status, seqno)

			if tunid > 0 and tunid < 65536:
				packer.tunid(tunid)

			if payload and isinstance(payload, (object, dict)):
				packer.payload(payload)

			return self._psend(packer, False)

	# Send datagram to client
	def datagram(self, url: str, payload: interface.Payload | dict = None, quick: bool = False) -> bool:
		if self.__close:
			return False

		packer = self.__server._packer

		with self.__server._lock:
			packer.header(parser.VSOA_TYPE_DATAGRAM, 0, 0, 0)
			packer.url(url)

			if payload and isinstance(payload, (object, dict)):
				packer.payload(payload)

			return self._psend(packer, quick)

	# Set client keepalive
	def keepalive(self, idle: int) -> None:
		if self._sock:
			sockopt.keepalive(self._sock, int(idle))

	# Set send timeout
	def sendtimeout(self, timeout: float) -> None:
		if self._sock:
			self._sock.settimeout(timeout)

# Server class
class Server:
	# Server sub-class
	Client = Client
	Stream = Stream

	def __init__(self, info: dict | str = '', passwd: str = '', raw: bool = False) -> None:
		# Server address
		self.__addr = None
		self.__raw  = raw

		# Protected prop
		self._running = False
		self._info    = info
		self._passwd  = passwd
		self._packer  = parser.Packer()
		self._lock    = threading.Lock()
		self._priocli : list[Client] = []
		self._sendto  = float(SERVER_DEF_SEND_TIMEOUT) / 1000

		# Remote clients
		self.__ncid   = 0
		self.__cidtbl : dict[int, Client] = {}
		self.__hslist : list[Client]      = []

		# Server commands
		self.__cmds   : dict[str, callable] = {}
		self.__wccmds : dict[str, callable] = {}

		# Server streams
		self._streams : list[Stream] = []
		self._strevt  = sockopt.pair()

		# Server hooks and send timeout
		self.ondata   = lambda cli, url, payload, quick: None
		self.onclient = lambda cli, connect: None

		# Server sockets
		self.__family = 0
		self.__listen = None
		self._quick   = None

		# Add this server to servers list
		with server_lock:
			server_list.append(self)

	# Generate new client id
	def __newcid(self) -> int:
		ncid = 0
		while True:
			ncid = self.__ncid
			self.__ncid += 1
			if ncid not in self.__cidtbl:
				break
		return ncid

	# Start server
	def __start(self, host: str, port: int, sslopt: dict) -> None:
		family = socket.AF_INET if host.find(':') < 0 else socket.AF_INET6
		addr   = (host, port)

		self.__listen = sockopt.create(family, 'tcp', server = True)
		self.__listen.bind(addr)
		self.__listen.listen(VSOA_SERVER_BACKLOG)

		self._quick = sockopt.create(family, 'udp', nonblock = False)
		self._quick.bind(addr)

		self.__family = family
		self.__addr   = addr

		if sslopt and ('cert' in sslopt) and ('key' in sslopt):
			raise Exception('SSL support for furture')

	# Server accept new connect
	def __accept(self) -> tuple[socket.socket, tuple[str, int]]:
		return self.__listen.accept()

	# Server handshake timer
	def _hstimer(self) -> None:
		with self._lock:
			for cli in self.__hslist:
				if cli._hsalive > SERVER_TIMER_PERIOD:
					cli._hsalive -= SERVER_TIMER_PERIOD
				else:
					cli._hsalive = 0
					cli.close()

		for stream in self._streams:
			if not stream.connected:
				if stream._alive > SERVER_TIMER_PERIOD:
					stream._alive -= SERVER_TIMER_PERIOD
				else:
					stream._alive = 0
					stream.close()

	# Client handshake success (with this server lock)
	def _hssuccess(self, cli: Client) -> None:
		if cli in self.__hslist:
			self.__hslist.remove(cli)

	# Get matched command function
	def _cmdfunc(self, url: str) -> callable:
		if url in self.__cmds:
			return self.__cmds[url]
		for cmd in self.__wccmds:
			if url.startswith(cmd) and url[len(cmd)] == '/':
				return self.__wccmds[cmd]

		defs = '/'
		if defs in self.__wccmds:
			return self.__wccmds[defs]
		else:
			return None

	# Clients
	def clients(self) -> list:
		with self._lock:
			clis = self._priocli[:]
		return clis

	# Get address
	def address(self) -> tuple[str, int]:
		if self.__addr is None:
			raise Exception('Server not started')
		return self.__addr

	# Set server password
	def passwd(self, passwd: str) -> None:
		self._passwd = passwd

	# Server publish
	def publish(self, url: str, payload: interface.Payload | dict = None, quick: bool = False) -> bool:
		if not url.startswith('/'):
			raise Exception('URL must start with /')
		if not self._running:
			return False

		with self._lock:
			self._packer.header(parser.VSOA_TYPE_PUBLISH, 0, 0, 0)
			self._packer.url(url)

			if payload and isinstance(payload, (object, dict)):
				self._packer.payload(payload)

			packet, _ = self._packer.packet()
			for cli in self._priocli:
				if cli.is_subscribed(url):
					cli._psend(packet, quick)
		return True

	# Whether the specified URL is subscribed.
	def is_subscribed(self, url: str) -> bool:
		with self._lock:
			for cli in self._priocli:
				if cli.is_subscribed(url):
					return True
		return False

	# Server command decorator
	def command(self, url: str) -> callable:
		if not url.startswith('/'):
			raise ValueError('URL must start with /')

		def decorator(func: callable) -> callable:
			if url.endswith('/'):
				self.__wccmds[url] = func
			else:
				self.__cmds[url] = func
			return func

		return decorator

	# Set server send timout
	def sendtimeout(self, timeout: float) -> None:
		with self._lock:
			for cli in self._priocli:
				cli.sendtimeout(timeout)
			self._sendto = timeout

	# Create server stream
	def create_stream(self, onlink: callable, ondata: callable, timeout: float = float(SERVER_DEF_HANDSHAKE_TIMEOUT / 1000)) -> Stream:
		if not self._running:
			raise Exception('Server not run')
		if not callable(onlink):
			onlink = lambda s, l: None

		return Stream(self, self.__family, self.__addr[0], onlink, ondata, timeout)

	# Server event loop
	def run(self, host: str, port: int, sslopt: dict = None) -> None:
		self.__start(host, port, sslopt)
		self._running = True

		while True:
			rlist = [ self._quick, self.__listen, self._strevt[0] ]
			for cli in self._priocli:
				rlist.append(cli._sock)

			with self._lock:
				for stream in self._streams:
					sock = stream._sock()
					if sock:
						rlist.append(stream._sock())

			elist, _, _ = select.select(rlist, [], [])
			if self._quick in elist:
				buf = self._quick.recv(parser.VSOA_MAX_QPACKET_LENGTH, sockopt.DWT)
				if buf:
					try:
						header, url, param, data = parser.Unpacker.pinput(buf, raw = self.__raw)
					except:
						pass
					else:
						if header.type == parser.VSOA_TYPE_DATAGRAM:
							cid = header.seqno
							if cid in self.__cidtbl:
								cli = self.__cidtbl[cid]
								cli._pinput(header, url, param, data, True)

			if self.__listen in elist:
				sock, addr = self.__accept()
				if sock:
					cid = self.__newcid()
					cli = Client(sock, self, addr[0], cid, self.__raw)
					cli.sendtimeout(self._sendto)
					cli.authed = cli._active = False

					with self._lock:
						self.__cidtbl[cid] = cli
						self._priocli.append(cli)
						if cli._active:
							self.__hslist.append(cli)

			for cli in self._priocli:
				if cli._sock in elist:
					try:
						buf = cli._sock.recv(parser.VSOA_MAX_PACKET_LENGTH, sockopt.DWT)
					except:
						buf = None

					if buf:
						if not cli._precv(buf):
							buf = None

					if not buf:
						sockopt.linger(cli._sock, 0)
						cli._finish()

						if cli._onconn:
							cli._onconn = False
							self.onclient(cli, False)

						with self._lock:
							self._priocli.remove(cli)
							del self.__cidtbl[cli.id]
							if cli in self.__hslist:
								self.__hslist.remove(cli)

			for stream in self._streams:
				sock = stream._sock()
				if sock in elist:
					stream._event(sock)

			if self._strevt[0] in elist:
				sockopt.event_read(self._strevt[0])

# Global mutex
server_lock = threading.Lock()

# All servers
server_list : list[Server] = []

# Server timer
def __server_timer() -> None:
	period = float(SERVER_TIMER_PERIOD) / 1000

	while True:
		time.sleep(period)

		with server_lock:
			for server in server_list:
				server._hstimer()

# Server timer thread
server_thread = threading.Thread(name = 'py_vsoa_srvtmr', target = __server_timer, daemon = True)
server_thread.start()

# Exports
__all__ = [ 'Server' ]

# Information
__doc__ = 'VSOA server module, provide `Server` class.'

# end
