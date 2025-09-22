from core.controller import ControllerServer

app = ControllerServer().app



import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.getenv('GUNICORN_PORT', 9200))