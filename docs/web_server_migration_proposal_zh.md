---
status: proposed
type: plan
owner: human
created: 2026-05-19
last_reviewed: 2026-06-11
expires: none
superseded_by: null
---

# 量化交易系統 Web Server 遷移企劃書

日期：2026-05-19  
提案目的：將目前 `quant_strategy` 專案遷移到可遠端存取、可長時間運行、可監控與可備份的 Web Server 架構，先支援 Dashboard、Backtest Viewer、資料查詢、Demo/Shadow 觀察流程。  
重要聲明：本提案不代表策略已可正式 live trading。Live trading 必須完成既有 gate：Historical Backtest、Walk-forward/CPCV、OKX Demo、Shadow、Half-size Live 與人工核准。

## 1. 決策摘要

建議採用「兩階段遷移」：

1. 第一期採用單台 VPS + Docker Compose，上線 Dashboard、Backtest Viewer、TimescaleDB、Redis、Prometheus/Grafana 與每日備份。
2. 第二期在 Demo/Shadow 穩定後，升級成 App Server + Managed PostgreSQL/TimescaleDB + Managed Redis，降低資料庫維運與資料遺失風險。

推薦決策：

- 若目標是快速上線內部 dashboard 與 demo server：選方案 A。
- 若目標是讓 demo/shadow 長時間穩定運行，並降低維運風險：選方案 B。
- 不建議一開始導入 Kubernetes，因為目前專案規模與團隊維運需求尚未達到 Kubernetes 的複雜度門檻。

## 2. 目前系統現況

目前專案已具備 Web Server 遷移基礎：

- FastAPI API server：提供 `/api/live`、`/api/backtest`、`/api/config`、`/api/data`
- 靜態前端 Dashboard：位於 `frontend/`
- 回測與結果 artifact：`backtesting/`、`results/`
- TimescaleDB/PostgreSQL：OHLCV、funding、backtest artifacts
- Redis：position snapshot 與 crash recovery
- Docker Compose：已有 `okx-quant`、`timescaledb`、`redis`、`prometheus`、`grafana`
- 監控與告警：Prometheus/Grafana 與 Telegram alert 已有基礎，但 production 前需補齊啟動與安全設定

主要缺口：

- API 未設定 `API_KEY` 時會停用 API authentication，正式部署必須強制設定。
- Docker Compose 目前 demo engine、web server、資料匯入服務角色仍需清楚拆分。
- Prometheus scrape target 已配置，但 engine 端 metrics server 啟動需確認或補強。
- `.env`、OKX credentials、Telegram credentials、DB password 需要改用部署環境 secret 管理。
- 尚未建立正式備份與還原演練流程。

## 3. 目標架構

第一期目標架構：

```text
Cloud VM / VPS
  Reverse Proxy with TLS
  FastAPI + Frontend container
  Demo or backtest-only service
  TimescaleDB container
  Redis container
  Prometheus + Grafana
  Persistent volumes for data/results/logs
  Daily backup to object storage or offsite storage
```

第二期目標架構：

```text
App VM or container service
  FastAPI + Frontend
  Demo/Shadow engine service

Managed PostgreSQL with TimescaleDB support
Managed Redis or Valkey
Object storage for backups and exported artifacts
Monitoring and alerting
Static outbound IP for OKX API key binding
```

## 4. 方案比較與成本估算

估算基準：

- 幣別：USD，並以 1 USD 約等於 31.5 TWD 粗估。
- 不含稅、網域、工程人力、交易成本與額外資料傳輸費。
- 實際月費會依地區、備份保留天數、儲存容量與流量調整。

| 方案 | 適用情境 | 月費估算 USD | 月費估算 TWD | 優點 | 主要風險 |
|---|---:|---:|---:|---|---|
| A. 單台 VPS 自管全部 | MVP、內部 Dashboard、短期 Demo | 25-40 | 790-1,260 | 最低成本、最快落地、貼近現有 Docker Compose | DB、Redis、備份、升級都需自行維運 |
| B. VPS + Managed DB/Redis | 長時間 Demo/Shadow、降低資料風險 | 60-100 | 1,890-3,150 | 資料庫備份與穩定性較好，維運負擔低 | 成本高於方案 A，仍需管理 App server |
| C. AWS Lightsail 自管或半代管 | 公司偏好 AWS、生態整合 | 55-90 | 1,730-2,840 | 固定價、靜態 IP、AWS 生態成熟 | 亞洲區價格較高，完整監控與備份仍需設計 |
| D. Render PaaS | 只需要 Web dashboard/backtest viewer | 60-120 | 1,890-3,780 | 部署、TLS、rollback、log 管理簡單 | 長時間交易 engine、固定出站 IP、TimescaleDB 限制需驗證 |
| E. Kubernetes | 多服務、多環境、多團隊 | 150+ | 4,725+ | 最強擴展與隔離能力 | 目前過度設計，維運成本高 |

## 5. 推薦方案

推薦採用方案 B 作為最終目標，並用方案 A 作為第一期落地方式。

理由：

- 目前 repo 已有 Docker Compose，方案 A 可以最快完成第一版部署。
- Trading/backtest 資料是核心資產，長期應避免將 TimescaleDB 只放在單台 VPS。
- Managed PostgreSQL 若支援 TimescaleDB extension，可降低備份、升級與資料遺失風險。
- Redis 目前用於 snapshot/crash recovery，長跑 demo/shadow 時也適合轉成 managed service。

