# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 语音合成引擎：edge-tts（免费、微软神经语音）"""
import asyncio
import time

import edge_tts

from config import AUDIO_DIR, ensure_dirs

# 可选中文音色
VOICES = [
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-YunxiNeural",
    "zh-CN-YunyangNeural",
    "zh-CN-liaoning-XiaobeiNeural",
    "zh-CN-shaanxi-XiaoniNeural",
    "zh-TW-HsiaoChenNeural",
    "zh-TW-YunJheNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
]


async def generate_tts(text: str, voice: str, rate: str, volume: str) -> str:
    """生成 mp3 音频，返回可访问的相对 URL；失败返回 None"""
    ensure_dirs()
    if not text:
        return None
    text = text[:500]  # 控制长度，保证响应速度
    fname = f"tts_{int(time.time() * 1000)}.mp3"
    out_path = AUDIO_DIR / fname
    try:
        com = edge_tts.Communicate(text, voice=voice, rate=rate, volume=volume)
        await com.save(str(out_path))
        if out_path.exists() and out_path.stat().st_size > 200:
            return f"/audio/{fname}"
        return None
    except Exception:
        return None


async def warm_up():
    """预热语音合成连接（可选）"""
    try:
        await generate_tts("系统已就绪", "zh-CN-XiaoxiaoNeural", "+0%", "+0%")
    except Exception:
        pass
