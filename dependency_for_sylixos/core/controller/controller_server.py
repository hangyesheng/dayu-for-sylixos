from core.lib.network import SkyHTTPServer, SkyBackgroundTasks

from core.lib.network import NetworkAPIPath, NetworkAPIMethod
from core.lib.common import FileOps
from core.lib.common import Context
from core.lib.content import Task

from .controller import Controller


class ControllerServer:
    def __init__(self):
        self.controller = Controller()

        self.app = SkyHTTPServer()
        self.app.add_route(
            path=NetworkAPIPath.CONTROLLER_TASK,
            method=NetworkAPIMethod.CONTROLLER_TASK,
            handler=self.submit_task
        )
        self.app.add_route(
            path=NetworkAPIPath.CONTROLLER_RETURN,
            method=NetworkAPIMethod.CONTROLLER_RETURN,
            handler=self.process_return
        )

        self.is_delete_temp_files = Context.get_parameter('DELETE_TEMP_FILES', direct=False)

    async def submit_task(self, request, backtask: SkyBackgroundTasks, ):
        file = self.app.parse_files_from_request(request=request)[0]
        file_data = await file.read()
        data = self.app.parse_forms_from_request(request=request)[0]['data']
        backtask.add_task(self.submit_task_background, data, file_data)

    async def process_return(self, request, backtask: SkyBackgroundTasks):
        data = self.app.parse_forms_from_request(request=request)[0]['data']
        backtask.add_task(self.process_return_background, data)

    def submit_task_background(self, data, file_data):
        """deal with tasks submitted by the generator or other controllers"""
        cur_task = Task.deserialize(data)
        FileOps.save_data_file(cur_task, file_data)
        # record end time of transmitting
        self.controller.record_transmit_ts(cur_task, is_end=True)

        action = self.controller.submit_task(cur_task)

        # for execute action, the file is remained
        # so that task returned from processor don't need to carry with file.
        if self.is_delete_temp_files and not action == 'execute':
            FileOps.remove_data_file(cur_task)

    def process_return_background(self, data):
        """deal with tasks returned by the processor"""
        cur_task = Task.deserialize(data)
        # record end time of executing
        self.controller.record_execute_ts(cur_task, is_end=True)

        actions = self.controller.process_return(cur_task)

        # for execute action, the file is remained
        # so that task returned from processor don't need to carry with file;
        # for wait action of joint node, the file is remained
        # so that joint task merged from waiting tasks has file to transmit.
        if self.is_delete_temp_files and 'execute' not in actions and 'wait' not in actions:
            FileOps.remove_data_file(cur_task)
