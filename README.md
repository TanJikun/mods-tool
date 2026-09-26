# 模组版本匹配工具

一个面向 Minecraft 的模组 / 材质包等多类型内容的版本兼容性检查、批量下载与 URL 管理工具，支持 Modrinth 与 CurseForge 平台。

---

## 功能总览

### 一、兼容性检查

- **版本范围分析**：输入最低 / 最高 Minecraft 版本，自动从 Modrinth 官方标签接口拉取完整版本列表，并筛选出范围内的所有版本。
- **内置备用版本列表**：当网络请求失败时，自动使用内置的完整版本列表（覆盖 1.13 ~ 26.2 等版本），保证功能可用。
- **版本号比较**：支持 `1.18`、`1.18.2`、`26.1` 等格式，自动补零对齐后逐段比较。
- **支持率统计**：对每个项目计算支持版本数、支持率（百分比），并输出支持率最高 / 最低的项目。
- **兼容性矩阵**：逐版本标记 `✔` / `✘`，形成完整矩阵。
- **Excel 报告导出**：
  - 列：序号、名称、平台、类型、URL、支持版本数、支持率 + 每个 Minecraft 版本列。
  - 样式：表头填充、边框、居中、冻结首行、自动列宽。
  - 支持 / 不支持分别使用绿色 / 红色填充与字体。
  - 不同类型（如材质包）使用不同颜色标识。
  - 文件名自动包含版本范围与加载器，例如 `mod_compatibility_1.20_to_1.21.1_fabric.xlsx`。

### 二、批量下载

- **按目标版本下载**：指定 Minecraft 版本 + 加载器 + 版本类型（Release / Beta / Alpha），自动定位匹配的文件。
- **版本类型优先级**：`release` 仅取稳定版；`beta` 取测试版优先、回退稳定版；`alpha` 取早期测试版优先、回退测试版 / 稳定版。
- **加载器过滤**：支持 Fabric、Forge、NeoForge、Quilt，或“全部（不过滤）”。
- **材质包 / 数据包豁免**：材质包等类型自动忽略加载器限制。
- **文件名规范化**：自动生成 `名称_版本_加载器.jar` 形式，并清理非法字符。
- **未完成清单**：将未找到版本或下载失败的 URL 汇总，可选择保存到 `missing_downloads.txt`（自动编号，不覆盖已有文件）。
- **下载汇总**：成功 / 跳过 / 失败 / 总计统计。
- **CurseForge 提示**：CurseForge 暂不支持自动下载，会明确提示手动下载。

### 三、下载管理器

- **Gopeed 集成（HTTP API 模式）**：
  - 自动检测本地 Gopeed 服务是否运行。
  - 支持自动启动（可配置无头模式 `--headless`、Windows 下独立进程组）。
  - 支持自定义 API 地址、Token、连接数。
  - 兼容多个 API 端点，自动尝试创建任务。
  - 使用 Gopeed 默认下载目录，不强制指定路径。
- **内置下载回退**：
  - Gopeed 不可用或失败时，自动回退到内置下载器。
  - 使用 `requests` 流式下载，带 `rich` 进度条（速度、大小、百分比）。
  - 下载目录可通过配置指定（默认 `./downloads`）。
- **可配置开关**：是否启用 Gopeed、是否启用回退、是否自动启动等。

### 四、URL 排序

- **多编码读取**：自动尝试 UTF-8，失败后回退 GBK。
- **有效性过滤**：仅保留可解析的 Modrinth / CurseForge URL，统计并忽略无效行。
- **字母排序**：对有效 URL 排序后写出。
- **输出方式**：可覆盖原文件，或另存为 `xxx_sorted.txt`。
- **结果预览**：显示前 5 条及总数。

### 五、URL 解析与类型识别

- **Modrinth 支持类型**：模组（mod）、材质包（resourcepack）、光影（shader）、数据包（datapack）、整合包（modpack）、插件（plugin）。
- **CurseForge 支持类型**：模组（mc-mods）、材质包（texture-packs）、光影（shaders）、世界（worlds）、整合包（modpacks）、Bukkit 插件（bukkit-plugins）。
- **类型探测与缓存**：URL 未体现类型时，通过 Modrinth API 查询 `project_type`，并缓存结果避免重复请求。
- **名称获取**：自动从平台获取项目显示名称（Modrinth API / CurseForge 页面标题）。
- **模糊搜索回退**：Modrinth 项目 ID 无效时，尝试搜索并定位替代项目。

### 六、交互界面（TUI）

- **方向键菜单**：使用 ↑↓ 选择、Enter 确认、ESC 取消，基于 `msvcrt` 实现。
- **模式选择器**：兼容性检查 / 批量下载 / 排序 URL。
- **加载器选择器**：Fabric / Forge / NeoForge / Quilt / 全部。
- **版本类型选择器**：Release / Beta / Alpha。
- **文件选择器**：当目录中存在多个有效 URL 文件时，方向键选择。
- **智能跳过**：文件仅含材质包时，自动跳过加载器选择。
- **文件自动扫描**：自动识别当前目录下包含有效 URL 的 `.txt` 文件。

### 七、配置与输出

- **配置文件 `config.json`**：首次运行自动生成，包含：
  - `default_dir`：内置下载目录。
  - `use_gopeed`：是否使用 Gopeed。
  - `fallback_enabled`：是否启用内置回退。
  - `gopeed`：可执行文件、API 地址、Token、连接数、自动启动、无头模式。
- **富文本输出**：使用 `rich` 输出面板、表格、进度条、彩色状态提示。
- **异常处理**：支持 Ctrl+C 中断，退出前提示按 Enter 关闭。

---

## 输入文件格式

在程序目录下放置任意 `.txt` 文件，每行一个 URL，例如：

```
https://modrinth.com/mod/sodium
https://modrinth.com/resourcepack/faithful
https://modrinth.com/shader/complementary-reimagined
https://www.curseforge.com/minecraft/mc-mods/jei
https://www.curseforge.com/minecraft/texture-packs/faithful
```

程序会自动扫描并识别其中的有效 URL。
