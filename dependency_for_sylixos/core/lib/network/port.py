import time

from core.lib.common import Context, SystemConstant, LOGGER
from .sky_server import sky_request
from .utils import merge_address
from .api import NetworkAPIPath, NetworkAPIMethod



class PortInfo:

    @staticmethod
    def get_component_port(component_name: str) -> int:
        ports_dict = PortInfo.get_all_ports(component_name)
        ports_list = list(ports_dict.values())
        if ports_list:
            return ports_list[0]
        assert None, f"Component '{component_name}' does not exist."

    @staticmethod
    def get_all_ports(keyword: str) -> dict:
        backend_ip = str(Context.get_parameter('BACKEND_IP'))
        backend_port = str(Context.get_parameter('BACKEND_PORT'))
        remote_api_url = merge_address(ip=backend_ip,
                                        port=backend_port,
                                        path=NetworkAPIPath.BACKEND_PORT_INFO)
        
        ports_dict = {}
        
        max_retries = 10
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = sky_request(
                    url=remote_api_url,
                    method=NetworkAPIMethod.BACKEND_PORT_INFO,
                    data={'keyword': keyword}
                )
                response_data = response.json()
                
                # 检查返回值是否有效
                if not response_data:
                    LOGGER.warning("Empty response from remote API.")
                elif isinstance(response_data, dict):
                    LOGGER.info(f"Get port info from backend: {response_data}")
                    ports_dict = response_data['ports_dict']
                    
                    break
                else:
                    LOGGER.warning(f"Remote API returned non-success status or invalid data")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
                
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)       
        
        return ports_dict

    @staticmethod
    def get_service_ports_dict() -> dict:
        component_name = SystemConstant.PROCESSOR.value
        ports_dict = PortInfo.get_all_ports(component_name)
        component_ports_dict = {}
        for svc_name in ports_dict:
            # get sub service name
            des_name = '-'.join(svc_name.split('-')[1:-1])
            component_ports_dict[des_name] = ports_dict[svc_name]

        return component_ports_dict

    @staticmethod
    def get_service_port(service_name: str) -> int:
        return PortInfo.get_service_ports_dict().get(service_name)
