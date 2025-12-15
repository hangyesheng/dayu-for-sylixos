from core.processor import ProcessorServer

app = ProcessorServer().app


import asyncio
import os

if __name__ == "__main__":
    asyncio.run(app.run(host="0.0.0.0", port=os.getenv('GUNICORN_PORT', 9000)))