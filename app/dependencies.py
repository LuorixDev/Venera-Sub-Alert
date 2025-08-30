# 导入所需的库
from fastapi import Request, HTTPException, status, WebSocket

# 检查用户是否已登录的依赖项 (用于 HTTP 请求)
def get_current_user(request: Request):
    # 从 cookie 中获取会话 ID
    session = request.cookies.get("session")
    # 如果没有会话 ID，则重定向到登录页面
    if not session:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )
    # 这里可以添加更复杂的会话验证逻辑，但为了简单起见，我们只检查会话是否存在
    return session

# 检查用户是否已登录的依赖项 (用于 WebSocket 连接)
async def get_current_user_ws(websocket: WebSocket):
    # 从 cookie 中获取会话 ID
    session = websocket.cookies.get("session")
    # 如果没有会话 ID，则关闭连接
    if not session:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    return session
