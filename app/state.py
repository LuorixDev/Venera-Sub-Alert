import json
import asyncio
import time
from collections import OrderedDict

from app.websocket import manager

# --- 全局状态管理器 ---
# 使用 OrderedDict 来保持任务插入的顺序
running_tasks = OrderedDict()
# 用于存储被用户请求取消的流程ID
cancelled_flows = set()

async def update_and_broadcast(flow_id: str, task_id: str, update_data: dict):
    """Helper to update state and broadcast the change."""
    if flow_id in running_tasks and task_id in running_tasks[flow_id]['tasks']:
        running_tasks[flow_id]['tasks'][task_id].update(update_data)
        await manager.broadcast(json.dumps(update_data))

def start_flow(flow_id: str):
    """Marks the start of a new update flow."""
    # 如果之前有取消标记，先清除
    if flow_id in cancelled_flows:
        cancelled_flows.remove(flow_id)
        
    running_tasks[flow_id] = {
        "active": True,
        "flowId": flow_id, # 将 flow_id 也加入，方便前端获取
        "tasks": OrderedDict()
    }

async def start_task(flow_id: str, task_id: str, command: str):
    """Adds a new task to the running flow."""
    if flow_id in running_tasks:
        task_state = {
            "type": "task_start",
            "flowId": flow_id,
            "taskId": task_id,
            "command": command,
            "status": "running",
            "start_time": time.time(),
            "logs": [],
            "progress": {"current": 0, "total": 0}
        }
        running_tasks[flow_id]['tasks'][task_id] = task_state
        await manager.broadcast(json.dumps(task_state))

async def add_log(flow_id: str, task_id: str, log: str, parsed: dict = None):
    """Adds a log entry and potential progress update to a task."""
    if flow_id in running_tasks and task_id in running_tasks[flow_id]['tasks']:
        # Store log for state reconstruction
        running_tasks[flow_id]['tasks'][task_id]['logs'].append(log)
        
        # Prepare broadcast message
        payload = {"type": "log", "taskId": task_id, "data": log}
        if parsed and parsed.get("message") == "Progress":
            progress_data = parsed.get("data", {})
            current, total = progress_data.get("current", 0), progress_data.get("total", 0)
            running_tasks[flow_id]['tasks'][task_id]['progress'] = {"current": current, "total": total}
            payload["parsed"] = parsed
        
        await manager.broadcast(json.dumps(payload))

async def end_task(flow_id: str, task_id: str):
    """Marks a task as complete."""
    if flow_id in running_tasks and task_id in running_tasks[flow_id]['tasks']:
        running_tasks[flow_id]['tasks'][task_id]['status'] = "complete"
        payload = {"type": "task_end", "taskId": task_id}
        await manager.broadcast(json.dumps(payload))

async def end_flow(flow_id: str):
    """Marks the end of an update flow and schedules its removal."""
    if flow_id in running_tasks:
        running_tasks[flow_id]['active'] = False
        # Keep completed flow data for a short period for late-connecting clients
        await asyncio.sleep(5)
        if flow_id in running_tasks:
            running_tasks.pop(flow_id)
        if flow_id in cancelled_flows:
            cancelled_flows.remove(flow_id)

def cancel_flow(flow_id: str):
    """Marks a flow to be cancelled."""
    print(f"请求取消流程: {flow_id}")
    cancelled_flows.add(flow_id)

def is_flow_cancelled(flow_id: str) -> bool:
    """Checks if a flow has been marked for cancellation."""
    return flow_id in cancelled_flows

def get_current_state() -> dict:
    """Gets the state of all currently running tasks for a new client."""
    active_flows = OrderedDict()
    is_currently_running = False

    for flow_id, flow_data in running_tasks.items():
        if flow_data.get('active', False):
            is_currently_running = True
            active_tasks = OrderedDict()
            for task_id, task_data in flow_data.get('tasks', {}).items():
                if task_data.get('status') == 'running':
                    active_tasks[task_id] = task_data
            
            # 只包括至少有一个正在运行任务的流程
            if active_tasks:
                active_flows[flow_id] = {
                    "active": True,
                    "tasks": active_tasks
                }

    return {
        "type": "current_state",
        "is_running": is_currently_running,
        "flows": active_flows
    }
