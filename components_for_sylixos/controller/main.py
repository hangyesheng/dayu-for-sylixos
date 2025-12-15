from core.controller import ControllerServer

app = ControllerServer().app


import asyncio
import os

if __name__ == "__main__":
    asyncio.run(app.run(host="0.0.0.0", port=os.getenv('GUNICORN_PORT', 9200)))