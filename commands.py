# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 系统命令执行引擎（Windows / PowerShell）
说明：所有命令在本机用户权限下执行；涉及系统级操作（关机/重启等）需界面二次确认。
"""
import base64
import re
import subprocess
import time

from config import SCREENSHOT_DIR, ensure_dirs


def run_ps(script: str, timeout: int = 30) -> tuple:
    """执行 PowerShell 脚本，返回 (stdout, returncode)。强制 UTF-8 输出，避免中文乱码。"""
    script = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $OutputEncoding=[Text.Encoding]::UTF8;\n" + script
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return p.stdout.strip(), p.returncode
    except Exception as e:
        return f"执行出错: {e}", -1


def run_ps_elevated(script: str) -> str:
    """以管理员权限执行（触发 UAC 确认弹窗），返回提示文本"""
    b64 = base64.b64encode(script.encode("utf-16-le")).decode()
    cmd = f"Start-Process powershell -Verb RunAs -ArgumentList '-EncodedCommand','{b64}'"
    out, code = run_ps(cmd, timeout=10)
    return "已请求管理员权限执行" if code == 0 else "权限请求未完成"


# ---------- 应用/网站 ----------
DIRECT_APPS = {
    "记事本": ("notepad", "notepad"),
    "notepad": ("notepad", "notepad"),
    "计算器": ("calc", "CalculatorApp"),
    "calc": ("calc", "CalculatorApp"),
    "画图": ("mspaint", "mspaint"),
    "paint": ("mspaint", "mspaint"),
    "命令提示符": ("cmd", "cmd"),
    "cmd": ("cmd", "cmd"),
    "终端": ("powershell", "powershell"),
    "powershell": ("powershell", "powershell"),
    "资源管理器": ("explorer", "explorer"),
    "explorer": ("explorer", "explorer"),
    "文件管理器": ("explorer", "explorer"),
    "文件夹": ("explorer", "explorer"),
    "任务管理器": ("taskmgr", "Taskmgr"),
    "taskmgr": ("taskmgr", "Taskmgr"),
    "控制面板": ("control", None),
    "设置": ("start ms-settings:", None),
    "chrome": ("start chrome", "chrome"),
    "谷歌浏览器": ("start chrome", "chrome"),
    "edge": ("start msedge", "msedge"),
    "微软浏览器": ("start msedge", "msedge"),
    "浏览器": ("start https://www.baidu.com", None),
}

URI_APPS = {
    "微信": ("weixin://", "WeChat"),
    "wechat": ("weixin://", "WeChat"),
    "qq": ("tencent://", "QQ"),
    "腾讯qq": ("tencent://", "QQ"),
    "网易云音乐": ("cloudmusic://", "cloudmusic"),
    "网易云": ("cloudmusic://", "cloudmusic"),
    "音乐": ("cloudmusic://", "cloudmusic"),
}


def _find_app_lnk(name: str) -> str:
    """在开始菜单中模糊查找应用快捷方式，返回完整路径"""
    script = r'''
$name = $args[0]
$dirs = @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs","$env:APPDATA\Microsoft\Windows\Start Menu\Programs")
$hits = @()
foreach($d in $dirs){
  if(Test-Path -LiteralPath $d){
    $hits += Get-ChildItem -LiteralPath $d -Filter *.lnk -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.BaseName -like "*$name*" }
  }
}
if($hits.Count -gt 0){ $hits | Select-Object -First 1 -ExpandProperty FullName }
'''.strip()
    out, _ = run_ps(f"& {{ {script} }} '{name}'", timeout=20)
    lines = [ln for ln in out.splitlines() if ln.strip().lower().endswith(".lnk")]
    return lines[0] if lines else ""


def open_app(name: str) -> str:
    name = name.strip().lower()
    # 1) 直接映射
    for key, (action, _proc) in {**DIRECT_APPS, **URI_APPS}.items():
        if key == name or (key in name and len(name) <= len(key) + 2):
            out, code = run_ps(f"Start-Process '{action}'")
            return f"已为你打开 {name.title() if name.isascii() else name}" if code == 0 else "启动失败"
    # 2) 开始菜单模糊查找
    lnk = _find_app_lnk(name)
    if lnk:
        out, code = run_ps(f"Start-Process -LiteralPath '{lnk}'")
        if code == 0:
            return f"已为你打开「{name}」"
    # 3) PATH 中的可执行程序
    out, code = run_ps(f"Get-Command '{name}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source")
    if code == 0 and out:
        run_ps(f"Start-Process '{out.splitlines()[0].strip()}'")
        return f"已为你打开「{name}」"
    return f"没有找到应用「{name}」，你可以直接告诉我网站地址，或我帮你搜索。"


def close_app(name: str) -> str:
    name = name.strip().lower()
    proc = None
    for key, (_action, _proc) in {**DIRECT_APPS, **URI_APPS}.items():
        if key == name or (key in name and len(name) <= len(key) + 2):
            proc = _proc
            break
    if not proc:
        proc = name
    out, code = run_ps(f"Stop-Process -Name '{proc}' -Force -ErrorAction SilentlyContinue")
    return f"已关闭「{name}」" if code == 0 else f"尝试关闭「{name}」，请确认该程序正在运行。"


def open_url(url: str) -> str:
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    out, code = run_ps(f"Start-Process '{url}'")
    return f"已在浏览器打开 {url}" if code == 0 else "打开网页失败"


# ---------- 系统控制 ----------
def set_volume(percent: int) -> str:
    percent = max(0, min(100, percent))
    v = int(0xFFFF * percent / 100)
    script = (
        "Add-Type -Namespace W -Name Vol -MemberDefinition @'"
        "[DllImport(\"winmm.dll\")] public static extern int waveOutSetVolume(IntPtr h, uint dwVolume);'@;"
        f"[W.Vol]::waveOutSetVolume([IntPtr]::Zero, {v})"
    )
    run_ps(script)
    return f"音量已调整为 {percent}%"


def volume_updown(direction: str, steps: int = 8) -> str:
    key = "0xAF" if direction == "up" else "0xAE"  # 音量+ / 音量-
    script = (
        "Add-Type -Namespace W -Name K -MemberDefinition @'"
        '[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);\'@;'
        f"1..{steps} | ForEach-Object {{ [W.K]::keybd_event({key},0,0,[UIntPtr]::Zero) }}"
    )
    run_ps(script)
    return "音量已调大" if direction == "up" else "音量已调低"


def mute_volume() -> str:
    script = (
        "Add-Type -Namespace W -Name Vol -MemberDefinition @'"
        '[DllImport("winmm.dll")] public static extern int waveOutSetVolume(IntPtr h, uint dwVolume);\'@;'
        "[W.Vol]::waveOutSetVolume([IntPtr]::Zero, 0)"
    )
    run_ps(script)
    return "已静音"


def lock_screen() -> str:
    run_ps("rundll32.exe user32.dll,LockWorkStation")
    return "已锁定屏幕"


def sleep_computer() -> str:
    run_ps("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "已进入睡眠"


def shutdown_computer(delay_sec: int = 30) -> str:
    run_ps(f"shutdown /s /t {delay_sec} /c 'Jarvis: 用户确认关机'")
    return f"将在 {delay_sec} 秒后关机"


def cancel_shutdown() -> str:
    run_ps("shutdown /a")
    return "已取消关机计划"


def restart_computer() -> str:
    run_ps("shutdown /r /t 10 /c 'Jarvis: 用户确认重启'")
    return "将在 10 秒后重启电脑"


def monitor_off() -> str:
    script = (
        "Add-Type -Namespace W -Name M -MemberDefinition @'"
        '[DllImport("user32.dll")] public static extern int SendMessage(int h,int m,int w,int l);\'@;'
        "[W.M]::SendMessage(-1,0x0112,0xF170,2)"
    )
    run_ps(script)
    return "显示器已关闭，移动鼠标即可唤醒"


# ---------- 信息查询 ----------
def disk_space() -> str:
    out, code = run_ps(
        "Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null } | "
        "ForEach-Object { '{0}: 总容量{1:N1}GB 可用{2:N1}GB 已用{3:N1}GB' -f $_.Name, (($_.Used+$_.Free)/1GB), ($_.Free/1GB), ($_.Used/1GB) }"
    )
    if code == 0 and out:
        return "磁盘空间如下：\n" + "\n".join(out.splitlines())
    return "暂时无法读取磁盘信息"


def system_stats() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        boot = psutil.boot_time()
        import datetime
        up = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot)
        days = up.days
        hrs = up.seconds // 3600
        mins = (up.seconds % 3600) // 60
        return (
            f"当前系统状态：CPU 使用率 {cpu}%，内存 {mem.percent}%（已用 {mem.used/1024**3:.1f}GB / 共 {mem.total/1024**3:.1f}GB），"
            f"系统已运行 {days} 天 {hrs} 小时 {mins} 分钟。"
        )
    except Exception:
        return "无法获取系统状态"


def screenshot() -> str:
    try:
        from PIL import ImageGrab
        ensure_dirs()
        fname = f"shot_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = SCREENSHOT_DIR / fname
        img = ImageGrab.grab()
        img.save(str(path))
        return f"截图已保存：{path}"
    except Exception as e:
        return f"截图失败：{e}"


# ---------- 剪贴板 ----------
def clipboard_get() -> str:
    out, code = run_ps("Get-Clipboard -Raw")
    if code == 0 and out:
        return f"剪贴板内容：{out[:200]}"
    return "剪贴板是空的"


def clipboard_set(text: str) -> str:
    b64 = base64.b64encode(text.encode("utf-8")).decode()
    script = f"Set-Clipboard -Value ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')))"
    out, code = run_ps(script)
    return "已复制到剪贴板" if code == 0 else "复制失败"


# ---------- 文件操作 ----------
def open_folder(path: str) -> str:
    if not re.match(r"^[a-zA-Z]:[\\/]", path):
        # 常见目录别名
        aliases = {
            "下载": "downloads",
            "文档": "documents",
            "桌面": "desktop",
            "图片": "pictures",
            "音乐": "music",
            "视频": "videos",
        }
        key = path.strip().lower()
        if key in aliases:
            path = run_ps(
                f"[Environment]::GetFolderPath('{aliases[key]}')"
            )[0]
    out, code = run_ps(f"Start-Process 'explorer.exe' -ArgumentList '{path}'")
    return f"已打开文件夹 {path}" if code == 0 else f"无法打开 {path}"
