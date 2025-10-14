import time
import subprocess
import json
import sys
import asyncio
from typing import Dict, Optional, Tuple

from core.ecs_manager import ECSManagerServer
from core.lib.network import sky_request
from core.lib.network import merge_address
from core.lib.network import NetworkAPIPath, NetworkAPIMethod

server = ECSManagerServer()

async def test(image_name: str, env_dict: Dict[str, str]):
    ecs_manager_ip = "127.0.0.1"
    ecs_manager_port = 9900


    ecs_manager_install_address = merge_address(ecs_manager_ip,
                                        port=ecs_manager_port,
                                        path=NetworkAPIPath.ECS_MANAGER_INSTALL)
    install_params = {
        'image_name': image_name,
        'env_dict': env_dict,
    }
    response = sky_request(url=ecs_manager_install_address,
                method=NetworkAPIMethod.ECS_MANAGER_INSTALL,
                data={'data': json.dumps(install_params)},
                timeout=30)
    if response.status_code == 200:
        print(f"Image installed successfully, message: {response.text}")
    else:
        raise Exception(f'Install image {image_name} failed, error message: {response.text}')
    

    time.sleep(15)


    # 2. 查询镜像是否存在
    ecs_manager_exists_address = merge_address(ecs_manager_ip,
                                        port=ecs_manager_port,
                                        path=NetworkAPIPath.ECS_MANAGER_EXISTS)
    exists_params = {
        'image_name': image_name,
    }
    exists_response = sky_request(url=ecs_manager_exists_address, 
                            method=NetworkAPIMethod.ECS_MANAGER_EXISTS,
                            data={'data': json.dumps(exists_params)},
                            timeout=30)
    is_exists = exists_response.json().get('is_exists')
    
    if is_exists:
        ecs_manager_delete_address = merge_address(ecs_manager_ip,
                                                   port=ecs_manager_port,
                                                   path=NetworkAPIPath.ECS_MANAGER_DELETE)
        delete_params = {
            'image_name': image_name
        }
        response = sky_request(url=ecs_manager_delete_address, 
                    method=NetworkAPIMethod.ECS_MANAGER_DELETE,
                    data={'data': json.dumps(delete_params)},
                    timeout=30)
        if response.status_code == 200:
            print(f"Image deleted successfully, message: {response.text}")
        else:
            raise Exception(f'Delete image {image_name} failed, error message: {response.text}')
    else:
        print("镜像不存在，无法删除。")




if __name__ == "__main__":

    image_name = "generator"

    env_dict = {
        'GEN_GETTER_NAME': 'rtsp_video',
        'SOURCE_URL': 'rtsp://192.168.1.1:554/live.sdp',
        'SOURCE_TYPE': 'video',
        'SOURCE_ID': '1',
        'SOURCE_METADATA': '{}',
        'ALL_EDGE_DEVICES': '[]',
        'DAG': '{}',
    }

    asyncio.run(test(image_name, env_dict))

    

    image_name = "controller"

    env_dict = {
        'GUNICORN_PORT': '9200'
    }
    
    asyncio.run(test(image_name, env_dict))