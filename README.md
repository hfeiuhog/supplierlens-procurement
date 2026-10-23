# SupplierLens · 企业采购知识协同平台

基于 [Onyx](https://github.com/onyx-dot-app/onyx) 的采购场景二次开发：让供应商资质、招标要求和人工审查记录形成可追溯的业务流程。

[![Enterprise CI](https://github.com/hfeiuhog/supplierlens-onyx/actions/workflows/enterprise-ci.yml/badge.svg?branch=enterprise)](https://github.com/hfeiuhog/supplierlens-onyx/actions/workflows/enterprise-ci.yml)

## 业务问题与本次实现

企业已有知识库能够回答问题，但采购评审还需要逐项要求、证据有效期、独立复核与审计链。本扩展把这些步骤加入平台后台，避免把模型回答直接当作采购批准。

| 平台已有能力 | 本次新增能力 |
|---|---|
| Onyx 文档连接器、权限过滤检索、问答引用、模型接入 | `/admin/procurement` 审查工作台及后台导航 |
| FastAPI、Next.js、PostgreSQL、OpenSearch、权限体系 | 结构化要求与证据契约、缺项及过期检查 |
| 用户、租户会话与数据库迁移框架 | 幂等建单、双人审批、版本条件更新和追加式审计事件 |

```mermaid
flowchart LR
  A[授权知识库与引用] --> B[采购审查工作台]
  B --> C[证据契约与有效期检查]
  C --> D[作者提交]
  D --> E[另一管理员复核]
  E --> F[事务状态更新与审计事件]
```

核心代码：`backend/onyx/server/manage/procurement/`、`backend/onyx/db/procurement.py`、`web/src/app/admin/procurement/page.tsx`。新增迁移接入上游 Alembic 链；九种语言目录包含对应 UI 键。
审查权限沿用 `FULL_ADMIN_PANEL_ACCESS`，每个私有接口均校验权限；数据库连接沿用租户会话。未改变文档 ACL。当前引用由授权审查人填入，不自动证明引用真实性；自动回查原文是下一阶段集成项。

## 部署与评审

完整上游源代码和历史保留于本 fork。按照 [上游部署说明](README.upstream.md) 部署 CE 基础平台，在维护窗口运行 `backend` 中的 `uv run alembic upgrade head`，随后构建本分支后端和前端镜像。迁移前先备份数据库并核对租户迁移策略。不要把删除审查表作为业务回滚手段。

- [企业实施与验收](enterprise/IMPLEMENTATION.md)
- [验证范围](enterprise/VALIDATION.md) · [数据边界](enterprise/DATA_POLICY.md)
- [上游基线](enterprise/UPSTREAM.json)

## 归属与许可

个人开源二次开发，新增实现使用 AI 辅助。上游平台能力归 Onyx 及其贡献者；本次贡献以固定基线之后的 diff 为准。保留原有 LICENSE、NOTICE 与作者署名。
Onyx 仓库有 CE/EE 授权边界，本次修改位于社区版路径；未修改或解除 EE 的商业授权要求。完整许可见 [LICENSE](LICENSE)。
