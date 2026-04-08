# ERP IMS — 庫存管理系統 SaaS

基於 **FastAPI + SQLite3** 的輕量級進銷存管理系統，支援多用戶帳號（管理員 / 一般員工），適合中小型企業自架部署。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116-green)](https://fastapi.tiangolo.com/)

---

## 功能特色

| 模組 | 功能 |
|------|------|
| 商品管理 | 商品 CRUD、SKU、單位、再訂購點警示 |
| 庫存管理 | 多倉庫庫存水位、原子性異動紀錄 |
| 採購單 | 建立採購單 → 提交 → 部分/全額收貨，自動更新庫存 |
| 供應商 | 供應商資料維護 |
| 異動紀錄 | 完整稽核日誌（入庫/出庫/盤點調整/倉庫轉移） |
| 儀表板 | 低庫存警示、開放採購單、近期異動 |
| 用戶管理 | 多用戶帳號，admin / staff 兩種角色 |

---

## 系統截圖

### 登入

![登入頁面](docs/screenshots/01_login.png)

### 儀表板

總覽低庫存警示、開放採購單數量、近期異動紀錄。

![儀表板](docs/screenshots/02_dashboard.png)

### 商品管理

支援搜尋、分頁，可查看各倉庫庫存水位。

![商品列表](docs/screenshots/03_products_list.png)

### 新增商品

設定 SKU、單位、成本、再訂購點。

![新增商品](docs/screenshots/04_product_new.png)

### 庫存異動紀錄

完整稽核日誌，支援分頁與篩選。

![庫存異動](docs/screenshots/05_movements_list.png)

### 新增庫存異動

支援入庫、出庫、盤點調增/調減、倉庫轉移。

![新增異動](docs/screenshots/06_movement_new.png)

### 供應商管理

![供應商列表](docs/screenshots/07_suppliers_list.png)

### 新增供應商

![新增供應商](docs/screenshots/08_supplier_new.png)

### 倉庫管理

支援多倉庫，每個商品在各倉庫各自追蹤庫存。

![倉庫管理](docs/screenshots/09_warehouses_list.png)

### 採購單

狀態流程：草稿 → 已提交 → 部分收貨 → 完成收貨。

![採購單列表](docs/screenshots/10_po_list.png)

### 新增採購單

選擇供應商、倉庫，逐行新增商品品項。

![新增採購單](docs/screenshots/11_po_new.png)

### 用戶管理

管理員可新增/編輯/停用用戶，指定角色。

![用戶管理](docs/screenshots/12_users_list.png)

---

## 快速開始

### 環境需求

- Python 3.12+

### 安裝

```bash
git clone https://github.com/stanwu/saas-erp-ims.git
cd saas-erp-ims

# 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 安裝依賴
pip install -r requirements.txt

# 啟動伺服器
uvicorn app.main:app --reload
```

開啟瀏覽器前往 **http://localhost:8000/login**

### 預設帳號

| 帳號 | 密碼 | 角色 |
|------|------|------|
| `admin` | `admin12345` | 管理員 |

> **重要：** 首次登入後請立即至「用戶管理」修改預設密碼。

### 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `ERP_IMS_SECRET_KEY` | `dev-secret-key` | Session 加密金鑰（生產環境必須更換） |
| `ERP_IMS_DATABASE_URL` | `sqlite:///erp_ims.db` | 資料庫連線字串 |
| `ERP_IMS_ADMIN_USERNAME` | `admin` | 初始管理員帳號 |
| `ERP_IMS_ADMIN_EMAIL` | `admin@example.com` | 初始管理員 Email |
| `ERP_IMS_ADMIN_PASSWORD` | `admin12345` | 初始管理員密碼 |

---

## 操作流程

### 初始設定

1. **建立倉庫**：前往「倉庫管理」→「新增倉庫」
2. **建立商品**：前往「商品管理」→「新增商品」，填入 SKU、名稱、單位、成本、再訂購點
3. **建立供應商**：前往「供應商」→「新增供應商」

### 採購入庫

1. 前往「採購單」→「新增採購單」
2. 選擇供應商、目標倉庫，新增商品明細（數量、單價）
3. 儲存後狀態為「草稿」，確認後點選「提交採購單」
4. 收到貨品後點選「收貨」，輸入實際收到數量
5. 系統自動建立入庫異動，更新對應倉庫的庫存水位

### 手動庫存異動

前往「新增異動」，選擇：

| 類型 | 說明 |
|------|------|
| 入庫 | 貨品進入倉庫 |
| 出庫 | 貨品離開倉庫（銷售/領料） |
| 盤點調增 | 盤點後實際數量多於系統 |
| 盤點調減 | 盤點後實際數量少於系統 |
| 倉庫轉入 | 從其他倉庫收到貨品 |
| 倉庫轉出 | 移送貨品至其他倉庫 |

### 低庫存警示

當商品在任一倉庫的庫存低於「再訂購點」時，儀表板會顯示警示。

---

## 資料架構

```
users               — 用戶帳號（admin / staff）
products            — 商品（SKU、名稱、成本、再訂購點）
warehouses          — 倉庫
stock_levels        — 各商品在各倉庫的即時庫存（product × warehouse）
inventory_movements — 不可變更的庫存異動稽核日誌
suppliers           — 供應商
purchase_orders     — 採購單（draft→submitted→partial→received）
purchase_order_lines — 採購單明細
```

**核心設計原則**：`stock_levels.quantity` 與 `inventory_movements` 的 INSERT 在同一個資料庫 transaction 中完成，確保資料一致性。

---

## 開發

```bash
# 執行測試
pytest tests/ -v
```

---

## License

[MIT](LICENSE) © 2026 stan
