# AI Office Agent - 项目记忆

> 本文件是项目的"长期记忆"，记录项目的整体状态与关键决策。
> 每次开发前必读。每完成一个任务必须更新。
> 不依赖聊天记录，所有长期信息以此文件为准。

## 1. 项目概况

- **项目名称**：AI Office Agent
- **目标用户**：通信设计人员
- **运行平台**：Windows 11 桌面软件
- **我的角色**：程序员（执行者），不擅自修改需求

## 2. 技术栈

- Python 3.14
- PySide6（已安装 6.11.1）
- SQLite
- 分层清晰的包结构，代码注释完整，便于维护

## 3. 开发纪律（长期规则）

> 详见 `DevelopmentRules.md`。摘要：

1. 项目所有记忆保存在 `docs/` 文件夹，不依赖聊天记录。
2. 每次开发前必须先读 `docs/ProjectMemory.md`、`docs/CHANGELOG.md`、`docs/Roadmap.md`、`docs/DevelopmentRules.md`。
3. 每完成一个任务即停止开发。
4. 停止前必须更新 `ProjectMemory.md` 与 `CHANGELOG.md`。
5. 需求变化时同步更新 `ProjectMemory.md`。

## 4. 工作约定

- **增量开发**：每次只完成一个任务，等用户确认后再继续。
- **不提前实现**：不擅自实现用户未要求的功能（文件整理、AI 等暂不做）。
- **不擅自改需求**：严格按用户给定的结构与字段开发。
- **真实数据优先**：自 v0.4.0 起首次接入真实数据，列表/导入不再使用模拟数据；后续功能默认基于真实库表开发。

## 5. 当前版本

**v1.5.6**

## 6. 当前开发阶段

**v1.5.6 预算识别修复与 UI 优化 — 开发完成** ✅

### 预算识别修复

- 删除 `"清单"` 关键词，避免 `设备清单` 等非预算文件误判。
- stem_no_digits 精确匹配 → prefix 匹配（`point_norm.startswith(stem_no_digits + "-")`），解决点位名含后缀描述时漏判。
- `_score_file_to_point` 重构为 4 层分层评分（Tier 1~4），解决文件名含点位A但路径在点位B目录下的所有权冲突。
- 反向排斥逻辑：stem 含其他已知点位名或含 `分纤箱扩容` 但当前点位名不含 → 不归属当前点位。
- `OwnershipResult` 新增 `unassigned_budget_files` 字段，标记关键词预算但无法确定点位的文件。
- `build_organize_plan`：用户选择「设计文件」目录时不再嵌套 `设计文件/设计文件/`。

### UI 优化

- 「扫描结果中心」→「扫描中心」。
- 「文件整理预览」+「执行整理」合并为「整理文件」按钮（预览→确认→执行）。
- 扫描中心新增项目选择下拉框，直接选择已导入项目。
- 窗口横向缩放修复（StatCard 130px→100px + MainWindow.setMinimumSize）。
- 项目选择器移出 info_bar，成为标题下方独立横幅。

### v1.5.6 修改模块

- `core/ownership.py` — 关键词清理、stem matching、4 层评分、反向排斥、unassigned_budget_files
- `core/file_organizer.py` — 关键词清理、stem matching、「设计文件」目录修复
- `core/scan_controller.py` — 序列化补字段
- `ui/widgets/pages/scan_center_page.py` — 重命名、按钮合并、项目选择器、StatCard 宽度、布局调整
- `ui/widgets/nav_tree.py` — 命名
- `ui/widgets/content_area.py` — 刷新项目列表
- `ui/main_window.py` — 最小窗口尺寸
- `tests/test_v1_5_ownership.py` — 新增 2 项测试

**v1.5.5 散落文件识别与整理闭环 — 开发完成** ✅

### 核心修复：识别选择目录下的散落文件并整理到标准点位目录

- 扫描继续递归遍历用户选择的项目文件夹下所有文件。
- 归属判断从原来的「文件名/父目录必须等于点位名」扩展为：
  - 文件名 stem
  - 父目录
  - 全部祖先目录片段
  - 项目相对路径文本
- 泛分类目录名（图纸/预算/其他文件/other/cad/pdf/资料 等）不再作为点位身份证据。
- 图纸类文件仍走严格证据，不恢复 fuzzy，避免跨点位图纸污染回归。
- 预算类 PDF 不被简单当成图纸严格拒绝，可按预算资料参与归属，最终分类为预算。
- 未识别到归属文件时的建议文案不再误导为「未在文件系统中找到对应文件夹；请创建点位文件夹并导入图纸」，改为提示检查文件名/路径或人工确认。
- 有归属文件时建议提示可执行整理创建标准点位文件夹并分类。
- 文件整理预览/执行继续读取 Scan Session 中的归属结果，目标目录使用 `scan_path`，不重新扫描、不重新归属。

### v1.5.5 修改模块

- `core/ownership.py` — 扩展归属证据、泛分类目录过滤、预算 PDF 跳过图纸严格规则。
- `core/scan_result.py` — 调整未匹配/已匹配建议文案。
- `core/file_organizer.py` — `_drawing_belongs_to_point` 与 ownership 严格证据对齐；新增预算类文件判断。
- `tests/test_v1_5_ownership.py` — 新增散落文件识别、泛分类目录不作为证据、预算 PDF 可归属测试。
- `tests/test_scan_session.py` — 新增建议文案与整理目标目录测试。

**v1.5.3 扫描结果生命周期管理 — 开发完成** ✅

### 核心修复：Scan Session + 禁止重复扫描

- 一次用户主动扫描完成后，生成当前项目 Scan Session。
- Scan Session 保存 `project_id`、`scan_path`、`scan_time`、文件索引、唯一归属结果和 ScanResult。
- 文件整理预览、文件整理执行、点位详情、分类统计全部读取当前扫描结果，禁止内部再次调用 scanner。
- 文件整理预览无有效 Scan Session 时提示「请先执行扫描」，不会自动扫描。
- 扫描按钮生命周期：初次为「执行扫描」，有有效 Scan Session 后显示「重新扫描」。
- 修改扫描目录会使当前 Scan Session 失效，等待用户主动重新扫描。
- 保持 v1.5 唯一归属模型：`assign_ownership` 只在显式扫描入口执行，整理预览/执行只消费已保存归属结果。

### v1.5.3 修改模块

- `core/scan_controller.py` — 新增 `scan_session` 表及保存/读取/失效辅助函数；`run_scan` 持久化扫描工件。
- `core/scan_result.py` — 新增 `ScanBuildOutput` / `build_scan_results_with_artifacts`，保留旧 `build_scan_results` 兼容入口。
- `core/file_organizer.py` — 新增 `build_organize_plan_from_scan_session`，不扫描、不重新归属。
- `ui/widgets/pages/scan_center_page.py` — 文件整理预览/执行改为读取 Scan Session；调整按钮文案与目录变更失效逻辑。
- `ui/widgets/pages/project_detail_page.py` — 遗留沙盒扫描函数改为不触发扫描。
- `tests/test_scan_session.py` — 新增 Scan Session 生命周期测试。

**v1.5.0 唯一归属模型（Single Ownership Model）— 开发完成** ✅

### 核心重构：两阶段唯一归属模型

- 阶段1 候选生成：文件→所有点位打分
- 阶段2 唯一归属决策：Top1 + 阈值 0.75 + 冲突检测
- 图纸特殊规则：DWG/DXF/BAK/PDF 必须 stem 精确匹配

### v1.5.0 新增模块
- `core/ownership.py`（~350 行）——唯一归属模型核心
- `tests/test_v1_5_ownership.py`——9 项专项测试

### v1.5.0 修改模块
- `core/scan_result.py` — `build_scan_results` 改用 `assign_ownership`，移除 `global_match_point`
- `core/file_organizer.py` — 新增 `build_organize_plan_from_ownership`
- `ui/widgets/pages/scan_center_page.py` — 文件整理预览/执行改用 ownership 模型

