# API Test 前后端分离版

## 技术栈
- 后端：FastAPI + Requests
- 前端：React + Vite + Ant Design

## 当前结构
- `backend/app.py`：接口入口与路由编排
- `backend/services.py`：账号查询、批量测活、重复检测等业务逻辑
- `backend/clients.py`：第三方平台访问客户端
- `backend/store.py`：会话存储
- `backend/schemas.py`：请求模型
- `frontend/src/App.tsx`：页面状态编排
- `frontend/src/components/`：登录区、工具栏、表格、弹窗组件
- `frontend/src/utils/account.ts`：账号视图工具函数

## 启动方式

### 1. 启动后端
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 2. 启动前端
```bash
cd frontend
npm install
npm run dev
```

前端默认请求后端地址：`http://127.0.0.1:8000`

## 当前能力
- 登录：支持 `Sub2API` / `CLIProxy`
- 账号列表：支持后端筛选、分页、刷新
- 批量测活：支持全部测活、选中测活、异常结果处理
- 重复清理：支持检测重复并按分组删除
- 删除能力：支持单个删除、批量删除、异常账号批量删除