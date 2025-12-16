from ast import parse
import time
import json
import threading
import os

from .processor import Processor

from core.lib.estimation import Timer
from core.lib.content import Task
from core.lib.common import LOGGER, Context, convert_ndarray_to_list
from core.lib.common import ClassFactory, ClassType
from vsoa.interface import Payload
from vsoa.client import Client
import vsoa.parser as parser
import vsoa


@ClassFactory.register(ClassType.PROCESSOR, alias='detector_processor')
class DetectorProcessor(Processor):
    def __init__(self):
        super().__init__()

        self.frame_size = None

        # === VSOA Client 初始化 ===
        self.SERVER_NAME = 'ecs_yolo_server'
        self.RPC_URL = '/yolo/input'
        self.SUB_URL = '/yolo/results'

        self.client = Client()

        # 用于同步等待结果
        self.received_results = {}
        self.results_event = threading.Event()
        self.received_count = 0
        self.total_frames = 0

        # 设置回调
        self.client.onconnect = self.onconnect
        self.client.onmessage = self.onmessage
        self.client.onreply = self.onreply

        # 启动客户端连接（非阻塞）
        self.client_thread = threading.Thread(target=self._run_client, daemon=True)
        self.client_thread.start()

    def _run_client(self):
        """运行 VSOA 客户端事件循环（持续重试直到连接成功）"""
        while True:
            err = self.client.connect(f'vsoa://{self.SERVER_NAME}')
            if err:
                LOGGER.error(f'Connect error: {err}. Retrying...')
                time.sleep(1)  # 等待一段时间后重试，避免频繁重连
            else:
                LOGGER.info('Connected successfully. Starting client loop.')
                self.client.run()
                break

    def onconnect(self, client: Client, conn: bool, info: str | dict | list):
        LOGGER.info(f"Connected to {info}, subscribing to {self.SUB_URL}")
        if not client.subscribe(self.SUB_URL):
            LOGGER.error("Failed to subscribe to results")

    def onmessage(self, client: Client, url: str, payload: vsoa.Payload, quick: bool):
        try:
            if isinstance(payload.data, (bytes, bytearray)):
                try:
                    json_str = payload.data.decode('utf-8')
                except UnicodeDecodeError as e:
                    LOGGER.error(f"Failed to decode payload as UTF-8: {e}")
                    return
            elif isinstance(payload.data, str):
                json_str = payload.data
            else:
                LOGGER.error(f"Unexpected payload.data type: {type(payload.data)}")
                return

            if not json_str.strip():
                LOGGER.error("Received empty JSON string")
                return

            data = json.loads(json_str)
            frame_id = data.get('frame_id')
            if frame_id is not None:
                self.received_results[frame_id] = data
                self.received_count += 1
                # 如果收到预期帧数，触发事件
                if self.received_count >= self.total_frames:
                    self.results_event.set()
        except json.JSONDecodeError as e:
            LOGGER.error(f"Invalid JSON received: '{json_str[:100]}...', error: {e}")
        except Exception as e:
            LOGGER.error(f"Unexpected error parsing YOLO result: {e}")

    def onreply(self, client: Client, header: vsoa.Header, payload: vsoa.Payload):
        if header is None or payload is None:
            return
        if header.status != vsoa.parser.VSOA_STATUS_SUCCESS:
            LOGGER.error(f'Command {self.RPC_URL} error: {header.status}')
            self.results_event.set()  # 触发错误退出
        else:
            LOGGER.info(f'Command {self.RPC_URL} reply: {payload.param.decode()}')
            
    def __call__(self, task: Task):

        data_file_path = os.path.join("/apps", task.get_file_path())

        # 调用ecs_yolo_iamge, 可能需要从meta_data中知道有几帧，然后subsribe后接收到对应数量的帧的结果，并把结果转换回现在的格式再返回

        # 清空上次结果
        self.received_results = {}
        self.received_count = 0
        self.results_event.clear()

        # 获取总帧数
        meta_data = task.get_metadata()
        self.total_frames = meta_data['buffer_size']

        # 构造请求数据
        data_payload = {
            'path': data_file_path
            # , 'class_filter_arr': [2]
            # , 'nms_score_threshold': 0.3
        }
        data_payload = parser.json.dumps(data_payload).encode()

        param_payload = {
            'request_time': int(time.time()),
            'url': self.RPC_URL,
            'method': 1,  # set
            'server_name': self.SERVER_NAME,
            'data_len': len(data_payload),
            'token': None,
            'span': None
        }
        param_payload = parser.json.dumps(param_payload).encode()

        payload = Payload(param=param_payload, data=data_payload)
        ret = self.client.call(self.RPC_URL, 'set', payload, self.onreply)
        if not ret:
            LOGGER.error(f"Failed to call {self.RPC_URL}")
            return None

        # 等待结果
        TIMEOUT = 5
        self.results_event.wait(timeout=TIMEOUT)

        # 整理结果 
        sorted_results = [self.received_results[i] for i in sorted(self.received_results.keys())]
        result = []
        for item in sorted_results:
            frame_bboxes = []
            for obj in item.get('objects', []):
                bbox = obj['bbox']  # [x1, y1, x2, y2]
                frame_bboxes.append(bbox)
            result.append(frame_bboxes)

        # 如果未收到任何结果，返回空
        if len(result) == 0:
            LOGGER.critical('ERROR: image list length is 0')
            LOGGER.critical(f'Source: {task.get_source_id()}, Task: {task.get_task_id()}')
            LOGGER.critical(f'file_path: {data_file_path}')
            return None

        task = self.get_scenario(result, task)
        task.set_current_content(result)

        return task

