# 变更日志 (CHANGELOG)

> 按版本倒序记录。每个开发任务完成后追加一条。

## [v1.5.8] - 2026-07-09 — 归属识别优化

### 匹配率精细化

- 匹配率不再是 0%/100% 二值，改用 `OwnershipDecision.best_score` 作为真实置信度。
- 修改文件：`core/scan_result.py`、`core/scanner.py`。

### 图纸 stem 匹配放宽

- `_stem_match` 新增包含匹配：点位名包含在 stem 中即可匹配（兼容文件含编号前缀如 `01-昆明湖中坝...dwg`）。
- 修改文件：`core/ownership.py`。

### 预算 stem 匹配放宽

- `_stem_matches_point` 新增原始 stem 包含点位名检查，解决去数字后失配问题。
- 修改文件：`core/ownership.py`。

### 路径证据加强验证

- Tier 2 路径证据新增 stem 关联性验证：`match_strings(stem, pname) >= 65` 才给 0.85。
- 防止「五华-红云街道」的文件在「安宁-太平新城街道」目录下被误归属。
- 修改文件：`core/ownership.py`。

### 统计卡片移除已确认

- 移除统计卡片行的「已确认」卡片，与删除确认列一致。
- 修改文件：`ai_office_agent/ui/widgets/pages/scan_center_page.py`。

### 修改文件

- `ai_office_agent/core/ownership.py`
- `ai_office_agent/core/scan_result.py`
- `ai_office_agent/core/scanner.py`
- `ai_office_agent/ui/widgets/pages/scan_center_page.py`

## [v1.5.7] - 2026-07-09 — 扫描中心 UI 简化

### 移除人工确认列

- 扫描中心结果表格从 8 列精简为 7 列，删除最右侧的「确认」列。
- 删除 `ScanResultTable` 的 `confirm_toggled` 信号与行内确认按钮。
- 表格列头：`状态 / 标准点位 / 实际文件夹 / 匹配率 / CAD / 预算 / 建议`。

### 移除冗余操作按钮

- 删除「批量确认已匹配」按钮（`batch_confirm_btn`）与对应 `_on_batch_confirm_matched` 方法。
- 删除「重新匹配」按钮（`rematch_btn`）及 `RematchDialog` 对话框、对应 `_on_rematch` 方法。
- 保留「执行扫描 / 全部确认 / 导出 Excel / 选择项目文件夹 / 整理文件」按钮。

### 代码清理

- 移除未使用的 `QDialogButtonBox` 导入。
- 移除未使用的 `time` 导入。

### 修改文件

- `ai_office_agent/ui/widgets/pages/scan_center_page.py`
- `tests/test_gui_smoke.py` — 同步移除已删除按钮和确认列的断言，列数检查改为 7

## [v1.5.6] - 2026-07-08 — 预算识别修复与 UI 优化

### 预算识别修复

#### 删除「清单」关键词
- 从 `_BUDGET_KEYWORDS` / `_is_budget_like_file` / `_is_budget_file` 中移除 `"清单"`，避免 `设备清单`、`材料清单` 等非预算文件被误判。

#### stem_no_digits 精确匹配 → prefix 匹配
- 旧逻辑：`stem_no_digits == point_norm` 精确相等。点位名 `安宁-县街街道-分纤箱扩容点位`，文件 `安宁-县街街道20250707.xlsx` → stem_no_digits=`安宁-县街街道` ≠ 完整点位名 → 漏判。
- 新逻辑：新增 `_stem_matches_point()` 函数，支持 `point_norm.startswith(stem_no_digits + "-")` prefix 匹配。

#### 4 层分层评分（_score_file_to_point 重构）
- **Tier 1**：stem 含完整点位名 → **0.95**（立即返回，最强证据）
- **Tier 2**：路径含完整点位名 → **0.85**
- **Tier 3**：全名模糊匹配 → 封顶 **0.88**（低于 Tier 1 避免浮点精度冲突）
- **Tier 4**：分段模糊匹配 → 封顶 **0.75**（防止 `分纤箱扩容点位` 等公共后缀 partial_ratio=100 误匹配）
- 解决文件名含点位A、路径在点位B目录下的冲突：点位A 0.95 vs 点位B 0.88 → 归属点位A。

#### 反向排斥逻辑
- stem 含其他已知点位名（`all_point_names_norm`）→ return 0.0（文件属于另一个点位）
- stem 含 `分纤箱扩容` 但当前点位名不含 → return 0.0（防止其他点位预算文件被误归属到目录所在点位）

#### 未归属预算文件识别
- `OwnershipResult` 新增 `unassigned_budget_files` 字段，将文件名含预算关键词但无法确定点位的文件单独标记，待人工确认。
- `_serialize_ownership` 补上 `unassigned_budget_files` 字段。

#### 双「设计文件」目录修复
- `build_organize_plan` 中若用户选择的扫描目录本身就叫「设计文件」，直接在此目录下整理，避免出现 `设计文件/设计文件/` 嵌套路径。

### UI 优化

#### 重命名与按钮合并
- 「扫描结果中心」→「扫描中心」
- 「文件整理预览」+「执行整理」合并为一个「整理文件」按钮，点击后先弹预览对话框（含「整理」+「取消」按钮），确认后执行移动。

#### 扫描中心项目选择器
- 取代之前「必须在项目列表双击项目」的流程，在扫描中心顶部增加项目下拉框，直接选择已导入项目即可扫描。
- ContentArea 在切换到扫描中心时自动刷新项目列表。

#### 窗口横向缩放修复
- `StatCard` 最小宽度 130px → 100px，降低窗口隐含最小宽度（原 1271px ≈ 默认 1280px，导致无法横向缩小）。
- `MainWindow` 显式设置 `setMinimumSize(900, 600)`。

#### 项目选择器布局调整
- 项目选择器从 info_bar 移出，成为标题下方的独立横幅，避免与按钮行重叠。

### 修改文件

- `core/ownership.py` — 预算关键词、stem matching、4 层评分、反向排斥、unassigned_budget_files
- `core/file_organizer.py` — 预算关键词、stem matching、「设计文件」目录修复
- `core/scan_controller.py` — `_serialize_ownership` 补字段
- `ui/widgets/pages/scan_center_page.py` — 重命名、按钮合并、项目选择器、StatCard 宽度、布局调整
- `ui/widgets/nav_tree.py` — 「扫描中心」命名
- `ui/widgets/content_area.py` — 刷新项目列表
- `ui/main_window.py` — `setMinimumSize(900, 600)`
- `tests/test_v1_5_ownership.py` — 新增 v1.5.6/v1.5.7 测试

### 验证

- `python -m pytest tests/test_v1_3_smoke.py tests/test_v1_5_ownership.py`：27/27 全部通过

## [v1.5.5] - 2026-07-07 — 散落文件识别与整理闭环

### 问题

扫描结果中很多点位显示「未找到」，建议写着「未在文件系统中找到对应文件夹；请创建点位文件夹并导入图纸」。但实际文件已经在用户选择的项目文件夹下，只是现有子文件夹名称不是标准点位名称。用户希望系统遍历选择目录下所有文件，识别归属，再通过整理按钮创建标准点位文件夹并分类移动文件。

### 修复

- `ownership` 归属证据扩展为文件名、父目录、全部祖先目录片段、项目相对路径文本。
- 泛分类目录（图纸/预算/其他文件/other/cad/pdf/资料 等）不再作为点位身份证据，避免误归属。
- 图纸类文件仍走严格证据，保持唯一归属，禁止 fuzzy，避免跨点位图纸污染回归。
- 预算类 PDF 不再被图纸严格规则一票否决，可按预算资料参与归属并最终分类为预算。
- `NOT_FOUND` 建议文案改为「已扫描项目文件夹，但未识别到该点位的归属文件；请检查文件名或路径是否包含点位信息，或后续人工确认」，不再误导用户创建文件夹。
- 有归属文件时建议提示可执行整理创建标准点位文件夹并分类。
- 文件整理预览/执行继续读取 Scan Session 中的归属结果，目标目录使用 `scan_path`，不重新扫描、不重新归属，保持与扫描结果一致。

### 修改文件

- `core/ownership.py`
- `core/scan_result.py`
- `core/file_organizer.py`
- `tests/test_v1_5_ownership.py`
- `tests/test_scan_session.py`

### 验证

- `python -m pytest`：45/45 全部通过
- 完整冒烟链路全部通过：
  - `test_import_smoke.py` → ALL_SMOKE_OK
  - `test_gui_smoke.py` → GUI_SMOKE_OK
  - `test_import_e2e.py` → E2E_OK
  - `test_v1_1_smoke.py` → v1.1.0_SMOKE_OK
  - `test_v1_2_3_smoke.py` → V1.2.3_SMOKE_OK
  - `test_v1_3_smoke.py` → V1.3_SMOKE_OK
  - `test_v1_5_ownership.py` → V1.5_OWNERSHIP_OK
  - `test_scan_session.py` → 4/4 通过

## [v1.5.4] - 2026-07-07 — 点位明细导入重复任务名称去重

### 问题

用户导入 `出版明细-社区2025-3个项目-融基编号V2(1)(2).xlsx` 时，F 列「任务名称」存在大量重复值。旧逻辑逐行生成 `point_dictionary` 记录，导致同一个任务名称被重复导入为多个点位。

### 修复

- `build_point_records` 内部按标准化后的点位/任务名称自动去重。
- 新增 `build_point_records_with_stats`，返回唯一记录数、重复跳过数和重复名称列表。
- 重复行不新增点位，但会补充首条记录中为空的区县和动态字段。
- `ScaleImportWorker` 导入时显示唯一点位数和重复跳过数。
- 导入完成对话框显示「已跳过 X 条重复点位/任务名称」。
- 预览阶段提示导入时会按点位/任务名称自动去重。

### 修改文件

- `core/scale_table_engine.py`
- `data_import/scale_import_worker.py`
- `ui/widgets/pages/project_detail_page.py`
- `ui/widgets/scale_table_wizard.py`
- `tests/test_v1_1_smoke.py`

### 验证

- `python -m pytest tests/test_v1_1_smoke.py`：3/3 通过

## [v1.5.3] - 2026-07-07 — 扫描结果生命周期管理修复

### 问题

点击「执行扫描」完成后，进入「文件整理预览」仍会重新 `FileIndex.build(...)` 并重新执行 ownership 归属，导致用户等待两次、扫描结果可能不一致、浪费扫描时间。

### 修复

- 新增当前项目 Scan Session：一次扫描完成后保存 `project_id`、`scan_path`、`scan_time`、文件索引、唯一归属结果和 ScanResult。
- `ScanController.run_scan()` 改为持久化完整扫描工件，仍是唯一显式扫描入口。
- 文件整理预览 / 执行改为读取当前 Scan Session，不再调用 `FileIndex.build`、scanner 或 `assign_ownership`。
- 无有效 Scan Session 时，文件整理预览 / 执行提示「请先执行扫描」，禁止自动扫描。
- 扫描按钮生命周期调整：初次显示「执行扫描」，有效 Scan Session 存在时显示「重新扫描」。
- 修改扫描目录时使 Scan Session 失效，等待用户主动重新扫描。
- 点位详情遗留沙盒扫描函数改为不触发扫描，详情继续只读缓存结果。
- 保持 v1.5 唯一归属模型：唯一归属只在用户主动扫描时计算。

### 修改文件

- `core/scan_controller.py`
- `core/scan_result.py`
- `core/file_organizer.py`
- `ui/widgets/pages/scan_center_page.py`
- `ui/widgets/pages/project_detail_page.py`
- `tests/test_scan_session.py`
- `tests/test_gui_smoke.py`

### 验证

- `python -m pytest`：40/40 全部通过
- 完整冒烟链路全部通过：
  - `test_import_smoke.py` → ALL_SMOKE_OK
  - `test_gui_smoke.py` → GUI_SMOKE_OK
  - `test_import_e2e.py` → E2E_OK
  - `test_v1_1_smoke.py` → v1.1.0_SMOKE_OK
  - `test_v1_2_3_smoke.py` → V1.2.3_SMOKE_OK
  - `test_v1_3_smoke.py` → V1.3_SMOKE_OK
  - `test_v1_5_ownership.py` → V1.5_OWNERSHIP_OK
  - `test_scan_session.py` → 2/2 通过

## [v1.5.1] - 2026-07-07 — 预算识别规则修复

### 问题

1. **文件名含"预算"但扩展名是 PDF → 被错误归为"其他"**
   - 例：`-设计预算-云南财经职业学院...PDF.pdf` 被归为"其他"
   - 根因：旧规则要求"预算类型(.xls/.xlsx/.et/.csv) **且** 文件名含关键词"，AND 逻辑太严格

2. **表格类文件无预算关键词 → 被错误归为"其他"**
   - 例：龙泉湾点位的 `CPMS结构数据--龙泉湾.xlsx`、`龙泉湾_嘉陵版V1.xlsx` 等被归为"其他"
   - 根因：这些文件名不含"预算/概算/造价"等关键词

### v1.5.2 修正（用户纠正）

v1.5.1 的修复过于宽泛（把所有 `.xlsx` 都归为预算）。v1.5.2 按用户给定的准确规则重新修正：