**v1.4.2 图纸识别跨点位污染修复 — 开发完成** ✅

### v1.4.2 修改模块
- `core/file_index.py` — `global_match_point` 目录匹配从 fuzzy 改为精确相等；目录内文件范围从递归改为仅直接文件
- `core/file_organizer.py` — 新增 `_drawing_belongs_to_point()` 归属校验函数；`classify_file` 对直接图纸类型加入归属校验；`build_organize_plan` 的 CAD 索引仅使用本点位图纸文件
- `tests/test_v1_3_smoke.py` — 新增 `test_organize_plan_no_cross_point_drawing` 跨点位污染测试

**v1.4.1 扫描结果中心 UI 微调 — 开发完成** ✅

### v1.4.1 修改模块
- `ui/widgets/pages/scan_center_page.py`：
  - 删除「重新扫描」按钮，仅保留「执行扫描」按钮
  - 建议列从 `Stretch` 改为 `Interactive`，允许拖动列宽
  - 确认列 `Fixed` 宽度
  - 表格显式启用水平滚动条，避免建议列被压缩
  - 新增 `OrganizePreviewDialog`：可调整大小、支持滚动、显示完整文件整理预览信息，不再截断冲突文件/点位/分类明细

**v1.4.0 扫描生命周期闭环修复 — 开发完成** ✅

### 问题背景

1. **打开项目自动扫描导致卡顿**：`content_area.show_project_detail()` → `scan_center_page.load_project()` → `_load_and_scan()` → `build_scan_results()` → 全量文件扫描，导致打开项目时 UI 严重卡顿。
2. **扫描入口重复冲突**：`project_detail_page._load_points_from_db()` 调用 `_try_match_from_sandbox()` 执行全量扫描；`scan_center_page` 也有独立扫描入口。两个页面各自触发扫描，入口分散且重复。

### 解决方案

- 创建 `core/scan_controller.py` 作为**唯一扫描入口**，管理完整扫描生命周期（5 步）
- 打开项目**仅加载缓存**（从 `scan_result` 表读取），**禁止触发扫描器**
- 仅在 `scan_center_page` 的「扫描」按钮中调用 `ScanController.run_scan()`

### 扫描生命周期（5 步闭环）

```
用户点击「扫描」按钮
    ↓
ScanController.run_scan(project_id, path)
    → Step1: 读取 point_dictionary + scan_match_history（历史确认优先）
    → Step2: scanner.scan_project()（文件系统扫描）
    → Step3: matcher.match_file_to_points()（唯一归属匹配）
    → Step4: 生成 ScanResultItem 列表 + ScanResultSummary
    → Step5: 写入 scan_result 表 + file_ownership 表 + scan_match_history 表
    ↓
刷新 UI
```

### v1.4.0 新增模块

- `core/scan_controller.py`（~350 行）——统一扫描生命周期控制器：
  - `init_scan_result_tables(conn)` — 创建 `scan_result` 和 `file_ownership` 表（含索引）
  - `clear_scan_results()` / `clear_file_ownership()` — 重新扫描前清理
  - `save_scan_results()` — 批量写入 ScanResultItem 到 `scan_result` 表
  - `save_file_ownership_batch()` — 批量写入唯一文件归属到 `file_ownership` 表
  - `load_scan_results_from_db()` — 从数据库读取缓存结果（**不触发扫描**）
  - `ScanController` 类：
    - `load_cached_results()` — 仅加载缓存（项目打开时使用）
    - `run_scan()` — 完整 5 步扫描生命周期（**唯一扫描入口**）

### v1.4.0 修改模块

- `core/scan_result.py` — `ScanResultItem.to_dict()` 新增 `standard_point_name` / `match_folder` / `match_score` 字段；`from_dict()` 新增 `match_method` 字段
- `ui/widgets/pages/scan_center_page.py`：
  - 新增 `load_project_cached()` — 仅从 `scan_result` 表加载缓存（不扫描）
  - `_load_and_scan()` 改用 `ScanController.run_scan()` 替代直接 `build_scan_results()`
  - 新增 `_rebuild_items_from_dict()` 辅助方法
- `ui/widgets/pages/project_detail_page.py`：
  - `_load_points_from_db()` 改为从 `scan_result` 表读取缓存（移除 `_try_match_from_sandbox()` 扫描触发）
  - 无缓存时回退默认「无」状态
- `ui/widgets/content_area.py`：
  - `show_project_detail()` 改为调用 `load_project_cached()`（仅加载缓存，不扫描）
- `app.py`：
  - 启动时调用 `init_scan_result_tables(conn)` 初始化新表

### 数据库新增表

- **`scan_result` 表**：持久化扫描结果缓存
  - 字段：id / project_id / standard_point_name / match_folder / match_score / match_status / match_method / cad_status / budget_status / cad_file_count / budget_file_count / suggestion / confirmed / scanned_at / file_list(JSON)
- **`file_ownership` 表**：文件→点位唯一归属记录
  - 字段：id / project_id / file_path(UNIQUE) / point_id / standard_point_name / match_score / is_conflict

### 正确交互流程

```
进入项目 → load_project_cached()（从 scan_result 表读缓存，0 扫描，0 卡顿）
    ↓
用户在 scan_center_page 点击「扫描」按钮
    ↓
ScanController.run_scan()（5 步闭环 → 写入 DB）
    ↓
刷新 UI
```

### 禁止行为

- ❌ `on_project_open → scan_project()` — 打开项目时绝对禁止触发扫描
- ❌ `project_detail_page._try_match_from_sandbox()` — 详情页禁止扫描
- ❌ 只读不写（scan → 无 DB 写入）— 扫描必须闭环写入数据库
- ❌ 多个扫描入口 — 只有 `ScanController.run_scan()` 一个入口

### v1.3.1 修改模块（保留记录）

- `core/matcher.py` — 新增 `match_file_to_points()`（file → all points → Top1 Winner）
- `core/scanner.py` — `match_points_from_index` 重写为唯一归属 + 冲突检测（返回 3-tuple）
- `core/scan_result.py` — ScanResultItem 新增 file_owner_point_id/match_confidence；Summary 新增 conflict_files
- `ui/widgets/pages/project_detail_page.py` — 适配新 3-tuple 返回值

**v1.3 新增模块**：
- `core/file_organizer.py`（320+ 行）——文件自动整理引擎
- `tests/test_v1_3_smoke.py` — 8 项 v1.3 专项测试

**v1.3 修改模块**：
- `ui/widgets/pages/scan_center_page.py` — 新增「文件整理预览」+「执行整理」按钮

**v1.2.3 新增模块**：
- `config/region_profile_2026_km.json` — 昆明区县语义归一化配置（7 活跃区县 + 10+ 别名）
- `core/region_profile.py` — 区县归一化（normalize/is_active） + 白名单过滤
- `core/file_index.py` — 全量文件索引扫描引擎（FileEntry/DirEntry/FileIndex）
- `tests/test_v1_2_3_smoke.py` — 8 项 v1.2.3 专项测试

**v1.2.3 修改模块**：
- `core/normalizer.py` — 新增 for_matching()（match_name）+ for_filesystem_path()（filesystem_name）
- `core/matcher.py` — `match_strings` 统一使用 for_matching() 标准化
- `core/scanner.py` — 新增 scan_with_file_index() + match_points_from_index() + 区县过滤
- `core/scan_result.py` — `build_scan_results` 切换 FileIndex + 区县归一化 + 非负责区县过滤；ScanResultSummary 新增 completed_points/completion_rate；全局缓存 _project_summaries
- `ui/widgets/pages/project_detail_page.py` — `_try_match_from_sandbox` 切换 FileIndex；`_load_points_from_db` 加区县归一化/过滤
- `ui/widgets/pages/project_management_page.py` — 删除区县数量列（9→8列）；`_fetch_project_stats` 改用 ScanResultSummary 缓存；点位/完成率实时更新

