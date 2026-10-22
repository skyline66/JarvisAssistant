# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 语音合成引擎：edge-tts（免费、微软神经语音）
支持：男女声、英文、多语言及自定义音色；语速 / 音量 / 音调调节。
"""
import asyncio
import time

import edge_tts

from config import AUDIO_DIR, ensure_dirs

# 音色库：分组（女声 / 男声 / 英文 / 多语言）
VOICE_GROUPS = [
    {
        "group": "女声（中文）",
        "voices": [
            ("zh-CN-XiaoxiaoNeural", "晓晓 · 温柔自然（推荐）"),
            ("zh-CN-XiaoyiNeural", "晓伊 · 活泼亲切"),
            ("zh-CN-XiaohanNeural", "晓涵 · 甜美悦耳"),
            ("zh-CN-XiaomengNeural", "晓萌 · 卡通可爱"),
            ("zh-CN-XiaomoNeural", "晓墨 · 沉稳知性"),
            ("zh-CN-XiaoruiNeural", "晓睿 · 干练成熟"),
            ("zh-CN-XiaoshuangNeural", "晓双 · 明亮清透"),
            ("zh-CN-XiaoxuanNeural", "晓萱 · 温柔治愈"),
            ("zh-CN-XiaoyouNeural", "晓悠 · 青春少女"),
            ("zh-CN-XiaozhenNeural", "晓甄 · 知性大方"),
            ("zh-CN-liaoning-XiaobeiNeural", "小北 · 东北腔"),
            ("zh-CN-shaanxi-XiaoniNeural", "小妮 · 陕西腔"),
            ("zh-TW-HsiaoChenNeural", "曉臻 · 台湾女声"),
            ("zh-TW-HsiaoYuNeural", "曉雨 · 台湾女声"),
        ],
    },
    {
        "group": "男声（中文）",
        "voices": [
            ("zh-CN-YunxiNeural", "云希 · 阳光少年（推荐）"),
            ("zh-CN-YunyangNeural", "云扬 · 专业播音"),
            ("zh-CN-YunfengNeural", "云枫 · 磁性低沉"),
            ("zh-CN-YunjianNeural", "云健 · 浑厚有力"),
            ("zh-CN-YunhaoNeural", "云皓 · 温暖男声"),
            ("zh-CN-YunxiaNeural", "云夏 · 年轻活力"),
            ("zh-TW-YunJheNeural", "雲哲 · 台湾男声"),
            ("zh-HK-HiuMaanNeural", "曉滿 · 粤语男声"),
            ("zh-HK-WanLungNeural", "雲龍 · 粤语男声"),
        ],
    },
    {
        "group": "英文",
        "voices": [
            ("en-US-AriaNeural", "Aria · 美式女声（推荐）"),
            ("en-US-JennyNeural", "Jenny · 美式女声"),
            ("en-US-MichelleNeural", "Michelle · 美式女声"),
            ("en-US-GuyNeural", "Guy · 美式男声"),
            ("en-US-ChristopherNeural", "Christopher · 美式男声"),
            ("en-US-EricNeural", "Eric · 美式男声"),
            ("en-GB-SoniaNeural", "Sonia · 英式女声"),
            ("en-GB-RyanNeural", "Ryan · 英式男声"),
        ],
    },
    {
        "group": "多语言",
        "voices": [
            ("ja-JP-NanamiNeural", "七海 · 日文女声"),
            ("ja-JP-KeitaNeural", "啓太 · 日文男声"),
            ("ko-KR-SunHiNeural", "선히 · 韩文女声"),
            ("ko-KR-InJoonNeural", "인준 · 韩文男声"),
            ("fr-FR-DeniseNeural", "Denise · 法文女声"),
            ("de-DE-KatjaNeural", "Katja · 德文女声"),
            ("es-ES-ElviraNeural", "Elvira · 西班牙文女声"),
            ("ru-RU-SvetlanaNeural", "Светлана · 俄文女声"),
        ],
    },
]

# 平铺列表（兼容旧接口）
VOICES = [v[0] for g in VOICE_GROUPS for v in g["voices"]]

# 音色显示名映射
VOICE_NAMES = {v[0]: v[1] for g in VOICE_GROUPS for v in g["voices"]}


def get_voice_catalog() -> list:
    """返回 {group, voices:[{name,label}]} 结构，供设置界面分组展示"""
    return [
        {"group": g["group"], "voices": [{"name": v[0], "label": v[1]} for v in g["voices"]]}
        for g in VOICE_GROUPS
    ]


async def generate_tts(text: str, voice: str, rate: str = "+0%",
                       volume: str = "+0%", pitch: str = "+0Hz") -> str:
    """生成 mp3 音频，返回可访问的相对 URL；失败返回 None"""
    ensure_dirs()
    if not text:
        return None
    text = text[:500]  # 控制长度，保证响应速度
    fname = f"tts_{int(time.time() * 1000)}.mp3"
    out_path = AUDIO_DIR / fname
    try:
        com = edge_tts.Communicate(text, voice=voice, rate=rate,
                                   volume=volume, pitch=pitch)
        await com.save(str(out_path))
        if out_path.exists() and out_path.stat().st_size > 200:
            return f"/audio/{fname}"
        return None
    except Exception:
        return None


async def preview_tts(voice: str, rate: str = "+0%", volume: str = "+0%",
                      pitch: str = "+0Hz", text: str = "你好，我是贾维斯，这是我当前的声音。") -> str:
    """试听：生成一小段音频返回 URL"""
    return await generate_tts(text, voice, rate, volume, pitch)


async def warm_up():
    """预热语音合成连接（可选）"""
    try:
        await generate_tts("系统已就绪", "zh-CN-XiaoxiaoNeural", "+0%", "+0%")
    except Exception:
        pass
