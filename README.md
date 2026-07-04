# APCS 選擇題練習平台

以 **Django + PostgreSQL + Bootstrap 5** 建立的 APCS 選擇題線上學習平台，透過 Docker 容器化一鍵啟動。

學生可以進行題目練習、參加考卷測驗、加入班級、複習錯題、收藏重要題目，並查看個人學習統計與弱點分析；教師可以管理題庫、建立考卷、組織班級並追蹤學生學習狀況。

---

## 功能總覽

| 模組 | 功能 |
|---|---|
| 帳號系統 | 學生 / 教師 / 管理員三種角色，登入、註冊、個人資料管理 |
| 題庫管理 | 新增、編輯、刪除題目；依分類、難度、年份、標籤篩選 |
| 題目練習 | 自由練習、隨機練習、錯題複習、收藏練習、弱點練習五種模式 |
| 考卷系統 | 建立考卷並自動產生 6 碼代號，支援倒數計時與自動批改 |
| 班級管理 | 建立班級並自動產生班級代號，指派考卷給班級 |
| 錯題追蹤 | 自動記錄錯題，搭配間隔複習排程（1 / 3 / 7 天） |
| 學習統計 | 個人正確率、分類弱點分析、練習紀錄 |
| 班級統計 | 考卷完成率、班級平均分、每題答對率、成績匯出 CSV |

---

## 技術棧

- **後端**：Python 3.11 / Django 4.2
- **資料庫**：PostgreSQL 15
- **前端**：Bootstrap 5 / Bootstrap Icons / JavaScript
- **容器化**：Docker / Docker Compose
- **工具**：pgAdmin 4、python-decouple、crispy-bootstrap5

---

## 系統需求

| 工具 | 最低版本 |
|---|---|
| Docker Desktop | 4.0+ |
| Git | 任意版本 |

不需要在本機安裝 Python 或 PostgreSQL，全部在 Docker 容器內執行。

---

## 快速啟動

### 1. 取得專案

```bash
git clone <repository-url>
cd apcs-practice-platform
```

### 2. 建立環境設定檔

```bash
cp .env.example .env
```

開啟 `.env`，將 `DJANGO_SECRET_KEY` 改為隨機字串（可用下方指令產生）：

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

`.env` 預設值說明：

```env
DJANGO_SECRET_KEY=your-secret-key-here     # 必須修改
DJANGO_DEBUG=True                           # 開發環境保持 True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_DB=apcs_db
POSTGRES_USER=apcs_user
POSTGRES_PASSWORD=apcs_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=adminpassword
```

### 3. 啟動服務

```bash
docker-compose up --build
```

首次啟動會自動執行：
- 拉取 `postgres:15` 和 `dpage/pgadmin4` 映像檔（約需數分鐘，視網路速度）
- 建置 Django web 映像檔
- 執行 `migrate`（建立所有資料表）
- 收集靜態檔案（`collectstatic`）

### 4. 建立管理員帳號

```bash
docker exec -it codejudge-web-1 python manage.py createsuperuser
```

依提示輸入 `Username`、`Email`、`Password`。系統會自動將 `UserProfile.role` 設為 `admin`，建立完成即可直接使用所有管理功能。

### 5. 開啟瀏覽器

| 服務 | 網址 |
|---|---|
| 平台主站 | http://localhost:8443 |
| Django Admin 後台 | http://localhost:8443/admin |
| pgAdmin 資料庫管理 | http://localhost:5050 |

---

## 服務說明

| 服務 | 容器名稱 | 容器內 Port | 對外 Port | 說明 |
|---|---|---|---|---|
| web | codejudge-web-1 | 8000 | 8443 | Django 主程式 |
| db | codejudge-db-1 | 5432 | 5432 | PostgreSQL 資料庫 |
| pgadmin | codejudge-pgadmin-1 | 80 | 5050 | 資料庫圖形化管理 |

---

## 常用指令

### 容器管理

```bash
# 前景啟動（看即時 log）
docker-compose up --build

# 背景啟動
docker-compose up --build -d

# 停止所有容器
docker-compose down

# 停止並刪除資料庫 volume（資料會清空）
docker-compose down -v

# 查看容器狀態
docker-compose ps

# 查看 web 容器 log
docker logs codejudge-web-1 -f
```

### Django 管理指令

```bash
# 進入容器 shell
docker exec -it codejudge-web-1 bash

# 執行 migration
docker exec codejudge-web-1 python manage.py migrate

# 建立 migration（修改 model 後執行）
docker exec codejudge-web-1 python manage.py makemigrations

# 建立超級管理員（UserProfile.role 會自動設為 admin）
docker exec -it codejudge-web-1 python manage.py createsuperuser

# 收集靜態檔案
docker exec codejudge-web-1 python manage.py collectstatic --noinput

# 進入 Django shell
docker exec -it codejudge-web-1 python manage.py shell
```

### pgAdmin 連線設定

首次登入 http://localhost:5050 後，新增伺服器：

