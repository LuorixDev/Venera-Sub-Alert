# 导入 os 和 dotenv 库，用于处理环境变量
import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 辅助函数，用于从环境变量中获取值
def get_env(key: str, default: str = None) -> str:
    return os.getenv(key, default)

# --- 应用配置 ---

# 用于签名会话 cookie 的密钥
SECRET_KEY = get_env("SECRET_KEY", "a_default_secret_key_for_testing")
# 管理员密码
ADMIN_PASSWORD = get_env("ADMIN_PASSWORD", "123456")

# 邮件服务器配置
MAIL_SERVER = get_env("MAIL_SERVER")
MAIL_PORT = int(get_env("MAIL_PORT", 587))
MAIL_USERNAME = get_env("MAIL_USERNAME")
MAIL_PASSWORD = get_env("MAIL_PASSWORD")
MAIL_RECIPIENT = get_env("MAIL_RECIPIENT")

# 数据和缓存目录
DATA_FILE = "data.json"
CACHE_DIR = "cache/comic_cover"

# --- 高级配置 ---

# 自动更新间隔 (分钟)
UPDATE_INTERVAL_MINUTES = int(get_env("UPDATE_INTERVAL_MINUTES", 60))
# 命令执行超时时间 (秒)
COMMAND_TIMEOUT_SECONDS = int(get_env("COMMAND_TIMEOUT_SECONDS", 120))

# --- .env 文件更新函数 ---

# 更新 .env 文件中的配置项
def update_env_file(updates: dict):
    from dotenv import find_dotenv
    # 查找 .env 文件路径
    env_path = find_dotenv()
    if not env_path: env_path = '.env'
    
    lines = []
    # 如果 .env 文件存在，则读取所有行
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
    
    updated_keys = set(updates.keys())
    # 重写 .env 文件
    with open(env_path, 'w') as f:
        # 遍历原有行
        for line in lines:
            key = line.split('=', 1)[0]
            # 如果 key 在待更新列表中，则写入新值
            if key in updated_keys:
                f.write(f"{key}={updates.pop(key)}\n")
            else:
                # 否则，写入原有行
                f.write(line)
        # 将新增的配置项写入文件
        for key, value in updates.items():
            f.write(f"{key}={value}\n")
