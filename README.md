# 🧩 Minecraft 模组版本匹配工具

一个基于 Python + Rich TUI 的 Minecraft 模组版本兼容性检查与批量下载工具。支持 **Modrinth** 和 **CurseForge** 链接，可自动筛选模组支持的 Minecraft 版本，并利用 **Gopeed** 高速下载模组文件。

---

## 📦 获取程序

### 方式一：直接下载 EXE（推荐）

- **无需安装 Python**，下载即用
- 下载地址：[dist文件夹里面](./dist)
- 将 `模组版本匹配.exe` 放入一个独立文件夹中

### 方式二：运行 Python 源码

```bash
git clone <你的仓库地址>
cd 模组版本匹配
pip install -r requirements.txt
python 模组版本匹配.py
```

---

## ✨ 功能特性

- ✅ **兼容性检查**：输入版本范围，自动统计每个模组支持的版本数量，生成 Excel 矩阵报告
- ✅ **批量下载**：选择加载器、Minecraft 版本和版本类型（Release / Beta / Alpha），一键批量下载所有模组
- ✅ **Gopeed 高速下载**：通过 HTTP API 调用 Gopeed 进行多线程下载，全自动无界面
- ✅ **版本类型智能回退**：选择 `Alpha` 时优先 Alpha，无则回退 Beta，再回退 Release；选择 `Beta` 同理
- ✅ **TUI 交互界面**：纯键盘操作（方向键 + Enter），无需鼠标，操作直观
- ✅ **配置文件持久化**：保存 Gopeed 路径、默认下载目录、并发数等设置
- ✅ **内置下载备用**：若 Gopeed 不可用，自动切换到 Python 内置下载（带进度条）

---

## 📂 文件说明

将以下文件放在**同一目录**下：

| 文件名             | 说明                                   |
| ------------------ | -------------------------------------- |
| `模组版本匹配.exe` | 主程序（若使用源码则为 `.py` 文件）    |
| `mod_urls.txt`     | **必填**：每行一个模组 URL             |
| `config.json`      | **自动生成**：配置文件，首次运行后出现 |

---

## 🚀 快速开始

### 第一步：准备 `mod_urls.txt`

在程序所在目录创建 `mod_urls.txt`，每行一个模组 URL：

```txt
https://modrinth.com/mod/sodium
https://modrinth.com/mod/fabric-api
https://modrinth.com/mod/iris
https://www.curseforge.com/minecraft/mc-mods/jei
```

> **注意**：
>
> - 支持 Modrinth 和 CurseForge 链接
> - CurseForge 链接目前仅用于兼容性检查，下载时会被跳过（需手动下载）
> - 空行会被忽略，可以随意换行

### 第二步：运行程序

双击 `模组版本匹配.exe`，或在终端中运行：

```bash
模组版本匹配.exe
```

### 第三步：选择模式

使用 **↑** / **↓** 方向键选择模式，按 **Enter** 确认：

```
┌─────────────────────────────────────────────┐
│ 模组版本兼容性检查工具                      │
│ 选择运行模式 (↑↓ 选择，Enter 确认)          │
└─────────────────────────────────────────────┘

  ▶  兼容性检查   检查模组对版本范围的兼容性并生成Excel报告
      批量下载     根据指定版本和加载器下载模组文件
```

---

## 🎮 操作流程详解

### 模式一：兼容性检查

| 步骤 | 操作                                                                   | 说明                                                            |
| ---- | ---------------------------------------------------------------------- | --------------------------------------------------------------- |
| 1    | 方向键选择 **兼容性检查**，按 Enter                                    | 进入检查模式                                                    |
| 2    | 输入最低版本（如 `1.20.4`），按 Enter                                  | 支持 `1.20.4`、`26.1`、`26.1.2` 等格式                          |
| 3    | 输入最高版本（如 `26.2`），按 Enter                                    | 程序会动态获取该范围内的所有版本                                |
| 4    | 方向键选择加载器（Fabric / Forge / NeoForge / Quilt / 全部），按 Enter | 选择是否过滤加载器                                              |
| 5    | 等待处理完成                                                           | 生成 Excel 报告：`mod_compatibility_1.20.4_to_26.2_fabric.xlsx` |

### 模式二：批量下载

| 步骤 | 操作                                                            | 说明                                                                                                       |
| ---- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 1    | 方向键选择 **批量下载**，按 Enter                               | 进入下载模式                                                                                               |
| 2    | 方向键选择加载器（Fabric / Forge / NeoForge / Quilt），按 Enter | **不能选“全部”**，必须指定具体加载器                                                                       |
| 3    | 方向键选择 Minecraft 版本（如 `26.2`），按 Enter                | 版本列表来自 Modrinth 动态获取                                                                             |
| 4    | 方向键选择版本类型，按 Enter                                    | **Release**：仅稳定版<br>**Beta**：优先 Beta，无则 Release<br>**Alpha**：优先 Alpha，无则 Beta，再 Release |
| 5    | 等待下载完成                                                    | 所有文件保存到 **Gopeed 的默认下载目录**                                                                   |

---

