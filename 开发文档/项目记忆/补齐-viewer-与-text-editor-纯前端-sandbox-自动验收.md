---
name: "补齐 viewer 与 text-editor 纯前端 sandbox 自动验收"
type: "task"
tags: [sandbox, frontend-build, release-gate, viewer, 20260702]
agent: "codex-viewer-sandbox-worker"
created: "2026-07-02T15:23:22.236018+00:00"
---

# 我是谁
codex-viewer-sandbox-worker

# 干了什么
为 doc-viewer、image-viewer、pdf-viewer、ppt-viewer、text-editor 补齐独立 Vite sandbox：package.json、package-lock.json、vite.config.ts、index.html、runtime.config.json、src/main.ts、src/App.vue。所有写入限定在对应 modules/{key}/sandbox/ 下。

# 关键细节
这些 viewer 入口依赖框架共享 viewer-shell，因此 sandbox vite.config.ts 显式提供 @ -> frontend/src 只读 alias，同时 @modules -> modules。pdf-viewer 额外声明 pdfjs-dist，并在 sandbox vite.config.ts 将裸导入 pdfjs-dist 显式解析到本 sandbox 的 node_modules/pdfjs-dist/build/pdf.mjs，避免借主 frontend node_modules。

# 验证了什么
分别在 5 个 sandbox 执行 npm install + npm run build，全部通过。随后执行 python3.14 dev_toolkit/module_sandbox_matrix.py --check，结果 34 modules / 34 pass / 0 fail / 0 skip；目标 5 个模块均为 frontend PASS。

# 残留风险
开工前工作树已有大量其他脏改，本次未触碰、未回滚。dist/ 与 node_modules/ 是构建/安装产物且被 ignore。

# 关联 commit
未提交。