**下一阶段：v1.3 — 规模表版本比较（增量更新）**

已完成：
- ✅ v1.0 ~ v1.2.1 全部功能（规模表导入、扫描结果中心、匹配引擎等）
- ✅ **v1.2.1 Patch 修复**：
  - ✅ Bug 1：动态字段 QLineEdit 文字绘制区域被压缩（setMinimumHeight(32)）
  - ✅ Bug 2：导入完成后闪退——信号槽线程亲和性违反（闭包→实例方法+QueuedConnection）
- ✅ **v1.2.2 扫描结果人工确认**：
  - ✅ 人工确认：结果列表增加"确认"按钮列，状态切换"未确认"/"已确认"
  - ✅ 重新匹配：RematchDialog 列出候选目录，NOT_FOUND/MULTIPLE_MATCH/PARTIAL_MATCH 可重新选择
  - ✅ 学习机制：确认结果保存 scan_match_history 表，下次扫描优先使用历史确认
  - ✅ 批量确认：全部确认 / 批量确认已匹配项
  - ✅ 导出 Excel：7 列（序号/标准点位/实际目录/CAD/预算/匹配率/确认状态/建议/匹配方式）
  - ✅ 统计卡片新增"已确认"指标
  - ✅ 新增 `core/scan_match_history_repository.py`（300+ 行完整 CRUD）

已完成：
- ✅ v1.0 阶段1：标准点位字典系统 (point_dictionary 表 + Excel 导入)
- ✅ v1.0 阶段2-4（沙盒模式）：文件扫描 + 匹配 + 状态计算
- ✅ v1.0 **架构升级**：扫描器从"平铺点位"升级为"项目资料 → 图纸根目录 → 点位"三级识别
- ✅ **v1.1 规模表智能识别引擎**：
  - ✅ Sheet 自动识别（多 Sheet 评分排序 + 用户选择）
  - ✅ 字段智能识别（关键词匹配 + 用户修正）
  - ✅ 区县自动识别
  - ✅ 点位生成规则（单字段 / 起点+终点拼接，按项目类型自动判断）
  - ✅ 动态字段（固定字段外全部自动归为动态列）
  - ✅ 项目配置 Project Profile（保存所有映射，下次复用）
- ✅ **v1.1.1 匹配引擎升级**：
  - ✅ 新增 `core/normalizer.py`：统一标准化（NFKC + 全角符号 + 中文括号/标点统一）
  - ✅ 新增 `core/matcher.py`：统一匹配引擎（RapidFuzz WRatio + partial_ratio）
  - ✅ 6 个模块升级为 matcher + normalizer
  - ✅ 删除手动 lowercase+in 等重复算法
  - ✅ 匹配置信阈值预留（exact=95/contains=85/fuzzy=70）
- ✅ **v1.2.0 扫描结果中心**：
  - ✅ 新增 `core/scan_result.py` — 统一扫描结果数据模型（ScanResultItem / ScanResultSummary / MatchStatus / build_scan_results）
  - ✅ 新增 `ui/widgets/pages/scan_center_page.py` — 扫描结果中心页面（统计卡片 + 结果列表 + 详情预览 + 筛选 + 重新扫描）
  - ✅ 预留接口：RenamePreviewInterface / FolderBuilderInterface / HealthScoreInterface / AISuggestionInterface
- ✅ **v1.2.1 规模表导入优化**：
  - ✅ Sheet 评分重构：综合考虑 Sheet 名称（最高优先 45%）+ 表格结构 35% + 字段关键词辅助 20%
  - ✅ 多行表头识别（二次修复，正确处理三层合并表头）：
    - 区分**横向合并**（同行）与**纵向合并**（同列）两种语义
    - 横向合并覆盖单元格 → 继承同行锚点值作为表头层
    - 纵向合并覆盖单元格 → 锚点值已在上层加入，跳过
    - 支持任意层数组合（如"线路部分-光缆线路设计长度-新建架空"）
  - ✅ 动态字段改为手动添加：默认仅区县+点位名称，用户点击「＋ 添加字段」手动选择
  - ✅ 修复导入崩溃：增强异常捕获，安全线程清理 _cleanup_thread
  - ✅ 真实规模表验证：昆明2025数字家庭项目「项目建设规模表」63列×482行正确识别
- ✅ **v1.2.1 BugFix**：
  - ✅ Bug 1：动态字段映射 QLineEdit 输入框不可见 → 设置最小宽度 + 尺寸策略 + 行高
  - ✅ Bug 2：确认导入后程序闪退 → 线程清理重构（非阻塞 quit + finished 信号回调，移除阻塞 wait/terminate）

**v1.2.2 新增模块**：
- `core/scan_match_history_repository.py` — scan_match_history 表完整 CRUD

**v1.2.2 修改模块**：
- `core/scan_result.py` — ScanResultItem/Summary 新增 confirmed/match_method/confirmed_count
- `ui/widgets/pages/scan_center_page.py` — 重写（人工确认+重新匹配+批量+导出+学习机制，800+ 行）
- `app.py` — 启动初始化 scan_match_history 表
- `tests/test_gui_smoke.py` — v1.2.2 架构校验
- `tests/test_import_smoke.py` — 新增 scan_match_history CRUD 测试

**v1.2.1-patch 修改模块**：
- `ui/widgets/scale_table_wizard.py` — `_add_dynamic_field`：QLineEdit/QComboBox `setMinimumHeight(32)` 修复文字绘制区域被压缩（Bug 1）
- `ui/widgets/pages/project_detail_page.py` — `_run_scale_import` 重写：闭包→实例方法 + QueuedConnection 修复线程亲和性违反（Bug 2），新增 `_on_import_progress` / `_on_import_succeeded` / `_on_import_failed` / `_on_import_cancel` 实例方法

**v1.2.1 BugFix 修改模块**：
- `ui/widgets/scale_table_wizard.py` — `_add_dynamic_field`：QLineEdit 尺寸策略 + 行高（Bug 1）
- `ui/widgets/pages/project_detail_page.py` — `_run_scale_import` 重写清理流程（Bug 2）：
  `_cleanup_thread` 拆为 `_request_thread_quit`（非阻塞）+ `_on_import_thread_finished`（finished 信号回调）
- `tests/test_gui_smoke.py` — 架构校验更新（新方法名）

**v1.2.1 修改模块**：
- `core/scale_table_engine.py` — 重写（Sheet 名称评分 _score_sheet_name / 表格结构评分 _score_table_structure / 多行表头 _build_merged_lookup + _detect_header_region + _build_composite_headers / 动态字段默认空）
- `ui/widgets/scale_table_wizard.py` — 重写（Step 3 改为动态字段手动添加/删除/修改 / 合并 Step 3 规则到 Step 2）
- `ui/widgets/pages/project_detail_page.py` — 增强 _run_scale_import 异常处理 + 新增 _cleanup_thread 安全线程清理
- `data_import/scale_import_worker.py` — _do_run_import 双保险异常保护
- `data_import/excel_reader.py` — 空表头占位从 __col_x__ 改为 列N

**v1.2.0 新增模块**：
- `core/scan_result.py` — 统一扫描结果模型（ScanResultItem / ScanResultSummary / MatchStatus / build_scan_results）
- `ui/widgets/pages/scan_center_page.py` — 扫描结果中心页面（700+ 行）

**系统架构**：

```
Excel（规模表，多 Sheet）
    ↓ read_all_sheets + detect_best_sheet
Sheet 自动识别（评分排序 + 用户选择/记忆）
    ↓ ScaleTableWizard 四步向导
字段智能识别 + 区县识别 + 点位规则 + 预览
    ↓ ScaleImportWorker 后台导入
标准点位字典（point_dictionary 表，含 dynamic_data JSON）
    ↓
沙盒文件系统扫描（core/scanner.py）
    ↓
自动匹配 + 状态计算（match_score / 图纸 / 预算）
    ↓
UI 实时展示（project_detail_page，固定 5 列 + 动态列）
    ↓
Project Profile（project_profiles 表，保存映射配置）
```