## ⚙️ 配置文件 `config.json`

首次运行自动生成，您可手动编辑调整。

```json
{
    "download": {
        "default_dir": "./downloads",          // 内置下载备用目录（Gopeed 不可用时使用）
        "use_gopeed": true,                    // 是否启用 Gopeed
        "fallback_enabled": true,              // Gopeed 失败时是否回退到内置下载
        "gopeed": {
            "executable": "gopeed",            // Gopeed 可执行文件路径
            "api_base": "http://127.0.0.1:9999", // Gopeed API 地址
            "token": "",                       // 若 Gopeed 设置了接口令牌，请填写
            "connections": 16,                 // 每个任务的并发连接数
            "auto_start": true,                // 脚本自动启动 Gopeed 服务（无界面）
            "headless": true                   // 以无界面模式启动 Gopeed
        }
    }
}
```

### 配置示例（Gopeed 在非默认路径）

假设 Gopeed 安装在 `D:\software\gopeed\gopeed.exe`：

```json
{
    "download": {
        "default_dir": "./downloads",
        "use_gopeed": true,
        "fallback_enabled": true,
        "gopeed": {
            "executable": "D:/software/gopeed/gopeed.exe",
            "api_base": "http://127.0.0.1:9999",
            "token": "",
            "connections": 16,
            "auto_start": true,
            "headless": true
        }
    }
}
```

> ⚠️ **注意**：路径中的反斜杠 `\` 请改为正斜杠 `/`，或使用双反斜杠 `\\`。

---

## 🛠️ Gopeed 配置（推荐）

为了获得最佳下载体验，建议配置 Gopeed：

1. **下载安装 Gopeed**：[https://github.com/GopeedLab/gopeed/releases](https://github.com/GopeedLab/gopeed/releases)
2. **打开 Gopeed 图形界面**
3. **启用 TCP 协议**：`设置` → `高级` → `通讯协议` → 选择 **TCP**
4. **（可选）设置默认下载目录**：`设置` → `下载` → `默认下载目录`
5. **重启 Gopeed** 使设置生效

> 💡 如果不想使用 Gopeed，可在配置文件中设置 `use_gopeed: false`，将使用内置下载。

---

## 🎮 TUI 键盘操作指南

所有界面均使用键盘控制：

| 按键      | 功能                           |
| --------- | ------------------------------ |
| `↑` / `↓` | 上/下移动选择项                |
| `Enter`   | 确认选择                       |
| `ESC`     | 取消当前操作（返回上级或退出） |

---

## 📁 输出文件

| 文件名                                                     | 说明                     |
| ---------------------------------------------------------- | ------------------------ |
| `mod_compatibility_{最低版本}_to_{最高版本}_{加载器}.xlsx` | 兼容性矩阵报告           |
| `config.json`                                              | 用户配置文件（自动生成） |

---

## ❓ 常见问题

### 1. 提示“未找到 Gopeed 可执行文件”

- 检查 `config.json` 中 `gopeed.executable` 路径是否正确
- 或将 Gopeed 所在目录添加到系统 `PATH` 环境变量

### 2. Gopeed 服务无法连接

- 确认 Gopeed 已开启 TCP 协议（设置 → 高级 → 通讯协议 → TCP）
- 确认防火墙未阻止 `9999` 端口
- 检查 `config.json` 中 `api_base` 是否与 Gopeed 监听地址一致

### 3. 下载的文件没有出现在预期目录

- 脚本不传递 `path` 参数，所有文件均保存到 **Gopeed 的默认下载目录**
- 请在 Gopeed 设置中修改默认下载目录，或接受默认位置

### 4. 版本类型选择 Alpha 但没有下载 Alpha 版本

- Alpha 模式会回退：Alpha → Beta → Release，若都没有则跳过该模组
- 可在 Gopeed GUI 中查看任务详情确认实际下载版本

### 5. 兼容性检查生成的 Excel 报告是乱码

- 用 Excel 打开时选择 UTF-8 编码，或使用 WPS 等支持 UTF-8 的软件

### 6. 双击 EXE 一闪而过

- 打开命令行，切换到 EXE 所在目录，手动运行查看报错信息
- 常见原因：缺少 `mod_urls.txt` 文件

---

## 📦 文件目录结构（建议）

```
你的文件夹/
├── 模组版本匹配.exe      # 主程序
├── mod_urls.txt          # 模组 URL 列表（必填）
├── config.json           # 配置文件（自动生成）
├── downloads/            # 内置下载目录（可选）
└── mod_compatibility_*.xlsx  # 兼容性报告（生成）
```

---

## 📄 许可证

本项目基于 **MIT License** 开源，详细条款请查看 [LICENSE](./LICENSE.txt) 文件。

简单来说，你可以自由使用、修改、分发和商业化本软件，唯一的要求是保留原始的版权和许可声明（即在某个地方注明 Copyright (c) 2026 Tanjikun 和 MIT 协议）。

---

> 💡 **提示**：首次使用建议先用少量模组测试，熟悉流程后再批量操作。如有问题，请查看程序输出的错误信息，或提交 Issue。
