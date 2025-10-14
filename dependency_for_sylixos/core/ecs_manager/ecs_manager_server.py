import os
import json
import subprocess
import sys
from typing import Dict, Optional, Tuple, List, Any

from core.lib.network import SkyHTTPServer, HTTPResponse
from core.lib.network import NetworkAPIPath, NetworkAPIMethod

# 镜像配置文件路径模板
CONFIG_PATH_TEMPLATE = "./{image_name}/config.json"
TAR_PATH_TEMPLATE = "/apps/images/{image_name}.tar"

def parse_from_forms(key: str, forms: List[Dict[str, Any]]) -> Any:
    # 检查是否为空
    if not forms:
        raise ValueError("未收到表单数据")

    # 在 forms 列表中查找 name == key 的项
    data_item = None
    for item in forms:
        if item.get("name") == key:
            data_item = item
            break

    if not data_item:
        raise ValueError(f"未找到名为 {key} 的表单字段")

    # 取出 value 字段, 解析为 JSON
    data_json_str = data_item['value']
    return data_json_str


class ECSManagerServer:
    def __init__(self):
        self.app = SkyHTTPServer()

        self.app.add_route(
            path=NetworkAPIPath.ECS_MANAGER_INSTALL,
            method=NetworkAPIMethod.ECS_MANAGER_INSTALL,
            handler=self.install
        )
        self.app.add_route(
            path=NetworkAPIPath.ECS_MANAGER_DELETE,
            method=NetworkAPIMethod.ECS_MANAGER_DELETE,
            handler=self.delete
        )
        self.app.add_route(
            path=NetworkAPIPath.ECS_MANAGER_EXISTS,
            method=NetworkAPIMethod.ECS_MANAGER_EXISTS,
            handler=self.exists
        )

    async def install(self, request):
        try:
            forms = self.app.parse_forms_from_request(request=request)
            data_json_str = parse_from_forms(key="data", forms=forms)
            data = json.loads(data_json_str)

            await self.load_and_start_image(image_name=data.get("image_name"), env_dict=data.get("env_dict"))
            return HTTPResponse(status_code=200)
        except Exception as e:
            return HTTPResponse(status_code=500, content=json.dumps({"message": str(e)}).encode())
        
    async def delete(self, request):
        try:
            forms = self.app.parse_forms_from_request(request=request)
            data_json_str = parse_from_forms(key="data", forms=forms)
            data = json.loads(data_json_str)

            await self.delete_image(image_name=data.get("image_name"))
            return HTTPResponse(status_code=200)
        except Exception as e:
            return HTTPResponse(status_code=500, content=json.dumps({"message": str(e)}).encode())
    
    async def exists(self, request):
        forms = self.app.parse_forms_from_request(request=request)
        data_json_str = parse_from_forms(key="data", forms=forms)
        data = json.loads(data_json_str)
        
        is_exists = await self.image_exists(image_name=data.get("image_name"))
        return HTTPResponse(content=json.dumps({
            "is_exists": is_exists
        }).encode())

    async def load_and_start_image(self, image_name: str, env_dict: Dict[str, str]):
        """
        下装镜像：
        1. 执行 ecs load xxx.tar xxx xxx
        2. 读取 xxx/config.json
        3. 根据 env_dict 更新或添加环境变量
        4. 写回 config.json
        5. 执行 ecs start xxx

        :param image_name: 镜像名称 (如 generator)
        :param env_dict: 要加入的环境变量字典
        """
        tar_file = TAR_PATH_TEMPLATE.format(image_name=image_name)

        # 检查 tar 文件是否存在
        if not os.path.exists(tar_file):
            raise ValueError(f"错误：镜像文件 {tar_file} 不存在。")

        # 步骤1: 执行 ecs load xxx.tar xxx xxx
        load_cmd = ["ecs", "load", tar_file, image_name, image_name]
        print(f"正在加载镜像: {' '.join(load_cmd)}")
        result = subprocess.run(load_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"加载镜像失败: {result.stderr}")
        print("镜像加载成功。")

        # 步骤2: 读取 config.json
        config_path = CONFIG_PATH_TEMPLATE.format(image_name=image_name)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"加载后未找到配置文件 {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            raise Exception(f"加载 config.json 失败: {e}")

        # 步骤3: 修改 env 环境变量
        # 获取 process.env 列表
        env_list = config.get("process", {}).get("env", [])
        if not isinstance(env_list, list):
            print("警告: config.json 中 env 不是列表，将初始化为空列表")
            env_list = []

        # 将现有 env 列表转为 dict 便于更新
        env_vars = {}
        for item in env_list:
            if '=' in item:
                k, v = item.split('=', 1)
                env_vars[k] = v

        # 更新或添加新的环境变量
        for k, v in env_dict.items():
            env_vars[k] = v

        # 转回列表
        new_env_list = [f"{k}={v}" for k, v in env_vars.items()]
        config["process"]["env"] = new_env_list

        # 步骤4: 写回 config.json
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"已更新 {config_path} 中的环境变量。")
        except Exception as e:
            raise Exception(f"写入 config.json 失败: {e}")

        # 步骤5: 执行 ecs start xxx
        start_cmd = ["ecs", "start", image_name]
        print(f"正在启动镜像: {' '.join(start_cmd)}")
        result = subprocess.run(start_cmd, stdout=sys.stdout, stderr=sys.stderr)
        if result.returncode != 0:
            raise Exception(f"启动镜像失败: {result.stderr}")

        print(f"镜像 {image_name} 启动成功。")


    async def delete_image(self, image_name: str):
        """
        删除镜像：
        依次执行 ecs kill xxx, ecs delete xxx, ecs unreg xxx

        :param image_name: 镜像名称
        """
        commands = [
            ["ecs", "kill", image_name],
            ["ecs", "delete", image_name],
            ["ecs", "unreg", image_name]
        ]

        for cmd in commands:
            print(f"执行: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"命令执行失败: {result.stderr}")
            else:
                print(f"执行成功: {' '.join(cmd)}")
        print(f"镜像 {image_name} 已成功删除。")


    async def image_exists(self, image_name: str) -> bool:
        """
        查询镜像是否存在（通过检查 config.json 是否存在）

        :param image_name: 镜像名称
        :return: 存在返回 True，否则 False
        """
        config_path = CONFIG_PATH_TEMPLATE.format(image_name=image_name)
        exists = os.path.exists(config_path)
        if exists:
            print(f"镜像 {image_name} 存在。")
        else:
            print(f"镜像 {image_name} 不存在。")
        return exists
