| 日期 | 错误 | 根因 | 修复 |
| --- | --- | --- | --- |
| 2026-05-09 | `python scripts/score_pipeline.py --help` 报 `ModuleNotFoundError: No module named 'scripts.jd_analyzer'` | 以文件路径直跑脚本时，`sys.path[0]` 是 `scripts/`，项目根目录未进入导入路径，导致 `from scripts...` 绝对导入失败 | 在 `scripts/score_pipeline.py` 入口导入前，当 `__package__` 为空时把项目根目录加入 `sys.path` |