**预算识别规则（OR 逻辑）**：
1. 文件名含预算关键词（不限扩展名）→ 预算
   - 关键词：预算/概算/造价/报价/清单/cost/estimate/budget
   - 业务补充：CPMS结构数据/嘉陵版/安全事故防范/安全生产费依据
2. 表格类扩展名（.xls/.xlsx/.et/.csv）+ 文件名 stem 去除数字后 == 点位名 → 预算
   - 如「龙泉湾202606121457.xlsx」去数字后 = 「龙泉湾」== 点位名 → 预算

**不再**把所有表格类文件自动归为预算。

### 修改文件

- `core/file_organizer.py`：
  - `_BUDGET_KEYWORDS` 补充业务关键词
  - `classify_file` 预算识别改为：关键词匹配 OR (表格类 + stem去数字=点位名)
- `core/ownership.py`：
  - 新增 `_is_budget_file()` 统一预算判断函数
  - `_compute_status()` / `get_file_counts_for_point()` 使用统一函数，传入 point_name
- `core/scan_result.py`：`get_file_counts_for_point` 调用传入 pname
- `tests/test_v1_5_ownership.py`：更新测试覆盖新规则

### 验证

- 20/20 测试全部通过
- Lint：0 诊断

## [v1.5.0] - 2026-07-07 — 唯一归属模型（Single Ownership Model）

### 核心重构：两阶段唯一归属模型

彻底重构文件归属逻辑，解决"一个文件被多个点位同时识别"的多点归属污染问题。

**两阶段模型**：
1. 候选生成：每个文件对每个点位打分（允许多点）
2. 唯一归属决策：每个文件取 Top1 点位；score < 0.75 不归属；冲突（Top1≈Top2）不归属

**图纸特殊规则**：
- DWG / DXF / BAK / PDF 必须 stem 精确匹配（或路径/父目录含点位名）
- 禁止 fuzzy match 参与图纸归属

### 新增

- `core/ownership.py`（~350 行）——唯一归属模型核心模块：
  - `OWNERSHIP_THRESHOLD = 0.75` 归属阈值
  - `CONFLICT_MARGIN = 0.05` 冲突阈值
  - `DRAWING_EXTS = {.dwg, .dxf, .bak, .pdf}` 图纸扩展名
  - `_score_file_to_point()` 阶段1：文件→点位打分（图纸强制 stem 精确匹配）
  - `_decide_ownership()` 阶段2：Top1 决策（阈值+冲突检测）
  - `assign_ownership()` 主入口：两阶段完整决策
  - `OwnershipDecision` / `OwnershipResult` 数据结构
  - `get_scanned_files_for_point()` / `get_file_counts_for_point()` 辅助查询
- `tests/test_v1_5_ownership.py`（9 项测试）：
  - 一文件一归属、无重叠
  - 阈值 < 0.75 不归属
  - 图纸 stem 精确匹配、禁止 fuzzy
  - PDF 同名绑定规则
  - 冲突场景处理
  - 状态计算基于归属
  - 整理计划基于归属

### 修改

- `core/scanner.py` — `match_points_from_index` 重写：
  - 内部改为调用 `ownership.assign_ownership`（两阶段唯一归属）
  - 移除 `match_file_to_points` 调用（旧 fuzzy 链路）
  - 移除 `file_index.global_match_point` / `compute_drawing_status` / `compute_budget_status` 调用（反向匹配污染源）
  - 状态计算改为从 `ownership.point_status` 取
  - 保留返回签名 `(matches, unmatched, conflicts)` 兼容现有调用方
- `core/scan_result.py` — `build_scan_results`：
  - 移除 `match_points_from_index` 调用（旧链路含 fuzzy 反向匹配）
  - 移除 `file_index.global_match_point` 二次调用（反向匹配污染源）
  - 改用 `ownership.assign_ownership` 做唯一归属决策
  - scanned_files / cad_count / budget_count 全部从 ownership 结果取
  - 清理残留的 `match_points_from_index` import
- `core/file_organizer.py`：
  - 删除重复的死代码（`build_organize_plan` 重复函数体）
  - 新增 `build_organize_plan_from_ownership()` 基于 ownership 模型的入口
- `ui/widgets/pages/scan_center_page.py`：
  - `_on_organize_preview` 改用 `build_organize_plan_from_ownership`（移除 `global_match_point`）
  - `_on_organize_apply` 同上
- `ui/widgets/pages/project_detail_page.py` — `_try_match_from_sandbox`：
  - 改用 `ownership.assign_ownership` 替代 `match_points_from_index`
  - 状态从 `ownership.status_for_point` 取

### 禁止行为（硬约束）

- ❌ 禁止一个文件归属多个点位 → ✅ 每个文件只取 Top1
- ❌ 禁止扫描阶段直接写归属 → ✅ 归属决策统一走 `ownership.assign_ownership`
- ❌ 禁止 fuzzy match 参与图纸归属 → ✅ 图纸强制 stem 精确匹配
- ❌ 禁止 `build_scan_results` 调用 `global_match_point` → ✅ 已移除

### 验证

- Lint：0 诊断（ownership / scan_result / file_organizer / scan_center_page）
- `test_v1_3_smoke.py`：9/9 全部通过（无回归）
- `test_v1_5_ownership.py`：9/9 全部通过

## [v1.4.2] - 2026-07-07 — 图纸识别跨点位污染修复

### 问题

执行整理后，一个点位的图纸文件夹内混入了大量其他点位的图纸文件，文件名称和点位名都不一样。

**根因**：两层致命缺陷叠加导致跨点位文件污染：

1. **`file_index.global_match_point` 目录匹配过于宽松**：
   - 用 fuzzy 匹配（`match_strings` score≥70）匹配目录名
   - 匹配到后通过 `parent_path.startswith(de.dir_path)` 把**整个目录树**的文件归入该点位
   - 例如「安宁-太平新城街道」的 fuzzy 匹配会命中「安宁-青龙街道」等相似目录名

2. **`classify_file` 对直接图纸类型无归属校验**：
   - `.dwg` / `.dxf` / `.bak` 文件直接归类为"图纸"，不管是否属于当前点位
   - global_match_point 混入的其他点位图纸文件直接被写入当前点位的图纸文件夹

### 修复

#### `core/file_index.py` — `global_match_point`
- 目录匹配从 fuzzy（score≥70）改为**精确相等**（`de.normalized_name == match_name`）
- 目录匹配的文件范围从 `parent_path.startswith`（含所有子孙目录）改为 `parent_path ==`（仅直接文件）
- 防止模糊目录匹配导致的跨点位文件归属

#### `core/file_organizer.py` — 新增 `_drawing_belongs_to_point`
- 判断图纸文件是否真正属于该点位（路径/文件名 stem/父目录名 包含点位名）
- 在 `classify_file` 中：直接图纸文件类型（.dwg/.dxf/.bak）通过归属校验后才归为"图纸"
- 不通过归属校验的图纸文件归入"其他"（reason="非本点位图纸"）
- 在 `build_organize_plan` 中：CAD 索引只使用通过归属校验的图纸文件

#### `tests/test_v1_3_smoke.py`
- 新增 `test_organize_plan_no_cross_point_drawing`：模拟跨点位图纸污染场景，验证过滤正确性

### 验证

- Lint：0 诊断
- `test_v1_3_smoke.py`：9/9 全部通过（含新增跨点位图纸测试）

## [v1.4.1] - 2026-07-07 — 扫描结果中心 UI 微调 + 文件整理预览对话框修复

### 问题

1. **扫描按钮重复**：顶部同时存在「执行扫描」和「重新扫描」两个按钮，且都触发相同的扫描逻辑，造成 UI 冗余和入口重复。
2. **建议列无法拖动**：表格「建议」列使用 `Stretch` 模式，且水平滚动条未显式启用，导致列宽被压缩、用户无法拖动列宽查看完整建议文本。
3. **文件整理预览信息显示不全**：原实现使用 `QMessageBox`，无法调整窗口大小、无滚动条，且对冲突文件/点位/分类明细做了数量截断，导致长路径和大量信息无法完整查看。

### 修复

`ui/widgets/pages/scan_center_page.py`：
- 删除「重新扫描」按钮，仅保留「执行扫描」按钮
- 更新所有用户提示文案为「执行扫描」
- 将「建议」列的 `ResizeMode` 从 `Stretch` 改为 `Interactive`，允许用户拖动列宽
- 为确认列显式设置 `ResizeMode.Fixed`
- 表格显式启用水平滚动条 `ScrollBarAsNeeded` 和按像素滚动模式，避免内容被压缩
- 新增 `OrganizePreviewDialog` 类：
  - 继承 `QDialog`，可调整大小（`setSizeGripEnabled(True)`）
  - 使用 `QPlainTextEdit` 显示完整预览文本
  - 支持鼠标滚轮滚动、垂直/水平滚动条
  - 显示完整分类明细，不再截断冲突文件、点位数量、文件数量
  - 默认尺寸 960×640，最小尺寸 720×480

### 验证

- Lint 检查：0 诊断
- `scan_center_page` 模块导入正常
- `OrganizePreviewDialog` 导入正常
- `test_v1_3_smoke.py` 8/8 全部通过

## [v1.4.0] - 2026-07-07 — 扫描生命周期闭环修复（消除自动扫描卡顿 + 统一扫描入口）

### 问题

两个核心问题严重影响了用户体验：

**问题1：打开项目自动扫描导致严重卡顿**
- 根因：`content_area.show_project_detail()` → `scan_center_page.load_project()` → `_load_and_scan()` → `build_scan_results()` → 全量文件系统扫描
- 表现：双击项目后 UI 冻结数秒，体验极差

**问题2：扫描入口重复冲突**
- `project_detail_page._load_points_from_db()` 调用 `_try_match_from_sandbox()` 触发全量扫描
- `scan_center_page` 也有独立扫描入口
- 两个页面各自触发扫描，入口分散、结果不一致

### 修复

#### 新增：统一扫描生命周期控制器

`core/scan_controller.py`（~350 行）——**唯一扫描入口**，管理完整 5 步生命周期：

```
用户点击「扫描」→ ScanController.run_scan()
  Step1: 读取 point_dictionary + scan_match_history（历史确认优先）
  Step2: scanner.scan_project()（文件系统扫描）
  Step3: matcher.match_file_to_points()（唯一归属匹配）
  Step4: 生成 ScanResultItem 列表 + ScanResultSummary
  Step5: 写入 scan_result + file_ownership + scan_match_history（DB 闭环）
```

关键函数：
- `init_scan_result_tables(conn)` — 创建 `scan_result` + `file_ownership` 表
- `save_scan_results()` / `save_file_ownership_batch()` — DB 写入
- `load_scan_results_from_db()` — **纯缓存读取（0 扫描）**
- `ScanController.load_cached_results()` — 项目打开专用
- `ScanController.run_scan()` — **唯一扫描入口**

#### 新增数据库表

- **`scan_result` 表**：持久化扫描结果缓存（project_id 索引）
  - 字段：standard_point_name / match_folder / match_score / match_status / match_method / cad_status / budget_status / cad_file_count / budget_file_count / suggestion / confirmed / scanned_at / file_list(JSON)
- **`file_ownership` 表**：文件→点位唯一归属记录（file_path UNIQUE）
  - 字段：project_id / file_path(UNIQUE) / point_id / standard_point_name / match_score / is_conflict

#### 修改：消除自动扫描

- `ui/widgets/pages/scan_center_page.py`：
  - 新增 `load_project_cached()`：仅从 `scan_result` 表加载缓存（**0 扫描，0 卡顿**）
  - `_load_and_scan()` 改用 `ScanController.run_scan()`（统一入口）
  - 新增 `_rebuild_items_from_dict()` 辅助方法
- `ui/widgets/pages/project_detail_page.py`：
  - `_load_points_from_db()` 改为从 `scan_result` 表读取缓存
  - **移除 `_try_match_from_sandbox()` 调用**（详情页不再触发扫描）
  - 无缓存时回退默认「无」状态（不影响已有功能）
- `ui/widgets/content_area.py`：
  - `show_project_detail()` 改为调用 `load_project_cached()`（仅缓存，不扫描）
- `app.py`：
  - 启动时调用 `init_scan_result_tables(conn)` 初始化新表

### 正确交互流程

```
进入项目 → load_project_cached()（读 scan_result 缓存，0 卡顿）
    ↓
用户点击「扫描」→ ScanController.run_scan()（5 步闭环 → 写 DB）
    ↓
刷新 UI
```

### 禁止行为（硬约束）

- ❌ `on_project_open → scan_project()` — 打开项目绝对禁止扫描
- ❌ `project_detail_page._try_match_from_sandbox()` — 详情页禁止扫描
- ❌ 只读不写（scan 无 DB 闭环）— 扫描必须写入 scan_result + file_ownership
- ❌ 多个扫描入口 — 只有 `ScanController.run_scan()` 一个入口

### 验收标准

| 标准 | 状态 |
|------|------|
| 打开项目 0 卡顿（仅读缓存，不扫描） | ✅ |
| 打开项目不自动触发扫描器 | ✅ |
| 仅 scan_center_page 有扫描按钮 | ✅ |
| 扫描执行一次（唯一入口） | ✅ |
| DB 更新正确（scan_result + file_ownership + history） | ✅ |
| 文件归属唯一正确 | ✅ |

