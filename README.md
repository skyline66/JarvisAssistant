# J.A.R.V.I.S. 桌面智能助理

<p align="center">
  <img src="https://img.shields.io/github/stars/skyline66/JarvisAssistant?style=flat-square&color=00e5ff" alt="GitHub stars"/>
  <img src="https://img.shields.io/badge/version-v1.2.0-00e5ff?style=flat-square" alt="version"/>
  <img src="https://img.shields.io/github/actions/workflow/status/skyline66/JarvisAssistant/ci.yml?style=flat-square" alt="CI"/>
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=flat-square" alt="License"/>
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Platform"/>
  <img src="https://img.shields.io/badge/TTS-edge--tts%20%28free%29-4FC08D?style=flat-square" alt="TTS"/>
</p>

托尼・斯塔克同款桌面语音助理：**语音对话 + 免费神经语音回复 + 实时字幕 + 酷炫全息界面 + 系统级命令执行**。

## 快速开始



1. 双击 `start_jarvis.bat`（自动检查 / 安装依赖，启动服务并打开界面）。

2. 首次打开界面，浏览器会请求麦克风权限，请允许（用于语音输入）。

3. 开始使用：

* **文字**：底部输入框输入指令，回车发送；

* **语音**：点击「⚡ 唤醒」开启连续聆听，说 **“贾维斯”** 唤醒后再下达指令；或按住「🎤 按住说话」直接说。

> 语音识别与语音合成均使用
>
> **免费方案**
>
> ：浏览器 Web Speech API（识别）+ Microsoft edge-tts 神经语音（合成，无需任何 Key）。没有网络时自动降级为浏览器本地语音朗读。

## 系统权限说明



* 贾维斯在本机**当前用户权限**下执行命令（打开应用、控制音量、锁屏、截图、查看磁盘等）。

* **关机 / 重启 / 退出助理**等高风险操作会在界面弹窗**二次确认**后才执行。

* 若需要管理员级操作，可右键 `start_jarvis.bat` → “以管理员身份运行”，服务即获得管理员权限。

## 支持的功能