**v1.1 新增模块**：
- `core/scale_table_engine.py` — 纯逻辑识别引擎（Sheet 评分、字段匹配、点位规则、动态字段）
- `core/project_profile_repository.py` — project_profiles 表 CRUD
- `data_import/scale_import_worker.py` — 规模表后台导入 Worker
- `ui/widgets/scale_table_wizard.py` — 四步导入向导对话框
- `tests/test_v1_1_smoke.py` — v1.1 冒烟测试

**v1.1 修改模块**：
- `core/projects_repository.py` — point_dictionary 升级 v1.1.0（新增 dynamic_data 列）
- `ui/widgets/pages/project_detail_page.py` — 接入 ScaleTableWizard + 动态列展示
- `app.py` — 启动时初始化 project_profiles 表
- `tests/test_gui_smoke.py` — 架构校验更新至 v1.1.0

**下一阶段：v1.2 — 规模表版本比较（增量更新）**

> 已预留接口，本次不实现。功能：新增/删除/修改点位增量更新。

## 7. 已完成功能清单

### 框架基础（v0.1.0）

- 标准项目目录结构
- 主入口 `run.py`，分层包结构
- 配置管理：`config/settings.json`（自动生成）
- 数据库初始化代码：`core/database.py`（仅连接管理，暂不建表）
- 日志系统：`utils/logger.py`（控制台 + 文件）
- 主窗口、左侧树形导航、右侧内容区域骨架

### 导航与页面切换骨架（v0.2.0）

- Windows11 风格 QSS（`ui/theme.py`）
- 左侧 QTreeWidget 严格按需求结构构建：
  - 📁 项目管理 → 社区 / 集客 / 接入段 / 设备 / 管道 / 城域网 / 机房配套
  - 🤖 AI助手（占位）
  - ⚙ 设置（占位）
- 右侧 QStackedWidget 承载 9 个独立页面
- 点击导航叶子节点 → 发信号 → 切换对应页面
- 每个页面独立文件，均继承 `BasePage`，当前显示标题占位
- 分组节点（项目管理）点击不切换页面

### 项目管理页面 UI（v0.3.0，仅界面）

- `project_management_page.py` 提供核心 UI，7 个类型页各自继承并复用
- 顶部工具栏：导入总体项目表 / 新增项目 / 刷新 / 搜索框
- 项目列表 QTableWidget，9 列：项目名称 / 项目编号 / 项目类型 / 年份 / 区县数量 / 点位数量 / 完成率 / 状态 / 最后更新时间
- 5 条模拟数据；数值列（年份/区县数/点位数/完成率）用 `NumericItem` 按数值排序
- 整行单选、表头点击排序、交替行底色、最后列吸边
- 双击项目行仅打印日志，不进入下一页
- 按钮/搜索暂未绑定行为（本阶段不含业务逻辑）

### 数值列排序修复（v0.3.1）

- `NumericItem` 不再调用 `super().__lt__()`（PySide6 下会无限递归 → 段错误）
- 数值改存 Python 实例属性 `_sortable_value`，避免 `data(EditRole)` 取回显示文本
- 已验证年份/完成率/点位升降序数值正确

### 总体项目表 Excel 导入（v0.4.0，首次接入真实数据）

- 新增 `core/projects_repository.py`：projects 表建表、按类型清空、批量插入、
  按类型查询、计数；统一类型转换。
- 新增 `data_import/excel_reader.py`：openpyxl 只读读取 + 表头动态识别。
- 新增 `data_import/import_worker.py`：`ImportWorker(QObject)` 两段式导入。
- 新增 `ui/widgets/field_mapping_dialog.py`：字段映射对话框。
- 改造 `project_management_page.py`：导入全流程编排，列表改为从库读取。
- v0.5.0 已重构此架构（见下）。详细列表见 CHANGELOG。

### 项目管理架构调整（v0.5.0，全局唯一导入口 + 类型分流）

> **架构变化原因**：v0.4.0 中 7 个分类页各自带「导入总体项目表」按钮，
> 但总体项目表是**一个**文件、内含**多种**类型的项目，让每个分类页都
> 能导入会造成：(1) 导入口分散，用户易混淆；(2) 同一文件需导入 7 次；
> (3) 各分类页导入时只清自己类型，跨类型数据无法一起替换。
> 故调整为：**全局唯一导入口**（项目管理总入口页）+ **导入按类型列自动分流**。

- 新增 `core/project_categories.py`：7 类别 + 别名→类别分流单一事实源。
  分流规则（先精确后子串匹配）：
  - 社区、数字家庭 → 社区
  - 集客、专线 → 集客
  - 管道 → 管道
  - 设备 → 设备
  - 接入段 → 接入段
  - 优化、输线路工程 → 城域网
  - 配套 → 机房配套
- `project_management_page.py` 拆分为两个基类：
  - `ProjectOverviewPage`（总入口页）：**全局唯一**含「导入总体项目表」+
    「新增项目」按钮，展示全部项目总览。
  - `ProjectCategoryPage`（分类展示页，7 个）：仅刷新 + 搜索 + 双击编辑
    project_type；**无导入/新增按钮**。
- 新增 `ui/widgets/pages/project_overview_page.py`：总入口页入口类。
- `import_worker.py` 重构：构造去掉 project_type；run_import 按「项目类型列」
  逐行 `resolve_category` 分流；导入为**全量替换**（先清空 7 类再插入）；
  无法识别类型的行跳过并回传统计；succeeded 信号改为 `(inserted, skipped)`。
- `projects_repository.py`：
  - `insert_projects` 每行自带 project_type（不再由调用方统一指定）。
  - 新增 `clear_projects_by_categories`（多类别批量清空，供全量替换）。
  - 新增 `update_project_type`（修改单条归属类别 + 刷新 updated_at）。
  - 新增 `fetch_all_projects`（总览页用）。
- 导航 `nav_tree.py`：「📁 项目管理」分组节点点击进入总入口页
  （page key="project_overview"），默认页改为总入口页。
- `content_area.py`：新增总入口页注册；把 7 个分类页引用注入总入口页，
  导入成功后联动刷新各分类页。总页面数 10（总入口+7 分类+AI+设置）。
- 7 个分类页（community/enterprise/access/equipment/pipeline/metro/facility）
  全部改为继承 `ProjectCategoryPage`。
- 测试三套全部更新并通过：
  - `test_import_smoke.py`：类别分流 + 仓储新方法 + worker 分流逻辑（5 入库/1 跳过）
  - `test_gui_smoke.py`：10 页、总入口有导入按钮、7 分类页无导入按钮、分组节点切换
  - `test_import_e2e.py`：总入口导入 7 行多类型→分流到 5 类、总览刷新、分类页无导入口

### 项目详情页面（基础结构）（v0.7.0）

- 新增 `ui/widgets/pages/project_detail_page.py`：项目详情页（只读基础结构）。
  - 页头标题动态为「项目名称（项目编码）」+ 「返回项目列表」按钮
  - 左侧 QTreeWidget 结构树：项目 → 项目整体资料 / 区县列表（空）/ 点位列表（空）
  - 右侧默认显示「项目概览」表单：项目名称 / 编码 / 类型 / 年份 / 状态，全部只读
  - `load_project(id)` 按 id 从 projects 表查询单条并渲染
- `projects_repository.py` 新增 `fetch_project_by_id(conn, id)`（详情页数据来源）
- `content_area.py`：注册详情页（page key=project_detail）；新增 `show_project_detail(id)`
  载入并切换；详情页「返回」按钮 → switch_to("all_projects")；全部项目页注入
  打开详情回调。总页面数 11。
