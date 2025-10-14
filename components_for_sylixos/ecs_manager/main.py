from core.ecs_manager import ECSManagerServer

app = ECSManagerServer().app

import os
import asyncio

if __name__ == '__main__':
    asyncio.run(app.run(host="0.0.0.0", port=os.getenv('GUNICORN_PORT', 9900)))




