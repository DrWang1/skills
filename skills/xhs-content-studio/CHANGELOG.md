# Changelog

本文件记录 xhs-content-studio 的变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [1.1.0] - 2026-09-16

### Changed

- 面向开源整理：补充 `license: MIT`、`CHANGELOG.md` 与元数据（`created` / `updated`）。
- 文档明确发布底座为**第三方**项目 `DeliciousBuding/xiaohongshu-skill`，从上游安装、本技能不分发其代码。

## [1.0.0] - 2026-09-15

### Added

- 首个版本：把素材（图片 / 链接 / 文字）整理成小红书笔记（标题、正文、标签、配图 / 封面），
  先预览、**用户确认后才发布**；发布通过 `xiaohongshu-skill` 底座完成。
- `scripts/ingest.py`：素材汇总（仅标准库）。
- `scripts/publish.py`：带确认门的发布封装（默认不触碰浏览器，`--confirm` 才发布）。
- `scripts/render_cover.py`：Markdown → 小红书配图 / 封面（复用底座环境）。
- `references/writing-guide.md`：小红书写作指南。
