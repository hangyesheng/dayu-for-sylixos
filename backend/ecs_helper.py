import time
from datetime import datetime
import pytz

from core.lib.common import LOGGER, Context
from core.lib.network import http_request, merge_address, NetworkAPIPath, NetworkAPIMethod

class ECSHelper:
    @staticmethod
    def generate_service_name(prefix, length=8):
        import random
        import string
        
        # 定义可用的字符：大写字母、小写字母、数字
        characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
        random_suffix = ''.join(random.choices(characters, k=length))
        return f"{prefix}-{random_suffix}"

    @staticmethod
    def query_service_id_by_name(service_name):
        ecsm_host = str(Context.get_parameter('ECSM_HOST'))
        ecsm_port = str(Context.get_parameter('ECSM_PORT'))
        remote_api_url = merge_address(ip=ecsm_host, 
                                    port=ecsm_port, 
                                    path=NetworkAPIPath.BACKEND_ECSM_QUERY_SERVICE.format(service_name=service_name))   
                
        service_id = None
        
        max_retries = 10
        retry_count = 0
        while retry_count < max_retries:
            try:
                response_data = http_request(
                    url=remote_api_url,
                    method=NetworkAPIMethod.BACKEND_ECSM_QUERY_SERVICE,
                    timeout=2
                )
                
                # 检查返回值是否有效
                if not response_data:
                    LOGGER.warning("Empty response from remote API.")
                elif isinstance(response_data, dict) and response_data.get('status') == 200:
                    service_id = response_data["data"]["list"][0]["id"]
                    break
                else:
                    error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                    LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
                
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)
        
        return service_id
    
    @staticmethod
    def get_service_info(service_id_list):
        info = []
        
        for service_id in service_id_list:
            ecsm_host = str(Context.get_parameter('ECSM_HOST'))
            ecsm_port = str(Context.get_parameter('ECSM_PORT'))
            remote_api_url = merge_address(ip=ecsm_host, 
                                        port=ecsm_port, 
                                        path=NetworkAPIPath.BACKEND_ECSM_GET_SERVICE_INFO.format(service_id=service_id))   
            
            max_retries = 10
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response_data = http_request(
                        url=remote_api_url,
                        method=NetworkAPIMethod.BACKEND_ECSM_GET_SERVICE_INFO,
                        timeout=2
                    )
                    
                    # 检查返回值是否有效
                    if not response_data:
                        LOGGER.warning("Empty response from remote API.")
                    elif isinstance(response_data, dict) and response_data.get('status') == 200:
                        container_info_list = response_data["data"]["list"]
                        for container_info in container_info_list:  
                            info_dict = {'age': datetime.fromisoformat(container_info["createdTime"].replace("Z", "+00:00"))
                                    .astimezone(pytz.timezone('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'),
                                'hostname': container_info["nodeName"],
                                'ip': container_info["address"],
                                'cpu': f'{container_info["cpuUsage"]["total"]:.2f}%',
                                'memory': f'{container_info["memoryUsage"] / container_info["memoryLimit"] * 100:.2f}%',
                                'bandwidth': ''}
                            info.append(info_dict)
                            
                        break
                    else:
                        error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                        LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")
                except Exception as e:
                    LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
                    
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1)
        
        return info
    
    @staticmethod
    def check_pods_running():
        ecsm_host = str(Context.get_parameter('ECSM_HOST'))
        ecsm_port = str(Context.get_parameter('ECSM_PORT'))
        remote_api_url = merge_address(ip=ecsm_host, 
                                    port=ecsm_port, 
                                    path=NetworkAPIPath.BACKEND_ECSM_QUERY_ALL_SERVICE)   
                
        _result = False
        
        max_retries = 10
        retry_count = 0
        while retry_count < max_retries:
            try:
                response_data = http_request(
                    url=remote_api_url,
                    method=NetworkAPIMethod.BACKEND_ECSM_QUERY_ALL_SERVICE,
                    timeout=2
                )
                
                # 检查返回值是否有效
                if not response_data:
                    LOGGER.warning("Empty response from remote API.")
                elif isinstance(response_data, dict) and response_data.get('status') == 200:
                    is_all_running = True
                    for service_info in response_data["data"]["list"]:
                        if service_info["status"] != "complete":
                            is_all_running = False
                            break
                        
                    if is_all_running:
                        _result = True
                        break
                else:
                    error_msg = response_data.get('message', 'Unknown error') if isinstance(response_data, dict) else 'Invalid response format'
                    LOGGER.warning(f"Remote API returned non-success status or invalid data: {error_msg}")
            except Exception as e:
                LOGGER.warning(f"Failed to fetch or parse remote node info: {e}")
                
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)
        
        return _result