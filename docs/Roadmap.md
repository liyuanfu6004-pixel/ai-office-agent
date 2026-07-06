# 路线图 (Roadmap)

> 项目开发路线规划。实际进度以 `ProjectMemory.md` 的"当前开发阶段"为准。
> 版本号遵循简易语义化：主版本.功能版本.修订号。

## 当前阶段

**v1.5.0 唯一归属模型 — 已完成** ✅

下一阶段：**v1.6 — 待定**

## v1.5.0 唯一归属模型（Single Ownership Model）✅

### 两阶段模型 ✅
- [x] 阶段1 候选生成：文件→所有点位打分
- [x] 阶段2 唯一归属决策：Top1 + 阈值 0.75 + 冲突检测

### 图纸特殊规则 ✅
- [x] DWG/DXF/BAK/PDF 必须 stem 精确匹配
- [x] 禁止 fuzzy match 参与图纸归属

### 禁止行为 ✅
- [x] 禁止一个文件归属多个点位
- [x] 禁止扫描阶段直接写归属
- [x] 禁止 fuzzy match 参与图纸归属
- [x] 禁止 build_scan_results 调用 global_match_point

### 输出目标 ✅
- [x] 每个文件只有一个归属点位
- [x] 点位详情文件不重叠
- [x] 图纸/预算分类稳定一致

## v1.4.2 图纸识别跨点位污染修复 ✅

### 修复内容 ✅
- [x] `global_match_point` 目录匹配从 fuzzy 改为精确相等
- [x] 目录内文件范围从 `startswith`（递归）改为 `==`（仅直接文件）
- [x] 新增 `_drawing_belongs_to_point()` 归属校验函数
- [x] `classify_file` 对直接图纸类型加入归属校验
- [x] `build_organize_plan` 的 CAD 索引仅使用本点位图纸文件
- [x] 新增跨点位污染测试

## v1.4.1 扫描结果中心 UI 微调 ✅

### 修复内容 ✅
- [x] 删除「重新扫描」按钮，仅保留「执行扫描」按钮
- [x] 建议列从 `Stretch` 改为 `Interactive`，允许用户拖动列宽
- [x] 确认列 `Fixed` 宽度
- [x] 表格显式启用水平滚动条，避免内容被压缩
- [x] 新增 `OrganizePreviewDialog`：可调整大小、带滚动条、显示完整文件整理预览
- [x] 文件整理预览不再截断冲突文件 / 点位数量 / 文件数量

## v1.4.0 扫描生命周期闭环修复 ✅

### 核心升级：消除自动扫描卡顿 + 统一扫描入口 ✅
- [x] 创建 `ScanController` 作为唯一扫描入口
- [x] 扫描生命周期 5 步闭环（读数据→扫描→匹配→生成结果→写 DB）
- [x] `scan_result` + `file_ownership` 表持久化扫描结果
- [x] `load_project_cached()` 仅从缓存加载（0 扫描，0 卡顿）
- [x] 移除 `project_detail_page._try_match_from_sandbox()` 扫描触发
- [x] 移除 `content_area.show_project_detail()` 中的自动扫描
- [x] 仅 `scan_center_page` 扫描按钮触发扫描

### 禁止行为（硬约束）✅
- [x] ❌ `on_project_open → scan_project()`
- [x] ❌ `project_detail_page._try_match_from_sandbox()`
- [x] ❌ 只读不写（scan 无 DB 闭环）
- [x] ❌ 多个扫描入口

## v1.3.1 文件唯一归属修复 ✅

### 核心升级：匹配方向反转 ✅
- [x] `match_file_to_points()` — file → all points → Top1 Winner
- [x] 冲突检测：top1 - top2 < 5 → CONFLICT
- [x] `match_points_from_index` 返回 3-tuple（含冲突列表）
- [x] 每个文件只归属一个 point_id

## v1.3 文件自动整理引擎路线图 ✅

### 图纸优先语义体系 ✅
- [x] CAD 索引机制：build_cad_index（dwg/dxf/bak → stem）
- [x] PDF↔CAD 同名规则：PDF stem 匹配 CAD stem → 图纸
- [x] 分类优先级：图纸 > 预算 > 其他（冲突永远归类为图纸）

