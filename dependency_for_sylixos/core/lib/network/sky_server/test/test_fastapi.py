'''
@Project ：dependency_for_sylixos 
@File    ：test_fastapi.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/25 16:35 
'''
'''
@Project ：dependency_for_sylixos 
@File    ：test_fastapi.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/25 16:35 
'''

import time
import json
from fastapi import FastAPI, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse

app = FastAPI()


# ======== GET /predict ========
@app.get("/predict")
async def predict():
    return JSONResponse({"status": "success", "data": 233})


# ======== POST /trans ========
@app.post("/trans")
async def trans_data(request: Request):
    data = await request.json()
    print(data)
    return JSONResponse({"status": "success", "data": 233})


# ======== POST /sleep ========
def sleep_2sec():
    time.sleep(2)
    print('2333')
    with open('test_server.jsonl', 'w', encoding='utf-8') as f:
        json.dump({"status": "success", "sleep_time": "2"}, f)


@app.post("/sleep")
async def sleep_task(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print(data)
    background_tasks.add_task(sleep_2sec)
    return JSONResponse({"status": "success", "data": "成功睡眠"})


# ======== POST /form ========
@app.post("/form")
async def form_task(command: str = Form(...)):
    # command 这里对应 application/x-www-form-urlencoded 的字段
    print(f"字段名: command, 值: {command}")
    return JSONResponse({"status": "success", "forms_count": 1})


# ======== POST /file ========
@app.post("/file")
async def file_task(own_file: UploadFile = File(...)):
    print(f"文件名: {own_file.filename}, Content-Type: {own_file.content_type}")
    content_bytes = await own_file.read()
    print(content_bytes)
    return JSONResponse({"status": "success", "files_count": 1})


# ======== 启动方式 ========
if __name__ == "__main__":
    import uvicorn
    import os

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("GUNICORN_PORT", 9200)))