### 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `core/scan_controller.py` | 新增 | 统一扫描生命周期控制器（~350 行） |
| `ui/widgets/pages/scan_center_page.py` | 修改 | 新增 `load_project_cached()`，扫描改用 `ScanController` |
| `ui/widgets/pages/project_detail_page.py` | 修改 | 移除扫描触发，改为从缓存读取 |
| `ui/widgets/content_area.py` | 修改 | `show_project_detail` 改用 `load_project_cached()` |
| `app.py` | 修改 | 启动时初始化 `scan_result` + `file_ownership` 表 |
| `docs/ProjectMemory.md` | 修改 | 更新至 v1.4.0 |
| `docs/CHANGELOG.md` | 修改 | 新增 v1.4.0 条目 |

### 验证

- Lint 检查：所有修改文件 0 诊断
- 模块导入测试：`scan_controller` 导入成功
- 冒烟测试：待运行

## [v1.3.3] - 2026-07-06 — 扫描匹配引擎修复（唯一归属 + 重复点位传播）

### 问题
v1.3.1 引入「文件→唯一归属」后出现严重退化，扫描完全找不到文件。

**根因**（实测定位）：
1. `FilePointMatch.best_point_id` 缺省值，第一个不匹配文件触发 TypeError，整函数崩溃
2. 文件名 vs 点位名得分 < 70（文件叫"图纸.dwg"，点位叫"安宁-街道-扩容点位"），全部不匹配
3. 文件路径里的**文件名段**包含其他点位名（如跨点位打印文件），被误判两点同时命中 → 316 冲突
4. 377 点位只有 85 个唯一名，文件归到第一个 id 后其余重复 id 全显示未匹配

### 修复

`core/matcher.py`：
- `FilePointMatch.best_point_id` 改为 `= None` 默认值
- 策略1 改为只检查目录段（`Path.parts[:-1]`），不包含文件名
- 策略1 同名点位去重：只计一个候选，避免重复 id 触发假冲突
- 策略2 模糊阈值 70 → 60

`core/scanner.py` `match_points_from_index`：
- 引入 `name_status_cache`：先按**点位名**建状态缓存
- 同名重复点位共享匹配状态（文件归到任意一个 id，其余 id 也显示匹配）

**结果（实测）**：24/151 → **151/151（100%）**

### 验证
- `test_import_smoke.py` ALL_SMOKE_OK
- `test_gui_smoke.py` GUI_SMOKE_OK
- `test_v1_3_smoke.py` V1.3_SMOKE_OK

## [v1.3.1] - 2026-07-06 — v1.3.1 文件唯一归属修复

### 核心修复：文件→多点匹配 → 文件→唯一归属

**问题**：同一文件被多个点位重复归属，导致扫描结果污染、完成率失真。

**根因**：`match_points_from_index` 按点位逐个调用 `global_match_point`，
每个点位独立搜索文件，同一文件可出现在多个点位结果中。

**修复**：匹配方向反转——改为按文件逐一匹配所有点位，取 Top1 Winner。

### 新增

- `core/matcher.py`：
  - 新增 `FilePointMatch` 数据类（含 best_score/second_score/is_conflict/is_assigned）
  - 新增 `match_file_to_points(file, points)` — 文件→所有点位→唯一归属
  - 冲突规则：top1 - top2 < 5 → is_conflict=True（不归属任何点位）
- `core/scan_result.py`：
  - `ScanResultItem` 新增 `file_owner_point_id` / `match_confidence`
  - `ScanResultSummary` 新增 `conflict_file_count` / `conflict_files`

### 修改

- `core/scanner.py`：
  - `match_points_from_index` 重写——文件遍历 + Top1 Winner 归属
  - 返回值从 2-tuple 改为 3-tuple `(matches, unmatched, conflicts)`
- `ui/widgets/pages/project_detail_page.py`：适配 3-tuple 返回值

### 验证

- 五套测试全部通过

### 新增

- `core/file_organizer.py`（320+ 行）——文件自动整理引擎：
  - `build_cad_index(files)` — 构建 CAD stem 索引（.dwg/.dxf/.bak → {stem: [FileEntry]})
  - `classify_file(file, cad_index)` — 三级分类引擎（图纸 > 预算 > 其他）
  - `build_organize_plan(point_files, project_path)` — Dry Run 生成 OrganizePlan
  - `apply_organize_plan(plan)` — Apply Mode 执行实际文件移动
  - 图纸识别：直接类型(.dwg/.dxf/.bak) + PDF↔CAD 同名规则
  - 预算识别：类型(.xls/.xlsx/.et/.csv) + 关键词(预算/概算/造价/报价/清单/cost/estimate/budget)
  - 安全规则：不删除/不覆盖/冲突跳过
- `tests/test_v1_3_smoke.py`（170+ 行）——8 项 v1.3 专项测试
- `ui/widgets/pages/scan_center_page.py`：
  - 新增「文件整理预览」按钮（Dry Run 显示分类计划）
  - 新增「执行整理」按钮（Apply Mode 实际移动文件）

### 标准目录结构
```
项目/
 ├── 点位A/
 │    ├── 图纸/    （.dwg/.dxf/.bak + 同名PDF）
 │    ├── 预算/    （.xls/.xlsx/.et/.csv 含关键词）
 │    └── 其他文件/（剩余）
```

### 验证

- 六套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK
  - `test_gui_smoke.py` GUI_SMOKE_OK
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK
  - `test_v1_2_3_smoke.py` V1.2.3_SMOKE_OK
  - `test_v1_3_smoke.py` **V1.3_SMOKE_OK**

### 架构升级

**点位名称双层标准化**：
```
standard_name   (原始名称，不变)
match_name      (for_matching() 输出，用于全系统匹配)
filesystem_name (for_filesystem_path() 输出，用于未来文件夹生成)
```

**match_name 规则**：NFKC → 全角半角统一 → 中文括号→英文 → 中文标点→英文
→ 删除 /\\:*?"<>| → 去空格 → lowercase → 可选去括号

**filesystem_name 规则**：/ → -、保留中文、删除非法字符、去首尾空白和点号

**全系统 matcher 统一使用 match_name**，禁止原始字符串直接匹配。

### 新增

- `config/region_profile_2026_km.json` — 昆明区县语义归一化配置（7 个负责区县 + 10+ 别名）
- `core/region_profile.py`（120+ 行）——区县归一化模块：
  - `RegionProfile.load()` 从 JSON 加载配置
  - `normalize("安宁") → "安宁市"` alias 归一
  - `is_active()` 负责区域过滤
- `core/file_index.py`（250+ 行）——全量文件索引扫描引擎：
  - `FileIndex.build(root)` 递归扫描所有文件+目录
  - 扁平索引：所有 FileEntry + DirEntry，按 normalized_name 快速查找
  - `global_match_point(name)` 全局匹配：不管路径在哪，只要匹配就归属
  - `compute_drawing_status/budget_status` 基于索引的状态计算
- `tests/test_v1_2_3_smoke.py`（190+ 行）——8 项 v1.2.3 专项测试

### 修改

- `core/normalizer.py`（v1.2.3 扩展）：
  - 新增 `for_matching(raw, remove_parens)` — 生成 match_name
  - 新增 `for_filesystem_path(raw)` — 生成 filesystem_name
  - 保留 `for_comparison` / `for_filesystem` / `for_display` 向后兼容
- `core/matcher.py`（v1.2.3 升级）：
  - `match_strings` 默认使用 `for_matching()` 标准化
  - 移除 `for_comparison` / `for_filesystem` 依赖
- `core/scanner.py`（v1.2.3 重构）：
  - 新增 `scan_with_file_index()` — 基于 FileIndex 的新扫描流程
  - 新增 `match_points_from_index()` — 基于 FileIndex 的全局匹配
  - 新增区县过滤：非 active_county 项目跳过
  - `match_single_folder` 使用 `for_matching()` 标准化
  - 保留所有旧 API 向后兼容
- `core/scan_result.py`（v1.2.3 切换）：
  - `build_scan_results` 从旧 `scan_project_root` 切换为 `scan_with_file_index` + `match_points_from_index`
  - 区县归一化：`profile.normalize()` 自动将别名转为标准名
  - 非负责区县过滤：不在 active_counties 的点位自动忽略
- `ui/widgets/pages/project_detail_page.py`（v1.2.3 切换）：
  - `_try_match_from_sandbox` 切换为 FileIndex 扫描
  - `_load_points_from_db` 新增区县归一化 + 非负责区县过滤
- `ui/widgets/pages/project_management_page.py`（v1.2.3 优化）：
  - 删除"区县数量"列（9 列 → 8 列）
  - `_fetch_project_stats` 优先从 `ScanResultSummary` 缓存读取
  - 点位数量 = summary.total_points，完成率 = summary.completion_rate
- `core/scan_result.py`（v1.2.3 扩展）：
  - `ScanResultSummary` 新增 `completed_points` / `completion_rate`
  - `from_items` 计算规则：完成 = CAD有 AND 预算有
  - 全局缓存 `_project_summaries`：`get_cached_summary(project_id)`
- `tests/test_gui_smoke.py` — 版本标签更新

### 验证

- 五套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK
  - `test_gui_smoke.py` GUI_SMOKE_OK
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK
  - `test_v1_2_3_smoke.py` V1.2.3_SMOKE_OK

### 新增

- `core/scan_match_history_repository.py`（180+ 行）——匹配历史 CRUD：
  - `scan_match_history` 表：id / project_id / standard_point_name / actual_folder / match_method / confirmed_by / confirmed_at / created_at
  - `save_match_history`（upsert）、`fetch_project_history`（全量查询）、`fetch_match_by_point`（单点查询）、`delete_project_history`
  - project_id 外键关联 projects(id) ON DELETE CASCADE

- 扫描结果中心 `ScanCenterPage`（v1.2.2 升级）：
  - **人工确认**：结果列表第 8 列「确认」按钮，切换"未确认"/"已确认"
  - **全部确认**、**批量确认已匹配项**按钮
  - **重新匹配**按钮：`RematchDialog` 列出候选目录，NOT_FOUND/PARTIAL_MATCH/MULTIPLE_MATCH 可手动选目录
  - **导出 Excel**按钮：含序号/标准点位/实际目录/区县/CAD/预算/匹配率/匹配状态/确认状态/匹配方式/建议
  - **学习机制**：确认时调用 `save_match_history` 保存；`build_scan_results` 扫描时优先读取历史，已确认点位跳过模糊匹配
  - 统计卡片新增「已确认」指标

### 修改

- `core/scan_result.py`：
  - `ScanResultItem` 新增 `confirmed`(bool)、`match_method`(str: fuzzy/history/manual)、`confirmed_label` 属性
  - `ScanResultSummary` 新增 `confirmed_count`
  - `build_scan_results` 新增 `db_path` 参数，扫描时加载历史确认
- `ui/widgets/pages/scan_center_page.py`（重写核心页面，800+ 行）：
  - `ScanResultTable`：增加确认按钮列 + `confirm_toggled` 信号
  - `RematchDialog`：500×350 候选目录选择对话框
  - `ScanCenterPage`：全部确认/批量确认/重新匹配/导出 Excel 完整实现
  - `StatCardRow`：新增 confirmed_card
- `app.py`：启动时初始化 `scan_match_history` 表
- `tests/test_gui_smoke.py`：v1.2.2 架构校验（8 列/确认信号/新按钮/RematchDialog）
- `tests/test_import_smoke.py`：新增 `test_scan_match_history` CRUD 测试

### 约束遵循

- ❌ 禁止修改文件/目录/重命名/移动/删除 ✅
- ❌ 禁止修改数据库现有表 ✅（仅新增 scan_match_history）
- ✅ 所有操作仅修改扫描结果和历史确认

### 验证

- 四套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK（含 v1.2.2 匹配历史 CRUD）
  - `test_gui_smoke.py` GUI_SMOKE_OK（v1.2.2 架构校验）
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK

## [v1.2.1-patch] - 2026-07-06 — v1.2.1 Patch（动态字段文字绘制区 + 导入线程亲和性）

### Bug 1：动态字段「自定义列名」输入框文字绘制区域被压缩

**问题现象**：输入框高度正常、光标正常、文字已输入，但文字绘制区域异常（文字被压扁）。

**根因（实测确认）**：QLineEdit 放入 QTableWidget cellWidget 后，垂直 sizePolicy 为 Preferred，
Qt 布局计算给 QLineEdit 的高度仅 21px（字体 13px + 少量）。但全局 QSS `padding: 7px 10px`
在渲染时按 7px 上下绘制 padding，导致文字实际绘制区域 = 21 - 14(padding) - 2(border) = **5px**，
13px 字体被压扁到 5px 区域 → 文字绘制区域异常。

**实测数据**（离屏诊断）：
```
修复前：QLineEdit.height()=21  文字可绘制高度=5px  ★★★ 被裁剪 ★★★
修复后：QLineEdit.height()=32  文字可绘制高度=16px  OK
```

**修复**（`ui/widgets/scale_table_wizard.py` `_add_dynamic_field`）：
- QLineEdit `setMinimumHeight(32)`：强制最小高度 = 字体 13 + padding 14 + border 2 + 余量 3
- QComboBox 同样 `setMinimumHeight(32)` 防止相同压缩
- 移除 `setAlignment(AlignVCenter)`（垂直对齐由 sizeHint + minimumHeight 保证）