- `project_management_page.py`：全部项目页双击项目行 → 调用注入回调打开详情
  （项目 id 存第 0 列 UserRole）；新增 `set_open_detail_handler` 注入入口
- 测试三套更新并通过：
  - `test_import_smoke.py`：增加 fetch_project_by_id 校验
  - `test_gui_smoke.py`：总页面数 11、详情页注册（返回按钮/结构树/概览字段）、
    全部项目页已注入详情回调
  - `test_import_e2e.py`：未变，确认详情页引入不影响导入分流链路

### 项目详情页 UI 结构调整（v0.8.0，删树 / 概略+资料横向 / 点位列表+筛选）

> **调整原因**：v0.7.0 详情页用左侧结构树（项目→区县→点位）承载层级，但业务上
> 区县/点位应作为可筛选的扁平表格呈现，且需「图纸状态/预算状态」列与动态列扩展；
> 树结构与这些需求冲突。故删除全部树结构，改为：顶部页头 → 概览卡与整体资料面板
> 横向并列 → 筛选栏 → 点位列表。仅改 UI 层。

- `ui/widgets/pages/project_detail_page.py` 重写（无树）：
  - `ProjectDetailPage`：页头（标题+返回按钮）→ 横向面板（左概览卡 / 右整体资料）→
    筛选栏 → 点位列表
  - `PointListTable(QTableWidget)`：固定 5 列（序号/区县/点位名称/图纸状态/预算状态）
    + `set_dynamic_columns` 动态列机制（追加在固定列后）；`load_points` 渲染
  - `ProjectDocumentsPanel(QFrame)`：项目整体资料面板，分类 PDF/Word/Excel/其他资料/
    点位文件夹以外的文件夹（本版占位，不解析文件）
  - `PointFilterBar(QWidget)`：区县下拉 + 点位名称搜索 + 图纸状态 + 预算状态，
    `filter_changed` 信号，组合条件
  - 模块级纯函数 `judge_drawing_status(has_cad, has_pdf)` / `judge_budget_status(has_budget_folder)`：
    严格按需求定义状态规则（图纸仅判 CAD；预算判文件夹存在与否），本版不接文件系统
- `ui/theme.py`：补充概览卡/资料面板/面板标题/占位计数 QSS（Windows11 风格）
- 测试更新并通过：
  - `test_gui_smoke.py`：详情页无树、含返回按钮/概览字段/资料面板/筛选栏/点位表 5 固定列、
    筛选栏含 4 个控件
  - `test_import_smoke.py` / `test_import_e2e.py`：未变，确认 UI 重构不影响导入链路

### 项目详情页 UI 交互优化（v0.9.0，布局比例 + 全分类双击 + 明细导入展示）

> **调整原因**：v0.8.0 点位列表占比过小、入口仅在全部项目页、且无明细导入入口。
> 本次只修 UI 与交互入口，不改业务逻辑/数据库结构。

- 布局比例：概览卡+资料面板外层改为 `QSizePolicy.Fixed` 紧凑靠上固定高度，
  点位列表 `stretch=1` 占据剩余纵向空间（≥50% 屏幕高度，为核心区域）
- 去重标题：详情页页头不再动态显示「项目名称+编码」（概览卡已有），固定为
  BasePage 静态「项目详情」标题；`_render_overview`/`_clear_overview` 不再改 `title_label`
- 全分类双击入口：`ProjectCategoryPage` 加 `_open_detail_handler` + `set_open_detail_handler`，
  行 id 存第 0 列 UserRole，双击调用回调（与全部项目页共用同一详情页）；
  `content_area` 给全部项目页 + 7 分类页统一注入 `show_project_detail`
- 明细导入展示：详情页页头加「导入项目明细表」按钮（返回按钮旁，default 高亮）；
  `_on_import_detail_clicked` 选 .xlsx → 复用 `excel_reader.read_sheet` 基础读取 →
  `_build_points_from_rows` 按表头关键词粗匹配区县/点位名称，其余列作动态列展示，
  图纸/预算状态本版无文件来源→判为「无」；不写库、不做映射对话框
- 测试更新并通过：
  - `test_gui_smoke.py`：详情页含 `import_detail_btn`；7 分类页均注入详情回调
  - `test_import_smoke.py` / `test_import_e2e.py`：未变，确认调整不影响导入链路

### 项目详情页 UI 微调（v0.9.1，点位明细表占半页）

> **调整原因**：v0.9.0 点位列表实际占比约 1/3（实测 0.36），未达"半页"。
> 本次仅调点表占比，不改动其他任何内容。

- `ui/widgets/pages/project_detail_page.py`：
  - `_setup_overview_and_documents`：上方面板加 `setMaximumHeight(210)`
    （= 资料面板内容下限 180 + 内边距 30，保证 5 项分类完整显示不裁切）
  - 新增 `resizeEvent` 重写：动态 `point_table.setMinimumHeight(self.height() // 2)`，
    任意窗口尺寸下点位表稳定占详情页半页
- 实测（真实主窗口 1280×800）：点表 398/796 = **0.500**；多尺寸 0.499-0.500
- 资料面板内容完整未裁切；概览卡/资料面板/筛选栏/按钮均未改动
- 三套冒烟测试全部通过

## 8. 目录结构

```
D:\AI-Office-Agent\
├─ run.py                          # 启动入口
├─ requirements.txt                # PySide6、openpyxl
├─ README.md
├─ .gitignore
├─ docs/                           # 项目记忆文档（本规则核心）
├─ tests/                          # 冒烟与端到端测试
│   ├─ test_import_smoke.py        # 类别分流/Excel 读取/仓库(含迁移)/worker 逻辑
│   ├─ test_gui_smoke.py           # GUI 启动 + 架构校验（v1.2.0 扫描中心验证）
│   ├─ test_import_e2e.py          # 端到端分流导入冒烟测试
│   └─ test_v1_1_smoke.py          # v1.1.0 引擎+配置+升级冒烟测试
├─ config/
│   └─ settings.json               # 应用配置
├─ data/                           # 运行时 SQLite 数据库
│   └─ ai_office_agent.db          # projects / point_dictionary / project_profiles
├─ logs/                           # 运行时日志（自动生成）
└─ ai_office_agent/                # 主包
    ├─ __init__.py                 # __version__ = "1.2.0"
    ├─ app.py                      # 应用入口与生命周期（v1.1.0: 启动时初始化 project_profiles）
    ├─ config.py                   # 配置加载/保存
    ├─ core/
    │   ├─ database.py             # SQLite 连接管理（含 open_db_connection 静态方法）
    │   ├─ projects_repository.py  # projects/point_dictionary 表（v1.1.0: dynamic_data 列）
    │   ├─ project_categories.py   # 7 类别 + 别名→类别分流（单一事实源）
    │   ├─ scanner.py              # 沙盒文件系统扫描（三级识别架构）
    │   ├─ normalizer.py           # v1.1.1 新增：统一标准化
    │   ├─ matcher.py              # v1.1.1 新增：统一匹配引擎（RapidFuzz）
    │   ├─ scan_result.py          # v1.2.0 新增：统一扫描结果模型
    │   ├─ scan_controller.py      # v1.4.0 新增：统一扫描生命周期控制器
    │   ├─ scale_table_engine.py   # v1.1.0 新增：规模表智能识别引擎（纯逻辑）
    │   └─ project_profile_repository.py  # v1.1.0 新增：project_profiles 表 CRUD
    ├─ data_import/                # Excel 导入数据包
    │   ├─ __init__.py
    │   ├─ excel_reader.py         # openpyxl 读取 + 表头动态识别
    │   ├─ import_worker.py        # 总体项目表导入 Worker
    │   └─ scale_import_worker.py  # v1.1.0 新增：规模表导入 Worker
    ├─ ui/
    │   ├─ theme.py                # Windows11 风格 QSS
    │   ├─ main_window.py          # 主窗口
    │   └─ widgets/
    │       ├─ nav_tree.py         # 树形导航（含"全部项目"+"扫描结果中心"节点）
    │       ├─ content_area.py     # 内容区域（12 页注册）
    │       ├─ field_mapping_dialog.py   # 字段映射对话框（5 字段）
    │       ├─ scale_table_wizard.py     # v1.1.0 新增：规模表导入向导（4 步）
    │       └─ pages/              # 页面包
    │           ├─ base_page.py
    │           ├─ project_management_page.py  # 全部项目页 + 分类展示页两个基类
    │           ├─ project_all_page.py         # 全部项目页入口类
    │           ├─ project_detail_page.py      # 项目详情页（v1.1.0 动态列+向导）
    │           ├─ scan_center_page.py         # v1.2.0 新增：扫描结果中心（700+ 行）
    │           ├─ community_page.py 等 7 个   # 分类展示页（只读）
    │           ├─ ai_assistant_page.py
    │           └─ settings_page.py
    └─ utils/
        └─ logger.py               # 日志工具
```

