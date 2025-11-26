import abc
import threading

from .base_monitor import BaseMonitor

from core.lib.common import ClassFactory, ClassType, LOGGER

__all__ = ('BandwidthMonitor',)


@ClassFactory.register(ClassType.MON_PRAM, alias='bandwidth')
class BandwidthMonitor(BaseMonitor, abc.ABC):
    def __init__(self, system):
        super().__init__(system)
        self.name = 'bandwidth'

        self.is_server = system.is_iperf3_server

        if self.is_server:
            self.iperf3_ports = system.iperf3_ports
            self.run_iperf_server()
        else:
            self.iperf3_port = system.iperf3_port
            self.iperf3_server_ip = system.iperf3_server_ip

    def run_iperf_server(self):
        for port in self.iperf3_ports:
            threading.Thread(target=self.iperf_server, args=(port,)).start()

    @staticmethod
    def iperf_server(port):
        import iperf3
        server = iperf3.Server()
        server.port = port
        LOGGER.debug(f'[Iperf3 Server] Running iperf3 server: {server.bind_address}:{server.port}')

        while True:
            try:
                result = server.run()
            except Exception as e:
                LOGGER.exception(e)
                continue

            if result.error:
                LOGGER.warning(result.error)

    def get_parameter_value(self):
        import iperf3
        from func_timeout import func_set_timeout as timeout
        if self.is_server:
            return 0

        @timeout(2)
        def fetch_bandwidth_by_iperf3():
            result = client.run()
            return result

        client = iperf3.Client()
        client.duration = 1
        client.server_hostname = self.iperf3_server_ip
        client.port = self.iperf3_port
        client.protocol = 'tcp'

        try:
            result_info = fetch_bandwidth_by_iperf3()

            del client

            if result_info.error:
                LOGGER.warning(f'resource monitor iperf3 error: {result_info.error}')
                bandwidth_result = 0
            else:
                bandwidth_result = result_info.sent_Mbps

        except Exception as e:
            LOGGER.exception(f'[Iperf3 Error] {e}')
            bandwidth_result = 0

        return bandwidth_result
