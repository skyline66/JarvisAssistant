# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 智能家居中枢
开箱即用的本地虚拟设备（灯/空调/窗帘/电视/风扇/加湿器/扫地机），
支持语音/文字指令控制与语音回复；可选接入 Home Assistant（REST API）。
设备状态持久化在 memory.json 的 smart_home 字段。
"""
import re

import aiohttp

from config import load_memory, save_memory

# 预设设备（type 决定控制参数与图标）
DEFAULT_DEVICES = [
    {"id": "living_light", "name": "客厅灯", "room": "客厅", "type": "light", "state": False, "brightness": 80},
    {"id": "bedroom_light", "name": "卧室灯", "room": "卧室", "type": "light", "state": False, "brightness": 60},
    {"id": "aircon", "name": "空调", "room": "客厅", "type": "ac", "state": False, "temp": 26},
    {"id": "curtain", "name": "窗帘", "room": "客厅", "type": "curtain", "state": False},
    {"id": "tv", "name": "电视", "room": "客厅", "type": "tv", "state": False, "volume": 30},
    {"id": "fan", "name": "风扇", "room": "卧室", "type": "fan", "state": False, "speed": 2},
    {"id": "humidifier", "name": "加湿器", "room": "卧室", "type": "humidifier", "state": False},
    {"id": "robot", "name": "扫地机器人", "room": "全屋", "type": "robot", "state": False},
]

# 设备别名 → id
ALIASES = {
    "客厅灯": "living_light", "客厅的灯": "living_light", "客厅照明": "living_light",
    "卧室灯": "bedroom_light", "卧室的灯": "bedroom_light", "床头灯": "bedroom_light",
    "空调": "aircon", "冷气": "aircon", "暖气": "aircon", "中央空调": "aircon",
    "窗帘": "curtain", "窗帘机": "curtain",
    "电视": "tv", "电视机": "tv", "投影": "tv",
    "风扇": "fan", "电扇": "fan",
    "加湿器": "humidifier",
    "扫地机器人": "robot", "扫地机": "robot", "机器人": "robot",
}

# 动作词
OPEN_WORDS = ("开", "打开", "开启", "启动", "亮")
CLOSE_WORDS = ("关", "关闭", "关上", "熄灭", "灭")
QUERY_WORDS = ("开没开", "开了吗", "状态", "什么情况", "怎么样", "关了吗", "关没关")
NUM_RE = re.compile(r"(-?\d+(?:\.\d+)?)")


class SmartHome:
    def __init__(self, cfg):
        self.cfg = cfg
        self.devices = self._load()

    # ---------- 状态持久化 ----------
    def _load(self):
        mem = load_memory()
        saved = mem.get("smart_home")
        if isinstance(saved, list) and saved:
            # 以预设为骨架，保留已存状态
            by_id = {d["id"]: d for d in saved}
            merged = []
            for d in DEFAULT_DEVICES:
                s = by_id.get(d["id"], {})
                nd = dict(d)
                for k in ("state", "brightness", "temp", "volume", "speed"):
                    if k in s:
                        nd[k] = s[k]
                merged.append(nd)
            return merged
        return [dict(d) for d in DEFAULT_DEVICES]

    def _save(self):
        mem = load_memory()
        mem["smart_home"] = self.devices
        save_memory(mem)

    def get_devices(self):
        return [dict(d) for d in self.devices]

    def get_device(self, device_id):
        for d in self.devices:
            if d["id"] == device_id:
                return d
        return None

    # ---------- 指令解析 ----------
    def parse(self, text: str):
        """返回 (device, action, value) 或 None；action: on/off/set/query"""
        text = text.lower()
        dev = None
        for alias, did in ALIASES.items():
            if alias in text:
                dev = self.get_device(did)
                if dev:
                    break
        if not dev:
            return None
        value = None
        # 数值参数（温度/亮度/音量/风速）
        num = NUM_RE.search(text)
        if num:
            value = int(float(num.group(1)))
        # 动作判定
        if any(w in text for w in QUERY_WORDS):
            return dev, "query", None
        if "温度" in text or "调到" in text or "设定" in text or ("度" in text and num):
            return dev, "set", value
        if "亮一点" in text or "调亮" in text:
            return dev, "dim", min((dev.get("brightness", 80) + 20), 100)
        if "暗一点" in text or "调暗" in text:
            return dev, "dim", max((dev.get("brightness", 80) - 20), 10)
        if any(w in text for w in OPEN_WORDS):
            return dev, "on", value
        if any(w in text for w in CLOSE_WORDS):
            return dev, "off", value
        return dev, "query", None

    # ---------- 执行 ----------
    async def execute(self, text: str) -> str:
        """返回语音/文字回复；未识别返回 None（交由其他意图）"""
        r = self.parse(text)
        if not r:
            return None
        dev, action, value = r
        if action == "query":
            return self._query_text(dev)
        # Home Assistant 桥接（可选）
        ha = self.cfg.get("smart_home", {})
        if ha.get("ha_url") and ha.get("ha_token"):
            ok = await self._ha_forward(dev, action, value)
            if ok:
                if action in ("on", "off"):
                    dev["state"] = (action == "on")
                elif action == "set":
                    if dev["type"] == "ac" and value:
                        dev["temp"] = value
                    elif dev["type"] in ("light", "tv") and value:
                        dev[("brightness" if dev["type"] == "light" else "volume")] = value
                elif action == "dim":
                    dev["brightness"] = value
                self._save()
                return self._confirm_text(dev, action, value)
        # 本地模拟
        if action == "on":
            dev["state"] = True
        elif action == "off":
            dev["state"] = False
        elif action == "set":
            if dev["type"] == "ac" and value:
                dev["temp"] = max(16, min(30, value))
            elif dev["type"] == "light" and value:
                dev["brightness"] = max(1, min(100, value))
            elif dev["type"] == "tv" and value:
                dev["volume"] = max(0, min(100, value))
            elif dev["type"] == "fan" and value:
                dev["speed"] = max(1, min(5, value))
        elif action == "dim":
            dev["brightness"] = max(1, min(100, value or 50))
        self._save()
        return self._confirm_text(dev, action, value)

    async def set_device(self, device_id: str, payload: dict) -> str:
        """面板直控：{on: bool, temp/brightness/volume/speed: int}"""
        dev = self.get_device(device_id)
        if not dev:
            return "没有找到这个设备。"
        action = "query"
        if "on" in payload:
            dev["state"] = bool(payload["on"])
            action = "on" if dev["state"] else "off"
        for k in ("temp", "brightness", "volume", "speed"):
            if k in payload and payload[k] is not None:
                dev[k] = max(0, min(100, int(payload[k])))
                if action == "query":
                    action = "set"
        self._save()
        return self._confirm_text(dev, action, None)

    # ---------- 文案 ----------
    def _confirm_text(self, dev, action, value):
        name = dev["name"]
        if action == "on":
            return f"已开启{name}。欢迎回到你的大宅，先生。"
        if action == "off":
            return f"已关闭{name}。"
        if action == "dim":
            return f"{name}亮度已调整为 {value}%。"
        if action == "set":
            if dev["type"] == "ac":
                return f"{name}已设定为 {dev['temp']} 度。"
            if dev["type"] == "light":
                return f"{name}亮度已设定为 {dev['brightness']}%。"
            if dev["type"] == "tv":
                return f"电视音量已调整为 {dev['volume']}。"
            if dev["type"] == "fan":
                return f"风扇风速已调到 {dev['speed']} 档。"
            return f"{name}已设置完成。"
        return f"{name}已就绪。"

    def _query_text(self, dev):
        name = dev["name"]
        st = "开启" if dev["state"] else "关闭"
        extra = ""
        if dev["type"] == "ac" and dev["state"]:
            extra = f"，温度 {dev['temp']} 度"
        elif dev["type"] == "light" and dev["state"]:
            extra = f"，亮度 {dev['brightness']}%"
        elif dev["type"] == "tv" and dev["state"]:
            extra = f"，音量 {dev['volume']}"
        elif dev["type"] == "fan" and dev["state"]:
            extra = f"，风速 {dev['speed']} 档"
        return f"{name}目前处于{st}状态{extra}。"

    # ---------- Home Assistant 桥接 ----------
    async def _ha_forward(self, dev, action, value) -> bool:
        ha = self.cfg.get("smart_home", {})
        url = ha["ha_url"].rstrip("/")
        headers = {"Authorization": "Bearer " + ha["ha_token"],
                   "Content-Type": "application/json"}
        entity = dev.get("entity_id", "")
        if not entity:
            return False
        mapping = {
            "light": ("light.turn_on", "light.turn_off", "light.turn_on"),
            "tv": ("media_player.turn_on", "media_player.turn_off", "media_player.volume_set"),
            "ac": ("climate.turn_on", "climate.turn_off", "climate.set_temperature"),
            "fan": ("fan.turn_on", "fan.turn_off", "fan.set_percentage"),
        }
        m = mapping.get(dev["type"])
        if not m:
            return False
        try:
            if action == "on":
                svc = m[0]
            elif action == "off":
                svc = m[1]
            elif action == "set" and value:
                svc = m[2]
                if dev["type"] == "light":
                    await self._ha_call(url, headers, "light.turn_on", {"entity_id": entity, "brightness_pct": value})
                    return True
                if dev["type"] == "tv":
                    await self._ha_call(url, headers, "media_player.volume_set", {"entity_id": entity, "volume_level": value / 100})
                    return True
                if dev["type"] == "fan":
                    await self._ha_call(url, headers, "fan.set_percentage", {"entity_id": entity, "percentage": value * 20})
                    return True
            else:
                return True  # 仅查询不转发
            data = {"entity_id": entity}
            if action == "on":
                data = {"entity_id": entity}
            if action == "set" and dev["type"] == "ac" and value:
                data["temperature"] = value
            return await self._ha_call(url, headers, svc, data)
        except Exception:
            return False

    async def _ha_call(self, url, headers, service, data) -> bool:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{url}/api/services/{service}", json=data,
                                  headers=headers, timeout=6) as r:
                    return 200 <= r.status < 300
        except Exception:
            return False


# 供语音/文字指令解析用的入口关键词（用于意图预筛）
SMART_KEYWORDS = ("灯", "空调", "冷气", "窗帘", "电视", "风扇", "加湿器", "扫地", "照明", "床头")
