"""通知通道：Windows 桌面 toast（winotify）+ Bark iOS 推送（HTTP）。"""
import os
import sys

import requests
from dotenv import load_dotenv
from winotify import Notification, audio

APP_NAME = "VIX 预警"

load_dotenv()
BARK_KEY = os.getenv("BARK_KEY", "").strip()
BARK_SERVER = os.getenv("BARK_SERVER", "https://api.day.app").rstrip("/")
BARK_SOUND_URGENT = os.getenv("BARK_SOUND", "alarm")


def desktop_popup(title: str, message: str, urgent: bool = False) -> None:
    toast = Notification(
        app_id=APP_NAME,
        title=title,
        msg=message,
        duration="long" if urgent else "short",
    )
    if urgent:
        toast.set_audio(audio.LoopingAlarm, loop=True)
    else:
        toast.set_audio(audio.Default, loop=False)
    toast.show()


def bark_push(title: str, message: str, urgent: bool = False, timeout: float = 10) -> None:
    if not BARK_KEY:
        raise RuntimeError("BARK_KEY 未配置；请在项目根目录 .env 中设置")
    payload = {
        "title": title,
        "body": message,
        "group": "VIX预警",
        "level": "critical" if urgent else "active",
        "sound": BARK_SOUND_URGENT if urgent else "default",
    }
    r = requests.post(f"{BARK_SERVER}/{BARK_KEY}", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200:
        raise RuntimeError(f"Bark 推送失败: {data}")


if __name__ == "__main__":
    if "--bark" in sys.argv:
        bark_push("VIX 预警 - Bark 测试", "如果手机响了，Bark 通道就通了。")
        print("Bark 推送已发送（请查看手机）")
    else:
        desktop_popup("VIX 预警 - 测试", "如果你看到这条通知，桌面弹窗正常。")
        print("桌面 toast 已发送（请查看屏幕右下角）")
