# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. Web 版启动器
绑定 0.0.0.0，局域网内其他设备可通过 http://<本机IP>:端口 访问。
注意：语音识别/麦克风属于浏览器安全特性，仅 localhost 或 HTTPS 下可用；
      远程设备通过 http 访问时可正常使用文字指令、字幕与语音播放。
"""
import json
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

BASE = Path(__file__).resolve().parent


def pick_port(cfg):
    port = int((cfg.get("server") or {}).get("port", 8770))
    for p in range(port, port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return port


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    print("[J.A.R.V.I.S.] Web 版启动中（监听 0.0.0.0，支持局域网访问）...")
    cfg = {}
    p = BASE / "config.json"
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    port = pick_port(cfg)

    proc = subprocess.Popen(
        [sys.executable, str(BASE / "jarvis_server.py"),
         "--host", "0.0.0.0", "--port", str(port)],
        cwd=str(BASE),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(40):
        if proc.poll() is not None:
            print("[错误] 服务启动失败。")
            return
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    ip = lan_ip()
    print("=" * 56)
    print("  J.A.R.V.I.S. Web 版已就绪")
    print(f"  本机访问 : http://127.0.0.1:{port}")
    print(f"  局域网访问: http://{ip}:{port}   （手机/其他电脑可访问）")
    print("  提示：远程访问语音识别需 HTTPS；文字/字幕/语音播放不受影响")
    print("  关闭本窗口即停止服务")
    print("=" * 56)
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass
    try:
        while True:
            if proc.poll() is not None:
                break
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()


if __name__ == "__main__":
    main()