## 9. 关键设计

- **导航 → 页面切换**：`NavTree.page_requested(str)` 信号 → `MainWindow` 连接 → `ContentArea.switch_to(key)`。页面标识用字符串常量。
- **页面键**：all_projects / community / enterprise / access / equipment / pipeline / metro / facility / project_detail / ai_assistant / settings。
- **配置**：`AppConfig` dataclass + `config/settings.json`，缺失自动生成，损坏回退默认值。`AppConfig` 由 `app.py` → `MainWindow` → `ContentArea` → 各项目页逐层传递，页面据此访问数据库。
- **项目管理页面复用**：v0.6.0 拆为两个基类——`ProjectAllPage`（全部项目，唯一总入口与编辑入口，展示全部项目）与 `ProjectCategoryPage`（分类展示，纯只读）；7 个分类页继承后者，全部项目页继承前者。
- **数值列排序**：`NumericItem` 将数值存入实例属性，覆盖 `__lt__` 按数值比较，避免字符串字典序错误；不调用 `super().__lt__()` 防段错误。
- **总体项目表导入**（v0.6.0）：
  - 唯一导入口在「全部项目」页；worker 按 Excel「项目类型列」分流，无值/无法识别→project_type=NULL（只显示在全部项目）。
  - 导入为**全量替换**：`DELETE FROM projects` 再插入（总体表是唯一主数据源）。
  - 只跳过缺项目名称的行；succeeded 信号 `(inserted, skipped_no_name)`。
  - 字段映射 5 项：项目名称/编码（必填）+ 年份/项目类型/状态（可选）；无区县/点位映射。
  - 两段式后台线程、无参信号触发、`QueuedConnection` 回主线程、worker 线程本地连接。
  - 关闭进度对话框前断开 `canceled` 信号，避免 close() 误判取消。
- **project_type 下拉编辑**（v0.6.0）：全部项目页 project_type 列用 QComboBox（未分类+7 类），`currentIndexChanged` 回写 `update_project_type`，改后联动刷新各分类页。分类页只读。
- **统计字段系统化**（v0.6.0）：county_count/site_count/completion_rate 不由总体表提供，库默认 0；导入总体表阶段 UI 显示 '--'，待导入规模表后系统统计填值。
- **数据库表 projects（v0.6.0）**：id / project_name / project_code / project_type(可空) / year / county_count(default 0) / site_count(default 0) / completion_rate(default 0) / status / created_at / updated_at。`init_projects_table` 对旧表无损迁移（保留旧数据与主键/约束）。
- **项目详情数据结构预留**（v0.6.0）：模块常量 `DETAIL_TREE` 声明 项目→项目整体资料/区县(多)→点位(多)→CAD/PDF/预算/照片/审批单/方案表。本版不实现，仅预留。
- **项目详情页面**（v0.7.0 引入，v0.8.0 重构为无树结构，v0.9.0 优化布局与入口）：
  - 双击入口（v0.9.0 扩展）：全部项目页 + 7 个分类页双击项目行 → 均调用
    `ContentArea.show_project_detail(id)` → 详情页 `load_project(id)`；共用同一详情页。
    页面通过 `set_open_detail_handler` 注入回调，项目 id 存表格第 0 列 UserRole。
  - v0.9.0 布局：页头(固定标题「项目详情」+「导入项目明细表」+「返回项目列表」按钮)
    → 概览卡+资料面板(`QSizePolicy.Fixed` + `setMaximumHeight(210)` 紧凑靠上、内容完整)
    → 筛选栏 → 点位列表(`stretch=1` + v0.9.1 `resizeEvent` 动态 `setMinimumHeight(height//2)`，
    稳定占详情页半页)。**无任何树结构**。
  - **v0.9.2 布局重构**：删除 v0.9.1 的 `setMaximumHeight(210)` 与 `resizeEvent` 半页强制；
    概览与资料从横向并列改为**纵向独立块**。从上到下：工具栏(Fixed) → 概览(Fixed，全宽，
    输入框 minimumHeight(24) 防压缩) → 资料(Fixed 中等高度，margin/spacing 收紧) →
    筛选栏(Fixed) → 点表(Expanding + stretch=1，占剩余全部纵向空间)。修复了概览被压缩、
    输入框文字截断、资料过小的问题。
  - **v0.9.3 双层布局**：概览与资料改回**横向并排**（显式 QHBoxLayout 嵌套在主 QVBoxLayout
    之内），比例 60/40（stretch 3:2）；中间区域 vertical=Fixed 紧凑完整；点表 Expanding +
    stretch=1 + `resizeEvent` 保 `setMinimumHeight(页面半高)` ≥50%。结构：工具栏 →
    中间HBox(概览|资料) → 筛选栏 → 点表。禁止概览/资料上下排列、禁止全页单列 QVBoxLayout。
  - **v0.9.4 微调**：中间区域概览/资料改 vertical=Preferred → QHBoxLayout 自动拉齐同高
    （修复右侧资料面板小于左侧）；resizeEvent 改 `setMinimumHeight(0)` → 窗口纵向可自由缩放。
  - 概览卡：项目名称/编码/类型/年份/状态（纵向只读）；项目整体资料面板：PDF/Word/
    Excel/其他资料/点位文件夹以外的文件夹（占位，不解析文件）。
  - 点位列表 `PointListTable`：固定 5 列（序号/区县/点位名称/图纸状态/预算状态）+
    动态列机制（`set_dynamic_columns`）。
  - 状态判定纯函数：`judge_drawing_status`（仅判 CAD）、`judge_budget_status`（预算文件夹
    存在与否）。本版不接文件系统，明细导入时均判「无」。
  - 明细导入（v0.9.0）：「导入项目明细表」按钮 → `excel_reader.read_sheet` 基础读取
    .xlsx → 按表头关键词粗匹配区县/点位名称，其余列作动态列展示；不写库、不做映射、
    不改数据库结构。
  - 筛选栏 `PointFilterBar`：区县下拉 + 点位名称搜索 + 图纸状态 + 预算状态，组合条件。
  - 「返回项目列表」按钮 → `switch_to("all_projects")`；纯只读、不新增业务、
    不接规模表、不解析文件、不用弹窗作主流程。

### v1.0.0 文件系统治理 — 阶段1：标准点位字典系统 ✅

> **架构升级**：系统从 Excel 工具升级为工程文件治理系统。
> Excel 是唯一标准来源 → 标准点位字典 → 文件系统扫描（待阶段2）→ 自动匹配

- `core/projects_repository.py` 新增 `point_dictionary` 表完整数据访问层：
  - `init_point_dictionary_table`：建表（IF NOT EXISTS 幂等）
  - `clear_points_by_project` / `insert_points`：清空+批量插入（可重入）
  - `fetch_points_by_project` / `fetch_points_with_status`：查询点位字典
  - `count_points_by_project`：统计点位数量
  - `normalize_point_name`：点位名称标准化（去除 / \\ * ? : " < > | 空格）
