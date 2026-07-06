# AI Office Agent — 更新报告

**生成时间**：2026-07-07 03:03  
**当前版本**：v1.5.2  
**自上次提交以来的变更范围**：v1.4.0 → v1.5.2

---

## 一、版本总览

| 版本 | 主题 | 状态 |
|------|------|------|
| v1.4.0 | 扫描生命周期闭环修复（消除自动扫描卡顿 + 统一扫描入口） | ✅ |
| v1.4.1 | 扫描结果中心 UI 微调 + 文件整理预览对话框修复 | ✅ |
| v1.4.2 | 图纸识别跨点位污染修复 | ✅ |
| v1.5.0 | 唯一归属模型（Single Ownership Model） | ✅ |
| v1.5.1 | 预算识别规则修复（初版） | ✅ |
| v1.5.2 | 预算识别规则修正（用户纠正版） | ✅ |

---

## 二、核心成果

### 1. v1.4.0 — 扫描生命周期闭环修复

**问题**：打开项目自动触发全量扫描导致 UI 严重卡顿；扫描入口分散重复。

**解决方案**：
- 新建 `core/scan_controller.py` 作为唯一扫描入口
- 打开项目仅加载缓存（从 `scan_result` 表读取），0 扫描 0 卡顿
- 新增 `scan_result` + `file_ownership` 数据库表持久化扫描结果
- 完整 5 步扫描生命周期闭环

### 2. v1.4.1 — UI 微调

- 删除重复的「重新扫描」按钮，仅保留「执行扫描」
- 建议列改为可拖动调整宽度
- 新增 `OrganizePreviewDialog`：可调整大小、支持滚动、显示完整文件整理预览

### 3. v1.4.2 — 图纸跨点位污染修复

- `global_match_point` 目录匹配从 fuzzy 改为精确相等
- 新增 `_drawing_belongs_to_point()` 图纸归属校验

### 4. v1.5.0 — 唯一归属模型（核心重构）

**问题**：一个文件被多个点位同时识别，图纸/预算归属混乱。

**解决方案**：实现两阶段唯一归属模型
- **阶段1 候选生成**：文件 → 所有点位打分
- **阶段2 唯一归属决策**：Top1 + 阈值 0.75 + 冲突检测
- **图纸特殊规则**：DWG/DXF/BAK/PDF 必须 stem 精确匹配，禁止 fuzzy
- 新建 `core/ownership.py`（~350 行）作为唯一归属决策的单一事实源
- 改造 `build_scan_results` / `match_points_from_index` / `_try_match_from_sandbox` / 文件整理全部使用 ownership 模型

### 5. v1.5.1 + v1.5.2 — 预算识别规则修正

**问题**：含"预算"关键词的 PDF 被误判为"其他"；龙泉湾点位的预算文件被误判为"其他"。

**最终规则（v1.5.2 用户纠正版）**：
1. 文件名含预算关键词（不限扩展名）→ 预算
   - 关键词：预算/概算/造价/报价/清单/cost/estimate/budget
   - 业务补充：CPMS结构数据/嘉陵版/安全事故防范/安全生产费依据
2. 表格类扩展名 + 文件名 stem 去除数字后 == 点位名 → 预算
   - 如「龙泉湾202606121457.xlsx」去数字 = "龙泉湾" = 点位名

---

## 三、新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `ai_office_agent/core/scan_controller.py` | ~350 | 统一扫描生命周期控制器 |
| `ai_office_agent/core/ownership.py` | ~380 | 唯一归属模型核心模块 |
| `tests/test_v1_5_ownership.py` | ~280 | 唯一归属专项测试（11 项） |

## 四、修改文件

