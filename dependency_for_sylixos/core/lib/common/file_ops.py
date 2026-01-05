import os
import shutil


class FileOps:
    @staticmethod
    def save_data_file(task, file_data):
        file_path = task.get_file_path()
        file_path = os.path.join("/apps", file_path.lstrip("/"))
        dir_path = os.path.dirname(file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        with open(file_path, 'wb') as buffer:
            buffer.write(file_data)

    @staticmethod
    def remove_data_file(task):
        file_path = task.get_file_path()
        FileOps.remove_file(file_path)

    @staticmethod
    def remove_file(file_path):
        file_path = os.path.join("/apps", file_path.lstrip("/"))
        if not os.path.exists(file_path):
            return

        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)

    @staticmethod
    def create_directory(dir_path):
        dir_path = os.path.join("/apps", dir_path.lstrip("/"))
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        else:
            assert os.path.isdir(dir_path), f'Path "{dir_path}" is a FILE'

