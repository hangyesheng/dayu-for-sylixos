'''
@Project ：dependency_for_sylixos 
@File    ：test_origin_request.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/25 17:17 
'''
'''
@Project ：dependency_for_sylixos 
@File    ：test_origin_request.py
@IDE     ：PyCharm 
@Author  ：Skyrim
@Date    ：2025/9/25 17:17 
'''

import json
import requests

BASE_URL = "http://127.0.0.1:9200"

# ======== GET /predict ========
res = requests.get(f"{BASE_URL}/predict")
print(res.status_code, res.text)

# ======== POST /trans ========
res = requests.post(f"{BASE_URL}/trans", json={'name': 'skyrim'})
print(res.status_code, res.text)

# ======== POST /sleep ========
res = requests.post(f"{BASE_URL}/sleep", json={'command': 'pls sleep'})
print(res.status_code, res.text)

# ======== POST /form (application/x-www-form-urlencoded) ========
form_data = {'command': 'form sleep', 'name': 'skyrim'}
res = requests.post(f"{BASE_URL}/form", data=form_data)
print(res.status_code, res.text)
print(res['plan'])

# ======== POST /file (multipart/form-data) ========
with open('test_server.jsonl', 'rb') as f:
    files = {
        "own_file": ("test_server_target.jsonl", f, "application/json")
    }
    res = requests.post(f"{BASE_URL}/file", files=files)
    print(res.status_code, res.text)
