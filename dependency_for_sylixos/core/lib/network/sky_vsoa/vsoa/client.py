#
# Copyright (c) 2024 ACOAUTO Team.
# All rights reserved.
#
# Detailed license information can be found in the LICENSE file.
#
# File: client.py Vehicle SOA client.
#
# Author: Han.hui <hanhui@acoinfo.com>
#

import core.lib.network.sky_vsoa.vsoa.parser as parser
import core.lib.network.sky_vsoa.vsoa.sockopt as sockopt
import core.lib.network.sky_vsoa.vsoa.position as position
import core.lib.network.sky_vsoa.vsoa.interface as interface
import os, time, struct, threading, socket, select, errno, ipaddress, urllib.parse
from datetime import datetime

# Client default timeout (s)
CLIENT_DEF_TIMEOUT = 60.0

# Client default connect timeout (s)
CLIENT_DEF_CONN_TIMEOUT = 10.0

# Client default send timeout (ms)
CLIENT_DEF_SEND_TIMEOUT = 500

# Client timer period (ms)
CLIENT_TIMER_PERIOD = 100

# Client robot max ping lost count
CLIENT_AUTO_MAX_PING_LOST = 3

# Client max pending
CLIENT_MAX_PENDING = 0xffff
CLIENT_MAX_POFFSET = 16

# All thread fetch event lock
event_lock = threading.Lock()

# All thread fetch event pool
event_pool : dict[int, threading.Event] = {}

# Thread resource recycle
def resource_recycle() -> None:
	with event_lock:
		invals = []
		idents = [alive.ident for alive in threading.enumerate()]

		for ident in event_pool:
			if ident not in idents:
				invals.append(ident)

		for ident in invals:
			del event_pool[ident]

# Client lookup server address
def lookup(url: str) -> tuple[tuple[str, int], str]:
	inval = ((None, None), None)
	ourl  = urllib.parse.urlparse(url)
	if not ourl.hostname:
		return inval
	if not ourl.scheme and ourl.scheme.lower() != 'sky_vsoa':
		return inval

	hostname = ourl.hostname
	if hostname.lower() == 'localhost':
		hostname = '127.0.0.1'

	try:
		ipaddress.ip_address(hostname)
	except:
		is_ip = False
	else:
		is_ip = True

	if is_ip:
		if not ourl.port:
			return inval
		else:
			return ((hostname, ourl.port), ourl.path)

	server = position.lookup(hostname)
	if server:
		return (server, ourl.path)
	else:
		return inval

# Client Stream
class Stream:
	def __init__(self, client: object, family: int, server: tuple[str, int], onlink: callable, ondata: callable, timeout: float) -> None:
		self.onlink = onlink
		self.ondata = ondata
		self._alive = int(timeout * 1000)

		# Create socket
		self._sock = sockopt.create(family, 'tcp', server = False)
		self._conn = True
		self.__cli = client

		ret = self._sock.connect_ex(server)
		if ret and ret != errno.EINPROGRESS and ret != errno.EWOULDBLOCK:
			raise Exception(f'Can not connect to server stream: {os.strerror(ret)} errno: {ret}')

		with client._lock:
			client._streams.append(self)
			client._eventemit()

	# Stream remove
	def __remove(self) -> None:
		with self.__cli._lock:
			self._sock.close()
			self._sock = None

			if self in self.__cli._streams:
				self.__cli._streams.remove(self)

		if callable(self.onlink):
			self.onlink(self, False)

	# Stream event
	def _event(self, conn: bool) -> None:
		if conn:
			if self._conn:
				self._conn = False
				if self._sock:
					self._sock.setblocking(True)
					if callable(self.onlink):
						self.onlink(self, True)
			return

		if self._sock:
			try:
				data = self._sock.recv(parser.VSOA_MAX_PACKET_LENGTH, sockopt.DWT)
			except:
				data = None

			if data:
				if callable(self.ondata):
					self.ondata(self, data)
			else:
				self.__remove()

	@property
	def connected(self) -> bool:
		return True if self._sock and not self._conn else False

	# Close stream
	def close(self) -> None:
		if self._sock:
			if self._conn:
				self.__remove()
			else:
				sockopt.tcpshutdown(self._sock)

	# Send data
	def send(self, data: bytearray | bytes) -> int:
		if self._sock == None:
			raise Exception('Stream closed')

		return sockopt.tcpsend(self._sock, data, len(data))

	# Set client keepalive
	def keepalive(self, idle: int) -> None:
		if self._sock:
			sockopt.keepalive(self._sock, int(idle))

	# Set send timeout
	def sendtimeout(self, timeout: float) -> None:
		if self._sock == None:
			raise Exception('Client not connected')

		self._sock.settimeout(timeout)