建議核准預算：

- 第一階段：每月 40 USD 以內，執行 2-4 週。
- 第二階段：每月 100 USD 以內，視 demo/shadow 觀察結果升級。
- 預留一次性工程時間：5-10 個工作天，依是否納入 CI/CD、備份演練與安全 hardening 調整。

## 6. 實施時程

| 階段 | 時間 | 交付成果 |
|---|---:|---|
| 0. 部署前檢查 | 0.5-1 天 | 確認 config、secret、API auth、OKX key 權限、部署區域 |
| 1. Web/Dashboard 上線 | 1-2 天 | HTTPS dashboard、FastAPI、backtest viewer、基本存取控制 |
| 2. DB 與 artifact 生產化 | 2-4 天 | TimescaleDB migration、artifact storage、每日備份、restore drill |
| 3. Demo/Shadow 服務拆分 | 3-5 天 | web、engine、ingestor、monitoring service profile 分離 |
| 4. 監控與告警 | 2-3 天 | Prometheus/Grafana、Telegram alert、healthcheck、log retention |
| 5. 長跑觀察 | 4-6 週以上 | Demo 4 週、Shadow 2 週、策略與 execution quality review |

## 7. 安全與風控要求

正式部署前必須完成：

- `API_KEY` 必填，避免 API authentication 被關閉。
- OKX API key 禁用 withdraw 權限，並綁定 server static IP。
- `.env` 不進 Git、不進 Docker image，改由環境變數或 secret manager 注入。
- 對外只開 HTTPS 443；DB、Redis、Grafana admin 不直接公開。
- Grafana、Prometheus、API docs 需加存取控制或僅限 VPN/內網。
- 每日 DB backup，至少保留 7-30 天。
- 至少完成一次 restore drill，確認備份真的可還原。
- Live trading 入口維持人工確認，不得由 Web UI 一鍵啟動。

## 8. 主要風險與緩解方式

| 風險 | 影響 | 緩解方式 |
|---|---|---|
| DB 資料遺失 | 回測、行情、artifact 遺失 | 每日備份、offsite copy、restore drill |
| API key 外洩 | 帳戶與資金風險 | 禁用 withdraw、綁定 IP、secret 管理、最小權限 |
| 系統長時間運行不穩 | Demo/Shadow 中斷，資料缺口 | healthcheck、restart policy、Telegram alert、監控面板 |
| 成本失控 | 預算超支 | 設定 billing alert，先用小規模 VPS，逐步升級 |
| 誤啟 live trading | 真實資金風險 | 保留 config gate、手動確認、部署環境分離 |
| TimescaleDB extension 限制 | migration 失敗或功能受限 | 選型前先跑 migration smoke test |

## 9. 驗收標準

第一期驗收：

- Dashboard 可透過 HTTPS 存取。
- `/api/backtest`、`/api/config`、`/api/data` 基本功能可用。
- TimescaleDB migration 可成功執行。
- Backtest artifact 可寫入並可由前端讀取。
- Grafana 可看到基礎系統狀態或 engine metrics。
- DB backup 可成功產生，並完成一次還原測試。
- `.env`、OKX key、DB password 未出現在 Git 或 image layer。

第二期驗收：

- Demo engine 可連續運行 4 週並保留 logs/artifacts。
- Shadow engine 可連續運行 2 週並產出 calibration logs。
- Telegram alert 與 kill switch 流程可用。
- 系統重啟後 position snapshot 與核心狀態可恢復。
- Claude 完成策略與 execution quality risk review。
- User/manager 明確核准後，才可進入 half-size live planning。

## 10. 請主管決策事項

需要核准：

1. 第一階段是否採用 VPS + Docker Compose。
2. 每月預算上限：建議第一階段 40 USD，第二階段 100 USD。
3. 部署區域：建議 Singapore 或 Tokyo，兼顧台灣存取與 OKX latency。
4. 是否需要公司網域與 VPN/Zero Trust 存取。
5. 是否同意第二階段改用 managed DB/Redis。
6. 是否將此部署定位為 demo/shadow 觀察環境，而非 live trading production。

## 11. 建議結論

建議先核准第一階段，採用 VPS + Docker Compose，在 1-2 週內交付可遠端使用的 Dashboard、Backtest Viewer、TimescaleDB、Redis、監控與備份流程。  
若 Demo/Shadow 觀察穩定，第二階段再升級至 Managed DB/Redis，並建立更完整的部署、備份、監控與權限治理。  
在所有 validation gates 通過前，不應將本部署視為正式 live trading 系統。

## 12. 參考來源

- DigitalOcean Droplet pricing: https://www.digitalocean.com/pricing/droplets
- DigitalOcean Managed Databases pricing: https://www.digitalocean.com/pricing/managed-databases
- DigitalOcean PostgreSQL supported extensions: https://docs.digitalocean.com/products/databases/postgresql/details/supported-extensions/
- AWS Lightsail pricing: https://aws.amazon.com/lightsail/pricing/
- Render pricing: https://render.com/pricing
- Render PostgreSQL extensions: https://render.com/docs/postgresql-extensions
- 專案既有部署與 collaboration gate：`docker/docker-compose.yml`、`docs/ai_collaboration.md`、`docs/ARCHITECTURE.md`
