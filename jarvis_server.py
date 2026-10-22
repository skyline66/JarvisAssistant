# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 桌面智能助理 · 主服务
功能：WebSocket 实时对话、edge-tts 语音合成、系统命令、天气/新闻/备忘/提醒、
      AI 大脑（可接入 DeepSeek 等 OpenAI 兼容 API）、实时系统状态推送。
"""
import argparse
import asyncio
import json
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from aiohttp import web, WSMsgType

from config import (BASE_DIR, WEBUI_DIR, AUDIO_DIR, load_config, save_config,
                    load_memory, save_memory, time_str)
from brain import Brain
from tts_engine import generate_tts, get_voice_catalog, preview_tts
from smart_home import SmartHome
import commands as C

VERSION = "1.7.0"

# 兼容打包环境：强制 stdout/stderr 使用 UTF-8，避免中文打印报错
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 动作映射：兜底回答里附带的可执行动作
ACTION_MAP = {
    "open_url": C.open_url,
    "open_app": C.open_app,
}


class JarvisHub:
    def __init__(self):
        self.cfg = load_config()
        self.sm = SmartHome(self.cfg)
        self.brain = Brain(self.cfg, sm=self.sm)
        self.clients = set()
        self.pending = {}  # confirm_id -> 回调/动作
        self._confirm_seq = 0

    # ---------- WebSocket ----------
    async def ws_handler(self, request):
        ws = web.WebSocketResponse(max_msg_size=2 * 1024 * 1024)
        await ws.prepare(request)
        self.clients.add(ws)
        try:
            await self.send_json(ws, {"type": "hello", "name": self.cfg["assistant_name"], "version": VERSION})
            await asyncio.sleep(0.3)
            await self.send_json(ws, {"type": "settings", "data": self.settings_payload()})
            await self.send_json(ws, {"type": "devices", "data": self.sm.get_devices()})
            await self.send_json(ws, {"type": "suggestions", "data": await self.suggestions_payload()})
            # 欢迎语（语音+字幕）
            await self.speak_to(ws, "系统已就绪。我是贾维斯，有什么可以帮你？")
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except Exception:
                        continue
                    await self.handle_client(ws, data)
                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            self.clients.discard(ws)
        return ws

    # ---------- 消息处理 ----------
    async def handle_client(self, ws, data):
        mtype = data.get("type", "")
        if mtype == "chat":
            text = (data.get("text") or "").strip()
            if not text:
                return
            # 用户消息由前端本地展示，此处不再回显，避免重复
            await self.send_json(ws, {"type": "status", "state": "thinking"})
            self.stop_event = asyncio.Event()
            try:
                async def on_delta(chunk):
                    await self.send_json(ws, {"type": "llm_delta", "text": chunk})

                async def on_step(step):
                    await self.send_json(ws, {"type": "agent_step", "data": step})

                resp = await self.brain.process(text, on_delta=on_delta, on_step=on_step,
                                                cancel=self.stop_event)
            except Exception as e:
                resp = {"text": f"处理时出了点问题：{e}"}
            await self.finish_response(ws, resp)
            # 对话后刷新动态提示词（热点 + 会话个性化）
            try:
                await self.send_json(ws, {"type": "suggestions",
                                          "data": await self.suggestions_payload()})
            except Exception:
                pass
            # 智能家居状态同步（语音/文字控制后各端面板一致）
            await self.broadcast({"type": "devices", "data": self.sm.get_devices()})
        elif mtype == "confirm":
            cid = data.get("id")
            ok = data.get("ok", False)
            act = self.pending.pop(cid, None)
            if act and ok:
                await self.execute_action(ws, act)
            elif act:
                await self.speak_to(ws, "好的，已取消。")
        elif mtype == "settings_save":
            new = data.get("data") or {}
            self._apply_settings(new)
            save_config(self.cfg)
            self.brain.cfg = self.cfg
            self.brain.history = []
            await self.send_json(ws, {"type": "settings", "data": self.settings_payload()})
            await self.speak_to(ws, "设置已保存。")
        elif mtype == "device_set":
            did = data.get("id")
            payload = data.get("payload") or {}
            reply = await self.sm.set_device(did, payload)
            await self.broadcast({"type": "devices", "data": self.sm.get_devices()})
            await self.speak_to(ws, reply)
        elif mtype == "stop":
            # 停止当前生成 / 播报（前端同时暂停音频）
            if self.stop_event and not self.stop_event.is_set():
                self.stop_event.set()
            await self.send_json(ws, {"type": "stopped", "text": "已停止生成。"})
        elif mtype == "ping":
            await self.send_json(ws, {"type": "pong"})

    def _apply_settings(self, new):
        if "assistant_name" in new:
            self.cfg["assistant_name"] = str(new["assistant_name"])[:20]
        if "workbench_title" in new:
            self.cfg["workbench_title"] = str(new["workbench_title"])[:40]
        if isinstance(new.get("llm"), dict):
            llm_new = new["llm"]
            for k in ("enabled", "provider", "base_url", "api_key", "model", "reasoning"):
                if k in llm_new and llm_new[k] is not None:
                    self.cfg["llm"][k] = llm_new[k]
            if isinstance(llm_new.get("providers"), dict):
                for pk, pv in llm_new["providers"].items():
                    if isinstance(pv, dict):
                        slot = self.cfg["llm"]["providers"].setdefault(pk, {})
                        for k in ("base_url", "model", "api_key"):
                            if k in pv and pv[k]:
                                slot[k] = pv[k]
            # 当前生效厂商与顶层字段互相同步，便于切换厂商
            prov = self.cfg["llm"]["providers"].setdefault(self.cfg["llm"]["provider"], {})
            for k in ("base_url", "model", "api_key"):
                v = self.cfg["llm"].get(k)
                if v:
                    prov[k] = v
            self.cfg["llm"]["providers"][self.cfg["llm"]["provider"]] = prov
        if isinstance(new.get("tts"), dict):
            self.cfg["tts"].update({
                k: new["tts"].get(k, self.cfg["tts"].get(k))
                for k in ("voice", "rate", "volume", "pitch")
            })
        if isinstance(new.get("location"), dict):
            self.cfg["location"].update({
                k: new["location"].get(k, self.cfg["location"].get(k))
                for k in ("city", "latitude", "longitude")
            })
        if isinstance(new.get("smart_home"), dict):
            self.cfg["smart_home"].update({
                k: str(new["smart_home"].get(k, self.cfg["smart_home"].get(k)) or "").strip()
                for k in ("ha_url", "ha_token")
            })
            self.sm.cfg = self.cfg

    def settings_payload(self):
        c = self.cfg
        return {
            "assistant_name": c["assistant_name"],
            "workbench_title": c.get("workbench_title", "贾维斯的智能AI工作台"),
            "llm": dict(c["llm"]),
            "tts": dict(c["tts"]),
            "location": dict(c["location"]),
            "smart_home": {"ha_url": c["smart_home"].get("ha_url", ""),
                           "ha_token": c["smart_home"].get("ha_token", "")},
            "voices": get_voice_catalog(),
        }

    async def suggestions_payload(self) -> list:
        """动态提示词推荐：热点（新闻）+ 个性化（会话记录/地点）+ 玩法（智能家居/趣味）"""
        city = self.cfg["location"].get("city", "深圳")
        hist = [m.get("content", "") for m in self.brain.history[-6:] if m.get("role") == "user"]
        pool = []
        # 1) 热点（基于新闻标题，带缓存）
        try:
            hot = await self.brain._news_headlines("科技", 5)
            if hot:
                pool.append({"cmd": "讲讲今天的科技热点", "label": "🔥 科技热点"})
                pool.append({"cmd": "搜索：" + hot[0][:16], "label": "🔎 " + hot[0][:16] + "…"})
        except Exception:
            pass
        try:
            fin = await self.brain._news_headlines("财经", 3)
            if fin:
                pool.append({"cmd": "看看今天财经新闻", "label": "📈 财经快讯"})
        except Exception:
            pass
        # 2) 个性化（会话记录 + 地点）
        joined = " ".join(hist)
        if "天气" in joined or "温度" in joined:
            pool.append({"cmd": f"{city}今天天气", "label": f"🌤 {city}天气"})
            pool.append({"cmd": "北京天气", "label": "🌤 北京天气"})
        if "新闻" in joined or "热点" in joined:
            pool.append({"cmd": "今天有什么新闻", "label": "📰 新闻头条"})
        if "备忘" in joined or "记下" in joined:
            pool.append({"cmd": "查看备忘", "label": "📝 查看备忘"})
        if "提醒" in joined:
            pool.append({"cmd": "查看提醒", "label": "⏰ 查看提醒"})
        # 3) 智能家居玩法
        pool.append({"cmd": "打开客厅灯", "label": "💡 开客厅灯"})
        pool.append({"cmd": "空调调到26度", "label": "❄️ 空调26度"})
        pool.append({"cmd": "关掉窗帘", "label": "🪟 关窗帘"})
        pool.append({"cmd": "扫地机器人开始工作", "label": "🤖 扫地机器人"})
        # 4) 通用趣味兜底
        pool.append({"cmd": "介绍一下你自己", "label": "🤖 自我介绍"})
        pool.append({"cmd": "讲个笑话", "label": "😂 讲个笑话"})
        pool.append({"cmd": "系统状态", "label": "🖥 系统状态"})
        pool.append({"cmd": "现在几点", "label": "🕐 现在几点"})
        # 去重
        seen, out = set(), []
        for s in pool:
            if s["cmd"] not in seen:
                seen.add(s["cmd"])
                out.append(s)
        import random
        random.shuffle(out)
        return out[:10]

    # ---------- 响应处理 ----------
    async def finish_response(self, ws, resp):
        text = resp.get("text") or ""
        if resp.get("confirm"):
            cid = resp["confirm"]["id"]
            self._confirm_seq += 1
            full_id = f"{cid}_{self._confirm_seq}"
            label = resp["confirm"].get("label", "确认执行吗？")
            self.pending[full_id] = ("confirm_action", resp)
            await self.send_json(ws, {"type": "confirm", "id": full_id, "label": label,
                                      "cancelable": True})
            return
        if resp.get("action"):
            act = resp["action"]
            if isinstance(act, (list, tuple)) and len(act) == 2:
                await self.execute_action(ws, ("action", act))
        await self.speak_to(ws, text, resp.get("speak_text"))

    async def execute_action(self, ws, act):
        """act: ("confirm_action", resp) 或 ("action", (fn, arg))"""
        kind = act[0]
        if kind == "confirm_action":
            resp = act[1]
            # 确认后真正执行
            if resp.get("action"):
                fn_name, arg = resp["action"]
                if fn_name == "exit_app":
                    await self.send_json(ws, {"type": "bye"})
                    await asyncio.sleep(1.2)
                    import os
                    os._exit(0)
                    return
                fn = ACTION_MAP.get(fn_name)
                if fn:
                    try:
                        result = fn(arg)
                        await self.send_json(ws, {"type": "action_log", "text": result})
                    except Exception as e:
                        await self.send_json(ws, {"type": "action_log", "text": f"执行失败：{e}"})
            text = resp.get("text") or ""
            await self.speak_to(ws, text, resp.get("speak_text"))
            return
        if kind == "action":
            fn_name, arg = act[1]
            fn = ACTION_MAP.get(fn_name)
            if fn:
                try:
                    result = fn(arg)
                    await self.send_json(ws, {"type": "action_log", "text": result})
                except Exception as e:
                    await self.send_json(ws, {"type": "action_log", "text": f"执行失败：{e}"})
        await self.send_json(ws, {"type": "status", "state": "idle"})

    # ---------- 语音 + 字幕 ----------
    async def speak_to(self, ws, text, speak_text=None):
        if not text:
            await self.send_json(ws, {"type": "status", "state": "idle"})
            return
        spoken = speak_text or text
        await self.send_json(ws, {"type": "status", "state": "speaking"})
        audio = await generate_tts(spoken, self.cfg["tts"]["voice"],
                                   self.cfg["tts"]["rate"], self.cfg["tts"]["volume"],
                                   self.cfg["tts"].get("pitch", "+0Hz"))
        await self.send_json(ws, {"type": "jarvis", "text": text, "spoken": spoken, "audio": audio})
        await self.send_json(ws, {"type": "status", "state": "idle"})

    # ---------- 广播 ----------
    async def broadcast(self, payload):
        dead = []
        for ws in list(self.clients):
            try:
                await self.send_json(ws, payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    @staticmethod
    async def send_json(ws, payload):
        try:
            await ws.send_json(payload)
        except Exception:
            pass

    # ---------- 后台任务 ----------
    async def reminder_loop(self):
        while True:
            try:
                mem = load_memory()
                now = time.time()
                due = [r for r in mem["reminders"] if not r.get("done") and r["due"] <= now]
                if due:
                    for r in due:
                        r["done"] = True
                        await self.broadcast({"type": "reminder", "text": r["text"]})
                        await self.broadcast({"type": "jarvis", "text": "提醒：" + r["text"],
                                              "spoken": "提醒：" + r["text"], "audio": None})
                    save_memory(mem)
            except Exception:
                pass
            await asyncio.sleep(2)

    async def stats_loop(self):
        import psutil
        while True:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                disk = psutil.disk_usage("/").percent
                await self.broadcast({"type": "stats", "cpu": round(cpu, 1),
                                      "mem": round(mem, 1), "disk": round(disk, 1)})
            except Exception:
                pass
            await asyncio.sleep(2)

    async def audio_cleanup_loop(self):
        while True:
            try:
                files = sorted(AUDIO_DIR.glob("tts_*.mp3"), key=lambda p: p.stat().st_mtime)
                for f in files[:-60]:
                    f.unlink(missing_ok=True)
            except Exception:
                pass
            await asyncio.sleep(300)


def pick_port(cfg):
    port = int(cfg["server"].get("port", 8770))
    for p in range(port, port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return port


def build_app() -> tuple:
    hub = JarvisHub()
    app = web.Application()
    app["hub"] = hub

    # 路由
    async def index(request):
        return web.FileResponse(WEBUI_DIR / "index.html")

    async def health(request):
        return web.json_response({"ok": True, "version": VERSION,
                                  "time": time_str()})

    async def tts_preview(request):
        voice = request.query.get("voice", "zh-CN-XiaoxiaoNeural")
        rate = request.query.get("rate", "+0%")
        volume = request.query.get("volume", "+0%")
        pitch = request.query.get("pitch", "+0Hz")
        url = await preview_tts(voice, rate, volume, pitch)
        return web.json_response({"url": url})

    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/tts_preview", tts_preview)
    app.router.add_get("/ws", hub.ws_handler)
    app.router.add_static("/static", WEBUI_DIR, show_index=False)
    app.router.add_static("/audio", AUDIO_DIR, show_index=False)

    # 后台任务
    async def on_startup(app_):
        asyncio.create_task(hub.reminder_loop())
        asyncio.create_task(hub.audio_cleanup_loop())
        if _psutil_available():
            asyncio.create_task(hub.stats_loop())

    app.on_startup.append(on_startup)
    return app, hub


def _psutil_available():
    try:
        import psutil
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. 桌面智能助理")
    parser.add_argument("--host", default=None, help="监听地址，默认取 config.json")
    parser.add_argument("--port", type=int, default=None, help="端口，默认取 config.json")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    cfg = load_config()
    port = args.port or pick_port(cfg)
    host = args.host or cfg["server"].get("host", "127.0.0.1")
    print("=" * 56)
    print(f"  J.A.R.V.I.S. v{VERSION}  桌面智能助理")
    print(f"  界面地址: http://{host}:{port}")
    print("  按 Ctrl+C 退出服务")
    print("=" * 56)

    # 打包 EXE 运行时自动打开浏览器
    if getattr(sys, "frozen", False) and not args.no_browser:
        url = f"http://127.0.0.1:{port}"
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    app, _hub = build_app()
    web.run_app(app, host=host, port=port, print=None, access_log=None)


if __name__ == "__main__":
    main()