# Pending
class Pending:
	FTYPE_MSG = 0
	FTYPE_RPC = 1
	FTYPE_RES = 2

	def __init__(self, alive: int, seqno: int, callback: callable, ftype: int) -> None:
		self.alive    = alive
		self.seqno    = seqno
		self.callback = callback
		self.ftype    = ftype

	# Timer
	def timer(self, period: int) -> bool:
		if self.alive > period:
			self.alive -= period
			return False
		else:
			self.alive = 0
			return True

	# Timeout
	def timeout(self, cli, onlyrpc: bool = False) -> None:
		if callable(self.callback):
			if self.ftype == Pending.FTYPE_RPC:
				self.callback(cli, None, None)
			elif not onlyrpc:
				self.callback(cli, False)

# Client auto robot status and parameter
class ClientAuto:
	def __init__(self, keepalive: float) -> None:
		self.clean()
		self.keepalive = float(keepalive)
		self.turbo     = 0

	# Clean
	def clean(self) -> None:
		self.ping_lost  = 0
		self.last_ping  = None
		self.last_turbo = None

# Client class
class Client:
	# Client sub-class
	Stream = Stream

	# Client errors
	CONNECT_OK = 0
	CONNECT_ERROR = 1
	SERVER_NOT_FOUND = 2
	SERVER_NO_RESPONDING = 3
	INVALID_RESPONDING = 4
	INVALID_PASSWD = 5

	def __init__(self, raw: bool = False) -> None:
		self.__info     = None
		self.__server   = None
		self.__family   = 0
		self.__pendings : list[Pending] = []
		self.__rpc_pcnt = 0

		# Parser
		self.__packer   = parser.Packer()
		self.__unpacker = parser.Unpacker(raw = raw)

		# Client ID
		self.__cid      = 0
		self.__cidvalid = False

		# Sequence number
		self.__seqno    = 0
		self.__seqno_nq = 0

		# Sockets and status
		self.__sock      = None
		self.__quick     = None
		self.__event     = sockopt.pair()
		self.__connected = False
		self.__sendto    = float(CLIENT_DEF_SEND_TIMEOUT) / 1000

		# Event runner
		self.__runthread = None
		self.__tquit_req = False
		self.__robotauto : ClientAuto = None

		# Lock and streams
		self._lock    = threading.Lock()
		self._streams : list[Stream] = []

		# Hooks
		self.onconnect = lambda cli, con, serinfo: None
		self.onmessage = lambda cli, url, payload, quick: None
		self.ondata    = lambda cli, url, payload, quick: None

		# Add this server to servers list
		with client_lock:
			client_list.append(self)

	# Emit a event
	def _eventemit(self) -> None:
		if self.__event[1]:
			sockopt.event_emit(self.__event[1])

	# Pending timer
	def _ptimer(self) -> None:
		emit = False

		with self._lock:
			for pending in self.__pendings:
				if pending.timer(CLIENT_TIMER_PERIOD):
					emit = True

			for stream in self._streams:
				if stream._conn:
					if stream._alive > CLIENT_TIMER_PERIOD:
						stream._alive -= CLIENT_TIMER_PERIOD
					else:
						stream._alive = 0
						stream.close()

		if emit:
			sockopt.event_emit(self.__event[1])

	# Pending all timeout
	def __ptimeout(self) -> None:
		with self._lock:
			pendings = self.__pendings
			self.__pendings = []
			self.__rpc_pcnt = 0

		for pending in pendings:
			pending.timeout(self, True)

	# Send packet
	def __psend(self, quick: bool) -> bool:
		total = 0
		packet, plen = self.__packer.packet()
		try:
			if quick:
				if self.__cidvalid:
					self.__quick.send(packet, sockopt.NO_SIG)
				total = plen
			else:
				total = sockopt.tcpsend(self.__sock, packet, plen)
		except:
			return False
		else:
			return True if total == plen else False

	# Client start
	def __start(self, url: str, sslopt: dict = None) -> tuple[str, int]:
		server, _ = lookup(url)
		if not server[0]:
			return server

		if self.__sock:
			self.__sock.close()
		if self.__quick:
			self.__quick.close()

		family = socket.AF_INET if server[0].find(':') < 0 else socket.AF_INET6
		self.__sock  = sockopt.create(family, 'tcp', nonblock = True)
		self.__quick = sockopt.create(family, 'udp', nonblock = False)

		if sslopt and ('cert' in sslopt) and ('key' in sslopt):
			raise Exception('SSL support for furture')

		self.__family = family
		return server

	# On connect
	def __onconnect(self, header: interface.Header, param: dict, data: bytes | bytearray, host: str) -> int:
		if not (header.flags & parser.VSOA_FLAG_REPLY):
			return Client.INVALID_RESPONDING
		if header.type != parser.VSOA_TYPE_SERVINFO or header.status:
			return Client.INVALID_RESPONDING

		self.__info = param
		if data:
			if len(data) >= 4:
				self.__cid,     = struct.unpack('>I', data)
				self.__cidvalid = True
				if len(data) >= 6:
					port, = struct.unpack_from('>H', data, 4)
					self.__quick.connect((host, port))

		self.__server = host
		return Client.CONNECT_OK

	# Client is connected
	@property
	def connected(self) -> bool:
		return self.__connected

	# Client close, This object is no longer allowed to be used
	def close(self) -> None:
		runner = self.__runthread
		if runner and runner.ident != threading.get_ident():
			self.__tquit_req = True
			sockopt.event_emit(self.__event[1])
			runner.join()
		else:
			self.__tquit_req = True

		self.__connected = False
		self.__ptimeout()

		for stream in self._streams:
			stream.close()

		with client_lock:
			if self in client_list:
				client_list.remove(self)

		if self.__sock:
			self.__sock.close()
			self.__sock = None
		if self.__quick:
			self.__quick.close()
			self.__quick = None

		if self.__event:
			self.__event[0].close()
			self.__event[1].close()
			self.__event = []

	# Client connect
	def connect(self, url: str, passwd: str = '', timeout: float = CLIENT_DEF_CONN_TIMEOUT, sslopt: dict = None) -> int:
		if self.__tquit_req:
			return Client.CONNECT_ERROR

		server = self.__start(url, sslopt = sslopt)
		if not server[0]:
			return Client.SERVER_NOT_FOUND

		self.__quick.connect(server)
		_, tunid = self.__quick.getsockname()

		ret = self.__sock.connect_ex(server)
		if ret and ret != errno.EINPROGRESS and ret != errno.EWOULDBLOCK:
			return Client.CONNECT_ERROR

		_, elist, _ = select.select([], [ self.__sock ], [], timeout)
		if self.__sock not in elist:
			return Client.CONNECT_ERROR

		packer = self.__packer
		with self._lock:

			packer.header(parser.VSOA_TYPE_SERVINFO, 0, 0, 0)
			packer.tunid(tunid)

			if passwd and type(passwd) == str:
				packer.payload(None, param = { 'passwd': passwd })
			if not self.__psend(False):
				return Client.CONNECT_ERROR

		elist, _, _ = select.select([ self.__sock ], [], [], timeout)

		if self.__sock not in elist:
			return Client.SERVER_NO_RESPONDING

		try:
			hsbuf = self.__sock.recv(parser.VSOA_MAX_PACKET_LENGTH, sockopt.DWT)
		except:
			hsbuf = None
		if not hsbuf:
			return Client.SERVER_NO_RESPONDING

		try:
			header, _, param, data = parser.Unpacker.pinput(hsbuf)
		except:
			return Client.INVALID_RESPONDING

		ret = self.__onconnect(header, param, data, server[0])
		if ret == Client.CONNECT_OK:
			self.__connected = True
			self.__sock.settimeout(self.__sendto)
			self.onconnect(self, True, self.__info)

		return ret

	# Client disconnect
	def disconnect(self) -> None:
		if not self.__connected:
			return False

		with self._lock:
			if self.__sock:
				sockopt.tcpshutdown(self.__sock)

		self.__ptimeout()

	# Set send timeout
	def sendtimeout(self, timeout: float) -> None:
		self.__sock.settimeout(timeout)

	# Set socket linger
	def linger(self, time: int = 0) -> bool:
		if self.__connected:
			sockopt.linger(self.__sock, time)
			return True
		else:
			return False

	# Prepare a non-queued seqno
	def __prepare_seqno(self, nonq: bool = False) -> int:
		with self._lock:
			if nonq:
				if self.__seqno_nq == 0:
					seqno = 1
					self.__seqno_nq = 2
				else:
					seqno = self.__seqno_nq
					self.__seqno_nq += 1
					if self.__seqno_nq >= 0x10000:
						self.__seqno_nq = 0
				seqno <<= CLIENT_MAX_POFFSET

			else:
				for _ in range(CLIENT_MAX_PENDING):
					seqno = self.__seqno
					self.__seqno = (seqno + 1) & CLIENT_MAX_PENDING
					for pending in self.__pendings:
						if pending.seqno == seqno:
							break
					else:
						break
		return seqno

	# Prepare a pending
	def __prepare_pending(self, callback: callable, ftype: int, timeout: float) -> Pending:
		alive = int(timeout * 1000)
		seqno = self.__prepare_seqno()
		return Pending(alive, seqno, callback, ftype)

	# Request
	def __request(self, type: int, flags: int, url: str, payload: interface.Payload | dict, callback: callable, timeout: float) -> bool:
		if not self.__connected:
			return False

		if callable(callback):
			if len(self.__pendings) >= CLIENT_MAX_PENDING:
				return False

			ftype   = Pending.FTYPE_RPC if type == parser.VSOA_TYPE_RPC else Pending.FTYPE_RES
			pending = self.__prepare_pending(callback, ftype, timeout)
			seqno   = pending.seqno
		else:
			pending = None
			seqno   = self.__prepare_seqno(True)

		packer = self.__packer
		with self._lock:
			packer.header(type, flags, 0, seqno)

			if url:
				packer.url(url)
			if payload and isinstance(payload, (object, dict)):
				packer.payload(payload)

			self.__psend(False)
			if pending:
				self.__pendings.append(pending)
				if pending.ftype == Pending.FTYPE_RPC:
					self.__rpc_pcnt += 1

		return True

	# RPC call
	def call(self, url: str, method: str | int = 0, payload: interface.Payload | dict = None, callback: callable = None, timeout: float = CLIENT_DEF_TIMEOUT) -> bool:
		if not url or type(url) != str:
			raise TypeError('URL invalid')
		if not url.startswith('/'):
			raise ValueError('URL must starts with: /')
		if not self.__connected:
			return False

		if type(method) == str:
			flags = parser.VSOA_FLAG_SET if method.lower() == 'set' else 0
		else:
			flags = parser.VSOA_FLAG_SET if method else 0

		return self.__request(parser.VSOA_TYPE_RPC, flags, url, payload, callback, timeout)

	# RPC fetch (RPC synchronous calls)
	def fetch(self, url: str, method: str | int = 0, payload: interface.Payload | dict = None, timeout: float = CLIENT_DEF_TIMEOUT) -> tuple[interface.Header, interface.Payload, int]:
		if not url or type(url) != str:
			raise TypeError('URL invalid')
		if not url.startswith('/'):
			raise ValueError('URL must starts with: /')
		if self.__runthread and self.__runthread.ident == threading.get_ident():
			raise RuntimeError('This function is not allowed to be executed in the client event loop thread')
		if not self.__connected:
			return (None, None, Client.CONNECT_ERROR)

		if type(method) == str:
			flags = parser.VSOA_FLAG_SET if method.lower() == 'set' else 0
		else:
			flags = parser.VSOA_FLAG_SET if method else 0

		ident = threading.get_ident()
		if ident in event_pool:
			event = event_pool[ident]
		else:
			event = threading.Event()
			with event_lock:
				event_pool[ident] = event

		r_h = r_p = None
		def wakeup(_, h: interface.Header, p: interface.Payload) -> None:
			nonlocal r_h, r_p
			r_h = h
			r_p = p
			event.set()

		event.clear()
		ret = self.__request(parser.VSOA_TYPE_RPC, flags, url, payload, wakeup, timeout)
		if not ret:
			return (None, None, Client.CONNECT_ERROR)

		event.wait()
		if r_h:
			return (r_h, r_p, Client.CONNECT_OK)
		else:
			return (None, None, Client.SERVER_NO_RESPONDING)

	# Ping request
	def ping(self, callback: callable = None, timeout: float = CLIENT_DEF_TIMEOUT) -> bool:
		if not self.__connected:
			return False

		return self.__request(parser.VSOA_TYPE_PINGECHO if callable(callback) else parser.VSOA_TYPE_NOOP, \
					0, None, None, callback, timeout)

	# Subscribe URLs
	def subscribe(self, url: str | list[str], callback: callable = None, timeout: float = CLIENT_DEF_TIMEOUT) -> bool:
		if not self.__connected:
			return False

		if type(url) == str:
			payload = None
		elif type(url) == list:
			payload = { 'param': url }
			url     = None
		else:
			raise TypeError('URL invalid')

		return self.__request(parser.VSOA_TYPE_SUBSCRIBE, 0, url, payload, callback, timeout)

	# Unsubscribe URLs
	def unsubscribe(self, url: str | list[str], callback: callable = None, timeout: float = CLIENT_DEF_TIMEOUT) -> bool:
		if not self.__connected:
			return False

		if type(url) == str:
			payload = None
		elif type(url) == list:
			payload = { 'param': url }
			url     = None
		else:
			raise TypeError('URL invalid')

		return self.__request(parser.VSOA_TYPE_UNSUBSCRIBE, 0, url, payload, callback, timeout)

	# Send datagram
	def datagram(self, url: str, payload: interface.Payload | dict = None, quick: bool = False) -> bool:
		if not url or type(url) != str:
			raise TypeError('URL invalid')
		if not url.startswith('/'):
			raise ValueError('URL must starts with: /')
		if not self.__connected:
			return False
		if quick and not self.__cidvalid:
			return False

		packer = self.__packer
		with self._lock:
			packer.header(parser.VSOA_TYPE_DATAGRAM, 0, 0, self.__cid if quick else 0)

			if url:
				packer.url(url)
			if payload and isinstance(payload, (object, dict)):
				packer.payload(payload)

			self.__psend(quick)

		return True

	# Get pendings
	@property
	def pendings(self) -> int:
		return len(self.__pendings)

	# Create client stream
	def create_stream(self, tunid: int, onlink: callable, ondata: callable, timeout: float = CLIENT_DEF_CONN_TIMEOUT) -> Stream:
		if not self.__connected:
			raise Exception('No connection')
		if tunid < 1 or tunid > 65535:
			raise ValueError('Invalid tunid')
		if not callable(onlink):
			onlink = lambda s, l: None

		return Stream(self, self.__family, (self.__server, tunid), onlink, ondata, timeout)

	# Packet input
	def __pinput(self, header: interface.Header, url: str, param: dict | list | bytes, data: bytes, quick: bool = False) -> None:
		ptype   = header.type
		payload = interface.Payload(param, data)

		if ptype == parser.VSOA_TYPE_DATAGRAM:
			self.ondata(self, url, payload, quick)
			return

		elif ptype == parser.VSOA_TYPE_PUBLISH:
			self.onmessage(self, url, payload, quick)
			return

		elif ptype == parser.VSOA_TYPE_QOSSETUP:
			sockopt.priority(self.__sock,  header.status)
			sockopt.priority(self.__quick, header.status)
			return

		elif not header.flags & parser.VSOA_FLAG_REPLY:
			return

		seqno = header.seqno
		with self._lock:
			for pending in self.__pendings:
				if pending.seqno == seqno:
					self.__pendings.remove(pending)
					if pending.ftype == Pending.FTYPE_RPC:
						self.__rpc_pcnt -= 1
					pendq = pending
					break
			else:
				pendq = None

		if pendq:
			# In order to compile with Cython, the `if ... elif ...` syntax is used here
			if  ptype == parser.VSOA_TYPE_SUBSCRIBE or \
				ptype == parser.VSOA_TYPE_UNSUBSCRIBE or \
				ptype == parser.VSOA_TYPE_PINGECHO:
				if pendq.ftype == Pending.FTYPE_RES and callable(pendq.callback):
					pendq.callback(self, header.status == 0)

			elif ptype == parser.VSOA_TYPE_RPC:
				if pendq.ftype == Pending.FTYPE_RPC and callable(pendq.callback):
					pendq.callback(self, header, payload)

	# Client event loop
	def __loop(self, funcping: callable = None, timeout: float = None) -> None:
		while self.__connected and not self.__tquit_req:
			wlist = []
			rlist = [ self.__quick, self.__sock, self.__event[0] ]

			with self._lock:
				for stream in self._streams:
					if stream._sock:
						if stream._conn:
							wlist.append(stream._sock)
						else:
							rlist.append(stream._sock)

			elist, clist, _ = select.select(rlist, wlist, [], timeout)
			if self.__quick in elist:
				buf = self.__quick.recv(parser.VSOA_MAX_QPACKET_LENGTH, sockopt.DWT)
				if buf:
					try:
						header, url, param, data = parser.Unpacker.pinput(buf, raw = self.__unpacker.raw)
					except:
						pass
					else:
						if header.type == parser.VSOA_TYPE_DATAGRAM or header.type == parser.VSOA_TYPE_PUBLISH:
							self.__pinput(header, url, param, data, quick = True)

			if self.__sock in elist:
				try:
					buf = self.__sock.recv(parser.VSOA_MAX_PACKET_LENGTH, sockopt.DWT)
				except:
					buf = None

				if buf:
					if not self.__unpacker.input(buf, self.__pinput):
						buf = None

				if not buf:
					self.__sock.close()
					self.__sock = None
					self.__quick.close()
					self.__quick = None
					self.__ptimeout()
					self.__connected = False
					self.onconnect(self, False, None)

			elif callable(funcping):
				funcping()

			for stream in self._streams:
				if stream._sock in elist:
					stream._event(False)
				elif stream._sock in clist:
					stream._event(True)

			if self.__event[0] in elist:
				sockopt.event_read(self.__event[0])

				pend_to = []
				with self._lock:
					for pending in self.__pendings:
						if pending.alive <= 0:
							self.__pendings.remove(pending)
							if pending.ftype == Pending.FTYPE_RPC:
								self.__rpc_pcnt -= 1
							pend_to.append(pending)

				for pending in pend_to:
					pending.timeout(self)

	# Client run (in current thread)
	def run(self):
		if self.__tquit_req:
			raise Exception('Client closing')

		with self._lock:
			if self.__runthread:
				raise Exception('Client already running')
			else:
				self.__runthread = threading.current_thread()

		self.__loop()
		self.__runthread = None

	# Client robot ping callback
	def __robot_ping_callback(self, _, success: bool) -> None:
		robot = self.__robotauto

		if success:
			robot.ping_lost = 0
		else:
			robot.ping_lost += 1
			if robot.ping_lost > CLIENT_AUTO_MAX_PING_LOST:
				if self.__connected:
					sockopt.linger(self.__sock, 0)
					self.disconnect()

	# Client auto keepalive and turbo ping
	def __robot_idle(self) -> None:
		now   = datetime.now()
		robot = self.__robotauto
		diff  = (now - robot.last_ping).total_seconds()
		if diff >= robot.keepalive:
			robot.last_ping = now
			self.ping(self.__robot_ping_callback, robot.keepalive)

		elif self.__rpc_pcnt > 0 and robot.turbo and diff >= robot.turbo:
			robot.last_turbo = now
			self.ping()

	# Client auto event loop
	def __robot(self, server, passwd: str, keepalive: float, \
				conn_timeout: float, reconn_delay: float, sslopt: dict) -> None:
		with self._lock:
			if self.__robotauto:
				robot = self.__robotauto
				robot.clean()
				robot.keepalive = keepalive
			else:
				robot = self.__robotauto = ClientAuto(keepalive)

		while not self.__tquit_req:
			ret = self.connect(server, passwd, conn_timeout, sslopt)
			if ret != Client.CONNECT_OK:
				if reconn_delay > 0:
					time.sleep(reconn_delay)
				continue

			robot.ping_lost = 0
			robot.last_ping = robot.last_turbo = datetime.now()

			while not self.__tquit_req:
				if not self.__connected:
					break

				if robot.turbo == 0:
					timeout = keepalive
				else:
					timeout = robot.turbo if robot.turbo < keepalive else keepalive

				self.__loop(self.__robot_idle, timeout)

			if self.__connected:
				self.disconnect()

			if reconn_delay > 0:
				time.sleep(reconn_delay)

	# Client robot loop (in new thread run)
	def robot(self, server: str, passwd: str = '', keepalive: float = 3.0, \
				conn_timeout: float = CLIENT_DEF_CONN_TIMEOUT, reconn_delay: float = 1.0, sslopt: dict = None) -> None:
		if keepalive < 0.05 or conn_timeout < 0.05:
			raise ValueError('Arguments error, `keepalive` and `conn_timeout` must >= 50ms')
		if self.__connected:
			raise Exception('Client already connected')
		if self.__tquit_req:
			raise Exception('Client closing')

		with self._lock:
			if self.__runthread:
				raise Exception('Client already running')
			else:
				args = (server, passwd, keepalive, conn_timeout, reconn_delay, sslopt)
				self.__runthread = threading.Thread(name = 'py_vsoa_robot', target = self.__robot, args = args, daemon = True)
				self.__runthread.start()

	# Cient robot ping turbo
	def robot_ping_turbo(self, turbo: float, max_cnt: int = 50) -> bool:
		if turbo > 0 and turbo < 25:
			raise ValueError('Turbo must in 0 ~ 25')

		with self._lock:
			if self.__robotauto:
				emit = True
			else:
				self.__robotauto = ClientAuto(3.0)
				emit = False

			self.__robotauto.turbo = turbo

			if emit:
				sockopt.event_emit(self.__event[1])

