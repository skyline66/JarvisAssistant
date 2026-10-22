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
from tts_engine import generate_tts, VOICES
import commands as C

VERSION = "1.1.0"

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
        self.brain = Brain(self.cfg)
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
            try:
                resp = await self.brain.process(text)
            except Exception as e:
                resp = {"text": f"处理时出了点问题：{e}"}
            await self.finish_response(ws, resp)
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
        elif mtype == "ping":
            await self.send_json(ws, {"type": "pong"})

    def _apply_settings(self, new):
        if "assistant_name" in new:
            self.cfg["assistant_name"] = str(new["assistant_name"])[:20]
        if isinstance(new.get("llm"), dict):
            self.cfg["llm"].update({
                k: new["llm"].get(k, self.cfg["llm"].get(k))
                for k in ("enabled", "base_url", "api_key", "model")
            })
        if isinstance(new.get("tts"), dict):
            self.cfg["tts"].update({
                k: new["tts"].get(k, self.cfg["tts"].get(k))
                for k in ("voice", "rate", "volume")
            })
        if isinstance(new.get("location"), dict):
            self.cfg["location"].update({
                k: new["location"].get(k, self.cfg["location"].get(k))
                for k in ("city", "latitude", "longitude")
            })

    def settings_payload(self):
        c = self.cfg
        return {
            "assistant_name": c["assistant_name"],
            "llm": dict(c["llm"]),
            "tts": dict(c["tts"]),
            "location": dict(c["location"]),
            "voices": VOICES,
        }

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
                                   self.cfg["tts"]["rate"], self.cfg["tts"]["volume"])
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

    app.router.add_get("/", index)
    app.router.add_get("/health", health)
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
