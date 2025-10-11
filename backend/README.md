backend/
├── .env                    # 环境变量文件
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt        # 主依赖
├── requirements-dev.txt    # 开发依赖
├── setup.py                # 项目安装配置
├── README.md
│
├── app/                    # 核心应用代码
│   ├── __init__.py
│   ├── main.py             # 应用入口
│   │
│   ├── api/                # API 路由层
│   │   ├── __init__.py
│   │   ├── v1/             # 版本化路由
│   │   │   ├── __init__.py
│   │   │   ├── users.py
│   │   │   ├── products.py
│   │   │   └── ...         # 其他功能模块
│   │   └── internal/       # 内部API
│   │       ├── health.py
│   │       └── monitoring.py
│   │
│   ├── core/               # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py       # 配置设置
│   │   ├── security.py     # 认证/授权
│   │   └── logging.py      # 日志配置
│   │
│   ├── models/             # 数据库模型
│   │   ├── __init__.py
│   │   ├── base.py         # 基础模型
│   │   ├── user.py
│   │   └── product.py
│   │
│   ├── schemas/            # Pydantic 模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── product.py
│   │   └── response.py     # 通用响应模型
│   │
│   ├── services/           # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── product_service.py
│   │
│   ├── repositories/       # 数据访问层
│   │   ├── __init__.py
│   │   ├── user_repo.py
│   │   └── product_repo.py
│   │
│   ├── dependencies/       # FastAPI 依赖项
│   │   ├── __init__.py
│   │   ├── database.py     # DB 会话依赖
│   │   └── auth.py         # 认证依赖
│   │
│   ├── utils/              # 工具函数
│   │   ├── __init__.py
│   │   ├── email.py
│   │   ├── file_handling.py
│   │   └── pagination.py
│   │
│   ├── db/                 # 数据库管理
│   │   ├── __init__.py
│   │   ├── session.py      # 会话工厂
│   │   └── init_db.py      # 初始化数据
│   │
│   ├── tasks/              # 后台任务
│   │   ├── __init__.py
│   │   └── celery_tasks.py # Celery 任务
│   │
│   └── tests/              # 测试
│       ├── __init__.py
│       ├── conftest.py     # pytest 配置
│       ├── test_api/
│       ├── test_services/
│       └── test_utils/
│
├── migrations/             # 数据库迁移脚本 (Alembic)
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
│
└── scripts/                # 辅助脚本
    ├── prestart.sh         # 启动前脚本
    └── migrate_db.py       # 数据库迁移脚本