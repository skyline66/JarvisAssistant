# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 配置与记忆管理"""
import json
import os
import sys
from pathlib import Path

# 可写数据目录：普通运行=脚本目录；打包 EXE=exe 所在目录
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# 只读资源目录（webui）：打包后位于 _MEIPASS 临时解包目录
if getattr(sys, "frozen", False):
    APP_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    APP_DIR = BASE_DIR

WEBUI_DIR = APP_DIR / "webui"
CONFIG_FILE = BASE_DIR / "config.json"
MEMORY_FILE = BASE_DIR / "memory.json"
NOTES_FILE = BASE_DIR / "notes.md"
AUDIO_DIR = BASE_DIR / "audio"
SCREENSHOT_DIR = BASE_DIR / "screenshots"

DEFAULTS = {
    "assistant_name": "贾维斯",
    "server": {"host": "127.0.0.1", "port": 8770},
    "llm": {
        "enabled": False,
        "provider": "deepseek",
        "base_url": "",
        "api_key": "",
        "model": "",
        "providers": {
            "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "label": "DeepSeek 深度求索"},
            "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "label": "OpenAI"},
            "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "label": "通义千问 Qwen"},
            "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k", "label": "Kimi 月之暗面"},
            "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash", "label": "智谱清言 GLM"},
            "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.0-flash", "label": "Google Gemini"},
            "claude": {"base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-20250514", "label": "Anthropic Claude"},
            "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "openrouter/auto", "label": "OpenRouter 聚合"},
            "custom": {"base_url": "", "model": "", "label": "自定义（OpenAI 兼容）"},
        },
    },
    "tts": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%", "volume": "+0%", "pitch": "+0Hz"},
    "location": {"city": "深圳", "latitude": 22.5431, "longitude": 114.0579},
    "smart_home": {"ha_url": "", "ha_token": ""},
    "open_browser_after_start": True,
}


def ensure_dirs():
    for d in (AUDIO_DIR, SCREENSHOT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}
    # 深合并默认值
    cfg = json.loads(json.dumps(DEFAULTS))
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            if k == "llm" and isinstance(v.get("providers"), dict):
                merged = dict(cfg[k].get("providers", {}))
                for pk, pv in v["providers"].items():
                    if isinstance(pv, dict):
                        merged[pk] = {**cfg[k]["providers"].get(pk, {}), **pv}
                v["providers"] = merged
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def save_config(cfg):
    ensure_dirs()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_memory():
    ensure_dirs()
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                mem = json.load(f)
        except Exception:
            mem = {}
    else:
        mem = {}
    mem.setdefault("notes", [])
    mem.setdefault("reminders", [])
    return mem


def save_memory(mem):
    ensure_dirs()
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)


def append_note(text):
    ensure_dirs()
    ts = time_str()
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"- [{ts}] {text}\n")


def read_notes():
    ensure_dirs()
    if not NOTES_FILE.exists():
        return []
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        return [ln for ln in f.read().splitlines() if ln.strip()]


def time_str(fmt="%Y-%m-%d %H:%M:%S"):
    from datetime import datetime
    return datetime.now().strftime(fmt)
