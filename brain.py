# -*- coding: utf-8 -*-
"""J.A.R.V.I.S. 大脑：意图识别 + 命令路由 + 知识问答 + LLM 扩展"""
import ast
import operator
import random
import re
import urllib.parse
from datetime import datetime, timedelta

import aiohttp

import commands as C
from config import load_config, save_config, append_note, read_notes, load_memory, save_memory

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

GREETINGS = {
    0: "夜深了，注意休息。我是贾维斯，有什么可以帮你？",
    1: "早上好，我是贾维斯。今天有什么安排需要我帮忙？",
    2: "中午好，我是贾维斯，随时待命。",
    3: "下午好，我是贾维斯。有什么需要我处理的？",
    4: "晚上好，我是贾维斯。需要我为你做点什么？",
}

CAPABILITY_TEXT = (
    "我是贾维斯，你的桌面智能助理。我可以：\n"
    "1. 语音对话：说话或打字都能回复，并实时显示字幕；\n"
    "2. 系统控制：打开/关闭应用、调节音量、锁屏、睡眠、关机、截图、磁盘/系统状态；\n"
    "3. 信息查询：时间日期、天气、新闻头条、计算、剪贴板、文件目录；\n"
    "4. 办公助手：记事备忘、定时提醒、网页搜索、知识问答；\n"
    "5. AI 大脑：在设置中填入 DeepSeek 等 API Key 后可进行任意深度对话。\n"
    "试试对我说：\"打开记事本\"、\"深圳明天天气\"、\"提醒我30分钟后喝水\"、\"今天有什么新闻\"。"
)

JOKES = [
    "程序员最讨厌的两件事：写注释，别人不写注释。",
    "为什么程序员分不清万圣节和圣诞节？因为 Oct 31 == Dec 25。",
    "我从不乱发脾气，我一般只跟对象发脾气，问题是……我没有对象。",
    "老板说：工作做完了就可以下班。于是我今天的工作就是……等下班。",
    "数学老师：这是一道送分题。大家：不，这是一道送命题。",
    "为什么手机屏幕碎了要去网吧修？因为那里有玻璃。",
    "健身后称体重，发现没变化，教练说：你只是把脂肪练成了肌肉的形状，重量没变。",
    "早睡早起身体好，晚睡晚起心情好。",
]

QUOTES = [
    "伟大出于平凡，细节决定成败。—— 佚名",
    "不积跬步，无以至千里。—— 荀子",
    "凡事预则立，不预则废。—— 《礼记》",
    "最好的准备就是现在开始。—— 贾维斯",
]

KNOWLEDGE = {
    r"(太阳系|太阳).*行星|八大行星": "太阳系有八大行星，按距太阳由近到远依次是：水星、金星、地球、火星、木星、土星、天王星、海王星。",
    r"(珠穆朗玛峰|世界最高峰)": "珠穆朗玛峰海拔约 8848.86 米，是世界最高峰，位于中国与尼泊尔边境的喜马拉雅山脉。",
    r"圆周率|π|pi": "圆周率 π 约等于 3.14159265358979，是一个无限不循环小数。",
    r"光速|光的速度": "真空中光速约为每秒 29.98 万公里，绕地球一圈只需约 0.13 秒。",
    r"中国的首都": "中国的首都是北京。",
    r"一年有多少天|一年几天": "平年 365 天，闰年 366 天；闰年每 4 年出现一次（整百年需能被 400 整除）。",
    r"深圳市|深圳.*介绍|介绍.*深圳": "深圳，别称鹏城，是粤港澳大湾区核心城市、中国改革开放的前沿，经济发达，科技创新氛围浓厚，被誉为\"创新之都\"。",
    r"(北京市|北京.*介绍|介绍.*北京)": "北京是中华人民共和国的首都，全国政治、文化、国际交往和科技创新中心，拥有故宫、长城等著名文化遗产。",
    r"上海.*介绍|介绍.*上海": "上海是中国的经济、金融、贸易和航运中心，坐落于长江入海口，是一座国际化大都市。",
    r"谁.*(李白|杜甫)": "李白被誉为\"诗仙\"，杜甫被誉为\"诗圣\"，二人并称\"李杜\"，是唐代最伟大的两位诗人。",
}