| 文件 | 关键改动 |
|------|----------|
| `ai_office_agent/core/scan_result.py` | `build_scan_results` 改用 `assign_ownership`，移除 `global_match_point` |
| `ai_office_agent/core/scanner.py` | `match_points_from_index` 重写为 ownership 模型 |
| `ai_office_agent/core/file_organizer.py` | 新增 `build_organize_plan_from_ownership`；预算识别规则修正 |
| `ai_office_agent/core/file_index.py` | `global_match_point` 目录匹配改为精确相等 |
| `ai_office_agent/ui/widgets/pages/scan_center_page.py` | 删除重复按钮；建议列可拖动；`OrganizePreviewDialog`；文件整理用 ownership |
| `ai_office_agent/ui/widgets/pages/project_detail_page.py` | `_try_match_from_sandbox` 改用 ownership |
| `ai_office_agent/ui/widgets/content_area.py` | `show_project_detail` 改用 `load_project_cached` |
| `ai_office_agent/app.py` | 启动时初始化 `scan_result` + `file_ownership` 表 |
| `tests/test_v1_3_smoke.py` | 新增跨点位图纸过滤测试 |

## 五、新增数据库表

| 表 | 用途 |
|----|------|
| `scan_result` | 持久化扫描结果缓存（项目打开时直接读取，0 延迟） |
| `file_ownership` | 文件→点位唯一归属记录 |

## 六、测试验证

| 测试套件 | 结果 |
|----------|------|
| `test_v1_3_smoke.py` | 9/9 ✅ |
| `test_v1_5_ownership.py` | 11/11 ✅ |
| Lint 诊断 | 0 ✅ |

---

## 七、Git 提交指南

当前环境未安装 git 命令行工具。请按以下步骤手动提交：

### 方式1：安装 Git 后提交

```powershell
# 1. 安装 Git（如未安装）
winget install Git.Git

# 2. 进入项目目录
cd D:\AI-Office-Agent

# 3. 查看变更
git status
git diff --stat

# 4. 暂存所有变更
git add -A

# 5. 提交
git commit -m "v1.5.2: 唯一归属模型 + 预算识别修正

- v1.4.0: 扫描生命周期闭环修复（消除自动扫描卡顿）
- v1.4.1: UI 微调（删除重复按钮、建议列可拖动、预览对话框）
- v1.4.2: 图纸跨点位污染修复
- v1.5.0: 唯一归属模型（两阶段决策 + 图纸stem精确匹配）
- v1.5.1: 预算识别规则修复（初版）
- v1.5.2: 预算识别规则修正（用户纠正版）

新增: core/scan_controller.py, core/ownership.py
修改: scan_result/scanner/file_organizer/file_index/scan_center_page等
测试: 20/20 全部通过"

# 6. 推送（如已配置远程仓库）
git push origin main
```

### 方式2：使用 GitHub Desktop

1. 打开 GitHub Desktop
2. 选择 `D:\AI-Office-Agent` 仓库
3. 查看变更文件列表
4. 填写 commit message（见上方）
5. 点击 Commit to main
6. 点击 Push origin

### 方式3：使用 VS Code Git

1. 打开 VS Code
2. 进入 Source Control 面板（Ctrl+Shift+G）
3. 暂存所有变更
4. 填写 commit message
5. 点击提交
6. 同步更改

---

## 八、变更文件清单（git add 参考）

```
新增:
  ai_office_agent/core/scan_controller.py
  ai_office_agent/core/ownership.py
  tests/test_v1_5_ownership.py

修改:
  ai_office_agent/__init__.py
  ai_office_agent/app.py
  ai_office_agent/core/file_index.py
  ai_office_agent/core/file_organizer.py
  ai_office_agent/core/scan_result.py
  ai_office_agent/core/scanner.py
  ai_office_agent/ui/widgets/content_area.py
  ai_office_agent/ui/widgets/pages/project_detail_page.py
  ai_office_agent/ui/widgets/pages/scan_center_page.py
  tests/test_v1_3_smoke.py
  docs/CHANGELOG.md
  docs/ProjectMemory.md
  docs/Roadmap.md
```
