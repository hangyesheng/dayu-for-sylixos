import json
import subprocess
import signal
import sys
from contextlib import contextmanager

from .generator import Generator

from core.lib.common import ClassType, ClassFactory, Context, LOGGER, FileOps

@contextmanager
def managed_process(*args, **kwargs):
    proc = subprocess.Popen(*args, **kwargs)
    def handler(signum, frame):
        print(f"收到信号 {signum}，终止子进程 {proc.pid}...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

@ClassFactory.register(ClassType.GENERATOR, alias='video')
class VideoGenerator(Generator):
    def __init__(self, source_id: int, source_url: str,
                 source_metadata: dict, dag: list):
        super().__init__(source_id, source_metadata, dag)
        self.video_data_source = source_url

        self.frame_filter = Context.get_algorithm('GEN_FILTER')
        self.frame_process = Context.get_algorithm('GEN_PROCESS')
        self.frame_compress = Context.get_algorithm('GEN_COMPRESS')
        self.getter_filter = Context.get_algorithm('GEN_GETTER_FILTER')

    def submit_task_to_controller(self, cur_task):
        self.record_total_start_ts(cur_task)
        super().submit_task_to_controller(cur_task)

    def write_meta_data_to_file(self, meta_data, file_path):
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(meta_data, file, ensure_ascii=False, indent=4)

    def run(self):
        # initialize with default schedule policy
        self.after_schedule_operation(self, None)

        self.generator_saved_dir = f"/apps/generator/data_of_source_{self.source_id}/"
        FileOps.remove_file(self.generator_saved_dir)
        FileOps.create_directory(self.generator_saved_dir)

        self.write_meta_data_to_file(self.meta_data, self.generator_saved_dir + 'meta.json')
        
        command = ["/apps/generator/rtsp_solverex", "--url", self.video_data_source, 
                                    "--saved_dir", self.generator_saved_dir, 
                                    "--meta_file", self.generator_saved_dir + "meta.json"]
        
        LOGGER.info(f"Starting rtsp_solverex with command: {' '.join(command)}")

        with managed_process(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True) as process:
            LOGGER.info(f"Subprocess started with PID: {process.pid}")

            while True:
                if not self.getter_filter(self):
                    LOGGER.info('[Filter Getter] step to next round of getter.')
                    continue
                self.write_meta_data_to_file(self.meta_data, self.generator_saved_dir + 'meta.json')
                LOGGER.info(f"Start getting data from source {self.source_id}...")
                self.data_getter(self)

                self.request_schedule_policy()