### 预算识别 ✅
- [x] 文件类型：.xls/.xlsx/.et/.csv
- [x] 关键词：预算/概算/造价/报价/清单/cost/estimate/budget

### 执行模式 ✅
- [x] Dry Run：build_organize_plan → 预览对话框
- [x] Apply：「执行整理」→ 确认后移动文件

### 安全规则 ✅
- [x] 不删除文件
- [x] 不覆盖文件（冲突跳过）
- [x] 只创建子目录 + 移动

## v1.2.3 区域标准化 + 全量索引扫描引擎 ✅

### 点位名称双层标准化 ✅
- [x] for_matching() 生成 match_name（去非法字符/空格/全角半角/lowercase/可选去括号）
- [x] for_filesystem_path() 生成 filesystem_name（/→-、保留中文、避免非法字符）
- [x] 全系统 matcher 统一使用 match_name

### 全量文件索引扫描 ✅
- [x] FileIndex：递归扫描全量文件+目录，扁平索引
- [x] global_match_point()：全局匹配，不管路径在哪
- [x] compute_drawing_status/budget_status 基于索引

### 区县语义归一化 ✅
- [x] config/region_profile_2026_km.json（7 区县 + 10+ 别名）
- [x] RegionProfile.normalize("安宁"→"安宁市")
- [x] is_active() 非负责区县过滤

### 扫描架构重构 ✅
- [x] build_scan_results 切换 FileIndex
- [x] _try_match_from_sandbox 切换 FileIndex
- [x] _load_points_from_db 区县归一化+过滤
- [x] 保留旧 API 向后兼容

## v1.2.2 扫描结果人工确认路线图 ✅

### 步骤1：人工确认 ✅
- [x] 扫描结果列表增加「确认」按钮列
- [x] 状态切换"未确认"/"已确认"
- [x] 确认后保存本次选择到 scan_match_history

### 步骤2：重新匹配 ✅
- [x] RematchDialog：列出候选目录供用户选择
- [x] NOT_FOUND / MULTIPLE_MATCH / PARTIAL_MATCH 支持重新匹配
- [x] 匹配结果保存到历史

### 步骤3：学习机制 ✅
- [x] save_match_history 保存 标准点位+实际目录+匹配方式
- [x] build_scan_results 优先使用历史确认结果
- [x] 已确认点位跳过模糊匹配

### 步骤4：批量确认 ✅
- [x] 全部确认按钮
- [x] 批量确认已匹配项

### 步骤5：导出 Excel ✅
- [x] 含 10 列（序号/标准点位/实际目录/区县/CAD/预算/匹配率/状态/确认/方式/建议）
- [x] 仅导出，不修改任何文件

### 步骤6：数据库 ✅
- [x] scan_match_history 表（完整 CRUD）

## v1.2.1 规模表导入优化路线图 ✅

### 问题一：Sheet 评分算法优化 ✅
- [x] Sheet 名称权重最高（规模/项目规模/工程规模/设计规模命中=满分）
- [x] 表格结构评分（列数/行数/数据密度，材料表自动降分）
- [x] 字段关键词降为辅助评分（20%权重）
- [x] 反例检测（材料表/封面/目录/汇总等→大幅降权）

### 问题二：多行表头识别 ✅
- [x] 扫描前15行，构建合并单元格查询映射
- [x] 区分横向合并（同行继承）与纵向合并（同列跳过）两种语义
- [x] 支持任意层数组合表头（如"线路部分-光缆线路设计长度-新建架空"）
- [x] 跳过纯标题行（只有1个独立文本列）
- [x] 数据行从表头结束行+1开始
- [x] 禁止生成 __col_x__，兜底使用"列N"
- [x] 真实规模表验证通过（63列×482行三层合并表头）

### 问题三：动态字段映射优化 ✅
- [x] 默认仅保留区县+点位名称
- [x] 界面增加「＋ 添加字段」按钮
- [x] 左侧自定义列名（QLineEdit），右侧选择规模表列（QComboBox）
- [x] 允许增加/删除/修改

### 问题四：程序崩溃修复 ✅
- [x] 全链路异常捕获（worker → detail_page）
- [x] _cleanup_thread 安全线程清理
- [x] 失败弹出错误提示 + 完整日志 + 保留窗口

