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
            # ---------- 订阅（登录即可，无需密钥，经 magpie 中转） ----------
            "claude": {"base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-20250514", "label": "🔥 Claude（订阅）", "group": "订阅"},
            "chatgpt": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "label": "🔥 ChatGPT（订阅）", "group": "订阅"},
            "chatgpt_api": {"base_url": "https://api.openai.com/v1", "model": "gpt-4.1-mini", "label": "🔥 ChatGPT API（订阅）", "group": "订阅"},
            "copilot": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "label": "🔥 Copilot（订阅）", "group": "订阅"},
            "zcode": {"base_url": "", "model": "", "label": "🔥 ZCode（订阅）", "group": "订阅"},
            "workbuddy": {"base_url": "", "model": "", "label": "🔥 WorkBuddy（订阅）", "group": "订阅"},
            "workbuddy_intl": {"base_url": "", "model": "", "label": "🔥 WorkBuddy 国际版（订阅）", "group": "订阅"},
            "gemini_cli": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash", "label": "🔥 Gemini CLI（订阅）", "group": "订阅"},
            "antigravity": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash", "label": "🔥 Antigravity（订阅）", "group": "订阅"},
            # ---------- 供应商（模型厂商 API） ----------
            "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-20250514", "label": "Anthropic Claude", "group": "供应商"},
            "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "label": "OpenAI", "group": "供应商"},
            "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash", "label": "Google Gemini", "group": "供应商"},
            "vertex_ai": {"base_url": "https://aiplatform.googleapis.com/v1beta1/openai", "model": "gemini-2.5-flash", "label": "Vertex AI", "group": "供应商"},
            "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "label": "DeepSeek 深度求索", "group": "供应商"},
            "xai": {"base_url": "https://api.x.ai/v1", "model": "grok-3", "label": "xAI Grok", "group": "供应商"},
            "kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-k2", "label": "Kimi 月之暗面", "group": "供应商"},
            "kimi_code": {"base_url": "https://api.moonshot.cn/v1", "model": "kimi-k2-turbo", "label": "Kimi Code", "group": "供应商"},
            "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4.5", "label": "智谱清言 GLM", "group": "供应商"},
            "z_ai": {"base_url": "https://api.z.ai/api/paas/v4", "model": "glm-4.5", "label": "Z.ai（GLM 国际）", "group": "供应商"},
            "minimax": {"base_url": "https://api.minimax.chat/v1", "model": "MiniMax-M1", "label": "MiniMax", "group": "供应商"},
            "stepfun": {"base_url": "https://api.stepfun.com/v1", "model": "step-2-16k", "label": "StepFun 阶跃星辰", "group": "供应商"},
            "mimo": {"base_url": "https://api.mimo.ai/v1", "model": "MiMo-7B-RL", "label": "Xiaomi MiMo", "group": "供应商"},
            "qianfan": {"base_url": "https://qianfan.baidubce.com/v2", "model": "ernie-4.5-turbo-128k", "label": "Baidu Qianfan 千帆", "group": "供应商"},
            "tencent": {"base_url": "https://api.hunyuan.cloud.tencent.com/v1", "model": "hunyuan-turbo-latest", "label": "Tencent Cloud 混元", "group": "供应商"},
            "huawei": {"base_url": "https://api.openai.huaweicloud.com/v1", "model": "", "label": "Huawei Cloud 盘古", "group": "供应商"},
            "ark": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-1-5-pro-32k", "label": "Volcengine Ark 豆包", "group": "供应商"},
            "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus", "label": "Qwen 通义千问", "group": "供应商"},
            "qwen_plan": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus-plan", "label": "Qwen Plan", "group": "供应商"},
            "bailian_plan": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-max-plan", "label": "Bailian Plan 百炼", "group": "供应商"},
            "mistral": {"base_url": "https://api.mistral.ai/v1", "model": "mistral-large-latest", "label": "Mistral", "group": "供应商"},
            "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile", "label": "Groq", "group": "供应商"},
            "bedrock": {"base_url": "https://bedrock.us-east-1.amazonaws.com", "model": "", "label": "Amazon Bedrock", "group": "供应商"},
            "bedrock_mantle": {"base_url": "https://bedrock.us-east-1.amazonaws.com", "model": "", "label": "Bedrock Mantle", "group": "供应商"},
            "azure_openai": {"base_url": "https://YOUR-RESOURCE.openai.azure.com/v1", "model": "gpt-4o", "label": "Azure OpenAI", "group": "供应商"},
            "ollama_cloud": {"base_url": "https://api.ollama.com/v1", "model": "llama3.3", "label": "Ollama Cloud", "group": "供应商"},
            "nous": {"base_url": "https://api.nousresearch.com/v1", "model": "hermes-4", "label": "Nous Portal", "group": "供应商"},
            "type_safe_jev": {"base_url": "", "model": "", "label": "TypeSafe Jev", "group": "供应商"},
            "bailian_decision": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-max-decision", "label": "Bailian Decision", "group": "供应商"},
            "qwen_decision": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-max-decision", "label": "Qwen Decision", "group": "供应商"},
            # ---------- 中转（一个密钥，多家模型） ----------
            "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "openrouter/auto", "label": "OpenRouter 聚合", "group": "中转"},
            "opencode_go": {"base_url": "", "model": "", "label": "OpenCode Go", "group": "中转"},
            "clinepass": {"base_url": "", "model": "", "label": "ClinePass", "group": "中转"},
            "opencode_zen": {"base_url": "", "model": "", "label": "OpenCode Zen", "group": "中转"},
            "kilo_gateway": {"base_url": "", "model": "", "label": "Kilo Gateway", "group": "中转"},
            "command_code": {"base_url": "", "model": "", "label": "Command Code", "group": "中转"},
            "together": {"base_url": "https://api.together.xyz/v1", "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "label": "Together AI", "group": "中转"},
            "fireworks": {"base_url": "https://api.fireworks.ai/inference/v1", "model": "accounts/fireworks/models/llama-v3p1-70b-instruct", "label": "Fireworks", "group": "中转"},
            "siliconflow": {"base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-ai/DeepSeek-V3", "label": "SiliconFlow 硅基流动", "group": "中转"},
            "nvidia_nim": {"base_url": "https://integrate.api.nvidia.com/v1", "model": "meta/llama-3.1-8b-instruct", "label": "NVIDIA NIM", "group": "中转"},
            "modelscope": {"base_url": "https://api.modelscope.cn/v1", "model": "Qwen/Qwen2.5-72B-Instruct", "label": "ModelScope 魔搭", "group": "中转"},
            "aihubmix": {"base_url": "https://api.aihubmix.com/v1", "model": "gpt-4o-mini", "label": "AiHubMix", "group": "中转"},
            "custom": {"base_url": "", "model": "", "label": "自定义（OpenAI 兼容）", "group": "其他"},
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
