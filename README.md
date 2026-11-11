# 投稿審查系統 (Submission and Review System)

本專案是一個基於 **單體式架構 (Monolithic Architecture)** 與 **伺服器端渲染 (Server-Side Rendering, SSR)** 的稿件管理與審查系統。
系統採用 **MVC (Model-View-Controller)** 分層架構，完全使用語意化純 HTML 與 Jinja2 模板渲染，並以「模擬登入 (Mock Login)」機制實現作者與編輯的角色切換與狀態流轉。

---

## 🛠 技術堆疊

- **後端框架**：[FastAPI](https://fastapi.tiangolo.com/) (高效能非同步/同步 API 與 SSR 控制器)
- **伺服器**：[Uvicorn](https://www.uvicorn.org/) (ASGI 伺服器)
- **模板引擎**：[Jinja2](https://palletsprojects.com/p/jinja/) (伺服器端渲染 HTML)
- **表單處理**：`python-multipart` (解析 POST Form 表單資料)
- **資料庫與 ORM**：[PostgreSQL](https://www.postgresql.org/) + [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + `psycopg2-binary`

---

## 📋 系統核心角色與業務狀態機 (State Machine)

### 1. 角色定義
- **作者 (Author)**：管理自己的稿件（新增、編輯、送審、刪除）。
- **編輯 (Editor)**：審核處於「審查中」狀態的稿件（通過、退回）。

### 2. 稿件狀態 (Status)
- **編輯中 (Draft)**：稿件正在撰寫或已被退回，僅作者可見、可修改、可刪除、可送審。
- **審查中 (Under Review)**：稿件已正式送審，作者端鎖定編輯與刪除，編輯端可進行審查。
- **已通過 (Approved)**：稿件已獲得編輯認可通過，流程圓滿結束。

### 3. 狀態流轉規則表

| 操作行為 | 執行角色 | 前置狀態 (Pre-condition) | 目標狀態 (Post-condition) | 說明與約束 |
| :--- | :--- | :--- | :--- | :--- |
| **新增稿件** | 作者 | 無 | **編輯中** | 初始狀態 |
| **編輯稿件** | 作者 | **編輯中** | **編輯中** | 僅能編輯自己的「編輯中」稿件 |
| **刪除稿件** | 作者 | **編輯中** | *(已刪除)* | 非「編輯中」稿件嚴禁刪除 (400 錯誤) |
| **送出投稿** | 作者 | **編輯中** | **審查中** | 轉入編輯審查池，作者無法再變更內容 |
| **審核通過** | 編輯 | **審查中** | **已通過** | 編輯通過該稿件，狀態定稿 |
| **退回修訂** | 編輯 | **審查中** | **編輯中** | 退回給作者，作者可重新編輯與再次投稿 |

---

## 📁 專案結構與職責分工

```text
軟工期中作業/
│
├── venv/                    # 專案獨立虛擬環境 (套件僅安裝於此目錄，不污染全域)
├── requirements.txt         # 系統相依套件清單
├── db.py                    # 資料庫連線、Session 建立與 Base 宣告
├── models.py                # SQLAlchemy ORM Model (User, Manuscript, ManuscriptStatus)
├── crud.py                  # 封裝所有資料庫查詢、新增、更新、刪除操作
├── main.py                  # FastAPI 主程式、MVC 控制器路由與例外處理
├── run.bat                  # Windows 一鍵啟動批次檔 (自動啟用 .\venv)
├── .gitignore               # Git 忽略檔 (已排除 venv/ 與快取)
├── README.md                # 專案完整說明文件
│
└── templates/               # Jinja2 網頁模板目錄 (純語意化 HTML，無任何 CSS)
    ├── index.html           # 模擬登入入口首頁 (角色切換)
    ├── author_dashboard.html# 作者儀表板 (稿件清單、狀態與操作)
    ├── editor_dashboard.html# 編輯儀表板 (待審清單、通過/退回決策)
    ├── manuscript_form.html # 新增/編輯稿件表單
    └── error.html           # 操作錯誤與非法狀態流轉之友善提示頁面
```

---

## ⚙️ 環境安裝與資料庫設定

### 步驟 1：專案專屬虛擬環境與套件 (已在本資料夾建立)

專案已在專案根目錄下建立了專屬虛擬環境 `venv/`，所有相依套件皆已安裝在此，完全不會污染系統的全域環境。

若後續需要重新安裝或更新套件，請在專案目錄下執行：
```powershell
# 啟用虛擬環境
.\venv\Scripts\activate

# 安裝套件
pip install -r requirements.txt
```

### 步驟 2：建立 PostgreSQL 資料庫

請開啟 PostgreSQL 的管理工具（如 `psql` 命令列或 `pgAdmin`），執行下列 SQL 建立專用資料庫：

```sql
CREATE DATABASE manuscript_db;
```

### 步驟 3：修改資料庫連線設定 (`db.py`)

開啟 `db.py`，依據您本地 PostgreSQL 的帳號密碼進行設定：

```python
# db.py
DATABASE_URL = "postgresql://postgres:your_password@localhost:5432/manuscript_db"
```
> **注意**：請將 `your_password` 替換為您在安裝 PostgreSQL 時所設定的實際密碼。

---

## 🚀 專案啟動方式

### 方法 A：Windows 一鍵啟動 (推薦)
直接雙擊執行專案目錄下的：
```bat
run.bat
```

### 方法 B：命令列啟動
在終端機中切換至專案根目錄，執行：
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

啟動後，開啟瀏覽器造訪：
👉 **http://127.0.0.1:8000**

---

## 🧪 完整功能操作與驗證流程

### 1. 模擬登入與角色切換
- 造訪首頁 `http://127.0.0.1:8000`。
- 點選「以『作者 1 (Author ID: 1)』身分登入」，系統會透過 URL 參數進入 `/author/1/dashboard`。

### 2. 作者新增與編輯稿件
1. 在作者 1 儀表板點選「**新增稿件**」。
2. 輸入標題（如：`軟工期中報告初稿`）與內容，點選「**確認新增**」。
3. 頁面將導回作者儀表板，該稿件狀態為 **「編輯中」**。
4. 點選「**編輯內容**」，修改內容後儲存，狀態仍維持 **「編輯中」**。

### 3. 作者送出投稿
1. 在作者儀表板中，針對狀態為「編輯中」的稿件點選「**送出審查**」。
2. 狀態將由 **「編輯中」** 轉換為 **「審查中」**。
3. 此時該稿件的操作按鈕變為「*審查中 (不可編輯與刪除)*」，防止投稿後被任意竄改。

### 4. 編輯審查流程
1. 返回首頁，點選進入「**編輯 (Editor) 審查後台**」 (`/editor/dashboard`)。
2. 剛剛送出的稿件會出現在「**待審查稿件清單 (狀態：審查中)**」中。
3. **測試退回功能**：
   - 點擊「**退回修改 (Return to Draft)**」，稿件狀態轉為 **「編輯中」**，從待審清單移出。
   - 回到作者 1 儀表板，可見該稿件重新解鎖為「編輯中」，作者可重新編輯並再次送審。
4. **測試通過功能**：
   - 作者再次送審後，編輯在待審清單中點擊「**審核通過 (Approved)**」。
   - 稿件狀態變為 **「已通過」**，審查流程正式完成。

### 5. 異常與安全性防護驗證
- **防竄改驗證**：若使用者試圖透過 URL 直接編輯他人稿件（例如以作者 2 身分進入 `/author/2/manuscripts/1/edit`），系統將回傳 **HTTP 403 Forbidden**。
- **非法狀態流轉防護**：若編輯端試圖對非「審查中」的稿件發送 approve/reject，或作者試圖刪除「審查中/已通過」的稿件，系統將回傳 **HTTP 400 Bad Request** 並顯示明確的純 HTML 錯誤提示。

---

## 🔒 嚴格遵守之架構約束說明

1. **純語意化 HTML (無 CSS)**：所有模板（`templates/*.html`）皆僅使用純 HTML 標籤（如 `<h1>`, `<table>`, `<form>`, `<ul>`, `<fieldset>` 等），**完全不含 `<style>` 標籤，亦無任何 `class` 或 `style="..."` 屬性**，方便未來獨立套用 UI 框架（如 Bootstrap、Tailwind）。
2. **模擬登入 (Mock Login)**：不依賴 Session Cookie 或 JWT，以乾淨的 RESTful URL 參數與表單隱藏欄位 (`<input type="hidden">`) 傳遞身分，輕量直觀。
3. **嚴格分層 (MVC)**：
   - **Model (`models.py`, `db.py`)**：資料模型與連線管理。
   - **Data Access Layer (`crud.py`)**：全數封裝資料庫查詢與更新，路由層絕不直接碰觸 ORM Session 邏輯。
   - **Controller (`main.py`)**：請求驗證、狀態轉換檢查與流程調度。
   - **View (`templates/`)**：純 HTML 頁面呈現。
