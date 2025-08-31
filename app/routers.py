# 导入所需的库
import asyncio
from fastapi import APIRouter, Request, Form, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# 导入本地模块
from app import services, config, state
from app.dependencies import get_current_user, get_current_user_ws
from app.models import MailSettings, AdvancedSettings
from app.websocket import manager

# 创建一个 FastAPI 路由器实例
router = APIRouter()
# 指定模板文件所在的目录
templates = Jinja2Templates(directory="templates")

# --- 认证路由 ---

# 登录页面
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# 处理登录请求
@router.post("/login")
async def login(password: str = Form(...)):
    if password != config.ADMIN_PASSWORD:
        # 如果密码不正确，则返回错误信息
        return templates.TemplateResponse("login.html", {"request": {}, "error": "密码错误"})
    
    # 创建重定向响应，并设置会话 cookie
    response = RedirectResponse(url="/", status_code=303)
    # 设置 cookie 过期时间为 7 天
    response.set_cookie(key="session", value="user", httponly=True, max_age=60 * 60 * 24 * 7)
    return response

# 退出登录
@router.get("/logout")
async def logout():
    # 创建到登录页面的重定向响应
    response = RedirectResponse(url="/login", status_code=303)
    # 删除会话 cookie
    response.delete_cookie(key="session")
    return response

# --- 页面路由 ---

# 根路由，用于显示主页
@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user: str = Depends(get_current_user)):
    # 加载漫画数据
    comics_data = services.load_data()
    # 渲染主页模板并返回
    return templates.TemplateResponse("index.html", {"request": request, "comics_data": comics_data})

# 设置页面路由
@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: str = Depends(get_current_user)):
    # 渲染设置页面模板并返回
    return templates.TemplateResponse("settings.html", {"request": request})

# --- API 路由 ---

# 获取邮件设置
@router.get("/settings/mail", dependencies=[Depends(get_current_user)])
async def get_mail_settings():
    # 返回当前的邮件设置
    return {
        "server": config.MAIL_SERVER, "port": config.MAIL_PORT, "username": config.MAIL_USERNAME,
        "password": "••••••••" if config.MAIL_PASSWORD else "", "recipient": config.MAIL_RECIPIENT
    }

# 更新邮件设置
@router.post("/settings/mail", dependencies=[Depends(get_current_user)])
async def update_mail_settings(settings: MailSettings):
    # 构建需要更新的配置项
    updates = {
        "MAIL_SERVER": settings.server, "MAIL_PORT": str(settings.port),
        "MAIL_USERNAME": settings.username, "MAIL_RECIPIENT": settings.recipient
    }
    # 如果密码有变动，则更新密码
    if settings.password != "••••••••":
        updates["MAIL_PASSWORD"] = settings.password
    
    # 更新 .env 文件
    config.update_env_file(updates)
    # 更新全局配置变量
    config.MAIL_SERVER, config.MAIL_PORT, config.MAIL_USERNAME, config.MAIL_RECIPIENT = settings.server, settings.port, settings.username, settings.recipient
    if "MAIL_PASSWORD" in updates: config.MAIL_PASSWORD = updates["MAIL_PASSWORD"]
    # 返回成功信息
    return {"message": "Mail settings updated successfully"}

# 更新密码
@router.post("/settings/password", dependencies=[Depends(get_current_user)])
async def update_password(current_password: str = Form(...), new_password: str = Form(...)):
    # 检查当前密码是否正确
    if current_password != config.ADMIN_PASSWORD:
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    # 更新密码
    config.ADMIN_PASSWORD = new_password
    # 更新 .env 文件中的密码
    config.update_env_file({"ADMIN_PASSWORD": new_password})
    # 返回成功信息
    return {"message": "Password updated successfully"}

# 获取高级设置
@router.get("/settings/advanced", dependencies=[Depends(get_current_user)])
async def get_advanced_settings():
    return {
        "update_interval": config.UPDATE_INTERVAL_MINUTES,
        "command_timeout": config.COMMAND_TIMEOUT_SECONDS,
    }

# 更新高级设置
@router.post("/settings/advanced", dependencies=[Depends(get_current_user)])
async def update_advanced_settings(settings: AdvancedSettings):
    updates = {
        "UPDATE_INTERVAL_MINUTES": str(settings.update_interval),
        "COMMAND_TIMEOUT_SECONDS": str(settings.command_timeout),
    }
    config.update_env_file(updates)
    # 更新全局变量 (注意: 更新间隔的更改需要重启应用才能生效)
    config.UPDATE_INTERVAL_MINUTES = settings.update_interval
    config.COMMAND_TIMEOUT_SECONDS = settings.command_timeout
    return {"message": "Advanced settings updated successfully. Please restart the application for the update interval to take effect."}

# 触发更新流程
@router.post("/update", dependencies=[Depends(get_current_user)])
async def update_subscriptions():
    current_state = state.get_current_state()
    if current_state["flows"]:
        raise HTTPException(status_code=409, detail="An update process is already running.")
    # 异步执行更新流程
    asyncio.create_task(services.run_update_flow())
    # 返回状态信息
    return {"status": "Update process started."}

# 触发单个漫画的更新流程
@router.post("/update_single/{comic_type}/{comic_id}", dependencies=[Depends(get_current_user)])
async def update_single_subscription(comic_type: str, comic_id: str):
    current_state = state.get_current_state()
    if current_state["flows"]:
        raise HTTPException(status_code=409, detail="An update process is already running.")
    
    # 异步执行单个漫画的更新流程
    asyncio.create_task(services.run_single_update_flow(comic_id, comic_type))
    return {"status": f"Update process for comic {comic_id} started."}

# 取消更新流程
@router.post("/cancel_update/{flow_id}", dependencies=[Depends(get_current_user)])
async def cancel_update(flow_id: str):
    state.cancel_flow(flow_id)
    return {"status": f"Cancellation request for flow {flow_id} received."}

# --- WebSocket ---

# WebSocket 端点，用于实时通信
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user: str = Depends(get_current_user_ws)):
    # 如果用户未通过认证，则直接返回
    if not user:
        return
    
    # 接受 WebSocket 连接
    await manager.connect(websocket)
    
    # 导入并获取当前状态
    from app.state import get_current_state
    import json
    # 将当前状态发送给新连接的客户端
    await websocket.send_text(json.dumps(get_current_state()))
    
    try:
        # 保持连接，等待客户端消息
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        # 如果连接断开，则从管理器中移除
        manager.disconnect(websocket)
