# 导入 Pydantic 相关模块，用于数据验证
from pydantic import BaseModel, EmailStr

# 定义邮件设置的数据模型
class MailSettings(BaseModel):
    server: str  # 邮件服务器地址
    port: int    # 邮件服务器端口
    username: EmailStr  # 发件人邮箱
    password: str       # 邮箱密码
    recipient: EmailStr # 收件人邮箱

# 定义高级设置的数据模型
class AdvancedSettings(BaseModel):
    update_interval: int  # 更新间隔 (分钟)
    command_timeout: int  # 命令超时 (秒)
