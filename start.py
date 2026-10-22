# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 启动器：自动安装依赖 -> 启动服务 -> 打开界面"""
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

BASE_DIR = Path(__file__).resolve().parent
REQ = BASE_DIR / "requirements.txt"


def ensure_deps():
    missing = []
    for mod in ("aiohttp", "edge_tts", "psutil", "PIL"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print("[J.A.R.V.I.S.] 正在安装依赖:", ", ".join(missing))
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(REQ), "-q"], check=False)
    # 复查
    for mod in ("aiohttp", "edge_tts"):
        try:
            __import__(mod)
        except ImportError:
            print("[错误] 依赖安装失败，请手动执行: pip install -r requirements.txt")
            sys.exit(1)


def main():
    print("[J.A.R.V.I.S.] 正在启动桌面智能助理...")
    ensure_deps()

    import json
    cfg_path = BASE_DIR / "config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    port = int((cfg.get("server") or {}).get("port", 8770))

    # 启动服务子进程
    proc = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "jarvis_server.py")],
        cwd=str(BASE_DIR),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    url = f"http://127.0.0.1:{port}"
    ok = False
    for _ in range(40):
        if proc.poll() is not None:
            print("[错误] 服务启动失败，请检查报错信息。")
            return
        try:
            with urllib.request.urlopen(url + "/health", timeout=1.5) as r:
                if r.status == 200:
                    ok = True
                    break
        except Exception:
            time.sleep(0.5)
    if not ok:
        print("[错误] 服务未就绪，请检查端口占用或 Python 环境。")
        proc.terminate()
        return

    print(f"[J.A.R.V.I.S.] 服务已就绪: {url}")
    print("[J.A.R.V.I.S.] 正在打开控制界面...（关闭本窗口即停止服务）")
    webbrowser.open(url)

    try:
        while True:
            if proc.poll() is not None:
                print("[提示] 服务已停止。")
                break
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()
    print("[J.A.R.V.I.S.] 已退出。")


if __name__ == "__main__":
    main()