# Client fetch
def fetch(url: str, passwd: str = None, method: str | int = 0, \
			payload: interface.Payload | dict = None, timeout: float = CLIENT_DEF_CONN_TIMEOUT, raw: bool = False, sslopt: dict = None) -> tuple[interface.Header, interface.Payload, int]:
	r_h = r_p = None

	# RPC callback
	def callback(c: Client, h: interface.Header, p: interface.Payload) -> None:
		nonlocal r_h, r_p
		r_h = h
		r_p = p
		c.disconnect()

	# Parse URL
	server, path = lookup(url)
	if not server[0]:
		return (None, None, Client.SERVER_NOT_FOUND)
	if not path:
		path = '/'

	cli = Client(raw)
	ret = cli.connect(f'sky_vsoa://{server[0]}:{server[1]}', passwd = passwd, timeout = timeout, sslopt = sslopt)
	if ret != Client.CONNECT_OK:
		return (None, None, ret)

	cli.call(path, method, payload, callback, timeout)
	cli.run()
	cli.close()

	if r_h:
		return (r_h, r_p, Client.CONNECT_OK)
	else:
		return (None, None, Client.SERVER_NO_RESPONDING)

# Global mutex
client_lock = threading.Lock()

# All clients
client_list : list[Client] = []

# Client timer
def __client_timer() -> None:
	period = float(CLIENT_TIMER_PERIOD) / 1000

	while True:
		time.sleep(period)

		with client_lock:
			for client in client_list:
				client._ptimer()

# Client timer thread
client_thread = threading.Thread(name = 'py_vsoa_clitmr', target = __client_timer, daemon = True)
client_thread.start()

# Exports
__all__ = [ 'Client', 'fetch', 'resource_recycle', 'CLIENT_DEF_TIMEOUT' ]

# Information
__doc__ = 'VSOA client module, provide `Client` class.'

# end