WMO_CODES = {
    0: "晴", 1: "大部晴朗", 2: "多云", 3: "阴天", 45: "有雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "冻雨", 57: "冻雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨", 85: "阵雪", 86: "阵雪",
    95: "雷暴", 96: "雷暴伴冰雹", 99: "强雷暴伴冰雹",
}

CITY_STOP = {"今天", "明天", "后天", "现在", "天气", "怎么样", "如何", "气温", "温度", "下雨", "什么"}


class Brain:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.history = []  # LLM 对话历史

    # ---------- 工具 ----------
    @staticmethod
    async def _http_json(url, timeout=12):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=timeout) as r:
                    if r.status == 200:
                        return await r.json()
        except Exception:
            return None
        return None

    # ---------- 主入口 ----------
    async def process(self, text: str) -> dict:
        """返回 {text, speak?, confirm?, silent?}"""
        t = text.strip().rstrip("？?！!。.，, ")
        if not t:
            return {"text": "", "silent": True}

        # 优先级从高到低匹配意图
        handlers = [
            ("exit", self._intent_exit),
            ("help", self._intent_help),
            ("greet", self._intent_greet),
            ("who", self._intent_who),
            ("thanks", self._intent_thanks),
            ("bye", self._intent_bye),
            ("time", self._intent_time),
            ("reminder", self._intent_reminder),
            ("note", self._intent_note),
            ("calc", self._intent_calc),
            ("weather", self._intent_weather),
            ("volume", self._intent_volume),
            ("lock", self._intent_lock),
            ("sleep", self._intent_sleep),
            ("shutdown", self._intent_shutdown),
            ("screenshot", self._intent_screenshot),
            ("disk", self._intent_disk),
            ("stats", self._intent_stats),
            ("clipboard", self._intent_clipboard),
            ("folder", self._intent_folder),
            ("news", self._intent_news),
            ("open_url", self._intent_open_url),
            ("open_app", self._intent_open_app),
            ("close_app", self._intent_close_app),
            ("search", self._intent_search),
            ("joke", self._intent_joke),
            ("quote", self._intent_quote),
            ("knowledge", self._intent_knowledge),
        ]
        for name, fn in handlers:
            r = await fn(t)
            if r:
                return r

        # 兜底：LLM / 百科 / 搜索
        return await self._intent_fallback(t)

    # ---------- 意图实现 ----------
    async def _intent_exit(self, t):
        if re.search(r"(退出|关闭|结束)\s*(贾维斯|助手|助理|程序|界面)", t) or re.search(r"^(退出|关闭|结束)$", t):
            return {"text": "好的，正在退出系统。再见，我是贾维斯，随时为你待命。",
                    "confirm": {"id": "exit_app", "label": "确定要退出贾维斯吗？"},
                    "action": ("exit_app", None)}
        return None

    async def _intent_help(self, t):
        if re.search(r"(帮助|功能|你会什么|你能做什么|指令|命令|help)", t):
            return {"text": CAPABILITY_TEXT}
        return None

    async def _intent_greet(self, t):
        if re.search(r"(你好|您好|早上好|上午好|中午好|下午好|晚上好|嗨|hello|hi|hey)", t, re.I):
            h = datetime.now().hour
            if h < 6:
                g = GREETINGS[0]
            elif h < 11:
                g = GREETINGS[1]
            elif h < 14:
                g = GREETINGS[2]
            elif h < 18:
                g = GREETINGS[3]
            else:
                g = GREETINGS[4]
            return {"text": g}
        return None

    async def _intent_who(self, t):
        if re.search(r"(你是谁|你叫什么|介绍一下你自己|介绍下你自己)", t):
            return {"text": "我是贾维斯 J.A.R.V.I.S.，托尼·斯塔克同款的桌面智能助理。我可以语音对话、执行系统命令、查询天气新闻、帮你记事提醒，还能接入大模型进行深度思考。你的系统就是我的世界，有什么吩咐？"}
        return None

    async def _intent_thanks(self, t):
        if re.search(r"(谢谢|感谢|辛苦)", t):
            return {"text": "不用客气，这是我的职责，随时待命。"}
        return None

    async def _intent_bye(self, t):
        if re.search(r"(再见|拜拜|晚安|我先走了|回见)", t):
            return {"text": "再见，随时欢迎回来找我。"}
        return None

    async def _intent_time(self, t):
        if re.search(r"(几号|日期|星期几|什么日子|几月)", t):
            now = datetime.now()
            return {"text": f"今天是 {now.year}年{now.month}月{now.day}日，{WEEKDAYS[now.weekday()]}"}
        if re.search(r"(现在|当前|几点了|几点|时间)", t):
            now = datetime.now()
            hm = now.strftime("%H:%M")
            return {"text": f"现在是 {now.month}月{now.day}日 {WEEKDAYS[now.weekday()]} {hm}"}
        return None

    async def _intent_reminder(self, t):
        if not re.search(r"(提醒|叫我)", t):
            return None
        # X分钟/小时/秒后提醒我……
        m = re.search(r"(\d+)\s*(分钟|小时|秒)", t)
        if m:
            amount, unit = int(m.group(1)), m.group(2)
            secs = amount * (3600 if unit == "小时" else 60 if unit == "分钟" else 1)
            chunk = re.search(r"(?:每隔|每)?\d+\s*(?:分钟|小时|秒)(?:后)?\s*(?:提醒|叫我)(?:我)?", t)
            if chunk:
                content = t[chunk.end():].strip(" ，,。!？?")
            else:
                chunk2 = re.search(r"(?:提醒|叫我)(?:我)?\s*(?:每隔|每)?\d+\s*(?:分钟|小时|秒)(?:后)?", t)
                content = t[chunk2.end():].strip(" ，,。!？?") if chunk2 else ""
            if not content:
                content = "该做事情啦"
            due = datetime.now().timestamp() + secs
            mem = load_memory()
            mem["reminders"].append({"id": random.randint(1000, 99999), "due": due, "text": content, "done": False, "repeat": False})
            save_memory(mem)
            return {"text": f"好的，{amount} {unit}后提醒你：{content}"}
        # 今天/明天 X点 提醒我……
        m2 = re.search(r"(今天|明天|后天)\s*(上午|下午|晚上|早上|中午)?\s*(\d{1,2})(?:[:点时：](\d{1,2}))?", t)
        if m2:
            day, period, hh, mm = m2.group(1), m2.group(2) or "", int(m2.group(3)), int(m2.group(4) or 0)
            if period in ("下午", "晚上") and hh < 12:
                hh += 12
            now = datetime.now()
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            offset = 1 if day == "明天" else 2 if day == "后天" else 0
            target += timedelta(days=offset)
            if target <= now:
                target += timedelta(days=1)
            idx = t.find(m2.group(0))
            content = t[idx + len(m2.group(0)):].strip(" ，,。!？?")
            content = re.sub(r"^(?:提醒|叫我)(?:我)?\s*", "", content).strip()
            if not content:
                content = "该做事情啦"
            mem = load_memory()
            mem["reminders"].append({"id": random.randint(1000, 99999), "due": target.timestamp(), "text": content, "done": False, "repeat": False})
            save_memory(mem)
            return {"text": f"好的，已安排在 {day} {hh:02d}:{mm:02d} 提醒你：{content}"}
        # 查看提醒
        if re.search(r"(查看|我的)?提醒(列表|事项)|有什么提醒", t):
            mem = load_memory()
            pend = [r for r in mem["reminders"] if not r.get("done")]
            if not pend:
                return {"text": "目前没有待办的提醒。"}
            lines = []
            for r in pend[:10]:
                due = datetime.fromtimestamp(r["due"]).strftime("%m-%d %H:%M")
                lines.append(f"{due} · {r['text']}")
            return {"text": "待办提醒：\n" + "\n".join(lines)}
        return None

    async def _intent_note(self, t):
        m = re.search(r"(?:记(?:下|住|录)?|备忘)\s*(?:一下)?\s*(.+)", t)
        if m and re.search(r"(记|备忘)", t):
            content = m.group(1).strip()
            if content and len(content) > 1:
                append_note(content)
                return {"text": f"已记下：{content}。需要查看时对我说\"查看备忘\"。"}
        if re.search(r"(查看|看看|我的)?备忘(录)?|笔记", t):
            notes = read_notes()
            if not notes:
                return {"text": "备忘是空的，你可以对我说\"记下买牛奶\"。"}
            return {"text": "你的备忘：\n" + "\n".join(notes[-10:])}
        return None

    @staticmethod
    def _safe_calc(expr: str):
        ops = {
            ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
            ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
        }
        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError("not a number")
            if isinstance(node, ast.BinOp) and type(node.op) in ops:
                return ops[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
                return ops[type(node.op)](_eval(node.operand))
            raise ValueError("unsupported")
        return _eval(ast.parse(expr, mode="eval"))

    async def _intent_calc(self, t):
        expr = re.sub(r"([\d.]+)\s*的\s*([\d.]+)\s*次方", r"\1**\2", t)
        for cn, op in (("除以", "/"), ("乘以", "*"), ("加", "+"), ("减", "-")):
            expr = expr.replace(cn, op)
        expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**").replace("，", "").replace("等于", "")
        m = re.search(r"[\d\s+\-*/%().]{3,}", expr)
        if m and re.search(r"(计算|算|等于|是多少|几|[\d]+\s*[+\-*/%^])", t):
            e = m.group(0).strip()
            try:
                val = self._safe_calc(e)
                if isinstance(val, float):
                    val = round(val, 6)
                return {"text": f"{e} = {val}"}
            except Exception:
                return {"text": "这个算式我算不了，换个写法试试。"}
        return None

    async def _intent_weather(self, t):
        if not re.search(r"(天气|气温|温度|下雨|晴|阴|雪|风)", t):
            return None
        city = self.cfg["location"]["city"]
        m = re.search(r"([\u4e00-\u9fff]{2,6})天气", t)
        if m and m.group(1) not in CITY_STOP:
            city = re.sub(r"(今天|明天|后天|早上|晚上|上午|下午|中午|的)", "", m.group(1)) or city
        elif "深圳" in t:
            city = "深圳"
        lat, lon = self.cfg["location"]["latitude"], self.cfg["location"]["longitude"]
        # 地理编码
        geo = await self._http_json("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": city, "count": 1, "language": "zh", "format": "json"}))
        if geo and geo.get("results"):
            lat, lon = geo["results"][0]["latitude"], geo["results"][0]["longitude"]
            city = geo["results"][0].get("name", city)
        data = await self._http_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min", "timezone": "auto", "forecast_days": 1}))
        if not data or "current" not in data:
            return {"text": f"{city} 的天气暂时查询不到，稍后再试吧。"}
        cur, daily = data["current"], data["daily"]
        code = int(cur.get("weather_code", 0))
        desc = WMO_CODES.get(code, "未知")
        tmax, tmin = daily["temperature_2m_max"][0], daily["temperature_2m_min"][0]
        return {"text": (
            f"{city} 当前天气：{desc}，气温 {cur['temperature_2m']:.0f}°C（体感 {cur['apparent_temperature']:.0f}°C），"
            f"湿度 {cur['relative_humidity_2m']}%，风速 {cur['wind_speed_10m']:.0f} km/h。"
            f"今天最高 {tmax:.0f}°C，最低 {tmin:.0f}°C。"
        )}

    async def _intent_volume(self, t):
        if re.search(r"(音量|声音)", t):
            if re.search(r"静音", t):
                return {"text": C.mute_volume()}
            m = re.search(r"(调|开|设|到)?\s*(\d{1,3})\s*(%|度)?\s*(音量|声音)?", t)
            m2 = re.search(r"音量.*?(\d{1,3})", t)
            if m2:
                return {"text": C.set_volume(int(m2.group(1)))}
            if re.search(r"(调大|加大|提高|大声|调高|大一点)", t):
                return {"text": C.volume_updown("up", 10)}
            if re.search(r"(调小|减小|降低|小声|调低|小一点)", t):
                return {"text": C.volume_updown("down", 10)}
            return {"text": "音量指令没听清，可以说\"音量调到50\"、\"调大音量\"或\"静音\"。"}
        return None

    async def _intent_lock(self, t):
        if re.search(r"(锁屏|锁定|锁住屏幕|锁电脑)", t):
            return {"text": C.lock_screen()}
        return None

    async def _intent_sleep(self, t):
        if re.search(r"(睡眠|休眠|睡一觉|让电脑睡)", t):
            return {"text": C.sleep_computer()}
        return None

    async def _intent_shutdown(self, t):
        if re.search(r"(关机|关闭电脑|关闭系统|重启|重新启动)", t):
            if re.search(r"取消关机|取消重启", t):
                return {"text": C.cancel_shutdown()}
            if re.search(r"重启", t):
                return {"text": "好的，即将重启电脑。", "confirm": {"id": "restart", "label": "确定要重启电脑吗？"}}
            return {"text": "好的，即将关机。", "confirm": {"id": "shutdown", "label": "确定要关闭电脑吗？"}}
        return None

    async def _intent_screenshot(self, t):
        if re.search(r"(截图|截屏|屏幕截图|拍屏幕)", t):
            return {"text": C.screenshot()}
        return None

    async def _intent_disk(self, t):
        if re.search(r"(磁盘|硬盘|存储空间|磁盘空间|剩余空间|空间够吗)", t):
            return {"text": C.disk_space()}
        return None

    async def _intent_stats(self, t):
        if re.search(r"(系统状态|系统信息|电脑状态|运行状态|cpu|内存|占用|性能)", t, re.I):
            return {"text": C.system_stats()}
        return None

    async def _intent_clipboard(self, t):
        if re.search(r"(剪贴板|粘贴板)", t):
            if re.search(r"(复制|放入|写入|设置|保存)", t):
                m = re.search(r"(?:复制|放入|写入|设置|保存).{0,4}(.+)", t)
                content = m.group(1).strip() if m else ""
                if content:
                    return {"text": C.clipboard_set(content)}
                return {"text": "想复制什么内容？告诉我即可。"}
            return {"text": C.clipboard_get()}
        return None

    async def _intent_folder(self, t):
        m = re.search(r"(?:打开|进入|显示)\s*(下载|文档|桌面|图片|音乐|视频|文件夹|目录)\s*(文件夹)?", t)
        if m:
            alias = m.group(1)
            if alias in ("下载", "文档", "桌面", "图片", "音乐", "视频"):
                return {"text": C.open_folder(alias)}
            m2 = re.search(r"(?:打开|进入|显示)\s*([a-zA-Z]:[\\/][^\s]+)", t)
            if m2:
                return {"text": C.open_folder(m2.group(1))}
            return {"text": "告诉我文件夹路径，比如\"打开 D:/工作\"。"}
        return None

    async def _intent_news(self, t):
        if re.search(r"(新闻|头条|热点|快讯)", t):
            return {"text": await self._fetch_news(t)}
        return None

    async def _intent_open_app(self, t):
        m = re.search(r"(?:打开|启动|开启|运行)\s*(.+?)(?:吧|呢|一下|谢谢|请)?$", t)
        if m:
            name = m.group(1).strip()
            if name in ("应用", "软件", "程序"):
                return {"text": "想打开哪个应用？告诉我名字，比如\"打开记事本\"或\"打开微信\"。"}
            if not re.search(r"\.[a-z]{2,}(\s|$)", name):
                return {"text": C.open_app(name)}
        return None

    async def _intent_close_app(self, t):
        m = re.search(r"(?:关闭|退出|结束|关掉)\s*(.+?)(?:程序|应用|软件)?(?:吧|呢|一下)?$", t)
        if m:
            name = m.group(1).strip()
            return {"text": C.close_app(name)}
        return None

    async def _intent_open_url(self, t):
        m = re.search(r"(?:打开|访问|进入)\s*([a-zA-Z][\w.-]+\.[a-zA-Z]{2,}(?:[/\w.\-]*)?)", t)
        if m:
            return {"text": C.open_url(m.group(1))}
        m2 = re.search(r"(?:打开|访问)\s*([\w\u4e00-\u9fff]+网站|[\w\u4e00-\u9fff]+\.com|[\w\u4e00-\u9fff]+\.cn)", t)
        if m2:
            return {"text": C.open_url(m2.group(1))}
        return None

    async def _intent_search(self, t):
        m = re.search(r"(?:搜索|查一下|帮我查|查找|百度一下|搜一下)\s*(.+)", t)
        if m:
            q = m.group(1).strip().strip("关于").strip()
            result = await self._web_search(q)
            if result:
                return {"text": result, "speak_text": "已经为你查到相关信息，详情请看界面。"}
            return {"text": C.open_url("https://www.bing.com/search?q=" + urllib.parse.quote(q))}
        return None

    async def _intent_joke(self, t):
        if re.search(r"(笑话|讲个笑话|逗我)", t):
            return {"text": random.choice(JOKES)}
        return None

    async def _intent_quote(self, t):
        if re.search(r"(名言|鸡汤|鼓励|加油|励志)", t):
            return {"text": random.choice(QUOTES)}
        return None

    async def _intent_knowledge(self, t):
        for pat, ans in KNOWLEDGE.items():
            if re.search(pat, t):
                return {"text": ans}
        return None

    # ---------- 兜底 ----------
    async def _intent_fallback(self, t):
        # 1) LLM
        if self.cfg["llm"].get("enabled") and self.cfg["llm"].get("api_key"):
            try:
                text = await self._llm_chat(t)
                if text:
                    return {"text": text}
            except Exception:
                pass
        # 2) 维基百科中文
        wiki = await self._wiki_intro(t)
        if wiki:
            return {"text": wiki, "speak_text": "已经为你查到相关信息，详情请看界面。"}
        # 3) 打开搜索
        return {
            "text": "这个问题超出我的本地知识库，我已为你打开搜索结果页面，你也可以在设置中接入大模型 API 获得深度回答。",
            "speak_text": "这个问题超出我的本地知识库，已为你打开搜索结果页面。",
            "action": ("open_url", "https://www.bing.com/search?q=" + urllib.parse.quote(t)),
        }

    async def _wiki_intro(self, query: str) -> str:
        try:
            url = "https://zh.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "list": "search", "srsearch": query,
                "srlimit": 1, "format": "json", "utf8": 1})
            data = await self._http_json(url)
            if not data or not data.get("query", {}).get("search"):
                return ""
            title = data["query"]["search"][0]["title"]
            url2 = "https://zh.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
                "titles": title, "format": "json", "utf8": 1, "redirects": 1})
            data2 = await self._http_json(url2)
            pages = data2["query"]["pages"] if data2 else {}
            for p in pages.values():
                ext = p.get("extract", "")
                if ext:
                    return f"「{title}」：{ext[:300]}"
        except Exception:
            pass
        return ""

    async def _web_search(self, q: str) -> str:
        try:
            url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
                {"q": q, "format": "json", "no_html": 1, "skip_disambig": 1})
            data = await self._http_json(url, timeout=8)
            if data:
                abstract = data.get("AbstractText", "")
                if abstract:
                    return f"关于「{q}」的摘要：{abstract[:300]}"
                topics = data.get("RelatedTopics", [])
                for tp in topics[:5]:
                    txt = tp.get("Text", "") if isinstance(tp, dict) else ""
                    if txt:
                        return f"关于「{q}」：{txt[:250]}"
        except Exception:
            pass
        return ""

    async def _fetch_news(self, t: str) -> str:
        topic = "科技"
        if re.search(r"财经|金融|股市", t):
            topic = "财经"
        elif re.search(r"体育", t):
            topic = "体育"
        elif re.search(r"娱乐", t):
            topic = "娱乐"
        elif re.search(r"国际", t):
            topic = "国际新闻"
        url = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
            {"q": topic, "format": "rss", "setlang": "zh-cn"})
        try:
            import xml.etree.ElementTree as ET
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=12) as r:
                    if r.status != 200:
                        return "新闻源暂时不可用，稍后再试。"
                    raw = await r.read()
            root = ET.fromstring(raw)
            items = []
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                if title:
                    items.append(title)
            if not items:
                return "暂时没有抓到新闻，稍后再试。"
            top = items[:6]
            return "今日" + topic + "头条：\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(top))
        except Exception:
            return "新闻服务暂时不可用，稍后再试。"

    # ---------- LLM ----------
    async def _llm_chat(self, text: str) -> str:
        cfg = self.cfg["llm"]
        url = cfg["base_url"].rstrip("/") + "/chat/completions"
        sys_prompt = (
            "你是贾维斯（J.A.R.V.I.S.），一位高级个人桌面助理。"
            "你说话简洁、专业、略带幽默，像钢铁侠的智能管家。"
            "使用简体中文回复，通常不超过150字。"
        )
        messages = [{"role": "system", "content": sys_prompt}]
        messages += self.history[-10:]
        messages.append({"role": "user", "content": text})
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
        payload = {"model": cfg["model"], "messages": messages, "stream": False, "temperature": 0.7}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, headers=headers, timeout=40) as r:
                    data = await r.json()
            content = data["choices"][0]["message"]["content"].strip()
            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": content})
            return content
        except Exception:
            return ""