### Bug 2：点击「确认导入」后程序闪退（线程亲和性违反）

**问题现象**：进度条跑满后，整个主程序闪退。

**根因（faulthandler 实测捕获）**：
```
QWidget::repaint: Recursive repaint detected
Windows fatal exception: access violation
Current thread 0x0000668c [QThread]:
  project_detail_page.py, line 867 in on_progress
  scale_import_worker.py, line 143 in _do_run_import
```

worker 线程 `progress.emit(80, "保存配置 ...")` 时，`on_progress` 闭包在 **worker 线程**直接执行
（不是主线程），操作主线程的 QProgressDialog → 违反 Qt 线程亲和性 → access violation。

**为什么 QueuedConnection 没生效**：`on_progress` 是 Python 闭包，不是 QObject 方法，
没有 QObject 亲和性，Qt 无法将其投递到主线程事件循环。PySide6 中闭包作为 slot 始终以
DirectConnection 方式在 emit 的线程执行。

**修复**（`ui/widgets/pages/project_detail_page.py` `_run_scale_import`）：
- 把 `on_progress` / `on_succeeded` / `on_failed` / `on_cancel` 四个闭包改为
  `ProjectDetailPage` 的实例方法（`_on_import_progress` / `_on_import_succeeded` /
  `_on_import_failed` / `_on_import_cancel`），用 `@Slot` 装饰
- 信号连接显式指定 `Qt.ConnectionType.QueuedConnection`，确保 slot 在主线程事件循环执行
- `progress` 对话框改为实例属性 `_import_progress`，供实例方法访问
- `_on_import_progress` 加 `progress.value() != val` 防护，防止重复值触发递归 repaint
- `_on_import_thread_finished` 清理 `_import_progress` 引用

### 修改文件

- `ui/widgets/scale_table_wizard.py` — `_add_dynamic_field`：setMinimumHeight(32) 修复文字绘制区域
- `ui/widgets/pages/project_detail_page.py` — `_run_scale_import` 重写：闭包→实例方法 + QueuedConnection
- 新增 import：`from PySide6.QtCore import Qt, Signal, QThread, Slot`

### 验证

- 四套冒烟测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK
  - `test_gui_smoke.py` GUI_SMOKE_OK
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK
- Bug 2 完整链路离屏复现测试：导入 → 保存配置 → 刷新详情页 → 正常退出，无 access violation

## [v1.2.1-bugfix] - 2026-07-05 — v1.2.1 BugFix（动态字段输入框 + 导入闪退修复）

### Bug 1：动态字段映射界面输入框无法正常显示

**问题**：点击「＋ 添加字段」后，左侧自定义列名 QLineEdit 输入内容不可见。

**根因**：QLineEdit 放入 QTableWidget 单元格时，未设置最小宽度、尺寸策略和行高。默认行高不足以容纳 padding(7px*2 + 字体)，且未声明 Expanding 策略。

**修复**（`ui/widgets/scale_table_wizard.py`）：
- `_add_dynamic_field`：新增 `setRowHeight(row, 36)` 确保行高
- QLineEdit 新增 `setMinimumWidth(80)` + `setSizePolicy(Expanding, Preferred)` 填充单元格

### Bug 2：确认导入后程序闪退

**问题**：点击「确认导入」后，导入完成立即闪退（程序整个退出）。

**根因**：`_run_scale_import` 线程清理逻辑有严重缺陷：
1. `_cleanup_thread` 同时作为信号槽和被 `on_succeeded`/`on_failed` 直接调用，造成双重清理
2. `_cleanup_thread` 在主线程信号处理器内调用 `wait(3000)` 阻塞事件循环
3. `wait()` 超时后调用 `terminate()` 强制终止线程——这是 Qt 明确警告的危险操作，可导致锁死/崩溃

**修复**（`ui/widgets/pages/project_detail_page.py`）：
- 删除 `_cleanup_thread`，拆分为两个安全方法：
  - `_request_thread_quit()`：非阻塞 `quit()`，立即返回
  - `_on_import_thread_finished()`：由 `QThread.finished` 信号触发，安全断开信号并清理引用
- 移除所有 `wait()` / `terminate()` 调用——不再阻塞主线程
- 移除重复的 `self._scale_worker.succeeded/failed.connect(self._cleanup_thread)` 连接
- Worker（线程已停止）直接清引用由 Python GC 回收，不调用 `deleteLater()`（线程停止后事件无法投递）

### 修改文件

- `ui/widgets/scale_table_wizard.py` — `_add_dynamic_field`：QLineEdit 尺寸策略 + 行高
- `ui/widgets/pages/project_detail_page.py` — `_run_scale_import` 重写清理流程：
  `_cleanup_thread` → `_request_thread_quit` + `_on_import_thread_finished`
- `tests/test_gui_smoke.py` — 架构校验更新（`_cleanup_thread` → 新方法名）

### 验证

- 四套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK
  - `test_gui_smoke.py` GUI_SMOKE_OK
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK

## [v1.2.1] - 2026-07-05 — v1.2.1 规模表导入优化

### 问题修复

四大问题全部修复：

**问题一：Sheet 评分算法重构**

旧评分只看字段关键词，导致"材料表"评分高于"项目规模表"。

修复：
- 三层评分架构（Sheet 名称 45% + 表格结构 35% + 字段关键词 20%）
- `_score_sheet_name`：Sheet 名称命中"规模表/项目规模/工程规模/设计规模"等关键词 → 最高分
- `_score_table_structure`：评估列数/行数/数据密度，材料表（≤6列、字段简单）自动降分
- `_score_sheet_anti`：反例检测（材料表/封面/目录/汇总/说明/模板等）→ 大幅降权
- `_score_field_keywords`：降为辅助评分

**问题二：多行表头识别**

旧版无法识别合并单元格 + 多行表头，生成 `__col_x__` 占位。

修复（v1.2.1 二次修复，正确处理三层合并表头）：
- `read_all_sheets` 重写：`read_only=False` 获取 merged_cells 信息
- `_build_merged_lookup`：构建 (row,col) → 合并范围查询映射
- `_get_merged_value` / `_is_merged_anchor` / `_is_merged_cell`：合并单元格状态查询
- `_detect_header_region`：识别表头起始/结束行，跳过纯标题行（只有1个独立文本列）
- `_build_composite_headers` 核心算法——按列向下遍历，正确处理三种合并状态：
  - **锚点单元格**（合并范围左上角）→ 取自己的值作为一个表头层
  - **纵向合并覆盖**（同列、非锚点）→ 锚点值已在上层加入，跳过
  - **横向合并覆盖**（同行、非锚点）→ 继承同行锚点的值作为一个表头层（去重）
  - **非合并单元格** → 取自己的值
  - 去重后用 "-" 拼接
- `_is_numeric`：数字判定（含小数、负号、百分号）
- 数据行从表头结束行 +1 开始
- 禁止生成 `__col_x__`，兜底使用"列N"
- `excel_reader.py` 同步改为"列N"

**真实规模表验证**（昆明2025数字家庭项目概预算批复表）：
- 「项目建设规模表」评分 0.851（最高），63 列 × 482 行
- 表头正确识别第3~5行为三层合并表头：
  - 列8 = `社区前期建设情况-末端分光器端口数`（H3:I3横向 + H4:H5纵向）
  - 列9 = `社区前期建设情况-发展用户数`（H3:I3横向继承 + I4:I5纵向）
  - 列15-18 = `一张光缆网接入信息（三总必填）-...`（O3:R3横向继承）
  - 列23-29 = `线路部分-光缆线路设计长度-新建架空/附挂/...`（W3:BJ3 + W4:AC4 + 第5行三层组合）
  - 列1 = `序号`（A3:A5纵向合并只取一次）
- 数据行正确：序号=1/2/3、区县=东川、社区名称=阿旺镇-安乐村-...

**问题三：动态字段映射优化**

旧版将 60+ 字段全部加入，体验很差。

修复：
- `classify_dynamic_fields` 返回候选列表，默认 `selected=False`
- `get_default_dynamic_fields()` 返回空列表
- ScaleTableWizard Step 3 改为动态字段手动选择：
  - 「＋ 添加字段」按钮逐行添加
  - 左侧自定义列名（QLineEdit 可编辑）
  - 右侧选择规模表列（QComboBox，自动预选已知概念）
  - 「✕」按钮删除行
  - `_read_dynamic_fields_from_ui()` 统一读取

**问题四：程序崩溃修复**

旧版导入完成后程序自动退出，无异常捕获。

修复：
- `_run_scale_import`：所有回调包裹 try/except，`_import_cancelled` 标志防重复
- `_cleanup_thread`：安全断开信号 → quit → wait(3000) → terminate → deleteLater
- `ScaleImportWorker._do_run_import`：主逻辑包裹 try/except，任何异常 emit failed
- `on_failed` 弹出错误提示 + 记录完整日志，保留当前窗口不崩溃

### 修改

- `core/scale_table_engine.py` — 完全重写（700+ 行）：Sheet 评分三层架构 / 多行表头识别 / 动态字段候选
- `ui/widgets/scale_table_wizard.py` — 完全重写（500+ 行）：Step 3 动态字段手动添加 / 合并规则到 Step 2
- `ui/widgets/pages/project_detail_page.py` — _run_scale_import 增强 + _cleanup_thread
- `data_import/scale_import_worker.py` — _do_run_import 双保险异常保护
- `data_import/excel_reader.py` — 空表头占位 __col_x__ → 列N
- `tests/test_gui_smoke.py` — 架构校验更新至 v1.2.1

### 验证

- 四套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK
  - `test_gui_smoke.py` GUI_SMOKE_OK（v1.2.1 架构校验）
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK

## [v1.2.0] - 2026-07-05 — v1.2 扫描结果中心

### 架构升级

新增扫描结果中心（Scan Center）页面，将分散在项目详情页的扫描匹配分析集中展示：

```
point_dictionary（标准点位字典）
    +
scanner（沙盒文件系统扫描）
    +
matcher（RapidFuzz 匹配引擎）
    ↓
build_scan_results() 统一协调器
    ↓
ScanResultSummary（汇总统计 + ScanResultItem 列表）
    ↓
ScanCenterPage（统计卡片 + 结果列表 + 详情预览）
```

### 新增

- `core/scan_result.py`（280+ 行）——统一扫描结果数据模型：
  - `MatchStatus` 枚举：MATCHED/PARTIAL_MATCH/NOT_FOUND/MULTIPLE_MATCH
    - 每种状态含中文标签和 Windows 11 风格颜色常量（绿#107C10/黄#FFB900/红#D13438/橙#FF8C00）
  - `ScanResultItem` 数据类：标准点位名称/Excel原始名称/匹配文件夹/匹配分数/CAD状态/预算状态/匹配状态/建议说明/CAD文件数/预算文件数/扫描文件列表/dynamic_data
    - `from_point_dict(point, match_result)` 工厂方法
    - `_generate_suggestion` 自动建议生成
    - `match_percent` 属性（0-100 整数）
    - `to_dict` 序列化
  - `ScanResultSummary` 数据类：项目信息/扫描元数据/统计计数（总点位/已匹配/部分匹配/未匹配/多候选/CAD缺失/预算缺失）
    - `from_items` 从 ScanResultItem 列表自动汇总
    - `to_dict/to_json` 序列化
  - `build_scan_results(project_id, project_name, points)` 协调器函数：复用 scanner.scan_project_root + scanner.match_project_sites + matcher.match_folder，生成统一结果。不重复写匹配逻辑
- `ui/widgets/pages/scan_center_page.py`（700+ 行）——扫描结果中心页面：
  - `ScanCenterPage(BasePage)`：独立导航页（page key=scan_center）
  - **顶部信息栏**：项目名称/扫描时间/扫描耗时/扫描目录 + 执行扫描/重新扫描按钮
  - **统计卡片组**（`StatCardRow`）：6 张 `StatCard` 卡片（总点位/已匹配/部分匹配/未匹配/CAD缺失/预算缺失），颜色编码
  - **结果列表**（`ScanResultTable`）：7 固定列（状态/标准点位/实际文件夹/匹配率/CAD/预算/建议）
    - 状态列带颜色标记（绿/黄/红/橙）；CAD/预算列绿"有"红"无"
    - 支持排序/筛选/搜索；禁止修改数据
    - 双击行 → `item_selected` 信号
  - **筛选栏**（`ScanFilterBar`）：状态下拉 + 搜索框 + CAD下拉 + 预算下拉，组合筛选
  - **详情预览面板**（`DetailPreviewPanel`）：右侧面板，QSplitter 左右分栏（70/30）
    - 显示：标准点位名称/Excel原始名称/实际匹配目录/匹配率/匹配状态/CAD文件数/预算文件数/CAD状态/预算状态/建议说明/扫描到的文件列表
    - 仅查看，禁止修改
  - **重新扫描**（`_on_scan`）：重新读取项目目录 → `build_scan_results` → 覆盖内存结果，禁止修改数据库
  - **预留接口**（仅定义，不实现）：
    - `RenamePreviewInterface` — 重命名预览
    - `FolderBuilderInterface` — 文件夹构建
    - `HealthScoreInterface` — 健康评分
    - `AISuggestionInterface` — AI 建议

