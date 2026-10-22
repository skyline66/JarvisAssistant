# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 集成自测：验证核心链路"""
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

RESULTS = []


def report(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


async def ws_chat(port, text, timeout=40):
    """通过 WebSocket 发一条消息，返回 jarvis 响应"""
    import aiohttp
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(f"http://127.0.0.1:{port}/ws", timeout=10) as ws:
            # 排干欢迎流程（hello / settings / 欢迎语 / 状态），直到回到 idle
            for _ in range(10):
                try:
                    m = await asyncio.wait_for(ws.receive_json(), timeout=15)
                except Exception:
                    break
                if m.get("type") == "jarvis" and "系统已就绪" in m.get("text", ""):
                    # 等待其后的 idle 状态
                    for _ in range(3):
                        m2 = await asyncio.wait_for(ws.receive_json(), timeout=10)
                        if m2.get("type") == "status" and m2.get("state") == "idle":
                            break
                    break
                if m.get("type") == "status" and m.get("state") == "idle":
                    break
            await ws.send_json({"type": "chat", "text": text})
            got = {}
            while True:
                m = await asyncio.wait_for(ws.receive_json(), timeout=timeout)
                if m.get("type") == "jarvis":
                    got = m
                    break
                if m.get("type") == "confirm":
                    got = m
                    break
                if m.get("type") == "action_log":
                    got = {"type": "action_log", "text": m["text"]}
            return got


async def main():
    # 1) 大脑本地意图（不依赖网络）
    from brain import Brain
    from config import load_config
    brain = Brain(load_config())
    cases = [
        ("时间", "现在几点", lambda r: "现在是" in r),
        ("日期", "今天星期几", lambda r: "星期" in r),
        ("计算", "计算 2的10次方", lambda r: "1024" in r),
        ("计算2", "3.14*8等于多少", lambda r: "25.12" in r),
        ("问候", "你好", lambda r: "贾维斯" in r or "你好" in r or "我是" in r),
        ("帮助", "你会什么", lambda r: "系统控制" in r),
        ("笑话", "讲个笑话", lambda r: len(r) > 5),
        ("音量", "音量调到30", lambda r: "30" in r),
        ("系统状态", "系统状态", lambda r: "CPU" in r),
        ("磁盘", "磁盘空间", lambda r: "磁盘" in r or "GB" in r),
        ("备忘", "记下测试备忘abc123", lambda r: "已记下" in r),
        ("剪贴板", "剪贴板有什么", lambda r: len(r) > 0),
        ("帮助退出", "退出贾维斯", lambda r: "确认" in r or "退出" in r),
    ]
    for name, q, check in cases:
        try:
            r = await brain.process(q)
            txt = r.get("text", "")
            report("brain." + name, check(txt), txt[:60].replace("\n", " "))
        except Exception as e:
            report("brain." + name, False, str(e))

    # 2) 命令引擎（只读项）
    import commands as C
    report("cmd.disk", "GB" in C.disk_space(), C.disk_space()[:60])
    report("cmd.stats", "CPU" in C.system_stats(), C.system_stats()[:60])
    report("cmd.clipboard_get", True, C.clipboard_get()[:40])

    # 3) TTS 语音合成（edge-tts）
    from tts_engine import generate_tts
    from config import AUDIO_DIR
    url = await generate_tts("你好，我是贾维斯，系统测试成功。", "zh-CN-XiaoxiaoNeural", "+0%", "+0%")
    files = sorted(AUDIO_DIR.glob("tts_*.mp3"))
    report("tts.edge", bool(url) and len(files) > 0,
           url or f"fallback needed; files={len(files)}")

    # 4) 启动真实服务并做 WS 端到端
    import jarvis_server
    cfg = load_config()
    port = jarvis_server.pick_port(cfg)
    proc = subprocess.Popen(
        [sys.executable, str(BASE / "jarvis_server.py")],
        cwd=str(BASE), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0)
    ok_http = False
    for _ in range(30):
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as r:
                ok_http = r.status == 200
                if ok_http:
                    break
        except Exception:
            time.sleep(0.5)
    report("server.health", ok_http, f"port={port}")

    # 页面可访问
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as r:
            html = r.read().decode("utf-8", "ignore")
            report("server.index", r.status == 200 and "J.A.R.V.I.S." in html, f"len={len(html)}")
    except Exception as e:
        report("server.index", False, str(e))

    if ok_http:
        # WS 端到端（时间 + 语音音频URL）
        try:
            r = await ws_chat(port, "现在几点")
            report("ws.chat_time", r.get("type") == "jarvis" and "现在是" in r.get("text", ""),
                   str(r.get("text", ""))[:60])
            audio = r.get("audio")
            report("ws.audio_url", bool(audio), str(audio))
        except Exception as e:
            report("ws.chat_time", False, str(e))
        # 天气（联网）
        try:
            r = await ws_chat(port, "深圳天气", timeout=45)
            report("ws.weather", "天气" in r.get("text", "") or "气温" in r.get("text", ""),
                   r.get("text", "")[:80])
        except Exception as e:
            report("ws.weather", False, str(e))

    # 清理
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    failed = [n for n, ok, _ in RESULTS if not ok]
    print("\n==== 结果汇总 ====")
    print(f"通过 {len(RESULTS) - len(failed)} / {len(RESULTS)}")
    if failed:
        print("失败项:", failed)
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    asyncio.run(main())
