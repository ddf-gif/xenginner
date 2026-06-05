"""
小说转剧本工具 — 入口文件。

快速启动：
    uvicorn main:app --reload

生产部署：
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

from app.main import app

# 如果希望用脚本方式启动，可以取消下面注释：
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