## v1.2 扫描结果中心路线图 ✅

### 步骤1：统一扫描结果模型 ✅
- [x] `core/scan_result.py`：MatchStatus 枚举 / ScanResultItem / ScanResultSummary / build_scan_results
- [x] MATCHED/PARTIAL_MATCH/NOT_FOUND/MULTIPLE_MATCH 匹配状态
- [x] 颜色规范：绿#107C10/黄#FFB900/红#D13438/橙#FF8C00
- [x] 复用 point_dictionary + scanner + matcher，不重复写匹配逻辑

### 步骤2：扫描结果页面 ✅
- [x] 顶部信息栏：项目名称/扫描时间/扫描耗时/扫描目录/扫描按钮/重新扫描按钮
- [x] 统计卡片：总点位/已匹配/部分匹配/未匹配/CAD缺失/预算缺失
- [x] 结果列表：状态/标准点位/实际文件夹/匹配率/CAD/预算/建议（7 固定列）
- [x] 排序/筛选/搜索，禁止修改数据

### 步骤3：详情预览 ✅
- [x] 双击结果 → 右侧详情面板：标准点位/原始名称/匹配目录/CAD文件数/预算文件数/扫描文件列表
- [x] 仅查看，禁止修改

### 步骤4：重新扫描 ✅
- [x] 重新读取项目目录 → 重新生成 ScanResult → 覆盖内存结果
- [x] 禁止修改数据库

### 步骤5：接口预留 ✅
- [x] RenamePreviewInterface / FolderBuilderInterface / HealthScoreInterface / AISuggestionInterface
- [x] 仅定义接口，不实现

## v1.1.1 匹配引擎升级路线图 ✅

系统匹配升级为：normalizer.py → matcher.py → RapidFuzz

### 步骤1：统一标准化模块 ✅
- [x] `core/normalizer.py`：for_comparison / for_filesystem / for_display
- [x] NFKC 统一 + 全角→半角 + 中文括号/标点统一 + 大小写统一
- [x] 删除文件系统特殊字符；保留原始数据不变

### 步骤2：统一匹配引擎 ✅
- [x] `core/matcher.py`：match_strings / match_sheet / match_field / match_point_name / match_folder / match_filename
- [x] MatchResult 数据结构：score / kind (EXACT/CONTAINS/FUZZY/WEAK/NONE) / reason
- [x] MatchThresholds 配置预留（exact=95 / contains=85 / fuzzy=70）
- [x] 批量匹配：best_match / any_match / is_match / is_strong_match

### 步骤3：6 个模块升级 ✅
- [x] `scanner.py`：删除 normalize_for_match + _match_keyword → matcher
- [x] `scale_table_engine.py`：5 处手动匹配 → matcher
- [x] `project_categories.py`：resolve_category → matcher
- [x] `excel_reader.py`：_detect_header_row → matcher
- [x] `field_mapping_dialog.py`：guess_mapping + _auto_guess → matcher
- [x] `project_detail_page.py`：_try_match_from_sandbox → matcher

## v1.1 规模表智能识别引擎路线图 ✅

系统架构升级为：Excel（多Sheet）→ Sheet识别 → 字段映射 → 点位规则 → 预览 → 导入

### 步骤1：Sheet 自动识别 ✅
- [x] `read_all_sheets`：读取 Excel 全部 Sheet
- [x] `score_sheet_likelihood`：三维评分（表头关键词 + 数据密度 + 行数）
- [x] `detect_best_sheet`：全部 Sheet 评分排序
- [x] 多候选时 UI 弹出选择窗口；选择后记录到 Project Profile

### 步骤2：字段智能识别 ✅
- [x] `detect_point_name_field` / `detect_county_field`：关键词自动匹配
- [x] `detect_start_field` / `detect_end_field`：起点/终点自动识别
- [x] `build_field_candidates`：候选列表，用户可修正
- [x] 修正后保存到 Project Profile

### 步骤3：区县识别 ✅
- [x] 自动识别区县列；允许用户修改；保存到 Project Profile

### 步骤4：点位生成规则 ✅
- [x] 接入段、城域网 → 默认「起点 + "-" + 终点」拼接
- [x] 其他类型 → 默认单字段
- [x] 用户可修改；保存到 Project Profile

