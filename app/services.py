import asyncio
import json
import os
import hashlib
import httpx
import anyio
import uuid
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

from app import state, config
from app.websocket import manager # Keep for data_updated broadcast

# --- 日期解析辅助函数 ---
def parse_comic_update_time(time_str: str) -> datetime | None:
    """
    一个灵活的日期解析函数，尝试多种格式.
    """
    if not time_str or time_str == 'None':
        return None
    
    # 替换 'Z' 以便 strptime 和 fromisoformat 处理
    if time_str.endswith('Z'):
        time_str = time_str[:-1] + '+00:00'

    # 尝试 fromisoformat (效率高，支持多种 ISO 格式)
    try:
        return datetime.fromisoformat(time_str)
    except ValueError:
        pass

    # 备用格式列表
    formats_to_try = [
        '%Y-%m-%d %H:%M:%S', # 带时间的完整格式
        '%Y-%m-%d',         # 年-月-日 格式
        '%Y/%m/%d',         # 年/月/日 格式
    ]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    print(f"警告: 无法解析日期字符串 '{time_str}'")
    return None

# --- 数据持久化 ---
def save_data(data: dict):
    with open(config.DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data() -> dict:
    if os.path.exists(config.DATA_FILE):
        with open(config.DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {"all_comics": [], "updated_comics": [], "last_updated": "从未"}

# --- 邮件通知 ---
async def send_email_notification(comic: dict):
    if not all([config.MAIL_SERVER, config.MAIL_PORT, config.MAIL_USERNAME, config.MAIL_PASSWORD, config.MAIL_RECIPIENT]):
        print("邮件配置不完整，跳过发送通知。")
        return

    import base64
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"漫画更新提醒: {comic['name']}"
    msg['From'] = config.MAIL_USERNAME
    msg['To'] = config.MAIL_RECIPIENT

    # --- Base64内嵌图片 ---
    base64_image_src = ""
    cover_path = os.path.join(os.getcwd(), comic['coverUrl'].lstrip('/'))
    if os.path.exists(cover_path):
        with open(cover_path, 'rb') as f:
            encoded_string = base64.b64encode(f.read()).decode('utf-8')
            # 简单的MIME类型推断
            mime_type = "image/jpeg" if cover_path.endswith(('.jpg', '.jpeg')) else "image/png"
            base64_image_src = f"data:{mime_type};base64,{encoded_string}"

    update_time_dt = parse_comic_update_time(comic.get('updateTime'))
    update_time_str = update_time_dt.strftime('%Y-%m-%d %H:%M') if update_time_dt else "未知"
    tags_html = ''.join(f'<span style="background-color: #eee; border-radius: 3px; padding: 2px 6px; font-size: 12px; margin-right: 5px;">{tag}</span>' for tag in comic.get('tags', []))

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            .header {{ background-color: #4a90e2; color: #ffffff; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .comic-cover {{ max-width: 100%; height: auto; border-radius: 4px; margin-bottom: 20px; }}
            .info-table {{ width: 100%; border-collapse: collapse; }}
            .info-table td {{ padding: 8px 0; border-bottom: 1px solid #eaeaea; }}
            .info-table td:first-child {{ font-weight: bold; width: 120px; }}
            .footer {{ background-color: #f8f8f8; color: #888; padding: 15px; text-align: center; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>漫画更新提醒</h1>
            </div>
            <div class="content">
                <h2 style="color: #333;">《{comic['name']}》 更新啦！</h2>
                {f'<img src="{base64_image_src}" alt="漫画封面" class="comic-cover">' if base64_image_src else ''}
                <table class="info-table">
                    <tr><td>漫画名称:</td><td>{comic['name']}</td></tr>
                    <tr><td>作 者:</td><td>{comic.get('author', 'N/A')}</td></tr>
                    <tr><td>更新时间:</td><td>{update_time_str}</td></tr>
                    <tr><td>标 签:</td><td>{tags_html or '无'}</td></tr>
                </table>
            </div>
            <div class="footer">
                <p>这是一个自动发送的通知，请勿回复。</p>
            </div>
        </div>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    def _send_mail_blocking():
        """在阻塞的执行器中运行的邮件发送函数"""
        server = None
        try:
            # 连接到 SMTP 服务器
            server = smtplib.SMTP_SSL(config.MAIL_SERVER, config.MAIL_PORT, timeout=10)
            # 登录
            server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
            # 发送邮件
            server.sendmail(config.MAIL_USERNAME, [config.MAIL_RECIPIENT], msg.as_string())
            print(f"成功发送《{comic['name']}》的更新邮件。")
        except Exception as e:
            # 捕获并打印异常，以便调试
            print(f"发送邮件失败: {e}")
        finally:
            # 确保关闭连接
            if server:
                server.quit()

    try:
        loop = asyncio.get_running_loop()
        # 在独立的线程中运行阻塞的邮件发送代码
        await loop.run_in_executor(None, _send_mail_blocking)
    except Exception as e:
        print(f"运行邮件发送任务时出错: {e}")

# --- 核心业务逻辑 ---
async def run_venera_command_streamed(command: str, flow_id: str, task_id: str, executable_path: str):
    await state.start_task(flow_id, task_id, command)
    
    full_command = f"{executable_path} --headless {command}"
    
    try:
        process = await asyncio.wait_for(
            asyncio.create_subprocess_shell(
                full_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            ),
            timeout=config.COMMAND_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        await state.add_log(flow_id, task_id, f"命令执行超时 ({config.COMMAND_TIMEOUT_SECONDS}秒)，任务被强制终止。", None)
        await state.end_task(flow_id, task_id)
        return []

    json_prefix = "[CLI PRINT] "
    final_json_output = []

    # 循环读取输出，直到进程结束
    while process.returncode is None:
        # 检查是否需要取消
        if state.is_flow_cancelled(flow_id):
            process.terminate()
            await process.wait() # 等待进程完全终止
            await state.add_log(flow_id, task_id, "任务被用户强制终止。", None)
            break

        try:
            # 带超时读取一行输出
            line_bytes = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
            if not line_bytes:
                # 如果读到空字节，可能意味着进程已结束
                await asyncio.sleep(0.1)
                continue

            line = line_bytes.decode().strip()
            
            parsed_json = None
            if line.startswith(json_prefix):
                try:
                    json_str = line[len(json_prefix):]
                    parsed_json = json.loads(json_str)
                    final_json_output.append(parsed_json)
                except json.JSONDecodeError: pass
            
            await state.add_log(flow_id, task_id, line, parsed_json)

        except asyncio.TimeoutError:
            # 读取超时是正常的，继续循环以检查取消状态
            continue
        except Exception as e:
            print(f"读取进程输出时出错: {e}")
            break
    
    await process.wait()
    await state.end_task(flow_id, task_id)
    return final_json_output

async def cache_image(url: str):
    if not url or not url.startswith(('http://', 'https://')): return None
    try:
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        file_ext = os.path.splitext(url)[1] or ".jpg"
        local_filename = f"{url_hash}{file_ext}"
        local_filepath = os.path.join(config.CACHE_DIR, local_filename)
        if os.path.exists(local_filepath): return f"/cache/comic_cover/{local_filename}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        async with await anyio.open_file(local_filepath, "wb") as f:
            await f.write(response.content)
        return f"/cache/comic_cover/{local_filename}"
    except Exception as e:
        print(f"图片缓存失败: {url}, 错误: {e}")
        return None

async def run_update_flow():
    from app.main import get_venera_executable_path
    executable_path = get_venera_executable_path()

    flow_id = str(uuid.uuid4())
    state.start_flow(flow_id)
    
    old_data = load_data()
    old_comics_map = {comic['id']: comic for comic in old_data.get('all_comics', [])}

    await run_venera_command_streamed("webdav down", flow_id, f"webdav_down_{flow_id}", executable_path)
    await run_venera_command_streamed("updatescript all", flow_id, f"updatescript_{flow_id}", executable_path)
    await run_venera_command_streamed("webdav up", flow_id, f"webdav_up_{flow_id}", executable_path)
    final_output = await run_venera_command_streamed("updatesubscribe", flow_id, f"updatesubscribe_{flow_id}", executable_path)
    
    all_comics_set = {}
    for item in final_output:
        if item.get("message") == "Progress" and "comic" in item.get("data", {}):
            all_comics_set[item["data"]["comic"]["id"]] = item["data"]["comic"]
    
    updated_comics_list = []
    if final_output and final_output[-1].get("message") == "Updated comics list.":
        updated_comics_list = final_output[-1].get("data", [])
        

    def sort_key(comic):
        """使用辅助函数解析日期，并返回一个可供排序的对象"""
        dt = parse_comic_update_time(comic.get('updateTime'))
        if not dt:
            # 将无法解析的日期排在最后
            return datetime.min.replace(tzinfo=None)
        
        # 如果有时区信息，则转换为本地时间以便统一比较
        if dt.tzinfo:
            return dt.astimezone(None).replace(tzinfo=None)
        return dt

    # --- 整合新旧数据，并标记失败的条目 ---
    final_all_comics_list = []
    for comic_id, old_comic in old_comics_map.items():
        if comic_id in all_comics_set:
            # 本次成功更新
            new_comic = all_comics_set[comic_id]
            new_comic['updateFailed'] = False # 明确标记成功
            final_all_comics_list.append(new_comic)
        else:
            # 本次更新失败，保留旧数据并标记
            old_comic['updateFailed'] = True
            final_all_comics_list.append(old_comic)

    # 处理本次新添加的漫画
    for comic_id, new_comic in all_comics_set.items():
        if comic_id not in old_comics_map:
            new_comic['updateFailed'] = False
            final_all_comics_list.append(new_comic)


    all_comics = sorted(final_all_comics_list, key=sort_key, reverse=True)
    # `updated_comics_list` 只包含ID，我们需要从 `all_comics_set` 获取完整数据
    updated_comics_ids = {c['id'] for c in updated_comics_list}
    updated_comics = sorted([c for c in all_comics if c['id'] in updated_comics_ids], key=sort_key, reverse=True)


    newly_updated_for_email = []
    current_fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def process_comics(comics, fetch_time: str):
        tasks = [cache_image(c.get("coverUrl")) for c in comics]
        cached_urls = await asyncio.gather(*tasks)
        for comic, url in zip(comics, cached_urls):
            if url: comic["coverUrl"] = url
            
            old_comic = old_comics_map.get(comic['id'])
            
            # 只为成功更新的漫画处理时间戳和邮件
            if not comic.get('updateFailed'):
                if old_comic:
                    # 继承上一次的成功获取时间，作为“上次”记录
                    if 'lastSuccessfulFetchTime' in old_comic:
                        comic['previousSuccessfulFetchTime'] = old_comic['lastSuccessfulFetchTime']

                    # 检查内容更新时间戳，用于邮件通知
                    if old_comic.get('updateTime') != comic.get('updateTime'):
                        print(f"检测到漫画 '{comic['name']}' 更新，准备发送邮件。")
                        newly_updated_for_email.append(comic)

                # 记录本次成功获取的时间
                comic['lastSuccessfulFetchTime'] = fetch_time
            
        return comics

    comics_data = load_data()
    # 注意：现在 all_comics 已经包含了所有条目（成功和失败的）
    comics_data["all_comics"] = await process_comics(all_comics, current_fetch_time)
    comics_data["updated_comics"] = await process_comics(updated_comics, current_fetch_time)
    comics_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(comics_data)
    
    # webdav up 可能会失败，但不应阻塞邮件发送
    try:
        await run_venera_command_streamed("webdav up", flow_id, f"webdav_up_final_{flow_id}", executable_path)
    except Exception as e:
        print(f"最后的 webdav up 失败: {e}")

    if newly_updated_for_email:
        email_tasks = [send_email_notification(comic) for comic in newly_updated_for_email]
        await asyncio.gather(*email_tasks)

    await manager.broadcast(json.dumps({"type": "data_updated", "data": comics_data}))
    await state.end_flow(flow_id)

async def run_single_update_flow(comic_id: str, comic_type: str):
    from app.main import get_venera_executable_path
    executable_path = get_venera_executable_path()

    flow_id = str(uuid.uuid4())
    state.start_flow(flow_id)

    command = f'updatesubscribe --update-comic-by-id-type "{comic_id}" "{comic_type}"'
    task_id = f"update_single_{comic_id}_{flow_id}"
    
    final_output = await run_venera_command_streamed(command, flow_id, task_id, executable_path)

    updated_comic_data = None
    for item in final_output:
        if item.get("message") == "Progress" and "comic" in item.get("data", {}):
            if item["data"]["comic"]["id"] == comic_id:
                updated_comic_data = item["data"]["comic"]
                break # 找到目标漫画后即可退出

    comics_data = load_data()
    found = False
    for i, comic in enumerate(comics_data["all_comics"]):
        if comic["id"] == comic_id:
            if updated_comic_data:
                # --- 更新成功 ---
                old_comic = comic
                updated_comic_data['updateFailed'] = False
                if 'lastSuccessfulFetchTime' in old_comic:
                    updated_comic_data['previousSuccessfulFetchTime'] = old_comic['lastSuccessfulFetchTime']
                updated_comic_data['lastSuccessfulFetchTime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cached_url = await cache_image(updated_comic_data.get("coverUrl"))
                if cached_url:
                    updated_comic_data["coverUrl"] = cached_url

                comics_data["all_comics"][i] = updated_comic_data
            else:
                # --- 更新失败 ---
                comics_data["all_comics"][i]['updateFailed'] = True
            
            found = True
            break
    
    # 如果是全新的漫画并且更新成功
    if not found and updated_comic_data:
        updated_comic_data['updateFailed'] = False
        updated_comic_data['lastSuccessfulFetchTime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cached_url = await cache_image(updated_comic_data.get("coverUrl"))
        if cached_url:
            updated_comic_data["coverUrl"] = cached_url
        comics_data["all_comics"].append(updated_comic_data)

    # 无论成功与否，都保存并广播数据，以确保前端UI同步
    comics_data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(comics_data)
    await manager.broadcast(json.dumps({"type": "data_updated", "data": comics_data}))

    await state.end_flow(flow_id)