| 分类        | 指令示例                                                     |
| --------- | -------------------------------------------------------- |
| 语音 / 文字对话 | “你好” “现在几点” “今天星期几”                                      |
| 应用控制      | “打开记事本 / 计算器 / 微信 / Chrome” “关闭记事本”                      |
| 网页 / 搜索   | “打开 [bilibili.com](https://bilibili.com)” “搜索 Python 教程” |
| 系统控制      | “调大音量” “音量调到 30” “静音” “锁屏” “睡眠” “截图”                     |
| 信息查询      | “深圳明天天气” “北京天气” “今天有什么新闻” “系统状态” “磁盘空间”                  |
| 计算        | “计算 3.14\*8” “2 的 10 次方”                                 |
| 办公备忘      | “记下买牛奶” “查看备忘”                                           |
| 定时提醒      | “提醒我 30 分钟后喝水” “明天 9 点提醒我开会” “查看提醒”                      |
| 剪贴板       | “剪贴板有什么” “复制 这段内容”                                       |
| 文件目录      | “打开下载文件夹” “打开 D:/ 工作”                                    |
| 知识问答      | “太阳系有几大行星” “圆周率是多少”                                      |
| 趣味        | “讲个笑话” “给我一句名言”                                          |
| 深度对话      | 在设置中填入 API Key 后，任意问题均可深度回答                              |

## 接入 AI 大脑（可选，推荐）

点击右上角 **⚙ 设置**：



1. 勾选 **启用 AI 大脑**；

2. 填写 OpenAI 兼容 API（默认 DeepSeek）：

* API 地址：`https://api.deepseek.com/v1`

* API Key：在 [platform.deepseek.com](https://platform.deepseek.com) 注册获取（价格约 ¥1 / 百万 tokens，新用户常赠送额度）

* 模型：`deepseek-chat`

1. 保存。之后贾维斯未命中本地指令时，会调用大模型深度回答，并具备多轮对话记忆。

未配置 Key 时，贾维斯使用 **本地意图引擎 + 中文维基百科 + 网页搜索** 兜底，开箱即用。

## 界面说明



* **中央全息核心**：待命（慢速光环）/ 聆听（加速）/ 思考（金色）/ 播报（波动条动画）；

* **底部大字幕**：实时显示贾维斯说的话（逐字输出，与语音同步）；

* **右侧日志面板**：完整交互记录；顶部实时显示 CPU / 内存 / 磁盘占用；

* **常用指令快捷芯片**：一键发送高频指令。

## 技术架构



```
浏览器界面 (全息 UI + 字幕 + Web Speech 语音识别)
        │  WebSocket (实时消息) / HTTP (音频、页面)
Python 服务 (aiohttp)
        ├─ 大脑 Brain：意图识别 → 命令路由 / 知识问答 / LLM 扩展
        ├─ 命令引擎 commands：PowerShell 系统控制
        ├─ 语音合成 tts_engine：edge-tts 免费神经语音 (MP3)
        ├─ 信息服务：Open-Meteo 天气 / 维基百科 / Bing 新闻 RSS
        └─ 后台任务：定时提醒、系统状态推送、音频清理
```

## 文件结构



```
JarvisAssistant/
├─ start_jarvis.bat    一键启动
├─ start.py            启动器（自动装依赖、开服务、开界面）
├─ jarvis_server.py    主服务（WebSocket + 路由 + 后台任务）
├─ brain.py            意图识别与对话大脑
├─ commands.py         系统命令执行引擎
├─ tts_engine.py       免费语音合成
├─ config.py           配置与记忆管理
├─ webui/index.html    全息界面
├─ config.json         本地配置（首次运行生成）
├─ memory.json         备忘与提醒（自动生成）
├─ notes.md            记事本
├─ audio/              语音缓存（自动清理）
└─ screenshots/        截图保存
```

## 常见问题



* **听不到声音**：检查系统音量；确认网络可用（edge-tts 需要联网，离线时自动用浏览器语音）。

* **语音识别不工作**：请使用 **Chrome 或 Edge** 浏览器；检查麦克风权限是否允许；Windows 麦克风隐私设置需开启 “允许应用访问麦克风”。

* **端口被占用**：服务会自动向后寻找可用端口（默认 8770）。

* **想要更高权限**：以管理员身份运行启动脚本。

## 卸载

删除整个 `JarvisAssistant` 文件夹即可（无系统残留、无后台服务、无开机自启）。

## 许可证

本项目基于 [MIT License](LICENSE) 开源，可自由使用、修改与分发。

## 自动化构建（GitHub Actions）

仓库已配置 CI 工作流（`.github/workflows/ci.yml`）：

- **每次 push / PR**：自动在 Windows 环境运行 `test_jarvis.py` 集成测试（意图识别 / 命令引擎 / edge-tts 语音 / WS 端到端 / 天气），通过后自动打包单文件 EXE，产物可在 Actions 页面下载。
- **打版本标签**：`git tag v1.1.0 && git push origin v1.1.0` 会自动发布 GitHub Release 并附带 EXE 安装文件。
- 也可以在 Actions 页面手动触发（workflow_dispatch）。

## 两个发布版本

本项目提供 **EXE 桌面版** 与 **Web 部署版** 两种形态：

| 版本 | 文件 | 说明 |
|---|---|---|
| EXE 桌面版 | `JarvisAssistant.exe`（见 `JarvisAssistant_exe/`） | 单文件免安装，双击即运行，自动打开界面；无需 Python 环境 |
| Web 部署版 | `JarvisAssistant_web/`（或 `JarvisAssistant_web.zip`） | 可部署到局域网/服务器，手机等设备通过浏览器访问；详见 `README_web.md` |

- EXE 版运行后数据（config.json / 备忘 / 截图）保存在 exe 同目录。
- Web 版默认监听 `0.0.0.0`；远程访问时**语音输入需 HTTPS**（文字、字幕、语音播放不受影响）。

## v1.2 更新记录

- **新增**：中央核心动效背景 **4 套主题可随时切换**（全息能量环 / 粒子漩涡 / 线框能量球 / 极光脉冲）——点击核心下方「主题」按钮轮换，或右上角 ⚙ 设置中固定选择，选择会本地记忆。
- **新增**：**三态视觉区分** —— 待命（青蓝呼吸环）/ 倾听中（绿色波纹 + 声波跳动）/ 执行任务中（金色能量急速环 + 双脉冲），字幕与状态灯同步联动。

## v1.1 更新记录

- **修复**：用户消息重复显示（去除服务端回显，日志中每条消息仅出现一次）。
- **新增**：首次进入引导弹窗 —— 使用简介 + 一键授权麦克风 + API Key 配置入口（可勾选“下次不再显示”）。
- **新增**：顶部 API Key 提示横幅 —— 未配置 Key 时持续提示，点击直达设置；配置后自动隐藏。
- **新增**：EXE 免安装桌面版 与 Web 局域网部署版两种打包形态。