- `point_dictionary` 表字段：id / project_id / standard_point_name / county / original_name
  - project_id 外键关联 projects(id) ON DELETE CASCADE
  - standard_point_name 为文件系统匹配基准
  - original_name 为 Excel 原始名称（溯源）
- `project_detail_page.py` 升级（v1.0.0）：
  - 明细导入从"纯展示"升级为"写入 point_dictionary + 从表加载"
  - `_on_import_detail_clicked`：Excel 读取 → `_build_point_dictionary_records`
    → `clear_points_by_project` + `insert_points` → `_load_points_from_db`
  - `load_project` 自动从 point_dictionary 表加载点位（不再空表）
  - `_load_points_from_db`：从表加载，图纸/预算状态默认「无」（待阶段4）
  - `_apply_filter` 已启用：区县精确 + 名称子串 + 图纸状态 + 预算状态组合筛选
  - 删除旧 `_build_points_from_rows`（已被 `_build_point_dictionary_records` 取代）
- 测试更新并通过：
  - `test_import_smoke.py`：新增 `test_point_dictionary` 测试（建表/插入/查询/清空/统计/标准化）
  - `test_gui_smoke.py`：架构校验更新（v1.0.0 `_load_points_from_db` / `_build_point_dictionary_records`）
  - `test_import_e2e.py`：未变，确认导入分流链路不受影响

### v1.0.0 沙盒模式 — 文件扫描 + 匹配 + 状态计算（阶段2-4）✅

> **安全约束**：仅扫描 TEST_ROOT_PATH = D:\AI-Office-Agent-Test\，硬编码安全边界不可绕过。

- `core/scanner.py` **新增**——沙盒文件系统扫描器（435 行）：
  - **安全校验**：`_validate_path` / `_safe_resolve` — 路径边界硬编码，访问外部路径抛 ValueError
  - **扫描引擎**：`scan_project_root` / `_scan_project_dir` / `_scan_folder`
    - 枚举 TEST_ROOT_PATH 下所有项目文件夹（ProjectNode）
    - 递归扫描点位文件夹（FolderNode），识图子目录（图纸/预算）
    - 文件节点（FileNode）含路径/扩展名
  - **匹配系统**：`match_single_folder` / `match_project_folders` / `normalize_for_match`
    - 策略1：标准化后完全相等 → score=1.0
    - 策略2：标准化后包含关系 → score=0.85
    - 均不匹配 → score=0.0
  - **状态计算**：`compute_drawing_status` / `compute_budget_status` / `compute_all_statuses`
    - 图纸状态：图纸子文件夹存在 *.dwg →「有」，否则 →「无」（仅判 CAD）
    - 预算状态：预算子文件夹存在且有文件 →「有」，否则 →「无」
  - **便捷入口**：`run_full_scan` — 扫描+匹配+状态一条龙
- `project_detail_page.py` 升级接入沙盒扫描器：
  - `_load_points_from_db`：从 point_dictionary 加载 → `_try_match_from_sandbox` 获取真实状态
  - `_try_match_from_sandbox`：扫描 TEST_ROOT_PATH → 按项目名匹配文件夹 → 匹配点位 → 计算图纸/预算状态
  - 未匹配到项目文件夹时回退默认「无」状态，无需扫瞄时不影响现有功能