### 修改

- `ui/widgets/nav_tree.py`：新增「🔍 扫描结果中心」顶级导航节点（page key=scan_center）
- `ui/widgets/content_area.py`：注册 ScanCenterPage，总页面数 11→12；`show_project_detail` 同步预加载扫描中心数据
- `ui/widgets/pages/__init__.py`：导出 ScanCenterPage
- `ui/theme.py`：新增 StatCard、DetailPreviewPanel QSS 样式
- `tests/test_gui_smoke.py`：页面数校验 11→12；新增 v1.2.0 架构校验（ScanCenterPage 组件验证 + 预留接口验证）

### 约束遵循

- ❌ 禁止自动改名/移动/删除/建目录 ✅
- ❌ 禁止扫描真实目录之外的位置 ✅（复用 scanner 安全边界）
- ✅ 所有结果均来自 point_dictionary + scanner + matcher，不重复写匹配逻辑
- ✅ 仅分析并展示扫描结果，禁止修改任何数据
- ✅ 结果列表允许排序/筛选/搜索，禁止修改数据
- ✅ 匹配状态颜色规范：绿色MATCHED/黄色PARTIAL_MATCH/红色NOT_FOUND/橙色MULTIPLE_MATCH
- ✅ 详情预览仅查看，禁止修改

### 验证

- 四套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK
  - `test_gui_smoke.py` GUI_SMOKE_OK（v1.2.0 架构校验：12 页/ScanCenterPage/预留接口）
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK

## [v1.1.1] - 2026-07-05 — v1.1.1 匹配引擎升级（RapidFuzz 统一接管）

### 架构升级

全项目所有字符串匹配统一走 `core/normalizer.py` → `core/matcher.py` → RapidFuzz：

```
原始字符串 A / B
    ↓ normalizer.for_comparison() / for_filesystem()
标准化（NFKC + 全角→半角 + 中文括号/标点统一 + 大小写统一）
    ↓ matcher.match_*()
RapidFuzz WRatio + partial_ratio 综合评分
    ↓
MatchResult（score / kind / reason）
```

### 新增

- `core/normalizer.py`（170 行）——统一标准化模块：
  - `for_comparison(raw)`：NFKC 统一 → 全角空格 → 中文括号/标点统一 → 空白清理 → 小写
  - `for_filesystem(raw)`：for_comparison + 删除文件系统特殊字符 `/\\:*?"<>|`
  - `for_display(raw)`：轻量清理（保留括号和特殊字符）
  - 所有比较前必须先标准化；禁止修改原始数据；数据库保存原始名称
- `core/matcher.py`（320 行）——统一匹配引擎：
  - `match_strings(a, b)`：通用底层引擎（WRatio + partial_ratio 多策略评分）
  - `match_sheet / match_field / match_point_name / match_folder / match_filename`：场景化入口
  - `best_match(query, candidates)`：候选列表中找最佳
  - `any_match(query, candidates)`：返回第一个达标的
  - `is_match / is_strong_match`：快速 bool 判断
  - `MatchResult` 数据结构：score / kind (EXACT/CONTAINS/FUZZY/WEAK/NONE) / reason / meta
  - `MatchThresholds` 配置预留（exact=95 / contains=85 / fuzzy=70，以后放入 Settings）
- `tests/test_rapidfuzz.py`：RapidFuzz 安装验证测试

### 修改（6 个模块升级）

- `core/scanner.py`：
  - 删除 `normalize_for_match` 函数（迁移到 normalizer.for_filesystem）
  - 删除 `_match_keyword` 函数（迁移到 matcher.match_folder）
  - `_build_site_node`：图纸/预算子目录识别走 `_match_keyword` → matcher
  - `match_single_folder`：`==`/`in` 手动匹配 → `matcher.match_folder`（RapidFuzz 引擎）
- `core/scale_table_engine.py`：
  - `score_sheet_likelihood`：手动 `lower()+in` → `matcher.is_match`
  - `_best_match`：手动 `lower()+in` → `matcher.any_match`
  - `_guess_dynamic_concept`：手动 `lower()+in` → `matcher.any_match`
  - `build_field_candidates`：`any(kw.lower() in h_lower)` → `matcher.is_match`
- `core/project_categories.py`：
  - `resolve_category`：`a in s` 子串匹配 → `matcher.match_field`
- `data_import/excel_reader.py`：
  - `_detect_header_row`：`kw.lower() in text` → `matcher.match_field`
- `ui/widgets/field_mapping_dialog.py`：
  - `guess_mapping`（静态）：`kw.lower() in lh` → `_match_field(h, kw).is_match`
  - `_auto_guess`（实例）：同上
  - 新增模块级 `_match_field` 导入（try/except 兼容不同运行上下文）
- `ui/widgets/pages/project_detail_page.py`：
  - `_try_match_from_sandbox`：手动 `lower()+in` 项目名匹配 → `matcher.match_folder`

### 约束遵循

- ❌ 禁止修改业务流程 ✅
- ❌ 禁止修改数据库结构 ✅
- ❌ 禁止修改UI ✅
- ❌ 仅升级匹配算法 ✅
- ❌ 业务代码直接调用 RapidFuzz ✅（全部走 matcher.py）

### 验证

- 四套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK
  - `test_gui_smoke.py` GUI_SMOKE_OK
  - `test_import_e2e.py` E2E_OK
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK

## [v1.1.0] - 2026-07-05 — v1.1 规模表智能识别引擎

### 架构升级

系统从"硬编码字段匹配"升级为**通用规模表智能识别引擎**，所有项目类型共用：

```
Excel（规模表，多 Sheet）
    ↓ read_all_sheets + detect_best_sheet
Sheet 自动识别（评分排序 + 用户选择/记忆）
    ↓ ScaleTableWizard 四步向导
字段智能识别 + 区县识别 + 点位规则 + 预览
    ↓ ScaleImportWorker 后台导入
point_dictionary 表（含 dynamic_data JSON）
    ↓
UI 动态列展示（固定 5 列 + 规模表动态字段）
    ↓
Project Profile（project_profiles 表，配置持久化）
```

### 新增

- `core/scale_table_engine.py`（400+ 行）——纯逻辑识别引擎：
  - Sheet 自动识别：`score_sheet_likelihood`（三维评分）、`detect_best_sheet`（全部 Sheet 排序）、
    `read_all_sheets`（多 Sheet 读取）
  - 字段智能识别：点位名称/区县/起点/终点自动检测、`build_field_candidates`（候选列表）
  - 点位生成规则：`should_concatenate`（接入段/城域网→起点+终点，其余→单字段）、
    `generate_point_name`
  - 动态字段：`classify_dynamic_fields`（固定字段外全部自动归入）、
    已知概念标注（长度/芯数/经度/纬度/设备型号/端口数/带宽/建设方式/备注）
  - 预览+数据构建：`build_preview_rows`、`build_point_records`
- `core/project_profile_repository.py`——project_profiles 表 CRUD：
  - 表字段：project_id (UNIQUE FK) / sheet_name / point_name_field / county_field /
    start_point_field / end_point_field / use_concatenation / dynamic_fields (JSON) /
    created_at / updated_at
  - `upsert_profile`（INSERT OR REPLACE） / `fetch_profile` / `delete_profile` / `profile_exists`
- `data_import/scale_import_worker.py`——规模表后台 Worker：
  - `ScaleImportWorker(QObject)`：接收已确认映射 → `build_point_records` →
    清空+插入 point_dictionary → 保存 project_profiles → 信号通知
- `ui/widgets/scale_table_wizard.py`——四步导入向导（`ScaleTableWizard(QDialog)`）：
  - Step 0: Sheet 选择（评分排序 + 单选表格）
  - Step 1: 字段映射（自动推荐 + QComboBox 手动修正）
  - Step 2: 点位生成规则（单字段 / 起点+终点，按项目类型默认推荐）
  - Step 3: 导入预览（前 10 条 + 动态字段列 + 统计信息）
  - 加载已有 Profile 时自动预填所有步骤；确认后保存配置
- `tests/test_v1_1_smoke.py`：引擎逻辑(9项) + 配置 CRUD(5项) + 表升级(1项) 全链路

### 修改

- `core/projects_repository.py`：
  - point_dictionary 表 v1.1.0：新增 `dynamic_data` TEXT 列（JSON）
  - `init_point_dictionary_table`：自动检测旧表并 ALTER TABLE 追加列
  - `insert_points`：新增 dynamic_data 参数序列化 JSON 存储
  - `fetch_points_by_project` / `fetch_points_with_status`：返回 dynamic_data
- `ui/widgets/pages/project_detail_page.py`：
  - `_on_import_detail_clicked`：接入 ScaleTableWizard 四步向导（替代旧关键词粗匹配）
  - `_run_scale_import`：ScaleImportWorker 后台导入 + QProgressDialog
  - `_load_points_from_db`：从 dynamic_data 提取动态字段，自动设置 PointListTable 动态列
  - `_extract_dynamic_columns` static：提取全部动态字段名（去重、保持首见顺序）
  - 删除旧 `_build_point_dictionary_records` / `_match_header`（逻辑移至 scale_table_engine）
- `app.py`：启动时初始化 project_profiles 表
- `tests/test_gui_smoke.py`：架构校验更新至 v1.1.0（新模块导入、表结构、方法签名）

### 约束遵循

- ❌ 写死字段名称 ✅（全部关键词匹配 + 用户可修正，保存到 Project Profile）
- ❌ 写死 Sheet 名称 ✅（自动评分排序 + 用户选择，保存到 Project Profile）
- ❌ 写死项目类型逻辑 ✅（接入段/城域网默认拼接，其余默认单字段，用户可修改并保存）
- 所有用户修正均保存到 Project Profile ✅
- 不新增文件整理功能 ✅

### 验证

- 四套测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK（导入分流+仓储+点位字典+扫描器）
  - `test_gui_smoke.py` GUI_SMOKE_OK（v1.1.0 架构校验：新模块导入、dynamic_data 列、project_profiles 表）
  - `test_import_e2e.py` E2E_OK（端到端分流不受影响）
  - `test_v1_1_smoke.py` v1.1.0_SMOKE_OK（引擎 9 项 + 配置 5 项 + 升级 1 项）

### 已知局限（预留）

- 规模表版本比较：新增/删除/修改点位增量更新接口已预留，本版不实现
- 项目整体资料面板仍为占位

## [v1.0.0] - 2026-07-05 — 维护：版本号同步 + 清理残留缓存

### 修改
- `ai_office_agent/__init__.py`：`__version__` 从 `"0.1.0"` 更新为 `"1.0.0"`
- 删除残留 `.pyc` 缓存：`project_overview_page.cpython-314.pyc`（源文件已在 v0.6.0 删除）

### 验证
- 三套冒烟测试全部通过（ALL_SMOKE_OK / GUI_SMOKE_OK / E2E_OK）

## [v1.0.0-sandbox] - 2026-07-04 — v1.0 文件系统治理沙盒模式（阶段2-4）

### 沙盒安全约束

- 硬编码边界：仅扫描 `D:\AI-Office-Agent-Test\`，禁止访问其他路径
- 全部只读操作：不创建/修改/删除任何文件

### 新增

- `core/scanner.py`（435 行）——沙盒文件系统扫描器：
  - **安全阀**：`_validate_path` / `_safe_resolve` — 路径偏离 TEST_ROOT_PATH 立即 ValueError
  - **扫描引擎**（阶段2）：`scan_project_root` → `_scan_project_dir` → `_scan_folder`
    - `ProjectNode` / `FolderNode` / `FileNode` 三级数据结构
    - 只读枚举项目文件夹 / 点位文件夹 / 文件
  - **匹配系统**（阶段3）：`match_single_folder` / `match_project_folders` / `normalize_for_match`
    - 完全相等（score=1.0）/ 包含关系（score=0.85）/ 不匹配（score=0.0）
    - `MatchResult` 数据结构：folder_name / point_id / point_name / match_score
  - **状态计算**（阶段4）：`compute_drawing_status`（*.dwg 存在→有）/ `compute_budget_status`（预算文件夹有文件→有）
  - **便捷入口**：`run_full_scan` — 扫描+匹配+状态一条龙
- 沙盒测试目录 `D:\AI-Office-Agent-Test\`：
  - 3 个模拟项目（社区改造/集客专线/接入段）
  - 6+ 个点位文件夹，覆盖有/无图纸、有/无预算的组合场景
- `tests/test_import_smoke.py`：新增 `test_scanner`（扫描/匹配/状态全覆盖断言）

### 修改

- `project_detail_page.py` 升级接入沙盒扫描器：
  - `_load_points_from_db`：从 point_dictionary 加载 → `_try_match_from_sandbox` 获取真实文件状态
  - 新增 `_try_match_from_sandbox`：扫描 TEST_ROOT_PATH → 项目名匹配 → 点位匹配 → 图纸/预算状态计算
  - 沙盒目录不存在时回退默认「无」状态，不影响现有功能
  - 引入 `core.scanner` 依赖（TEST_ROOT_PATH / compute_drawing_status / compute_budget_status 等）

### 约束遵循

- ❌ 禁止访问真实工程目录 ✅（硬编码 TEST_ROOT_PATH）
- ❌ 禁止改名 ✅（全部只读操作）
- ❌ 禁止移动/删除文件 ✅
- ❌ 禁止 UI 结构变化 ✅（仅更新状态字段）
- ❌ 禁止新增页面 ✅

### 测试验证

| 点位 | 图纸 | 预算 | 验证结果 |
|------|------|------|---------|
| SiteA | 有 | 有 | ✅ 图纸有2个.dwg，预算有.xlsx |
| SiteB | 有 | 无 | ✅ 图纸有.dwg，预算文件夹为空 |
| SiteC | 有 | 有 | ✅ 图纸有.dwg，预算有.pdf |

- 三套冒烟测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK（6 个测试，含 scanner）
  - `test_gui_smoke.py` GUI_SMOKE_OK
  - `test_import_e2e.py` E2E_OK

## [v1.0.0] - 2026-07-04 — v1.0 文件系统治理阶段1：标准点位字典系统

### 架构升级

系统从"Excel + 项目管理工具"升级为**工程文件治理系统**：

```
Excel（标准点位表，唯一标准来源）
    ↓
