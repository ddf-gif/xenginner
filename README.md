<div align="center">

# ✦ AI 小说转剧本工具

**将小说章节自动转换为结构化 YAML 剧本 — 降低改编门槛，提升创作效率**

<br>

### 🚀 在线体验

# [http://49.233.93.220:8000](http://49.233.93.220:8000)

### 🎬 Demo 视频

# [📺 点击观看作品演示](https://www.bilibili.com/video/BV1k3Eb6AET1/?spm_id_from=333.1387.homepage.video_card.click&vd_source=7800ac290873999daa9270adf898de07)

> ⚠️ 免费额度：每 IP 每天 10 次调用。高频使用请在「设置」中填入自己的 API Key。

<br>

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](https://fastapi.tiangolo.com)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/ddf-gif/xenginner/pulls)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

---

## ✨ 功能亮点

| 功能 | 说明 |
|------|------|
| 🎭 **多风格预设** | 电影剧本、电视剧本、舞台剧、短视频脚本，一键切换 |
| 📖 **可视化预览** | YAML 与剧本预览双视图，台词可双击编辑 |
| 📊 **角色分析** | 自动统计台词数量、情感分布，数据辅助打磨 |
| 📤 **多格式导出** | HTML 精美排版、Markdown、纯文本 |
| 🔑 **自带 API** | 支持 DeepSeek / Kimi / GLM / 通义千问 / 豆包 |
| 📂 **文件拖放** | 支持 .txt / .docx 拖入解析，文件夹批量导入 |
| 🖊️ **对话式编辑** | 预览模式双击台词直接修改，自动同步 YAML |
| 🚦 **频率限制** | 每 IP 每天 10 次免费调用，自带 Key 不限制 |

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| **后端** | Python FastAPI + uvicorn |
| **AI** | DeepSeek / Kimi / GLM / 通义千问 / 豆包（OpenAI 兼容 SDK） |
| **前端** | 纯 HTML + CSS + JS（自定义设计系统） |
| **数据** | YAML（结构化剧本）+ Pydantic 校验 |
| **部署** | Docker / systemd |

---

## 🚀 快速开始

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 3. 启动服务
uvicorn main:app --reload

# 4. 打开浏览器
open http://localhost:8000
```

### 使用 API

```bash
# 转换小说为剧本
curl -X POST http://localhost:8000/api/convert \
  -H "Content-Type: application/json" \
  -d '{"novel_text": "第一章\n林晓舟...", "temperature": 0.3}'

# 健康检查
curl http://localhost:8000/api/health
```

---

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | Web 前端页面 |
| `POST` | `/api/convert` | 小说文本 → YAML 剧本 |
| `GET` | `/api/schema` | 获取 Schema 定义 |
| `GET` | `/api/providers` | 获取支持的模型列表 |
| `GET` | `/api/presets` | 获取剧本风格预设 |
| `POST` | `/api/upload` | 上传 .txt / .docx 文件 |
| `GET` | `/api/sample-novel` | 获取示例小说 |
| `GET` | `/api/health` | 健康检查 |

---

## 📦 部署

### Docker

```bash
docker-compose build
docker-compose up -d
```

### 服务器手动部署

```bash
# 拉取代码
git clone https://github.com/ddf-gif/xenginner.git
cd xenginner

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
echo 'DEEPSEEK_API_KEY=sk-your-key' > .env

# 启动（前台）
uvicorn main:app --host 0.0.0.0 --port 8000

# 或注册为 systemd 服务
cat > /etc/systemd/system/novel-to-script.service << 'EOF'
[Unit]
Description=AI Novel to Script Tool
After=network.target

[Service]
WorkingDirectory=/path/to/xenginner
EnvironmentFile=/path/to/xenginner/.env
ExecStart=/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl enable novel-to-script --now
```

---

## 📁 项目结构

```
xenginner/
├── app/                    # 应用核心代码
│   ├── api/routes.py       # 8 个 RESTful API 端点
│   ├── core/config.py      # pydantic-settings 配置管理
│   ├── core/models.py      # Pydantic 数据模型
│   ├── services/converter.py   # AI 转换服务
│   └── services/file_parser.py # .docx 文件解析
├── static/index.html       # Web 前端（着陆页 + 工具页）
├── docs/schema_design.md   # YAML Schema 设计文档
├── schema.yaml             # Schema 定义 + 示例
├── sample_novel.txt        # 示例小说（3 章）
├── docker-compose.yml      # Docker 部署配置
├── Dockerfile
├── deploy.sh               # 一键部署脚本
├── requirements.txt
└── .env.example
```

---

## 📐 Schema 设计

剧本数据结构采用 **Act → Scene → Event** 三层模型，支持 4 种事件类型：

| 类型 | 用途 | 必填字段 |
|------|------|---------|
| `dialogue` | 角色对话 | character + line |
| `action` | 角色动作 | character + description |
| `stage_direction` | 环境/舞台指示 | description |
| `voiceover` | 旁白/心理独白 | text |

[查看完整设计文档 →](docs/schema_design.md)

---

## 📋 开发指南

- **每个 PR 只做一件事** — 保持粒度细、可审查
- **主分支随时可运行** — 提交前确保服务正常
- **依赖在 README 中声明** — 新增依赖需更新 requirements.txt

### 已合并 PR

| # | 功能 |
|---|------|
| 1 | 前端界面重设计 |
| 2 | 拖放文件加载 |
| 3 | 用户自选模型 + 自传 API Key |
| 4 | .docx 文件解析 |
| 5 | 剧本风格预设 + YAML 可视化 + 回到顶部 |
| 6 | 多格式导出 HTML/MD/TXT |
| 7 | 角色台词统计分析 |

---

<div align="center">

**MIT License** · Made with ❤️

</div>