### 步骤5：动态字段 ✅
- [x] 固定字段仅区县、点位名称
- [x] 其余全部自动归为动态字段（长度/芯数/经度/纬度/设备型号…）
- [x] `classify_dynamic_fields` + 已知概念标注
- [x] 详情页自动增加动态列（`_extract_dynamic_columns`）

### 步骤6：Project Profile ✅
- [x] `project_profiles` 表：Sheet名称/点位字段/区县字段/生成规则/动态字段
- [x] `upsert_profile` / `fetch_profile`：INSERT OR REPLACE 语义
- [x] 重新导入同项目直接自动使用

### 步骤7：导入预览 ✅
- [x] `ScaleTableWizard` 四步向导：Sheet→字段→规则→预览
- [x] 预览前 10 条点位 + 动态字段列 + 统计信息
- [x] 确认后 `ScaleImportWorker` 后台导入

### 步骤8：版本比较（预留接口）✅
- [x] 接口预留；暂不实现（增量更新：新增/删除/修改点位）

## v1.0 文件系统治理路线图

系统架构升级为：Excel → 标准点位字典 → 文件扫描 → 匹配 → UI

### 阶段1：标准点位字典系统 ✅（v1.0.0）
- [x] `point_dictionary` 表：id / project_id / standard_point_name / county / original_name
- [x] Excel 明细表导入 → 写入 point_dictionary（先清空本项目，可重入）
- [x] 点位名称标准化（去特殊字符：/ \ * ? : " < > | 空格）
- [x] `load_project` 从 point_dictionary 表加载点位
- [x] 筛选栏已启用（区县/名称/图纸/预算组合条件）

### 阶段2：文件系统扫描（只读）✅（沙盒模式）
- [x] `core/scanner.py`：scan_project_root / _scan_project_dir / _scan_folder
- [x] 数据结构：ProjectNode / FolderNode / FileNode
- [x] 安全阀：硬编码 TEST_ROOT_PATH = D:\AI-Office-Agent-Test\
- [x] 只读操作：不修改任何文件
- [x] 沙盒测试目录 3 个项目 / 6+ 个点位

### 阶段3：匹配系统 ✅（沙盒模式）
- [x] match_single_folder / match_project_folders：文件夹名 ↔ standard_point_name
- [x] 完全相等 → score=1.0；包含关系 → score=0.85；不匹配 → score=0.0
- [x] normalize_for_match：去特殊字符/空格/小写
- [x] MatchResult 数据结构：folder_name / point_id / match_score

### 阶段4：状态计算 ✅（沙盒模式）
- [x] 图纸状态：图纸子文件夹存在 *.dwg →「有」；否则 →「无」
- [x] 预算状态：预算子文件夹存在且有文件 →「有」；否则 →「无」
- [x] compute_all_statuses：批量填入真实状态
- [x] UI 接入：project_detail_page._try_match_from_sandbox

### 阶段5：自动标准化（危险操作）🔲
- [ ] 文件夹重命名为标准点位名称
- [ ] 文件归类（图纸/预算/其他）
- [ ] dry-run 预览模式（默认开启）
- [ ] 改动日志 + rollback 映射记录

### 阶段6：UI 实时展示 🔲
- [ ] 点位列表展示真实图纸/预算状态（已通过沙盒模式预验证）
- [ ] 不重构 UI 结构
- [ ] 输出文件夹结构树 + 文件列表
- [ ] 不允许修改任何文件

### 阶段3：匹配系统 🔲
### 阶段5：自动标准化（危险操作）🔲
- [ ] 文件夹重命名为标准点位名称
- [ ] 文件归类（图纸/预算/其他）
- [ ] dry-run 预览模式（默认开启）
- [ ] 改动日志 + rollback 映射记录

### 阶段6：UI 实时展示 🔲
- [ ] 更新图纸/预算状态字段为真实值
- [ ] 不重构 UI 结构

## 已规划阶段（历史）
- [x] Python 项目与启动入口
- [x] 主窗口
- [x] 左侧树形导航、右侧内容区域骨架
- [x] 数据库初始化代码（暂不建表）
- [x] 配置文件
- [x] 程序可启动