| 欄位 | 值 |
|---|---|
| Host | db |
| Port | 5432 |
| Database | apcs_db |
| Username | apcs_user |
| Password | apcs_password |

---

## 專案目錄結構

```
apcs-practice-platform/
│
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── .env.example
│
├── config/                  # Django 主設定
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── accounts/                # 帳號與角色管理
├── questions/               # 題庫、分類、標籤
├── practice/                # 練習、錯題、收藏、筆記
├── exams/                   # 考卷系統
├── classes/                 # 班級管理
├── dashboard/               # 學習統計
│
├── templates/               # HTML 模板（Bootstrap 5）
└── static/                  # CSS、JS 靜態資源
```

---

## 角色與權限

| 功能 | 學生 | 教師 | 管理員 |
|---|:---:|:---:|:---:|
| 題目練習 | ✅ | ✅ | ✅ |
| 錯題複習 / 收藏 | ✅ | ✅ | ✅ |
| 查看個人成績 | ✅ | ✅ | ✅ |
| 題庫管理（新增/編輯/刪除） | ❌ | ✅ | ✅ |
| 建立考卷 | ❌ | ✅ | ✅ |
| 建立班級 | ❌ | ✅ | ✅ |
| 指派考卷給班級 | ❌ | ✅ | ✅ |
| 查看班級成績統計 | ❌ | ✅ | ✅ |
| Django Admin 後台 | ❌ | ❌ | ✅ |
| 平台設定（Google OAuth 等） | ❌ | ❌ | ✅ |

---

## Google OAuth 登入設定

Google 帳號登入需要先在 Google Cloud Console 建立 OAuth 憑證，設定方式有兩種：

### 方式一：透過前端管理員設定頁面（推薦）

1. 以管理員帳號登入平台
2. 上方「管理」選單 → **平台設定**（或直接前往 http://localhost:8443/dashboard/settings/）
3. 在「Google 帳號登入」區塊填入 Client ID 和 Client Secret，並開啟啟用開關
4. 點「儲存設定」，**立即生效，無需重啟容器**

### 方式二：環境變數（`.env` 檔案）

在 `.env` 填入並重啟容器：

```env
GOOGLE_OAUTH2_CLIENT_ID=你的Client_ID.apps.googleusercontent.com
GOOGLE_OAUTH2_CLIENT_SECRET=你的Client_Secret
```

> **優先順序**：資料庫設定 > 環境變數。若資料庫已設定憑證，環境變數會被忽略。

### 如何取得 Google OAuth 憑證

1. 前往 [Google Cloud Console → 憑證](https://console.cloud.google.com/apis/credentials)
2. 「建立憑證」→「OAuth 用戶端 ID」→ 應用程式類型：**網頁應用程式**
3. 「已授權的重新導向 URI」加入：
   ```
   http://localhost:8443/social-auth/complete/google-oauth2/
   ```
4. 建立後複製 Client ID 與 Client Secret

> **⚠️ 注意**：若 Google OAuth 同意畫面處於「測試」狀態，需在「測試使用者」中加入要登入的 Gmail 帳號。

---

## URL 路徑

```
/                            首頁
/accounts/login/             登入
/accounts/logout/            登出
/accounts/register/          註冊
/accounts/profile/           個人資料

/questions/                  題目列表
/questions/create/           新增題目（教師/管理員）
/questions/<id>/             題目詳情
/questions/<id>/edit/        編輯題目

/practice/start/             選擇練習模式
/practice/random/            隨機練習
/practice/question/<id>/     作答題目
/practice/result/<id>/       作答結果
/practice/wrong/             錯題複習
/practice/favorites/         收藏題目
/practice/weakness/          弱點練習

/exams/                      考卷列表
/exams/create/               建立考卷
/exams/join/                 輸入考卷代號
/exams/session/<id>/         考卷作答
/exams/session/<id>/result/  考卷結果

/classes/                    我的班級
/classes/create/             建立班級
/classes/join/               輸入班級代號
/classes/<id>/               班級詳情

/dashboard/                  個人學習統計
/dashboard/weakness/         弱點分析
/dashboard/history/          練習紀錄
```

---

## 開發注意事項

**修改 model 後**，需重新建立並套用 migration：

```bash
docker exec codejudge-web-1 python manage.py makemigrations
docker exec codejudge-web-1 python manage.py migrate
```

**新增靜態檔案後**，需重新收集：

```bash
docker exec codejudge-web-1 python manage.py collectstatic --noinput
```

**`.env` 不應提交至 git**（已加入 `.gitignore`），請各自在本機建立。

---

## 未來擴充方向

- 支援圖片題目與程式碼語法高亮
- 支援 Markdown 格式題目內容
- REST API 與前後端分離（Vue / React）
- 使用 Nginx + Gunicorn 正式部署
- Redis + Celery 背景任務（學習報告、電子郵件通知）
- 建立班級排行榜與學生學習報告
- 匯入歷屆 APCS 官方題目
