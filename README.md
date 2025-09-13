# 本地文档智能搜索系统

一个基于 Flask 和 PostgreSQL 的本地文档智能搜索 Web 应用。它能自动扫描您指定的本地文件夹，将多种格式的文档（如 Office 全家桶、PDF、代码、日志等）统一转换为 Markdown 格式，并利用 PostgreSQL 的高级索引（PGroonga 全文搜索、Trigram 模糊搜索）为您提供毫秒级的精准、高效的搜索体验。

## ✨ 主要功能

- **📁 智能文件夹扫描**：递归扫描本地文件夹，可根据文件修改日期、文件类型进行增量或全量索引。
- **📄 强大的格式转换**：内置 `markitdown`，支持将 `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.md`, `.txt` 及各类代码和日志文件自动转换为结构化的 Markdown。
- **🚀 高性能全文搜索**：集成 **PGroonga** 扩展，为文档内容和文件名提供高速、精准的全文搜索能力。
- **✍️ 模糊与相似度搜索**：利用 **pg_trgm** 扩展，支持文件名和内容的 trigram 模糊匹配，即使有拼写错误也能找到相关结果。
- **🖥️ 简洁易用的 Web 界面**：
    - 提供清晰的搜索页面，支持关键词搜索。
    - 搜索结果列表会生成包含关键词的**内容摘要**并**高亮**显示。
    - 支持点击文件名预览完整的 Markdown 内容。
    - 支持从搜索结果中直接调用系统默认程序打开本地的原始文件。
- **🔄 错误重试与管理**：对于转换失败的文档，提供一键重试功能。
- **📝 详细的日志系统**：记录应用运行、文档处理和错误信息，便于追踪和调试。

## 🛠️ 技术栈

- **后端**: Python 3, Flask, SQLAlchemy
- **数据库**: PostgreSQL
- **数据库扩展**: PGroonga (全文搜索), pg_trgm (模糊搜索)
- **前端**: 原生 HTML, CSS, JavaScript (无复杂框架)
- **核心依赖**: 
    - `Flask-Migrate`: 用于数据库结构迁移。
    - `psycopg2-binary`: PostgreSQL 驱动。
    - `markitdown[all]`: 强大的多格式文件转 Markdown 工具。
    - `python-dotenv`: 用于管理环境变量。

## ⚙️ 安装与设置

#### 1. 环境准备
- 确保您已经安装了 Python 3.10+。
- 安装并运行 **PostgreSQL** (建议版本 12+)。
- (可选但推荐) 创建并激活一个 Python 虚拟环境。
  ```bash
  python -m venv venv
  # Windows
  .\venv\Scripts\activate
  # macOS/Linux
  source venv/bin/activate
  ```

#### 2. 安装依赖
在项目根目录下，运行以下命令安装所有必需的 Python 库：
```bash
pip install -r requirements.txt
```

#### 3. 配置数据库与扩展
- 在 PostgreSQL 中创建一个新的数据库（例如，`local_doc_search`）。
- 连接到您刚创建的数据库，并启用 `pg_trgm` 和 `pgroonga` 扩展。您可以使用 `psql` 或任何图形化工具执行以下 SQL 命令：
  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE EXTENSION IF NOT EXISTS pgroonga;
  ```
  > **重要**: PGroonga 可能需要单独安装。请参考 [PGroonga 官方安装文档](https://pgroonga.github.io/install/) 完成在您操作系统上的安装。

#### 4. 配置环境变量
- 在项目根目录下，创建一个名为 `.env` 的文件。
- 复制以下内容到 `.env` 文件中，并根据您的实际情况修改数据库连接信息和文件路径。

  ```env
  # .env

  # ---------------------------------
  # --- 数据库配置 (必须修改) ---
  # ---------------------------------
  # 格式: postgresql://YourUser:YourPassword@YourHost:YourPort/YourDatabase
  DATABASE_URL=postgresql://postgres:your_password@localhost:5432/local_doc_search

  # ---------------------------------
  # --- Flask 配置 (建议修改) ---
  # ---------------------------------
  FLASK_ENV=development
  FLASK_DEBUG=1
  FLASK_SECRET_KEY=a-very-secret-and-long-random-string-for-security

  # ---------------------------------
  # --- 文件类型配置 (按需修改) ---
  # ---------------------------------
  # 支持的所有文件扩展名，用逗号分隔
  SUPPORTED_FILE_TYPES=md,html,htm,pdf,docx,xlsx,pptx,sql,py,txt,log
  # 直接作为 Markdown 处理的文件
  NATIVE_MARKDOWN_TYPES=md
  # 作为纯文本转 Markdown 的文件
  PLAIN_TEXT_TO_MARKDOWN_TYPES=txt
  # 作为代码转 Markdown 的文件 (会添加代码块)
  CODE_TO_MARKDOWN_TYPES=sql,py
  # 作为日志转 Markdown 的文件
  LOG_TO_MARKDOWN_TYPES=log
  # 使用 markitdown 结构化转换的文件
  STRUCTURED_TO_MARKDOWN_TYPES=html,htm,pdf,docx,xlsx,pptx
  ```

#### 5. 初始化数据库
如果您是首次运行，需要初始化数据库表结构。在项目根目录下，运行以下命令：
```bash
# 设置 Flask 应用入口 (仅在当前终端会话中有效)
# Windows (CMD)
set FLASK_APP=run.py
# Windows (PowerShell)
$env:FLASK_APP="run.py"
# macOS/Linux
export FLASK_APP=run.py

# 应用数据库迁移 (将创建所有表和索引)
flask db upgrade
```
> `migrations` 文件夹已包含初始迁移脚本，您无需执行 `init` 或 `migrate` 命令。

## 🚀 如何使用

1.  **启动应用**：
    在项目根目录下运行：
    ```bash
    python run.py
    ```

2.  **访问应用**：
    打开浏览器，访问 `http://127.0.0.1:5000`。

3.  **导入与处理文档**：
    -   点击页面上的“文档转换”链接，或直接访问 `/convert`。
    -   在输入框中填入您想要扫描的本地文件夹的**绝对路径**。
    -   点击“开始转换”按钮，程序将开始在后台扫描和处理文件。您可以在终端查看进度日志。

4.  **搜索文档**：
    -   处理完成后，访问主页 (`/`) 或搜索页 (`/search`)。
    -   在搜索框中输入关键词，即可查找已处理过的文档。

## 🏗️ 项目结构

```
local_document_search/
├── app/                      # Flask 应用核心代码
│   ├── routes/               # 路由蓝图 (视图函数)
│   ├── services/             # 核心业务逻辑 (文件扫描, 转换, 搜索)
│   ├── templates/            # HTML 模板
│   ├── utils/                # 辅助工具函数
│   ├── __init__.py           # 应用工厂函数
│   └── models.py             # SQLAlchemy 数据模型
├── migrations/               # Flask-Migrate 数据库迁移脚本
├── scripts/                  # 辅助脚本 (如重建索引)
├── tests/                    # 单元测试
├── .env                      # 环境变量 (需自行创建)
├── config.py                 # 配置文件
├── requirements.txt          # Python 依赖
└── run.py                    # 应用启动入口
```

## 🤝 贡献

欢迎提交 Pull Requests 或 Issues 来改进这个项目。

## 📄 许可证

本项目采用 MIT 许可证。
