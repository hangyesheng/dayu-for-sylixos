import threading

from core.lib.network import SkyHTTPServer, sky_request, SkyBackgroundTasks
from core.lib.common import Context, SystemConstant
from core.lib.common import LOGGER, FileOps
from core.lib.network import NodeInfo, PortInfo, merge_address, NetworkAPIMethod, NetworkAPIPath
from core.lib.content import Task
from core.lib.estimation import TimeEstimator


class ProcessorServer:
    def __init__(self):
        self.app = SkyHTTPServer()
        self.app.add_route(
            path=NetworkAPIPath.PROCESSOR_PROCESS,
            method=NetworkAPIMethod.PROCESSOR_PROCESS,
            handler=self.process_service
        )
        self.app.add_route(
            path=NetworkAPIPath.PROCESSOR_PROCESS_RETURN,
            method=NetworkAPIMethod.PROCESSOR_PROCESS_RETURN,
            handler=self.process_return_service
        )
        self.app.add_route(
            path=NetworkAPIPath.PROCESSOR_QUEUE_LENGTH,
            method=NetworkAPIMethod.PROCESSOR_QUEUE_LENGTH,
            handler=self.query_queue_length
        )

        self.processor = Context.get_algorithm('PROCESSOR')

        self.task_queue = Context.get_algorithm('PRO_QUEUE')

        self.local_device = NodeInfo.get_local_device()
        self.processor_port = Context.get_parameter('GUNICORN_PORT')
        self.controller_port = PortInfo.get_component_port(SystemConstant.CONTROLLER.value)
        self.controller_address = merge_address(NodeInfo.hostname2ip(self.local_device),
                                                port=self.controller_port,
                                                path=NetworkAPIPath.CONTROLLER_RETURN)

        threading.Thread(target=self.loop_process).start()

    async def process_service(self, request, backtask: SkyBackgroundTasks,):
        """
        修改方案:file和form直接解析，backtask可以正常使用
        """
        file_list, data_dict = self.app.parse_data_files_from_request(request=request)
        file = file_list[0]
        file_data = await file.read()
        data = data_dict['data']
        
        cur_task = Task.deserialize(data)

        backtask.add_task(self.process_service_background, data, file_data)
        LOGGER.debug(f'[Monitor Task] (Process Request) '
                     f'Source: {cur_task.get_source_id()} / Task: {cur_task.get_task_id()} ')

    def process_service_background(self, data, file_data):
        cur_task = Task.deserialize(data)
        FileOps.save_data_file(cur_task, file_data)
        self.task_queue.put(cur_task)
        LOGGER.debug(f'[Task Queue] Queue Size (receive request): {self.task_queue.size()}')
        LOGGER.debug(f'[Monitor Task] (Process Request Background) '
                     f'Source: {cur_task.get_source_id()} / Task: {cur_task.get_task_id()} ')

    async def process_return_service(self,request):
        file_list, data_dict = self.app.parse_data_files_from_request(request=request)
        file = file_list[0]
        file_data = await file.read()
        data = data_dict['data']
        
        cur_task = Task.deserialize(data)

        LOGGER.info(f'[Process Return Background] Process task: source {cur_task.get_source_id()}  / '
                    f'task {cur_task.get_task_id()}')
        FileOps.save_data_file(cur_task, file_data)

        new_task = self.processor(cur_task)
        LOGGER.debug(f'[Processor Return completed] content length: {len(new_task.get_current_content())}')
        FileOps.remove_data_file(cur_task)
        if new_task:
            return new_task.serialize()

    async def query_queue_length(self):
        return self.task_queue.size()

    def loop_process(self):
        LOGGER.info('Start processing loop..')
        while True:
            if self.task_queue.empty():
                continue
            task = self.task_queue.get()
            if not task:
                continue
            LOGGER.debug(f'[Task Queue] Queue Size (loop): {self.task_queue.size()}')

            try:
                new_task = self.process_task_service(task)
            except Exception as e:
                LOGGER.critical("[Processor Error] Processor encountered error when processing data.")
                LOGGER.exception(e)
                continue

            if new_task:
                self.send_result_back_to_controller(new_task)
            FileOps.remove_data_file(task)

    def process_task_service(self, task: Task):
        LOGGER.debug(f'[Monitor Task] (Process start) Source: {task.get_source_id()} / Task: {task.get_task_id()} ')

        TimeEstimator.record_dag_ts(task, is_end=False, sub_tag='real_execute')
        new_task = self.processor(task)
        duration = TimeEstimator.record_dag_ts(new_task, is_end=True, sub_tag='real_execute')
        new_task.save_real_execute_time(duration)

        LOGGER.debug(f'[Monitor Task] (Process end) Source: {task.get_source_id()} / Task: {task.get_task_id()} ')
        LOGGER.info(f'[Process Task] Source: {task.get_source_id()} / Task: {task.get_task_id()} Duration: {duration} ')

        return new_task

    def send_result_back_to_controller(self, task):
        sky_request(method=NetworkAPIMethod.CONTROLLER_RETURN, url=self.controller_address,
                    data={'data': task.serialize()})
