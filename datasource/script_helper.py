import subprocess
import signal
import os


class ScriptHelper:
    @staticmethod
    def start_script(command):
        process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid)
        return process

    @staticmethod
    def stop_script(process):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
