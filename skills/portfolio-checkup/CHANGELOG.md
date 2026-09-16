# Changelog

本文件记录 portfolio-checkup 的变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [1.1.0] - 2026-09-16

### Changed

- **示例数据改为合成数据**（`references/example-*.json`）：标的名称、代码、账户标识全部替换为虚构值，
  避免真实持仓/账户信息随技能分发而外泄；报告结构、字段口径保持不变，仍可直接用于演示与自测。
- `SKILL.md` 中去掉含用户名的绝对路径（`/Users/<user>` → `~`）。

### Added

- 本 `CHANGELOG.md`，纳入自研技能规范（`skill-creator/scripts/validate.py --strict`）。

## [1.0.0] - 2026-09-15

### Added

- 首个版本：对一组标的做**估值 / 基本面 / 资金 / 技术**四维打分，输出单页 HTML「持仓体检报告」，
  含保留 / 观察 / 减仓判断、相关性矩阵、组合结构（集中度 / 杠杆 / 穿透敞口）分析与加减仓优先级。
- 支持单只标的的四维快速体检，以及多账户叠加分析的前置确认流程。