- 沙盒测试目录：`D:\AI-Office-Agent-Test\`
  - 社区改造工程2026：SiteA（图纸有+预算有）/ SiteB（图纸有+预算无）/ SiteC（图纸有+预算有）
  - 集客专线2026：点位D（图纸有+预算有）/ Site_E（图纸无+预算无）
  - 接入段工程2026：SiteF（图纸有+预算有）/ SiteG（图纸无+预算无）
- 测试覆盖：
  - 沙盒扫描：3 个项目、完整的 ProjectNode/FolderNode/FileNode 结构
  - 匹配系统：完全匹配 (1.0) / 包含匹配 (0.85) / 不匹配 (0.0) / normalize_for_match
  - 状态计算：SiteA=有+有, SiteB=有+无, SiteC=有+有
  - 三套冒烟测试全部通过（ALL_SMOKE_OK / GUI_SMOKE_OK / E2E_OK）

### v1.0.0 扫描架构升级 — 项目目录识别（项目资料 → 图纸根目录 → 点位）✅

> **升级原因**：旧扫描器假设一级目录即点位，不符合实际工程目录结构。
> 实际项目目录为：项目/ → 图纸根目录（设计图/CAD/施工图…）/ → 点位/ → 图纸/预算/其它。

- `core/scanner.py` 完全重写（310 行），三步识别架构：
  - **第一步：项目整体资料识别**
    - `ProjectDocGroup` 数据结构：category / folder / matched_by
    - `_PROJECT_DOC_KEYWORDS`：7 类关键词（规模表/材料表/照片/勘察报告/流程文件/批复/其它资料）
    - 关键词子串匹配（大小写不敏感）
  - **第二步：图纸根目录识别**
    - `DrawingRoot` 数据结构：folder / name / candidate_count
    - `_DRAWING_ROOT_KEYWORDS`：图纸/设计图/CAD/施工图/Drawing/图/dwg
    - **兜底识别**：关键词未命中但目录内含大量 .dwg → 也纳入候选
    - 多候选时记录在 `drawing_candidates`（UI 层后续可弹出确认，本版取首个）
  - **第三步：点位提取**
    - `SiteNode` 数据结构：name / path / folder / drawing_dir / budget_dir
    - `_extract_sites`：图纸根目录直接子目录 = 点位
    - `_build_site_node`：点位下自动识别图纸子目录（图纸/drawing/dwg/cad/图）和预算子目录（预算/budget/造价/cost）
    - 跳过明显非点位文件夹（以 _ 开头 / backup / 备份 / temp / tmp）
  - 移除旧数据结构：不再使用 FolderNode 作为点位（改为 SiteNode）
  - 移除旧函数：`find_subfolder` / `compute_all_statuses` / `match_project_folders`
  - 新增函数：`compute_all_statuses_for_sites` / `match_project_sites` / `_extract_sites`
- `project_detail_page.py` 适配升级：
  - `_try_match_from_sandbox` 改用 `match_project_sites`（状态在匹配阶段已填入 MatchResult）
  - import 更新：移除 `find_subfolder` / `match_project_folders`，新增 `match_project_sites`
- 沙盒测试目录重构为实际工程结构：
  - 社区改造工程2026：设计图/ → SiteA/SiteB/SiteC（图纸根目录=设计图）
  - 集客专线2026：CAD/ → 点位D/Site_E（图纸根目录=CAD）
  - 接入段工程2026：施工图/ → SiteF/SiteG（图纸根目录=施工图）
  - 每项目含规模表/材料表/照片/勘察报告等资料文件夹
- 测试覆盖：
  - 项目资料识别：7 类全部命中
  - 图纸根目录：设计图/CAD/施工图 三种不同目录名均正确识别
  - 点位提取：SiteNode 含 drawing_dir / budget_dir 子引用
  - 状态计算：SiteA(有+有) / SiteB(有+无) / SiteC(有+有) 正确
  - 三套冒烟测试全部通过（ALL_SMOKE_OK / GUI_SMOKE_OK / E2E_OK）

### v1.1.0 规模表智能识别引擎 ✅

> **升级原因**：v1.0.0 的明细导入只能用关键词粗匹配，写死字段名（点位名称/区县），
> 不支持多 Sheet、字段映射、动态字段、项目配置记忆。v1.1.0 建立统一的智能识别引擎，
> 所有项目类型共用。

- `core/scale_table_engine.py` **新增**（400+ 行）——纯逻辑识别引擎：
  - **Sheet 自动识别**：`score_sheet_likelihood`（表头关键词 + 数据密度 + 行数，三维评分）、
    `detect_best_sheet`（全部 Sheet 评分排序）、`read_all_sheets`（多 Sheet 读取）
  - **字段智能识别**：`detect_point_name_field` / `detect_county_field` /
    `detect_start_field` / `detect_end_field` / `detect_all_fields` / `build_field_candidates`
    关键词匹配但不写死，用户可修正
  - **点位生成规则**：`should_concatenate`（接入段/城域网默认起点+终点，其余单字段）、
    `generate_point_name`（按规则生成）
  - **动态字段**：`classify_dynamic_fields`（固定字段之外全部自动归入动态字段）、
    `_guess_dynamic_concept`（已知概念标注：长度/芯数/经度/纬度/设备型号/端口数/带宽/建设方式/备注）
  - **预览**：`build_preview_rows`（按当前映射生成前 N 条预览）
  - **数据构建**：`build_point_records`（Excel 行 → point_dictionary 表记录 + dynamic_data JSON）
- `core/project_profile_repository.py` **新增**——project_profiles 表 CRUD：
  - 表结构：project_id (UNIQUE FK) / sheet_name / point_name_field / county_field /
    start_point_field / end_point_field / use_concatenation / dynamic_fields (JSON) /
    created_at / updated_at
  - `upsert_profile` / `fetch_profile` / `delete_profile` / `profile_exists`
- `data_import/scale_import_worker.py` **新增**——规模表后台 Worker：
  - 接收已确认的映射 → `build_point_records` → 清空+插入 point_dictionary →
    保存 project_profiles 配置 → 信号通知完成
- `ui/widgets/scale_table_wizard.py` **新增**——四步导入向导：
  - Step 0: Sheet 选择（评分排序 + 单选）
  - Step 1: 字段映射（自动推荐 + 手动修正 QComboBox）
  - Step 2: 点位生成规则（单字段 / 起点+终点，按项目类型给默认推荐）
  - Step 3: 导入预览（前 10 条点位 + 动态字段列 + 统计信息）
  - 加载已有 Project Profile 时自动预填所有步骤
  - 确认后后台线程导入
- `core/projects_repository.py` 升级：
  - point_dictionary 表 v1.1.0：新增 `dynamic_data` TEXT 列（JSON）
  - `init_point_dictionary_table`：自动检测旧表并 ALTER TABLE 追加 dynamic_data 列
  - `insert_points`：新增 dynamic_data 参数，序列化 JSON 存储
  - `fetch_points_with_status`：返回 dynamic_data（反序列化为 dict）
- `project_detail_page.py` 升级：
  - `_on_import_detail_clicked`：接入 ScaleTableWizard 四步向导（替代旧关键词粗匹配）
  - `_run_scale_import`：ScaleImportWorker 后台导入 + QProgressDialog
  - `_load_points_from_db`：从 dynamic_data 提取动态字段，自动设置 PointListTable 动态列
  - `_extract_dynamic_columns` static：从点位字典提取全部动态字段名
  - 删除旧 `_build_point_dictionary_records` / `_match_header`（移至 scale_table_engine）
- `app.py`：启动时初始化 project_profiles 表
- `tests/test_v1_1_smoke.py` **新增**：引擎逻辑 + 配置 CRUD + 表升级 三项全链路测试
- `tests/test_gui_smoke.py`：架构校验更新至 v1.1.0（新模块导入、表结构、方法签名）
- 四套测试全部通过

### v1.2.0 扫描结果中心 ✅

> **升级原因**：需要一个独立页面统一展示扫描匹配分析结果，
> 而非将扫描状态分散在项目详情页。所有后续模块（重命名预览/文件夹构建/
> 健康评分/AI建议）都使用统一的 ScanResult 数据模型。

- `core/scan_result.py` **新增**（280+ 行）——统一扫描结果数据模型：
  - `MatchStatus` 枚举：MATCHED/PARTIAL_MATCH/NOT_FOUND/MULTIPLE_MATCH
    - 每种状态带中文标签和颜色常量（绿/黄/红/橙）
  - `ScanResultItem` 数据类：含点位字典字段 + 匹配结果 + 文件状态 + 建议
    - `from_point_dict` 工厂方法从 point_dictionary + scanner 结果构造
    - `_generate_suggestion` 自动生成建议文本
    - `to_dict` 序列化
  - `ScanResultSummary` 数据类：汇总统计（总数/已匹配/部分/未找到/CAD缺失/预算缺失）
    - `from_items` 从 ScanResultItem 列表自动统计
    - `to_dict` / `to_json` 序列化
  - `build_scan_results` 协调器函数：协调 point_dictionary + scanner + matcher 三者
    生成统一结果，不重复写匹配逻辑
- `ui/widgets/pages/scan_center_page.py` **新增**（700+ 行）——扫描结果中心页面：
  - `ScanCenterPage(BasePage)`：独立页面，导航可点击进入
  - **顶部信息栏**：项目名称、扫描时间、扫描耗时、扫描目录 + 执行扫描/重新扫描按钮
  - **统计卡片组**（StatCardRow）：6 张卡片（总点位/已匹配/部分匹配/未匹配/CAD缺失/预算缺失）
    - 颜色编码：已匹配=绿、部分匹配=黄、未匹配=红
  - **结果列表**（ScanResultTable）：7 固定列（状态/标准点位/实际文件夹/匹配率/CAD/预算/建议）
    - 状态列带颜色标记；CAD/预算列带绿色"有"/红色"无"
    - 双击行 → 触发详情预览
  - **筛选栏**（ScanFilterBar）：状态 + 搜索 + CAD + 预算组合筛选
  - **详情预览面板**（DetailPreviewPanel）：右侧面板，显示标准点位/原始名称/匹配目录/
    CAD文件数/预算文件数/扫描文件列表等；仅查看不可修改
  - **重新扫描**：重新读取项目目录，重新生成 ScanResult，覆盖内存结果，禁止修改数据库
  - **预留接口**（仅定义签名，不实现）：
    - `RenamePreviewInterface` — 重命名预览
    - `FolderBuilderInterface` — 文件夹构建
    - `HealthScoreInterface` — 健康评分
    - `AISuggestionInterface` — AI 建议
- `ui/widgets/nav_tree.py`：新增「🔍 扫描结果中心」导航节点
- `ui/widgets/content_area.py`：注册扫描中心页（page key=scan_center），总页面数 11→12
  - `show_project_detail` 同步预加载扫描中心数据
- `ui/widgets/pages/__init__.py`：导出 ScanCenterPage
- `ui/theme.py`：新增 StatCard / DetailPreviewPanel QSS 样式
- `tests/test_gui_smoke.py`：架构校验更新至 v1.2.0（12 页、ScanCenterPage 验证、预留接口验证）

### 约束遵循

- ❌ 禁止自动改名/移动/删除/建目录 ✅
- ❌ 禁止扫描真实目录之外的位置 ✅（复用 scanner 安全边界）
- ✅ 所有结果均来自 point_dictionary + scanner + matcher，不重复写匹配逻辑
- ✅ 仅分析并展示扫描结果，禁止修改任何数据

## 10. 下一步规划

> 按开发路线，下一阶段：
**v1.6 — 待用户指定**

## 11. 待办/约束

- 沙盒模式路径硬编码为 D:\AI-Office-Agent-Test\，真实工程路径待后续配置化
- 自动标准化（阶段5）尚未实现
- 项目整体资料面板仍为占位（不解析文件）
- 规模表版本比较接口已预留，暂不实现
- project_profiles 表当前与 projects 表同一数据库，未来可考虑独立配置存储
- v1.4.0 扫描结果已持久化到 `scan_result` 表，打开项目直接从缓存加载，0 延迟

## 12. 变更历史指针

- 完整变更记录见 `CHANGELOG.md`。
- 路线规划见 `Roadmap.md`。
- 开发规则见 `DevelopmentRules.md`。