### 第二阶段：导航与页面切换骨架 ✅（v0.2.0）
- [x] QTreeWidget 严格按需求结构构建
- [x] QStackedWidget 承载功能页
- [x] 点击导航切换右侧页面
- [x] 每页独立文件，显示标题占位
- [x] Windows11 风格样式

### 第三阶段：项目管理页面 UI ✅（v0.3.0 + v0.3.1 修复，仅界面）
- [x] 顶部工具栏：导入总体项目表 / 新增项目 / 刷新 / 搜索框
- [x] 项目列表表格（9 列字段）
- [x] 5 条模拟数据
- [x] 表头点击排序（数值列按数值排序，v0.3.1 修复段错误）
- [x] 整行选中
- [x] 双击项目打印日志
- [x] Windows11 风格

### 第四阶段：总体项目表 Excel 导入 ✅（v0.4.0，首次接入真实数据）
- [x] 选择 .xlsx 文件（仅允许 Excel）
- [x] Excel 读取（openpyxl）
- [x] 表头动态识别（表头不固定）
- [x] 字段映射对话框（6 字段，状态可选，智能预选 + 必选校验）
- [x] 写入 SQLite projects 表（表不存在则创建）
- [x] 导入后自动刷新列表
- [x] 导入进度提示（QProgressDialog）
- [x] 导入成功/失败提示（QMessageBox）
- [x] UI 不卡死（后台 QThread + Worker，信号 QueuedConnection 回主线程）
- [x] 业务逻辑全模块化（读取/worker/仓储/对话框独立，页面只编排）
- [x] 真实数据接入（列表从库读取，移除模拟数据）

### 第四阶段补丁：架构调整 ✅（v0.5.0，全局唯一导入口 + 类型分流）
- [x] 全局唯一导入口（导入/新增仅在项目管理总入口页）
- [x] 7 个分类页改为纯展示页，禁止导入
- [x] 导入按「项目类型列」自动分流到 7 个业务模块
- [x] 导入全量替换语义（清空 7 类再插入）
- [x] project_type 列可双击编辑，改后回写并刷新到对应类别
- [x] 类别分流单一事实源（core/project_categories.py）

### 第四阶段补丁2：架构整体调整 ✅（v0.6.0，以「全部项目」为唯一总入口）
- [x] 导航新增「全部项目」节点，为所有项目唯一总入口
- [x] 导入/新增/刷新/搜索仅在全部项目页；分类页纯只读
- [x] 总体表字段映射精简为 5 项（名称/编码必填，年份/类型/状态可选）
- [x] 删除区县数量/点位数量映射（总体表无此字段）
- [x] project_type 可选：无值只入全部项目，用户后续指定
- [x] 全部项目页 project_type 下拉修改（7 类+未分类），改后联动刷新
- [x] projects 表加 project_code/completion_rate，统计列默认 0
- [x] 统计字段导入总体表阶段显示 '--'，待规模表统计
- [x] 项目详情数据结构预留（DETAIL_TREE）
- [x] 旧数据库无损迁移到 v0.6.0

### 第四阶段补丁3：项目详情页面（基础结构）✅（v0.7.0）
- [x] 「全部项目」列表双击项目 → 打开项目详情页
- [x] 详情页标题：项目名称 + 项目编码
- [x] 左侧结构树：项目 → 项目整体资料 / 区县列表（空）/ 点位列表（空）
- [x] 右侧默认显示「项目概览」：名称/编码/类型/年份/状态（只读）
- [x] 数据来自 projects 表，不接入规模表
- [x] 「返回项目列表」按钮回到全部项目；不改主框架、全只读

### 第四阶段补丁4：项目详情页 UI 结构调整 ✅（v0.8.0）
- [x] 删除区县列表 TreeView 与所有层级导航树结构（详情页无树）
- [x] 概览卡 + 项目整体资料面板横向并列
- [x] 项目整体资料面板：PDF / Word / Excel / 其他资料 / 点位文件夹以外的文件夹
- [x] 点位列表固定 5 列：序号 / 区县 / 点位名称 / 图纸状态 / 预算状态
- [x] 动态列机制（规模表/明细表用户映射字段追加在固定列后，本版 0 列）
- [x] 筛选栏：区县下拉 + 点位名称搜索 + 图纸状态 + 预算状态（组合条件）
- [x] 图纸状态规则：仅判 CAD（有 CAD→有，仅 PDF 无 CAD→无）
- [x] 预算状态规则：预算文件夹存在→有
- [x] 仅改 UI 层，不改业务逻辑、不接规模表、不解析文件、不用弹窗作主流程

