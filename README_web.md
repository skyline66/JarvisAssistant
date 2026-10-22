# J.A.R.V.I.S. Web 版部署指南

Web 版让贾维斯可以作为**局域网/服务器上的 Web 应用**运行：手机、平板、其他电脑通过浏览器访问，适合办公室内共享或部署到云服务器。

## 快速开始（局域网）

1. 本目录放置了完整服务端（`jarvis_server.py` 等）与前端（`webui/`）。
2. 双击 **`start_web.bat`**（或命令行执行 `python start_web.py`）。
3. 启动后终端会打印两个地址：
   - `http://127.0.0.1:8770` —— 本机访问
   - `http://<本机IP>:8770` —— 局域网其他设备访问（需放行防火墙端口）
4. 其他设备打开局域网地址即可使用。

## 部署到服务器 / 公网

- 环境要求：Python 3.9+（`pip install -r requirements.txt`）。
- 后台运行：`python start_web.py` 或自行用 systemd / supervisor / PM2 托管 `jarvis_server.py --host 0.0.0.0 --port 8770`。
- 建议在前面加一层 **HTTPS 反向代理**（Caddy / Nginx / Cloudflare Tunnel），原因见下。

## 重要限制：语音识别需要 HTTPS

浏览器的**麦克风/语音识别（Web Speech API）属于安全特性**：

| 访问方式 | 语音输入 | 文字指令 | 字幕 | 语音播放 |
|---|---|---|---|---|
| http://127.0.0.1 | ✅ | ✅ | ✅ | ✅ |
| http://局域网IP | ❌ | ✅ | ✅ | ✅ |
| https://域名 | ✅ | ✅ | ✅ | ✅ |

> 本机 localhost 被浏览器视为安全上下文，所以桌面版语音完全可用；
> 远程通过纯 http 访问时语音输入会被浏览器拦截（可打字），字幕与语音播放不受影响。
> 如需远程语音，请用 HTTPS（推荐 Caddy 一键自动证书，或 Cloudflare Tunnel）。

## 安全提示

- 服务未设密码认证，**请勿直接暴露到公网**；公网部署必须加访问控制（反向代理 Basic Auth / 令牌）。
- 命令执行功能会在客户端本机生效——注意：Web 版被远程访问时，系统命令执行的是**运行服务的这台电脑**，请确保部署环境受信任。
- API Key 保存在服务器本地 config.json 中，注意保护。

## 文件清单

```
jarvis_server.py   主服务（WebSocket + 路由 + 后台任务）
brain.py           意图识别与对话大脑
commands.py        系统命令执行引擎
tts_engine.py      免费神经语音合成（edge-tts）
config.py          配置与记忆管理
webui/index.html   全息界面
start_web.py       Web 版启动器（绑定 0.0.0.0）
start_web.bat      Web 版一键启动
requirements.txt   依赖清单
```
