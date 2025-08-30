# Venera 订阅提醒与 Web UI

这是一个为 [Venera](https://github.com/venera-app/venera) 漫画阅读器设计的 Web 应用，旨在提供一个现代、易用的网页界面来管理和监控您的漫画订阅，并通过邮件发送更新通知。

## 项目简介

本应用通过调用 Venera 的无头模式（headless mode）命令行接口，实现了一系列自动化功能。它为您提供了一个带密码保护的网页界面，您可以在此查看所有收藏的漫画、最近更新的内容，并手动触发更新检查。

更重要的是，它可以在后台以指定的时间间隔自动检查更新。当检测到您收藏的漫画有新章节发布时，系统会自动发送一封包含漫画封面和更新信息的邮件到您指定的邮箱，确保您不会错过任何更新。

## 功能特性

- **现代 Web 界面**：使用 FastAPI 和 Vue.js（通过模板渲染）构建，界面美观，响应迅速。
- **密码保护**：所有页面和 API 都受到密码保护，确保您的数据安全。
- **漫画展示**：清晰地分为“最近更新”和“所有收藏”两个区域，并按更新时间从新到旧排序。
- **实时更新终端**：在执行更新任务时，网页顶部会显示一个仿终端窗口，实时直播每个命令的输出和进度，任务完成后会自动消失。
- **状态保持**：即使在更新过程中刷新页面，终端状态也会被完整恢复，不会丢失。
- **智能邮件通知**：当且仅当漫画的 `updateTime` 发生变化时，才会触发邮件通知，避免重复提醒。
- **Base64 图片内嵌**：提醒邮件中的漫画封面直接以 Base64 编码内嵌在邮件正文中，无需加载外部图片。
- **网页化配置**：您可以在网页的“设置”页面中方便地修改登录密码和邮件服务器配置，无需直接编辑文件。
- **数据持久化**：所有漫画数据都会被保存在 `data.json` 文件中，重启服务后数据不会丢失。
- **图片缓存**：漫画封面会被自动下载到本地缓存，解决了跨域问题，并加快了后续加载速度。
- **后台自动更新**：应用启动后，会自动在后台根据您设定的时间间隔，周期性地检查更新。
- **性能优化**：在应用启动时，会自动将 Venera 的核心文件复制到内存文件系统（tmpfs）中运行，以提高执行效率。

## 技术原理

项目后端基于 **FastAPI** 构建，通过 `asyncio.create_subprocess_shell` 调用 Venera 的命令行程序。

前端界面通过 **Jinja2** 模板渲染，并使用 **WebSocket** 与后端建立实时通信。当用户触发更新时，后端会通过 WebSocket 实时地将命令行输出和任务进度广播给前端，前端则动态地渲染出终端界面。

应用通过维护一个全局的状态管理器，确保了即使用户刷新页面，正在运行的任务状态也能够被完整地恢复。所有配置（密码、邮件服务器等）都通过 `.env` 文件进行管理，并可以在网页上动态修改。

## 使用指南

请严格按照以下步骤在您的服务器上部署和配置本项目。

### 步骤 1：部署本项目

首先，将本项目克隆或下载到您的服务器上。然后，安装所需的 Python 依赖：

```bash
# 建议在虚拟环境中操作
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤 2：配置初始密码和密钥

项目包含一个 `.env.example` 文件。您需要复制它来创建自己的配置文件：

```bash
cp .env.example .env
```

然后，编辑 `.env` 文件。**强烈建议**您修改 `SECRET_KEY` 为一个随机的长字符串，并可以根据需要修改初始的 `ADMIN_PASSWORD`。

### 步骤 3：引入 Venera 可执行文件

由于Venera上游还未合并Pr,本项目会临时提供二进制文件，所以本步骤展示无需执行。

将您最新版的 Venera Linux 可执行文件和其附带的 `data` 文件夹，一同放入项目根目录下的 `venera_core` 文件夹内。最终的目录结构应如下所示：

```
.
├── venera_core/
│   ├── venera      <-- 这是您的 Venera 可执行文件
│   ├── lib/
│   └── data/
├── app/
├── static/
├── templates/
└── ... (其他项目文件)
```

### 步骤 4：配置 Venera 代理（关键步骤）

为了确保服务器上的 Venera 能够正常访问各个漫画源，您可能需要为其配置网络代理。

1.  在您的**本地电脑**上打开 Venera 客户端。
2.  进入 `设置` -> `网络`。
3.  在“代理”部分，填写您服务器所使用的代理地址（例如 `http://127.0.0.1` 和`7890` 密码可以留空，为http代理）。
4.  **保存设置**。

### 步骤 5：迁移 Venera 配置文件

现在，您需要将刚刚在本地电脑上配置好的文件，迁移到服务器上。

1.  在您的**本地电脑**上，进入 Venera 的 `设置` -> `应用`。
2.  在“本地漫画存储地址”选项中，点击“复制路径”。
3.  打开您的文件管理器，粘贴刚刚复制的路径。然后，**返回上一级目录**。您现在应该能看到 Venera 的所有配置文件（例如 `appdata.json` 等文件）。
4.  将这个整个文件夹上传到您的服务器，并覆盖远程服务器venera的配置文件（应该在`~/.local/share/com.github.wgh136.venera/`文件夹下。（如果没有，可能需要服务器先启动一次venera,你也可以选择复制完整的文件夹到服务器的这个目录）

### 步骤 6：恢复本地代理设置

回到您**本地电脑**的 Venera 客户端，将网络代理设置改回您本地所需的配置（或者清空），然后保存。

### 步骤 7：运行本项目

在服务器上，返回到本项目的根目录，运行以下命令来启动应用：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 步骤 8：完成网页配置

1.  在浏览器中访问 `http://您的服务器IP:8000`。
2.  使用您在 `.env` 文件中设置的密码登录。
3.  进入右上角的“设置”页面。
4.  **务必**填写并保存在“邮件通知配置”部分的所有信息，否则邮件通知功能将无法工作。
5.  （可选）您也可以在这里修改登录密码。

至此，所有配置已完成！应用现在将根据您设定的时间间隔，在后台自动为您检查漫画更新。

## 在无桌面环境的 Linux 中运行（使用 Docker）

为了在没有图形界面的 Linux 服务器上运行，您需要构建一个 Docker 容器来提供必要的环境。

### 步骤 1：创建 Dockerfile

在项目根目录下创建一个名为 `Dockerfile` 的文件，内容如下，镜像比较大，大约1164MB：

```Dockerfile
# 使用 Ubuntu 24.04 LTS
FROM ubuntu:24.04

# 非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# 使用国内镜像源加速 apt
RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list \
 && sed -i 's|http://security.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list

# 更新 apt 并安装基础工具、Python3、GTK3/WebKitGTK
RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-dev \
    build-essential \
    libgtk-3-dev libglib2.0-dev libpango1.0-dev libcairo2-dev \
    libwebkit2gtk-4.1-0 libwebkit2gtk-4.1-dev \
    xvfb wget curl ca-certificates sudo \
    && rm -rf /var/lib/apt/lists/*

# 创建挂载目录
RUN mkdir -p /workspace
WORKDIR /workspace

# 默认启动命令
CMD ["bash"]
```

### 步骤 2：准备启动脚本

本项目包含一个 `start.sh` 启动脚本，用于在 Docker 容器内启动应用。在继续之前，请确保该脚本具有执行权限：

```bash
chmod +x start.sh
```

### 步骤 3：构建 Docker 镜像

在项目根目录下执行以下命令：
```bash
docker build -t venera-headless .
```

### 步骤 4：首次安装与配置

如果您是第一次运行，需要先进入一个临时的容器来完成项目初始化（例如克隆代码、安装依赖包）。

1.  **准备配置文件目录**：
    ```bash
    # 在宿主机创建用于存放配置文件的目录
    mkdir -p venera_config
    # 将您的配置文件放入 venera_config 文件夹，可以全部复制过来
    # cp /path/to/your/ ./venera_config/
    ```

2.  **进入临时容器进行设置**：
    ```bash
    docker run -it --rm \
      -v "$(pwd)":/workspace \
      -v "$(pwd)/venera_config":/root/.local/share/com.github.wgh136.venera \
      venera-headless bash
    ```

3.  **在容器内执行初始化**：
    ```bash
    # (如果宿主机当前目录没有代码) 克隆仓库代码
    # git clone https://github.com/LuorixDev/Venera-Sub-Alert.git .

    # 创建 Python 虚拟环境
    python3 -m venv .venv

    # 激活虚拟环境并安装依赖
    source .venv/bin/activate
    pip install -r requirements.txt

    # 完成后退出容器
    exit
    ```

### 步骤 5：启动应用

完成首次配置后，您可以随时使用以下命令在后台启动应用：

```bash
docker run -d -p 8000:8000 \
  -v "$(pwd)":/workspace \
  -v "$(pwd)/venera_config":/root/.local/share/com.github.wgh136.venera \
  --name venera-app --restart always \
  venera-headless ./start.sh
```

现在，您的应用应该已经在 Docker 容器中成功运行，并且可以通过 `http://您的服务器IP:8000` 访问。要查看日志，可以使用 `docker logs -f venera-app`。