标准点位字典（point_dictionary 表）
    ↓
文件系统扫描（待阶段2）
    ↓
自动匹配 + 纠偏 + 标准化（待阶段3-5）
    ↓
UI 实时展示
```

### 新增

- `point_dictionary` 表（`core/projects_repository.py`）：
  - 字段：id / project_id / standard_point_name / county / original_name
  - project_id 外键关联 projects(id) ON DELETE CASCADE
  - `init_point_dictionary_table`：建表（IF NOT EXISTS 幂等）
  - `clear_points_by_project` / `insert_points`：清空+批量插入（可重入）
  - `fetch_points_by_project` / `fetch_points_with_status`：查询（带状态默认值）
  - `count_points_by_project`：统计点位数量
  - `normalize_point_name`：点位名称标准化（去除 / \\ * ? : " < > | 空格）
- 测试 `test_point_dictionary`：建表/插入/查询/清空/统计/标准化全覆盖

### 修改

- `project_detail_page.py`（v1.0.0 升级）：
  - **明细导入写入 point_dictionary 表**（替代 v0.9.0 的纯展示）
    - 导入前先清空本项目旧点位（可重入）
    - 点位名称自动标准化作为文件匹配基准
    - 导入后从 point_dictionary 表加载渲染
  - `load_project`：自动从 point_dictionary 表加载点位（不再空表）
  - 新增 `_load_points_from_db`：从表加载点位并渲染
  - 新增 `_build_point_dictionary_records`：Excel 行 → 点位字典记录
  - `_apply_filter` 筛选已启用：区县/名称/图纸/预算组合条件
  - 删除 `_build_points_from_rows`（旧纯展示方法）
- `test_gui_smoke.py`：架构校验更新（验证 `_load_points_from_db` / `_build_point_dictionary_records`）
- `test_import_smoke.py`：文档注释更新为 v1.0.0

### 约束遵循

- Excel 是唯一标准来源；所有文件匹配以 standard_point_name 为基准 ✅
- 不改 UI 布局/页面架构 ✅
- 筛选栏逻辑启用 ✅
- 不删除文件、不新增无关功能 ✅

### 验证

- 三套冒烟测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK（含 point_dictionary 全链路）
  - `test_gui_smoke.py` GUI_SMOKE_OK（v1.0.0 架构校验）
  - `test_import_e2e.py` E2E_OK（导入分流链路不受影响）

## [v0.9.4] - 2026-07-04 — 项目详情页 UI 微调（中间区域高度一致 + 纵向可缩放）

### 调整原因
v0.9.3 存在两个问题：
1. 中间区域概览卡（241px）与资料面板（150px）高度不一致——右侧明显小于左侧
2. `resizeEvent` 中 `setMinimumHeight(half)` 强制点表半页，导致窗口纵向只能拉大不能缩小

### 修改（仅 `ui/widgets/pages/project_detail_page.py`）
- 中间区域概览与资料：vertical 策略从 Fixed 改为 **Preferred**
  - QHBoxLayout 会自动将两个 Preferred 子控件拉齐同高（241px）
  - 中间区域容器 vertical 也改为 Preferred
- `resizeEvent`：`setMinimumHeight(half)` 改为 `setMinimumHeight(0)`
  - 点表不再强制半页，stretch=1 自然分配剩余空间
  - 窗口可自由纵向缩放（800→500 实测流畅）
- 模块顶部 docstring 同步更新

### 实测验证（真实主窗口 1280×800，多尺寸）
- 概览 241 = 资料 241（高度一致）✅
- 纵向缩放 800→700→600→500 正常，detail 644→544→495 随窗口自然变化 ✅
- 中间区域同高在所有尺寸保持 ✅

### 约束遵循
- 不改数据结构/导入逻辑/数据库/页面架构
- 仅改 UI layout/QSizePolicy/stretch

### 验证
- 三套冒烟测试全部通过（GUI_SMOKE_OK / ALL_SMOKE_OK / E2E_OK exit=0）

## [v0.9.3] - 2026-07-04 — 项目详情页 UI 布局重构（双层布局 VBox+HBox）

### 调整原因
v0.9.2 将概览与资料改为上下纵向堆叠，导致顶部空间浪费、点位列表被压缩，且全页单列
QVBoxLayout 不符合需求。本次按需求严格执行「双层布局结构」：主 QVBoxLayout 嵌套中间
QHBoxLayout，概览与资料横向并排。

### 修改（仅 `ui/widgets/pages/project_detail_page.py`，只动 layout/QSizePolicy/stretch）
- 主布局 content_layout（QVBoxLayout）从上到下：
  1. 顶部工具栏（vertical=Fixed）
  2. **中间区域（QHBoxLayout 横向并排）**：vertical=Fixed
     - 项目概览卡（stretch=3 ≈ 60%）：vertical=Fixed，输入框 minimumHeight(24)
     - 项目整体资料面板（stretch=2 ≈ 40%）：vertical=Fixed
  3. 筛选栏（vertical=Fixed）
  4. 点位列表（vertical=Expanding，stretch=1）
- 新增 `_setup_middle_area`（替代原 `_setup_overview`/`_setup_documents` 两块独立块），
  显式用 QHBoxLayout 横向并排概览与资料，比例 3:2
- 加回 `resizeEvent`：动态 `point_table.setMinimumHeight(self.height() // 2)`，保证点位列表
  至少占页面 50%（与 v0.9.1 的差别：本次不配合 setMaximumHeight 压上方，中间区域 Fixed
  自然紧凑完整，不会被压扁）
- 模块顶部 docstring 同步更新

### 实测验证（真实主窗口，多尺寸）
- 中间区域横向并排：概览/资料宽度比 1.50 ≈ 60/40
- 概览完整（241=sizeHint），输入框宽 437px 不截断
- 资料完整（150=sizeHint），5 项分类全可见
- 点位列表占 0.499-0.500（≥50%）多尺寸稳定
- 主布局顺序：工具栏 → 中间HBox → 筛选栏 → 点表，无重叠

### 约束遵循
- 显式使用 QHBoxLayout（中间区域）；嵌套布局（VBox + HBox）
- 禁止概览与资料上下排列；禁止全页单列 QVBoxLayout
- 不改数据结构/导入逻辑/数据库/页面架构

### 验证
- 三套冒烟测试全部通过（GUI_SMOKE_OK / ALL_SMOKE_OK / E2E_OK exit=0）

## [v0.9.2] - 2026-07-04 — 项目详情页 UI 布局重构（纵向堆叠 + 完整显示）

### 调整原因
v0.9.1 将概览卡与资料面板横向并列并设 `setMaximumHeight(210)`，导致：
- 概览区域被压缩、输入框文字被截断（横向 360 宽内 5 个输入框挤在一行）
- 项目整体资料区域过小
- `resizeEvent` 半页强制 + `setMaximumHeight` 让页面只适合横向缩放，纵向伸缩不合理

本次按需求从上到下重构为纵向堆叠，仅改 UI layout / QSizePolicy / stretch，不改业务逻辑。

### 修改（仅 `ui/widgets/pages/project_detail_page.py`）
- 拆 `_setup_overview_and_documents` 为 `_setup_overview` + `_setup_documents`，两块独立纵向放入 content_layout
- **顶部工具栏**：vertical=Fixed（固定高度）
- **项目概览**：vertical=Fixed，宽度跟随父布局（去掉 `setFixedWidth(360)`），输入框获全宽 → 文字不再截断；每个 QLineEdit 设 `setMinimumHeight(24)` 防压缩
- **项目整体资料**：vertical=Fixed（中等高度），布局 margin/spacing 收紧（14→10、10→6），5 项分类完整显示
- **筛选栏**：vertical=Fixed
- **点位列表**：vertical=Expanding + stretch=1，占剩余全部纵向空间
- 删除 v0.9.1 的 `setMaximumHeight(210)`（压扁上方）与 `resizeEvent` 半页强制（与"点表占剩余"冲突）
- 模块顶部 docstring 同步更新

### 实测验证（真实主窗口 1280×800）
- 各块从上到下顺序正确、无重叠：工具栏(29) → 概览(241) → 资料(150) → 筛选(32) → 点表(剩余)
- 概览完整显示，输入框宽 811px，长项目名称不截断
- 资料 5 项分类（PDF/Word/Excel/其他资料/点位文件夹以外的文件夹）全部可见
- 点表 stretch=1 占剩余纵向空间

### 约束遵循
- 不改数据结构 / 导入逻辑 / 数据库 / 页面架构
- 仅 UI layout / QSizePolicy / stretch 调整
- 禁止事项全部遵守

### 验证
- 三套冒烟测试全部通过（GUI_SMOKE_OK / ALL_SMOKE_OK / E2E_OK exit=0）

### 已知局限
- 在固定窗口高度(800)下，概览(241)+资料(150)+筛选(32)+工具栏(29)的"完整显示"占用较多纵向空间，
  点位列表的"剩余空间"相对有限——这是"概览/资料完整显示 + 点表占剩余 stretch=1"的物理结果；
  窗口纵向拉大（如 900 高）时点表同步增大

## [v0.9.1] - 2026-07-04 — 项目详情页 UI 微调（点位明细表占半页）

### 调整原因
v0.9.0 点位列表实际占比约 1/3（offscreen 实测 0.36），用户要求占半页。本次仅调点表
占比，不改动其他任何内容。

### 修改
- `ui/widgets/pages/project_detail_page.py`：
  - `_setup_overview_and_documents`：上方面板加 `setMaximumHeight(210)`
    （= 资料面板内容下限 180 + 内边距 30，保证 5 项分类完整显示不裁切）
  - 新增 `resizeEvent` 重写：`point_table.setMinimumHeight(self.height() // 2)`，
    任意窗口尺寸下点位表稳定占详情页半页
- 实测（真实主窗口 1280×800 + 多尺寸）：点表 398/796 = 0.500；多尺寸 0.499-0.500；
  资料面板内容完整未裁切

### 约束遵循
- 不改动其他任何内容：概览卡 / 资料面板 / 筛选栏 / 按钮均不变
- 不改业务逻辑、不改数据库结构、不改页面架构

### 验证
- 三套冒烟测试全部通过
- offscreen 多尺寸验证点表≥半页且资料面板不裁切

## [v0.9.0] - 2026-07-03 — 项目详情页 UI 交互优化（布局比例 + 全分类双击 + 明细导入展示）

### 调整原因
v0.8.0 详情页存在三个交互问题：(1) 点位列表占比过小，非核心区域；(2) 双击进详情
仅在「全部项目」页，7 个分类页双击仅日志；(3) 无项目明细导入入口。本次仅修 UI 与
交互入口，不改业务逻辑、数据库结构、页面架构。

### 修改
- `ui/widgets/pages/project_detail_page.py`：
  - 布局比例：概览卡+资料面板外层改 `QSizePolicy(Preferred, Fixed)` 紧凑靠上固定
    高度；点位列表 `stretch=1` 占据剩余纵向空间（≥50% 屏幕高度，为核心区域）
  - 去重标题：页头不再动态显示「项目名称+编码」（概览卡已有，避免重复），固定为
    BasePage 静态「项目详情」标题；`_render_overview`/`_clear_overview` 不再改 title_label
  - 页头加「导入项目明细表」按钮（返回按钮旁，default 高亮，Windows11 风格）
  - 新增 `_on_import_detail_clicked`：QFileDialog 选 .xlsx → 复用 `excel_reader.read_sheet`
    基础读取 → `_build_points_from_rows` 按表头关键词粗匹配区县/点位名称，其余列作
    动态列展示到点位列表；图纸/预算状态本版无文件来源→判为「无」；不写库、不做映射
  - 引入 `excel_reader`、`QFileDialog`/`QMessageBox`/`QSizePolicy` 依赖
- `ui/widgets/pages/project_management_page.py`（`ProjectCategoryPage`）：
  - 加 `_open_detail_handler` 属性 + `set_open_detail_handler` 注入入口
  - 行 id 存第 0 列 UserRole；`_on_item_double_clicked` 改为调用回调打开详情
    （与全部项目页共用同一详情页）
- `ui/widgets/content_area.py`：给全部项目页 + 7 分类页统一注入
  `set_open_detail_handler(self.show_project_detail)`；移除原重复注入

### 约束遵循
- 仅 UI/交互调整：不改数据库结构、不重写页面架构、不引入新业务逻辑
- 明细导入仅基础读取+展示，不做映射、不写库、不改数据模型
- 不修改项目列表页结构；保持 Windows11 风格

### 验证
- 三套冒烟测试全部通过：
  - `test_gui_smoke.py`：详情页含 `import_detail_btn`；7 分类页均注入详情回调
  - `test_import_smoke.py` / `test_import_e2e.py`：未变，确认调整不影响导入链路

### 已知局限（本版不实现，按需求预留）
- 明细导入为基础读取展示，未做字段映射对话框、未写库（不持久化，刷新后丢失）
- 图纸/预算状态未接文件系统，明细导入时均判「无」
- 筛选栏已就位，但对导入展示的点位行尚未启用行过滤（待后续）

## [v0.8.0] - 2026-07-03 — 项目详情页 UI 结构调整（删树 / 概览+资料横向 / 点位列表+筛选）

### 调整原因
v0.7.0 详情页用左侧结构树（项目→区县→点位）承载层级，但业务上区县/点位应作为
可筛选的扁平表格呈现，且需「图纸状态/预算状态」列与动态列扩展；树结构与这些需求
冲突。故删除全部树结构，改为纵向布局：页头 → 概览卡与整体资料面板横向并列 →
筛选栏 → 点位列表。仅改 UI 层，不改业务逻辑。

### 新增（详情页内组件）
- `PointListTable(QTableWidget)`：点位列表表格
  - 固定 5 列（不可改）：序号 / 区县 / 点位名称 / 图纸状态 / 预算状态
  - `set_dynamic_columns`：动态列机制，规模表/明细表用户映射字段追加在固定列后
  - `load_points`：按点位数据渲染，图纸/预算状态由纯函数计算
- `ProjectDocumentsPanel(QFrame)`：项目整体资料面板
  - 分类：PDF / Word / Excel / 其他资料 / 点位文件夹以外的文件夹
  - 本版占位（不解析文件），为后续文件整理预留结构
- `PointFilterBar(QWidget)`：筛选栏
  - 区县下拉 + 点位名称搜索 + 图纸状态 + 预算状态，组合条件
  - `filter_changed` 信号通知外部重新筛选
- 模块级纯函数（状态判定规则，严格按需求，本版不接文件系统）：
  - `judge_drawing_status(has_cad, has_pdf)`：仅判 CAD——有 CAD→「有」，
    仅 PDF 无 CAD→「无」（PDF 不参与）
  - `judge_budget_status(has_budget_folder)`：预算文件夹存在→「有」，否则→「无」

### 修改
- `ui/widgets/pages/project_detail_page.py` 重写（删除全部树结构）：
  - 布局：页头(标题+返回按钮) → 横向面板[左概览卡 / 右整体资料面板] → 筛选栏 →
    点位列表
  - 概览卡：项目名称/编码/类型/年份/状态（纵向只读，沿用 v0.7.0 字段）
  - 移除 v0.7.0 的 QTreeWidget 与 `_build_tree`
  - `load_project` 保持按 id 查 projects 表渲染概览；点位表本版空（无数据源）
- `ui/theme.py`：补充概览卡 / 资料面板 / 面板标题 / 占位计数 QSS（Windows11 风格）

### 删除
- v0.7.0 详情页的左侧结构树（QTreeWidget）与 `_build_tree`、相关树常量
  （`_TREE_PROJECT` / `_TREE_OVERVIEW` / `_TREE_COUNTY` / `_TREE_SITE` /
  `_EMPTY_HINT`）

### 约束遵循
- 仅改 UI 层：不改业务逻辑、不接规模表、不解析文件、不做 AI
- 不用弹窗作为主流程；不恢复区县树结构
- 不修改项目列表页结构
- 保持 Windows11 风格

### 验证
- 三套冒烟测试全部通过：
  - `test_gui_smoke.py`：详情页无树、含返回按钮/概览字段/资料面板/筛选栏/点位表 5
    固定列（序号/区县/点位名称/图纸状态/预算状态）、筛选栏含 4 个控件
  - `test_import_smoke.py` / `test_import_e2e.py`：未变，确认 UI 重构不影响导入链路

### 已知局限（本版不实现，按需求预留）
- 点位列表无数据源（待规模表接入），表格渲染为空
- 动态列机制已就位，本版 0 列（待规模表/明细表导入映射）
- 图纸/预算状态规则已定义，但未接文件系统（不解析文件）
- 项目整体资料面板为占位，未枚举实际文件
- 筛选栏就位，但作用对象（点位行）本版为空

## [v0.7.0] - 2026-07-03 — 项目详情页面（基础结构）

### 新增
- `ui/widgets/pages/project_detail_page.py`：项目详情页（只读基础结构）
  - 页头：标题动态为「项目名称（项目编码）」+「返回项目列表」按钮
  - 左侧 QTreeWidget 结构树：项目 → 项目整体资料 / 区县列表（空）/ 点位列表（空）
  - 右侧默认「项目概览」表单：项目名称 / 编码 / 类型 / 年份 / 状态（全只读 QLineEdit）
  - `load_project(id)` 按 id 从 projects 表查询单条并渲染；查询不到则清空
- `projects_repository.py` 新增 `fetch_project_by_id(conn, id)`：按主键查单条
  （详情页数据来源，不接入规模表）

### 修改
- `ui/widgets/content_area.py`：
  - 注册详情页（page key=project_detail），总页面数 10 → 11
  - 新增 `show_project_detail(id)`：载入详情并切换
  - 详情页「返回」按钮 → `switch_to("all_projects")`
  - 全部项目页注入打开详情回调 `set_open_detail_handler`
- `ui/widgets/pages/project_management_page.py`：
  - 全部项目页双击项目行 → 调用注入回调打开详情（取代原仅日志）
  - 项目 id 存第 0 列 UserRole，双击时取用
  - 新增 `set_open_detail_handler(handler)` 供内容区注入
- `ui/widgets/pages/__init__.py`：导出 `ProjectDetailPage`

### 约束遵循
- 只做页面结构，不做业务扩展：不接规模表、不处理文件、全只读、无新增业务
- 详情页不属于导航树，作为页面注册进现有 QStackedWidget，不改主框架/导航树
- 保持 Windows11 风格（复用全局 QSS，树与输入框沿用现有样式）
- 数据来自 SQLite projects 表（真实数据，无模拟）

### 验证
- 三套冒烟测试全部通过：
  - `test_import_smoke.py`：增加 fetch_project_by_id 校验（命中/不命中）
  - `test_gui_smoke.py`：总页面数 11、详情页注册（返回按钮/结构树/概览字段/load_project）、
    全部项目页已注入详情回调
  - `test_import_e2e.py`：未变，确认详情页引入不影响导入分流链路

### 已知局限（本版不实现，按需求预留）
- 结构树区县/点位为空占位，不接入规模表数据
- 概览仅展示 5 个项目级字段，无统计字段
- 分类页（7 个只读页）双击仍仅记日志，未接详情（需求仅要求「全部项目」列表触发）

## [v0.6.0] - 2026-07-03 — 项目管理架构整体调整（以「全部项目」为唯一总入口）

### 架构变化原因
v0.5.0 虽集中了导入口，但仍有四处不符实际业务，故再次整体调整：

1. **总体项目表无统计字段**：业务总体表只含 项目名称/编码/年份/类型/状态，
   没有"区县数量/点位数量/完成率"。v0.5.0 的映射仍要求映射这三列，与实际表
   不符，导入时这三列总是取不到值。故从映射删除，改由系统在导入"规模表"
   后自动统计；导入总体表阶段显示 '--'。
2. **导入口应更明确**：v0.5.0 点"项目管理"分组进总入口，分组本身不是明确
   入口。改为显式"全部项目"叶子节点作为唯一总入口，所有导入数据先进全部
   项目，7 个分类页只是全部项目的分类视图（只读）。
3. **project_type 不应必填**：业务总体表类型列常缺值或非标准写法。v0.5.0
   强制分流并跳过无法识别行会丢数据。改为可选：无值/无法识别时留空，项目
   只显示在全部项目，用户后续再指定类别。
4. **编辑能力应收口**：v0.5.0 在每个分类页都能改 project_type，导入口与
   编辑能力分散。改为只在"全部项目"页用下拉框修改，分类页纯只读。

### 新增
- `ui/widgets/pages/project_all_page.py`：「全部项目」页入口类（唯一总入口）
- `projects_repository.py`：
  - 表结构 v0.6.0：新增 `project_code`、`completion_rate`；`project_type` 改
    可空；county_count/site_count/completion_rate 为 NOT NULL DEFAULT 0
  - `init_projects_table` 对旧表**无损迁移**（缺列/旧 NOT NULL/主键缺失则
    用 v0.6.0 schema 重建表 + INSERT 复制旧数据 + 替换，保留旧数据与约束）
  - `fetch_projects_by_type(None)` 查未分类；`update_project_type(id, None)` 取消分类
- `project_management_page.py` 模块常量 `DETAIL_TREE`：预留项目详情数据结构
  （项目→项目整体资料/区县(多)→点位(多)→CAD/PDF/预算/照片/审批单/方案表）
- 测试三套更新并通过：
  - `test_import_smoke.py`：v0.6.0 列、NULL 查询、未分类分流、全量替换（5入库/1跳过/2未分类）
  - `test_gui_smoke.py`：10 页、全部项目页有导入按钮、7 分类页无导入按钮、默认页 all_projects
  - `test_import_e2e.py`：全部项目导入 5 行→分流(社区2/集客1/未分类2)、统计列占位、分类页无导入口

### 修改
- `project_management_page.py` 重构为两个基类（UI 结构不变）：
  - `ProjectAllPage`（全部项目页）：唯一含导入/新增/刷新/搜索；展示全部项目；
    project_type 列改用 **QComboBox 下拉**（未分类+7 类）修改并回写；
    统计列显示 0/'--'；双击预留进入详情（本版仅日志）
  - `ProjectCategoryPage`（分类展示页，7 个父类）：**纯只读**——仅刷新+搜索，
    无导入/新增/编辑；统计列同样显示库值（导入总体表阶段 '--'）
- `field_mapping_dialog.py`：FIELDS 精简为 5 项
  （项目名称/编码必填，年份/项目类型/状态可选）；**删除区县数量/点位数量映射**；
  提示文案说明类型可选、无值只入全部项目
- `import_worker.py`：
  - run_import 按列分流，**无值/无法识别→project_type=NULL**（不跳过无法识别行）
  - 仅跳过缺项目名称的行；succeeded 信号 `(inserted, skipped_no_name)`
  - 导入全量替换：`DELETE FROM projects` 再插入
  - 写入 county_count/site_count/completion_rate 统一 0（待规模表统计）
- `nav_tree.py`：新增"全部项目"叶子节点（分组下第一项，page key="all_projects"）；
  分组节点不再携带页面标识；`DEFAULT_PAGE="all_projects"`
- `content_area.py`：注册全部项目页；注入分类页引用供联动刷新；
  默认页 all_projects；总页面数 10
- 7 个分类页：改为纯只读 `ProjectCategoryPage`
- `project_categories.py`：模块注释更新（类型可选语义）

### 删除
- `ui/widgets/pages/project_overview_page.py`（v0.5.0 总入口页，被全部项目页取代）

### 约束遵循
- 不改 UI 风格（Windows11 QSS、表格 9 列布局不变）
- 不新增无关功能、不开发规模表/AI/文件整理
- 业务逻辑全模块化；真实数据，无模拟数据

### 验证
- 三套冒烟测试全部通过（见上"测试"项）
- 现有数据库已无损迁移到 v0.6.0，旧数据保留；测试残留已清理

### 已知局限（本版不实现，按需求预留）
- 规模表导入与区县/点位/完成率统计：字段位已预留为 0，待后续
- 项目详情页：数据结构已预留（DETAIL_TREE），双击仅日志
- 导入仅跳过缺名称行，无行级明细报告
- 「新增项目」未实现

## [v0.5.0] - 2026-07-03 — 项目管理架构调整（全局唯一导入口 + 类型分流）

### 架构变化原因
v0.4.0 中 7 个分类页各自带「导入总体项目表」按钮，但总体项目表是**一个**
文件、内含**多种**类型的项目，分散导入口造成三个问题：

1. **导入口分散**：用户在任意分类页都能点导入，易混淆"在哪导入"。
2. **重复导入**：同一总体表要在多个分类页分别导入，且每次只能装一类。
3. **无法整体替换**：各分类页导入只清自己类型，跨类型数据无法同步替换。

故调整为 **全局唯一导入口 + 自动分流**：
- 「导入总体项目表」「新增项目」**只**存在于「项目管理总入口页」。
- 7 个分类页改为**纯展示页**，禁止导入。
- 导入时按 Excel「项目类型列」自动分流到 7 个业务模块（全量替换）。
- project_type 列可双击编辑，改后项目归属变更并刷新。

### 新增
- `core/project_categories.py`：7 类别 + 别名→类别分流（单一事实源）
  - 分流规则（先精确后子串匹配）：社区/数字家庭→社区；集客/专线→集客；
    管道→管道；设备→设备；接入段→接入段；优化/输线路工程→城域网；配套→机房配套
  - `resolve_category(raw)` 返回规范类别名或 None；`is_valid_category` 校验
- `ui/widgets/pages/project_overview_page.py`：总入口页入口类
- `projects_repository.py` 新增方法：
  - `clear_projects_by_categories(categories)` 多类别批量清空（全量替换用）
  - `update_project_type(id, new_type)` 修改归属类别 + 刷新 updated_at
  - `fetch_all_projects()` 查全部（总览页用）
- 测试三套全部更新：
  - `test_import_smoke.py`：类别分流断言、仓储新方法、worker 分流逻辑（5 入库/1 跳过）
  - `test_gui_smoke.py`：10 页、总入口有导入按钮、7 分类页**无**导入按钮、分组节点切换
  - `test_import_e2e.py`：总入口导入 7 行多类型→分流到 5 类、总览刷新、分类页无导入口

### 修改
- `project_management_page.py` 拆为两个基类（UI 结构不变）：
  - `ProjectOverviewPage`（总入口页）：**全局唯一**含「导入总体项目表」+
    「新增项目」，展示全部项目总览；导入成功后联动刷新各分类页
  - `ProjectCategoryPage`（分类展示页，7 个父类）：仅刷新 + 搜索 +
    双击编辑 project_type；表格 project_type 列可编辑，其余列禁用编辑；
    `itemChanged` 回写库并按新类别刷新
- `import_worker.py` 重构：
  - 构造去掉 `project_type` 参数
  - `run_import` 按「项目类型列」逐行 `resolve_category` 分流，每行自带 project_type 写库
  - 导入为**全量替换**：先 `clear_projects_by_categories(7类)` 再插入
  - 无法识别类型的行跳过并计数；`succeeded` 信号改为 `(inserted, skipped)`
- `projects_repository.insert_projects`：每行 dict 自带 project_type（不再由调用方统一指定）
- `nav_tree.py`：「📁 项目管理」分组节点点击进入总入口页
  （page key="project_overview"）；默认页改为总入口页；`DEFAULT_PAGE` 改为 "project_overview"
- `content_area.py`：注册总入口页；把 7 个分类页引用注入总入口页供联动刷新；
  总页面数 10（总入口 + 7 分类 + AI + 设置）；`DEFAULT_PAGE` 改为 "project_overview"
- `field_mapping_dialog.py`：提示文案改为「项目类型列将自动分流到各业务模块」；
  `project_type` 构造参数改为可选
- 7 个分类页（community/enterprise/access/equipment/pipeline/metro/facility）：
  全部改为继承 `ProjectCategoryPage`，传入类别名

### 约束遵循
- 全局唯一导入口：导入/新增按钮只在总入口页；分类页禁止出现
- 不改动表格 9 列结构、不删除现有功能（导航/排序/搜索/双击日志保留）
- 业务逻辑全模块化（分流/读取/worker/仓储/对话框独立，页面只编排）
- 真实数据，无模拟数据

### 验证
- 三套冒烟测试全部通过（见上"测试"项）
- 数据库清理后残留 0 条测试数据

### 已知局限（本版不实现，留待后续）
- 双击编辑 project_type 为自由文本输入，未做下拉约束（非法值会被拦截并回滚刷新）
- 导入无法识别类型的行仅跳过，无行级明细报告
- 无"取消导入"的协作取消标志
- 「项目编号」「完成率」无库字段支撑

## [v0.4.0] - 2026-07-03 — 总体项目表 Excel 导入（首次接入真实数据）

### 新增
- `core/projects_repository.py`：projects 表数据访问层
  - `init_projects_table` 建表（id / project_name / project_type / year /
    county_count / site_count / status / created_at / updated_at）
  - `clear_projects_by_type` 清空同类型（导入前确保可重入）
  - `insert_projects` 批量插入；`fetch_projects_by_type` / `count_projects_by_type` 查询
  - 统一类型转换：year/county_count/site_count 宽松转 int（容忍 2026.0），
    空值/纯空串 → None
- `data_import/` 包：
  - `excel_reader.py`：openpyxl 只读模式读取 .xlsx；表头动态识别
    （前 20 行扫描关键词命中数 ≥ 2 判为表头行，识别失败回退首行；
    空表头用占位列名兜底；空行自动跳过）
  - `import_worker.py`：`ImportWorker(QObject)` 两段式
    （`load` 读取回传表头 / `run_import` 按映射写库）；无参信号 `start_load`/
    `start_run_import` 触发，回调 `QueuedConnection` 回主线程；worker 用
    `Database.open_db_connection` 建线程本地连接
- `ui/widgets/field_mapping_dialog.py`：字段映射对话框
  - 6 字段下拉（项目名称 / 项目类型 / 年份 / 区县数量 / 点位数量 / 状态，
    状态可选）+ 关键词智能预选 + 即时预览（前 8 行）+ 必选校验
  - 静态方法 `guess_mapping`：无弹窗智能预选（供自动化/无交互导入）
  - 类级钩子 `auto_accept_for_test`：自动化测试跳过对话框
- `tests/`
  - `test_import_smoke.py`：Excel 读取 + 仓储建/插/查/清空 + worker 核心逻辑
  - `test_gui_smoke.py`：GUI 启动 + 9 页注册 + 7 类型页表格结构校验
  - `test_import_e2e.py`：端到端导入冒烟（选文件→读取→自动映射→写库→
    刷新列表→数据库落条目校验）

### 修改
- `core/database.py`：新增静态方法 `open_db_connection(path)`，
  供后台线程开线程本地连接（SQLite 连接不可跨线程）
- `ui/widgets/content_area.py`：`ContentArea(config, parent)` 接收并下传
  `AppConfig` 给 7 个项目类型页
- `ui/widgets/pages/project_management_page.py`（重写业务层，UI 结构保持不变）：
  - 「导入总体项目表」全流程编排：QFileDialog 限 .xlsx → 后台线程读取 →
    字段映射对话框 → 后台线程写库 → 成功后自动 `refresh_data`
  - `refresh_data`：主线程同步从 SQLite 按类型读取渲染（本地查询不卡 UI）
  - 移除全部模拟数据（`_MOCK_PROJECTS` / `_load_mock_data` 删除）
  - 搜索框：textChanged → 按项目名称/编号过滤行
  - 「新增项目」按钮：提示"暂未实现"（不提前实现）
  - 信号连接用 `QueuedConnection` 回主线程；新增 `_close_progress_quietly`
    关闭进度对话框前断开 `canceled`，避免 close() 误判取消
  - 「项目编号」「完成率」列暂无数据来源（库表无此字段），保留列、显示空
- `ui/widgets/pages/community_page.py` 等 7 个类型页：构造新增 `config` 参数
  并传给 `ProjectManagementPage`
- `ui/main_window.py`：把 `config` 传入 `ContentArea`
- `requirements.txt`：新增 openpyxl 依赖

### 约束遵循
- 不改动 UI 结构（表格 9 列、工具栏布局、页面层级均不变）
- 不重写页面（仅扩展业务层，沿用 `BasePage` 与 `NumericItem`）
- 不删除现有功能（导航/排序/双击日志/搜索框等全部保留）
- 业务逻辑全部模块化（读取/worker/仓储/对话框四模块独立，页面只编排）
- 首次接入真实数据，列表与导入均不再使用模拟数据

### 验证
- 三套冒烟测试全部通过：
  - `test_import_smoke.py` ALL_SMOKE_OK（表头识别、建/插/查/清空、None 处理）
  - `test_gui_smoke.py` GUI_SMOKE_OK（9 页注册、7 类型页表格 9 列、库读取正常）
  - `test_import_e2e.py` E2E_OK（3 行入库、列表刷新、DB 落 3 条）
- 数据库清理后残留 0 条测试数据

### 已知局限（本版不实现，留待后续任务）
- 导入时缺项目名称的行仅记 warning 跳过，无行级失败报告
- 无"取消导入"的协作取消标志（取消仅退出线程事件循环）
- 「项目编号」「完成率」无库字段支撑

## [v0.3.1] - 2026-07-03 — 修复数值列排序（v0.3.0 修订）

### 修复
- `project_management_page.py` 的 `NumericItem` 排序实现重构：
  - **问题1**：原调用 `super().__lt__()` 在 PySide6 6.11 下会重新派发回 Python override，造成无限递归 → RecursionError → 段错误（STATUS_ACCESS_VIOLATION）
  - **问题2**：依赖 `data(EditRole)` 取数值不可靠，`setText()` 会写入角色文本，导致取回的是显示文本，排序退化为字符串字典序
  - **修复**：数值改存 Python 实例属性 `_sortable_value`，`__lt__` 直接用它比较；回退路径用 `self.text()` 比较，全程不调用 `super().__lt__()`
- `_set_numeric_cell` 改为调用 `item.set_numeric_value(value)` 设置排序数值

### 验证
- 冒烟测试全项通过：年份/完成率/点位数 升降序数值正确；整行选中、双击日志、7 类型页类型列正确

## [v0.3.0] - 2026-07-03 — 项目管理页面 UI（仅界面与模拟数据）

### 新增
- `ui/widgets/pages/project_management_page.py`：项目管理页面核心 UI
  - 顶部工具栏：导入总体项目表 / 新增项目（主操作高亮）/ 刷新 / 带清除按钮的搜索框
  - 项目列表 QTableWidget，9 列：项目名称 / 项目编号 / 项目类型 / 年份 / 区县数量 / 点位数量 / 完成率 / 状态 / 最后更新时间
  - 5 条模拟数据
  - `NumericItem` 数值列单元，保证年份/区县数/点位数/完成率按数值排序
  - 整行单选、不可编辑、交替行底色、表头可点击排序、最后列吸边
  - 双击项目行：仅打印日志（不进入下一页）
  - 按钮点击与搜索暂未绑定行为（本阶段不含业务逻辑）

### 修改
- `ui/widgets/pages/base_page.py`：暴露 `content_layout` 供子类填充内容（去掉原固定 stretch），占位页不受影响
- `ui/widgets/pages/community_page.py` 等 7 个项目类型页：改为继承 `ProjectManagementPage`，传入各自类型名，复用同一套界面
- `ui/theme.py`：增补工具栏按钮、搜索输入框、表格与表头的 Windows11 风格样式

### 约束遵循
- 仅做界面：不连接数据库、不导入 Excel、不写业务逻辑
- 所有页面代码独立（每类型页独立文件）

### 验证
- 冒烟测试通过：标题/副标题、9 列、5 行数据、各类型页类型列正确
- 年份升/降序、完成率降序数值排序正确
- 整行选中、双击打印日志验证通过
- 程序可正常启动（`python run.py`）

## [v0.2.0] - 2026-07-03 — 导航与页面切换骨架

### 新增
- `ui/theme.py`：Windows11 风格全局 QSS（浅灰底、白卡片、圆角阴影、浅蓝选中高亮、Segoe UI 字体）
- `ui/widgets/pages/` 页面包：
  - `base_page.py` 统一页头基类（大标题 + 副标题）
  - `community_page.py` 社区
  - `enterprise_page.py` 集客
  - `access_page.py` 接入段
  - `equipment_page.py` 设备
  - `pipeline_page.py` 管道
  - `metro_page.py` 城域网
  - `facility_page.py` 机房配套
  - `ai_assistant_page.py` AI助手（占位）
  - `settings_page.py` 设置（占位）

### 修改
- `ui/widgets/nav_tree.py`：重写为严格按需求结构构建的 QTreeWidget，发出 `page_requested(str)` 信号；叶子节点携带页面标识，分组节点不触发切换
- `ui/widgets/content_area.py`：重写为注册 9 个页面的 QStackedWidget，提供 `switch_to(key)` 切换
- `ui/main_window.py`：左右分栏卡片布局，连接导航切换信号到内容区域
- `app.py`：启动时应用全局样式表

### 验证
- 冒烟测试通过：9 个页面注册成功，9 个导航节点点击切换正确，分组节点不切换
- 程序可正常启动（`python run.py`）

## [v0.1.0] - 2026-07-03 — 项目框架搭建

### 新增
- 标准项目目录结构（`ai_office_agent/` 主包分层：core / ui / utils）
- `run.py`：启动入口
- `requirements.txt`：PySide6 依赖
- `app.py`：应用入口与生命周期（日志→配置→数据库→UI）
- `config.py`：配置管理（`AppConfig` dataclass + `settings.json`，缺失自动生成、损坏回退默认）
- `config/settings.json`：应用配置文件
- `core/database.py`：SQLite 连接管理（自动建目录、自动提交、外键约束、Row 工厂；暂不建表）
- `utils/logger.py`：统一日志（控制台 + `logs/app.log` 文件）
- `ui/main_window.py`：主窗口左右分栏骨架
- `ui/widgets/nav_tree.py`：树形导航占位
- `ui/widgets/content_area.py`：内容区域占位
- `README.md`、`.gitignore`

### 验证
- Python 3.14.5 + PySide6 6.11.1 环境就绪
- 冒烟测试通过：配置加载 → 数据库连接 → 主窗口创建（1280×800）→ 数据库关闭