### 第四阶段补丁5：项目详情页 UI 交互优化 ✅（v0.9.0）
- [x] 点位列表占详情页≥50% 高度（核心区域）；概览卡+资料面板紧凑靠上
- [x] 删除详情页左上角项目名称+编码（概览卡已有，避免重复）
- [x] 全部项目页 + 7 个分类页双击项目行 → 均进入同一项目详情页
- [x] 详情页加「导入项目明细表」按钮（返回按钮旁，Windows11 风格）
- [x] 明细导入：基础读取 .xlsx → 展示到点位列表（不做映射/写库）
- [x] 仅 UI/交互调整，不改数据库结构、不重写页面架构、不引入新业务逻辑

### 第四阶段补丁6：项目详情页 UI 微调 ✅（v0.9.1）
- [x] 点位明细表占项目详情页半页（此前约 1/3）
- [x] 仅调点表占比，未改动其他任何内容（上方面板 setMaximumHeight(210) + resizeEvent 动态半页）

### 第四阶段补丁7：项目详情页 UI 布局重构 ✅（v0.9.2）
- [x] 概览与资料从横向并列改为纵向独立块（上→下：工具栏→概览→资料→筛选→点表）
- [x] 概览 vertical=Fixed 完整显示，输入框全宽不截断、minimumHeight 防压缩
- [x] 资料 vertical=Fixed 中等高度，5 项分类完整显示
- [x] 点表 vertical=Expanding + stretch=1 占剩余全部纵向空间
- [x] 删除 v0.9.1 的 setMaximumHeight(210) 与 resizeEvent 半页强制
- [x] 仅改 UI layout / QSizePolicy / stretch，不改业务逻辑/数据/架构

### 第四阶段补丁8：项目详情页 UI 布局重构（双层 VBox+HBox）✅（v0.9.3）
- [x] 主 QVBoxLayout 嵌套中间 QHBoxLayout（双层布局结构）
- [x] 中间区域 QHBoxLayout 横向并排：概览(60%, stretch=3) / 资料(40%, stretch=2)
- [x] 概览/资料 vertical=Fixed 完整紧凑，输入框 minimumHeight(24) 防压缩
- [x] 点表 vertical=Expanding + stretch=1 + resizeEvent 保 minimumHeight=页面半高（≥50%）
- [x] 禁止概览/资料上下排列、禁止全页单列 QVBoxLayout；仅改 layout/QSizePolicy/stretch

### 第四阶段补丁9：项目详情页 UI 微调 ✅（v0.9.4）
- [x] 中间区域概览/资料高度一致（Preferred 策略，QHBoxLayout 自动同高）
- [x] 系统界面纵向可自由缩放（删除 resizeEvent 半页强制，点表 stretch=1 自然分配）
- [x] 仅改 layout/QSizePolicy/stretch，不改业务逻辑/数据/架构

### 第五阶段：项目管理业务化（待定）
> 等用户指示。候选：
- [ ] 明细导入字段映射对话框 + 写库（当前仅基础读取展示，未持久化）
- [ ] 点位列表图纸/预算状态接入文件系统
- [ ] 筛选栏行过滤启用（待点位表有真实数据源）
- [ ] 项目整体资料面板接入文件整理
- [ ] 「新增项目」功能实现（入口在全部项目页）
- [ ] 导入失败的行级报告
- [ ] 菜单栏 / 工具栏
- [ ] AI助手 / 设置 页面开发

### 未来阶段（远期，仅备忘，不提前实现）
- [ ] AI 助手功能
- [ ] 文件整理功能
- [ ] Excel 导入功能
- [ ] 其他通信设计相关业务模块

## 开发原则

- 每次只完成一个任务，完成后停止，等用户确认
- 不提前实现未要求的功能
- 不擅自修改需求
- 严格按用户给定的结构/字段开发
