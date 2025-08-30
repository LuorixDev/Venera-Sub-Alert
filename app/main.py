# 导入所需的库
import os
import shutil
import tempfile
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 导入本地模块
from app import routers, config, services

# --- 全局变量 ---
# 用于存储 venera 可执行文件的临时路径
VENERA_TMP_PATH = ""
# 用于控制后台定时任务
background_task = None

# --- 应用生命周期事件 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global VENERA_TMP_PATH, background_task
    print("应用启动中...")

    # 1. 将 venera_core 复制到 tmpfs
    source_dir = "venera_core"
    # 创建一个临时目录
    temp_dir = tempfile.mkdtemp()
    dest_dir = os.path.join(temp_dir, "venera_core")
    try:
        shutil.copytree(source_dir, dest_dir)
        VENERA_TMP_PATH = os.path.join(dest_dir, "venera")
        # 确保可执行权限
        os.chmod(VENERA_TMP_PATH, 0o755)
        print(f"'{source_dir}' 已成功复制到临时目录: '{dest_dir}'")
    except Exception as e:
        print(f"复制 '{source_dir}' 失败: {e}")
        # 如果复制失败，则回退到使用本地路径
        VENERA_TMP_PATH = os.path.join(source_dir, "venera")

    # 2. 启动后台定时更新任务
    async def periodic_update():
        while True:
            await asyncio.sleep(config.UPDATE_INTERVAL_MINUTES * 60)
            print(f"开始执行定时更新任务 (间隔: {config.UPDATE_INTERVAL_MINUTES} 分钟)...")
            try:
                await services.run_update_flow()
                print("定时更新任务执行完毕。")
            except Exception as e:
                print(f"定时更新任务执行失败: {e}")

    background_task = asyncio.create_task(periodic_update())
    print(f"后台定时更新任务已启动，每 {config.UPDATE_INTERVAL_MINUTES} 分钟检查一次。")

    yield # 应用运行

    print("应用关闭中...")
    # 3. 清理后台任务和临时文件
    if background_task:
        background_task.cancel()
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        print(f"临时目录 '{temp_dir}' 已清理。")

# --- FastAPI 应用实例 ---
app = FastAPI(lifespan=lifespan)

# --- 中间件 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 路由 ---
app.include_router(routers.router)

# --- 静态文件 ---
# 在挂载前确保目录存在
os.makedirs("static", exist_ok=True)
os.makedirs("cache", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/cache", StaticFiles(directory="cache"), name="cache")

# --- 辅助函数 ---
def get_venera_executable_path() -> str:
    """获取 venera 可执行文件的路径 (优先使用 tmpfs 中的路径)"""
    return VENERA_TMP_PATH

# 确保缓存目录存在
os.makedirs(config.CACHE_DIR, exist_ok=True)
