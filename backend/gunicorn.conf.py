import os

workers = 4

worker_class = "uvicorn.workers.UvicornWorker"

bind = f"0.0.0.0:{os.getenv('GUNICORN_PORT', 8910)}"

accesslog = '-'

errorlog = '-'
