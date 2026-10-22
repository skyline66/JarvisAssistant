# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 集成自测：验证核心链路"""
import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

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

    # 1.5) Agent 工具层（无需 API Key）
    try:
        tool_tests = [
            ("agent_tool_calc", "calc", "3.14*8", lambda r: "25.12" in r),
            ("agent_tool_time", "time", "", lambda r: ":" in r),
            ("agent_tool_date", "date", "", lambda r: "年" in r and "星期" in r),
            ("agent_tool_note", "note_add", "Agent测试备忘xyz", lambda r: "已记下" in r),
            ("agent_tool_note_read", "note_read", "", lambda r: "Agent测试备忘xyz" in r),
        ]
        for name, tool, arg, check in tool_tests:
            try:
                r = await brain._run_tool(tool, arg)
                report(name, check(r), str(r)[:60])
            except Exception as e:
                report(name, False, str(e))
    except Exception as e:
        report("agent_tools", False, str(e))
    try:
        from tts_engine import get_voice_catalog, VOICE_NAMES
        cat = get_voice_catalog()
        groups = len(cat)
        total = sum(len(g["voices"]) for g in cat)
        report("tts.catalog", groups >= 4 and total >= 30 and "zh-CN-YunxiNeural" in VOICE_NAMES,
               f"groups={groups} voices={total}")
    except Exception as e:
        report("tts.catalog", False, str(e))
    try:
        import re
        m = re.search(r"\[\[TOOL:(\w+)\|(.*?)\]\]", "请稍等 [[TOOL:calc|3.14*8]] 好的")
        report("agent.marker_parse", bool(m) and m.group(1) == "calc" and m.group(2) == "3.14*8",
               str(m.groups()) if m else "no match")
    except Exception as e:
        report("agent.marker_parse", False, str(e))

    # 1.6) 智能家居（本地模拟 + 语音指令）
    try:
        from smart_home import SmartHome
        from config import load_config as _lc
        sm = SmartHome(_lc())
        brain_sm = Brain(_lc(), sm=sm)
        home_cases = [
            ("home_light_on", "打开客厅灯", lambda r: "已开启客厅灯" in r),
            ("home_ac_set", "空调调到24度", lambda r: "24" in r and "空调" in r),
            ("home_light_off", "关闭卧室灯", lambda r: "已关闭卧室灯" in r),
            ("home_query", "客厅灯开着吗", lambda r: "客厅灯" in r and "开启" in r),
            ("home_curtain", "把窗帘关上", lambda r: "已关闭窗帘" in r),
            ("home_robot", "扫地机器人开始工作", lambda r: "已开启扫地机器人" in r),
        ]
        for name, q, check in home_cases:
            try:
                r = await brain_sm.process(q)
                txt = r.get("text", "")
                report(name, check(txt), txt[:60])
            except Exception as e:
                report(name, False, str(e))
        # 面板直控
        r = await sm.set_device("living_light", {"on": True})
        d = sm.get_device("living_light")
        report("home_panel_set", d["state"] is True and "已开启" in r, r[:40])
    except Exception as e:
        report("home_intent", False, str(e))

    # 1.7) 动态提示词（热点 + 个性化）
    try:
        import jarvis_server as _js
        hub = _js.JarvisHub()
        sg = await hub.suggestions_payload()
        report("suggestions", isinstance(sg, list) and len(sg) >= 5 and any("客厅灯" in s["cmd"] for s in sg),
               f"count={len(sg)}")
        # 对话记录影响推荐
        hub.brain.history.append({"role": "user", "content": "深圳明天天气怎么样"})
        sg2 = await hub.suggestions_payload()
        report("suggestions_personal", any("深圳" in s["cmd"] for s in sg2),
               " | ".join(s["cmd"] for s in sg2[:6]))
        # magpie 供应商列表
        provs = hub.cfg["llm"]["providers"]
        groups = {p.get("group") for p in provs.values()}
        report("providers_magpie", len(provs) >= 40 and {"订阅", "供应商", "中转"} <= groups,
               f"count={len(provs)} groups={sorted(groups)}")
    except Exception as e:
        report("suggestions", False, str(e))

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
