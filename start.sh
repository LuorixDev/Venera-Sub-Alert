#!/bin/sh
# 启动虚拟桌面环境并在后台运行
Xvfb :99 -screen 0 1920x1080x24 &

# 设置 DISPLAY 环境变量
export DISPLAY=:99

# 激活虚拟环境并启动应用
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
