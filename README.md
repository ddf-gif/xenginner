# AI 小说转剧本工具

一句话简介：帮助作者将小说文本自动转换为结构化 YAML 剧本。降低改编门槛，提升创作效率。

## 技术栈

- **后端框架**：Python FastAPI
- **AI 模型**：DeepSeek（通过 OpenAI 兼容 SDK 调用）
- **前端样式**：Pico.css（轻量语义化 CSS 框架）
- **数据格式**：YAML（结构化剧本）

## 项目结构

```
novel-to-script/
├── app/                    # 应用核心代码
│   ├── main.py             # FastAPI 应用工厂
│   ├── api/
│   │   └── routes.py       # RESTful API 路由
│   ├── core/
│   │   ├── config.py       # 配置管理（pydantic-settings）
│   │   └── models.py       # Pydantic 数据模型
│   └── services/
│       └── converter.py    # AI 转换服务（DeepSeek 集成）
├── static/
│   └── index.html          # Web 前端页面
├── docs/
│   └── schema_design.md    # YAML Schema 设计文档
├── schema.yaml             # 剧本 YAML Schema 定义 + 示例
├── sample_novel.txt        # 示例小说（用于测试）
├── main.py                 # 应用入口文件
├── Dockerfile              # Docker 部署配置
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

创建 `.env` 文件（可参考 `.env.example`）：

```bash
cp .env.example .env
```

然后编辑 `.env`，填入你的 DeepSeek API Key：

```
DEEPSEEK_API_KEY=sk-your-key-here
```

> 注册获取 API Key：https://platform.deepseek.com/api_keys

### 3. 启动服务

```bash
uvicorn main:app --reload
```

访问 http://localhost:8000 即可使用。

### 4. 使用 API

**转换小说为剧本：**

```bash
curl -X POST http://localhost:8000/api/convert \
  -H "Content-Type: application/json" \
  -d '{"novel_text": "第一章\n林晓舟...", "temperature": 0.3}'
```

**健康检查：**

```bash
curl http://localhost:8000/api/health
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web 前端页面 |
| POST | `/api/convert` | 小说文本 → YAML 剧本 |
| GET | `/api/schema` | 获取 Schema 定义 |
| GET | `/api/sample-novel` | 获取示例小说 |
| GET | `/api/health` | 健康检查 |

## 部署

### Docker 部署

```bash
# 构建镜像
docker build -t novel-to-script .

# 运行容器（挂载 .env 文件）
docker run -d --name novel-to-script \
  -p 8000:8000 \
  --env-file .env \
  novel-to-script
```

### 云服务器部署

1. 将代码上传到服务器
2. 安装依赖：`pip install -r requirements.txt`
3. 配置 `.env` 文件
4. 使用 systemd 或 supervisor 管理进程：

```bash
# 安装 uvicorn 作为服务
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## 开发指南

1. **每个 PR 只做一件事** — 保持粒度细、可审查
2. **主分支随时可运行** — 提交前确保 `uvicorn main:app --reload` 正常
3. **依赖在 README 中声明** — 新增依赖需更新 README 和 requirements.txt

## 依赖清单

| 包 | 用途 | 官方文档 |
|----|------|---------|
| fastapi | Web 框架 | https://fastapi.tiangolo.com |
| uvicorn | ASGI 服务器 | https://www.uvicorn.org |
| openai | DeepSeek API 客户端 | https://pypi.org/project/openai |
| pyyaml | YAML 解析/生成 | https://pyyaml.org |
| pydantic-settings | 环境变量管理 | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ |

## 许可证

MIT License
