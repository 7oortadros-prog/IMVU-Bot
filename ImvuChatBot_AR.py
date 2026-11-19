from __future__ import annotations

import asyncio
import base64
import copy
import json
import re
import sys
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSettings, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QImage,
                           QKeySequence, QPainter, QPainterPath, QPixmap,
                           QPen, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog,
                               QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QSplitter, QTabWidget, QTextEdit,
                               QVBoxLayout, QWidget)

try:
    import requests
except Exception as _e:
    requests = None
    _REQ_ERR = str(_e)

try:
    import websockets
except Exception as _e:
    websockets = None
    _WS_ERR = str(_e)

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
LOG_PATH = APP_DIR / "bot_debug.log"

IMQ_ENDPOINT = "wss://wss-imq.imvu.com/streaming/imvu_pre"
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")

MAX_PACKETS = 500
AVATAR_SIZE = 300

import logging
logging.basicConfig(filename=str(LOG_PATH), level=logging.INFO)


def make_qss() -> str:
    p = {
        "BG":      "#14161f",
        "PANEL":   "#1c1f2b",
        "PANEL2":  "#242838",
        "BORDER":  "#32374a",
        "TEXT":    "#e6e8f0",
        "MUTED":   "#9aa0b5",
        "ACCENT":  "#c93cd0",
        "ACCENT_H":"#a92bb1",
        "ON_ACC":  "#ffffff",
        "DANGER":  "#f4547c",
        "OK":      "#3ddc84",
        "SEL":     "rgba(201,60,208,0.25)",
    }
    qss = """
    * { font-size: 13px; }
    QWidget              { background: $BG; color: $TEXT; }

    QTabWidget::pane     { border: 1px solid $BORDER; border-radius: 10px;
                           top: -1px; background: $BG; }
    QTabBar::tab         { background: transparent; color: $MUTED;
                           padding: 9px 18px; margin-right: 4px;
                           border: 1px solid transparent;
                           border-top-left-radius: 9px;
                           border-top-right-radius: 9px; }
    QTabBar::tab:selected{ background: $PANEL; color: $TEXT;
                           border: 1px solid $BORDER; border-bottom: none; }
    QTabBar::tab:hover   { color: $TEXT; }

    QLineEdit, QTextEdit { background: $PANEL; border: 1px solid $BORDER;
                           border-radius: 9px; padding: 8px 12px;
                           selection-background-color: $SEL; }
    QLineEdit:focus      { border-color: $ACCENT; }
    QTextEdit[mono="1"]  { font-family: 'Consolas','DejaVu Sans Mono',monospace;
                           font-size: 12px; }

    QPushButton          { background: $PANEL; border: 1px solid $BORDER;
                           border-radius: 9px; padding: 8px 16px; color: $TEXT; }
    QPushButton:hover    { background: $PANEL2; border-color: $MUTED; }
    QPushButton:pressed  { background: $BORDER; }
    QPushButton:disabled { color: $MUTED; }
    QPushButton[variant="primary"]       { background: $ACCENT;
                                           border-color: $ACCENT;
                                           color: $ON_ACC; font-weight: 700; }
    QPushButton[variant="primary"]:hover { background: $ACCENT_H; }
    QPushButton[variant="danger"]        { color: $DANGER; }

    QListWidget          { background: $PANEL; border: 1px solid $BORDER;
                           border-radius: 10px; padding: 4px;
                           outline: none; }
    QListWidget::item    { padding: 6px 8px; border-radius: 8px; margin: 1px; }
    QListWidget::item:hover    { background: $PANEL2; }
    QListWidget::item:selected { background: $SEL; color: $TEXT; }

    QHeaderView::section { background: $PANEL2; color: $MUTED; border: none;
                           padding: 6px; font-weight: 700; }
    QLabel#Hint          { color: $MUTED; font-size: 11px; }
    QLabel#Big           { font-size: 15px; font-weight: 800; }

    #Panel               { background: $PANEL; border: 1px solid $BORDER;
                           border-radius: 12px; }
    QStatusBar           { background: $PANEL; border-top: 1px solid $BORDER;
                           color: $MUTED; }
    QMenu                { background: $PANEL; border: 1px solid $BORDER;
                           border-radius: 10px; padding: 6px; }
    QMenu::item          { padding: 7px 26px 7px 14px; border-radius: 6px; }
    QMenu::item:selected { background: $SEL; }

    QScrollBar:vertical  { background: transparent; width: 10px; margin: 2px; }
    QScrollBar::handle:vertical { background: $BORDER; border-radius: 5px;
                                  min-height: 30px; }
    QScrollBar::handle:vertical:hover { background: $MUTED; }
    QScrollBar:horizontal{ background: transparent; height: 10px; margin: 2px; }
    QScrollBar::handle:horizontal { background: $BORDER; border-radius: 5px;
                                    min-width: 30px; }
    QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
    """
    for k, v in sorted(p.items(), key=lambda kv: -len(kv[0])):
        qss = qss.replace(f"${k}", v)
    return qss


def make_app_icon() -> QIcon:
    ico_file = APP_DIR / "imvu.ico"
    if ico_file.exists():
        return QIcon(str(ico_file))
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    pt = QPainter(pm)
    pt.setRenderHint(QPainter.Antialiasing)
    pt.setPen(Qt.NoPen)
    pt.setBrush(QColor("#1c1f2b"))
    pt.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)
    pt.setBrush(QColor("#c93cd0"))
    pt.drawRoundedRect(QRectF(12, 14, 40, 28), 12, 12)
    path = QPainterPath()
    path.moveTo(22, 40)
    path.lineTo(22, 50)
    path.lineTo(32, 40)
    pt.drawPath(path)
    pt.setBrush(QColor("#ffffff"))
    for x in (22, 30, 38):
        pt.drawEllipse(QRectF(x, 25, 5, 5))
    pt.end()
    return QIcon(pm)



B64_RE = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')


def decode_b64_fields(d):
    if isinstance(d, dict):
        for k in list(d.keys()):
            v = d[k]
            if isinstance(v, str):
                if len(v) > 4 and len(v) % 4 == 0 and B64_RE.match(v):
                    try:
                        decoded = base64.b64decode(v).decode('utf-8')
                        try:
                            d[k] = json.loads(decoded)
                        except Exception:
                            d[k] = decoded
                    except Exception:
                        pass
            elif isinstance(v, (dict, list)):
                decode_b64_fields(v)
    elif isinstance(d, list):
        for i in range(len(d)):
            v = d[i]
            if isinstance(v, str):
                if len(v) > 4 and len(v) % 4 == 0 and B64_RE.match(v):
                    try:
                        decoded = base64.b64decode(v).decode('utf-8')
                        try:
                            d[i] = json.loads(decoded)
                        except Exception:
                            d[i] = decoded
                    except Exception:
                        pass
            elif isinstance(v, (dict, list)):
                decode_b64_fields(v)


def parse_room_id(text: str) -> str | None:
    text = (text or "").strip().replace(" ", "")
    m = re.search(r'room-(\d+-\d+)', text)
    if m:
        return m.group(1)
    if re.match(r'^\d+-\d+$', text):
        return text
    return None



class ImvuBot(QObject):
    sig_log = Signal(str, str)
    sig_chat = Signal(str, str)
    sig_auth = Signal(str, str)
    sig_part_clear = Signal()
    sig_part_add = Signal(str, str, str, str)
    sig_part_remove = Signal(str)
    sig_part_update = Signal(str, str, str, str)
    sig_state = Signal(bool, str)

    def __init__(self, config: dict | None = None):
        super().__init__()
        self.config = config
        self.ws = None
        self.op_id = 0
        self.is_connected = False
        self.is_running = True
        self.loop: asyncio.AbstractEventLoop | None = None
        self.target_imq_queue: str | None = None
        self.target_chat_id: str | None = None
        self.user_cache: dict[str, str] = {}

    def get_next_op_id(self) -> int:
        self.op_id += 1
        return self.op_id

    def api_headers(self, extra: dict | None = None) -> dict:
        h = {
            "Cookie": self.config.get(
                "cookies", f"osCsid={self.config.get('osCsid', '')}"),
            "X-Imvu-Application": "next_desktop/1",
            "X-Imvu-Sauce": self.config.get("sauce", ""),
            "User-Agent": self.config.get("user_agent", DEFAULT_UA),
        }
        if extra:
            h.update(extra)
        return h

    def _download_image_b64(self, url: str) -> str:
        if not url or not self.config:
            return ""
        try:
            res = requests.get(url, headers=self.api_headers(
                {"Referer": "https://www.imvu.com/"}),
                allow_redirects=False, timeout=15)
            if res.status_code == 302 and 'Location' in res.headers:
                res2 = requests.get(res.headers['Location'],
                                    headers=self.api_headers(), timeout=15)
                if res2.status_code == 200:
                    return base64.b64encode(res2.content).decode('utf-8')
            elif res.status_code == 200:
                return base64.b64encode(res.content).decode('utf-8')
        except Exception:
            pass
        return ""

    def _fetch_user_info_sync(self, user_id: str) -> str:
        if not self.config:
            return f"ID:{user_id}||"
        headers = self.api_headers(
            {"Accept": "application/json; charset=utf-8"})
        p_url = (f"https://api.imvu.com/chat/chat-{self.target_chat_id}"
                 f"/participants/user-{user_id}")
        try:
            response = requests.get(p_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                denorm = data.get("denormalized", {})
                if p_url in denorm:
                    p_data = denorm[p_url].get("data", {})
                    look_img = p_data.get("look_image", "")
                    u_url = denorm[p_url].get("relations", {}).get("ref", "")
                    if u_url and u_url in denorm:
                        u_data = denorm[u_url].get("data", {})
                        uname = u_data.get("username", f"ID:{user_id}")
                        dname = u_data.get("display_name", "")
                        img_b64 = self._download_image_b64(look_img)
                        return f"{uname}|{dname}|{img_b64}"
        except Exception:
            pass
        u_url_api = f"https://api.imvu.com/user/user-{user_id}"
        try:
            response = requests.get(u_url_api, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                denorm = data.get("denormalized", {})
                if u_url_api in denorm:
                    u_data = denorm[u_url_api].get("data", {})
                    uname = u_data.get("username", f"ID:{user_id}")
                    dname = u_data.get("display_name", "")
                    img_b64 = self._download_image_b64(
                        u_data.get("avatar_image", ""))
                    return f"{uname}|{dname}|{img_b64}"
        except Exception:
            pass
        return f"ID:{user_id}||"

    async def get_user_info(self, user_id: str) -> str:
        if user_id in self.user_cache:
            return self.user_cache[user_id]
        info = await asyncio.to_thread(self._fetch_user_info_sync, user_id)
        self.user_cache[user_id] = info
        return info

    def join_room_api(self) -> str | None:
        if not self.config:
            self.sig_chat.emit("error", "ملف config.json غير موجود. سجّل الدخول أولاً.")
            return None
        self.sig_chat.emit("system", "جارٍ الدخول إلى الغرفة عبر واجهة IMVU…")
        try:
            headers = self.api_headers({
                "Content-Type": "application/json; charset=UTF-8",
                "Accept": "application/json; charset=utf-8",
                "Origin": "https://www.imvu.com",
                "Referer": (f"https://www.imvu.com/next/chat/"
                            f"room-{self.target_chat_id}/")})
            post_url = (f"https://api.imvu.com/chat/chat-{self.target_chat_id}"
                        f"/participants")
            response = requests.post(post_url, headers=headers, json={},
                                     timeout=10)
            if response.status_code not in [200, 201]:
                self.sig_chat.emit("error",
                                   f"فشل الدخول: {response.text[:200]}")
                return None
            get_url = f"https://api.imvu.com/chat/chat-{self.target_chat_id}"
            get_response = requests.get(get_url, headers=headers, timeout=10)
            if get_response.status_code == 200:
                data = get_response.json()
                chat_data = data.get("denormalized", {}).get(get_url, {})
                imq_queue = chat_data.get("data", {}).get("imq_queue")
                if imq_queue:
                    return imq_queue
        except Exception as e:
            self.sig_chat.emit("error", f"حدث خطأ أثناء طلب الاتصال: {e}")
        return None

    def fetch_participants_sync(self) -> list[str]:
        if not self.config:
            return []
        try:
            headers = self.api_headers(
                {"Accept": "application/json; charset=utf-8",
                 "Origin": "https://www.imvu.com"})
            url = (f"https://api.imvu.com/chat/chat-{self.target_chat_id}"
                   f"/participants")
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                denorm = data.get("denormalized", {})
                if url not in denorm:
                    return []
                items = denorm[url].get("data", {}).get("items", [])
                results = []
                for p_url in items:
                    if p_url not in denorm:
                        continue
                    p_data = denorm[p_url].get("data", {})
                    look_img = p_data.get("look_image", "")
                    u_url = denorm[p_url].get("relations", {}).get("ref", "")
                    if u_url not in denorm:
                        continue
                    u_data = denorm[u_url].get("data", {})
                    uname = u_data.get("username", "Unknown")
                    dname = u_data.get("display_name", "")
                    m = re.search(r'user-(\d+)', u_url)
                    if m:
                        uid = m.group(1)
                        img_b64 = self._download_image_b64(look_img)
                        self.user_cache[uid] = f"{uname}|{dname}|{img_b64}"
                        results.append(f"{uid}|{uname}|{dname}|{img_b64}")
                return results
        except Exception:
            pass
        return []

    async def fetch_participants(self):
        self.sig_part_clear.emit()
        for user_str in await asyncio.to_thread(self.fetch_participants_sync):
            uid, uname, dname, img = (user_str.split("|") + ["", "", ""])[:4]
            self.sig_part_add.emit(uid, uname, dname, img)

    async def send_presence_keepalive(self):
        if not self.config:
            return
        headers = self.api_headers({
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json; charset=utf-8",
            "Origin": "https://www.imvu.com",
            "Referer": (f"https://www.imvu.com/next/chat/"
                        f"room-{self.target_chat_id}/")})
        post_url = (f"https://api.imvu.com/chat/chat-{self.target_chat_id}"
                    f"/participants/user-{self.config['user_id']}")
        while self.is_running:
            await asyncio.sleep(10)
            if self.is_connected:
                try:
                    await asyncio.to_thread(requests.post, post_url,
                                            headers=headers, json={}, timeout=10)
                except Exception:
                    pass

    async def send_json(self, data: dict):
        if self.ws:
            try:
                await self.ws.send(json.dumps(data))
                self._log_packet("OUT", data)
            except Exception:
                pass

    def _log_packet(self, prefix: str, data):
        try:
            debug_data = copy.deepcopy(data) if isinstance(data, dict) else {}
            decode_b64_fields(debug_data)
            self.sig_log.emit(prefix, json.dumps(
                debug_data, separators=(',', ':'), ensure_ascii=False))
        except Exception:
            self.sig_log.emit(prefix, str(data))

    async def connect_ws(self) -> bool:
        if not self.config:
            return False
        headers = {"Origin": "https://www.imvu.com",
                   "User-Agent": self.config.get("user_agent", DEFAULT_UA)}
        try:
            try:
                self.ws = await websockets.connect(
                    self.config["imq_endpoint"],
                    additional_headers=headers, ping_interval=None)
            except TypeError:
                self.ws = await websockets.connect(
                    self.config["imq_endpoint"],
                    extra_headers=headers, ping_interval=None)
            return True
        except Exception as e:
            self.sig_chat.emit("error", f"WebSocket: {e}")
            return False

    async def send_connect(self):
        if not self.config:
            return
        encoded = base64.b64encode(
            self.config['osCsid'].encode('utf-8')).decode('utf-8')
        await self.send_json({
            "record": "msg_c2g_connect",
            "user_id": str(self.config["user_id"]),
            "cookie": encoded,
            "metadata": [
                {"record": "metadata", "key": "app", "value": "aW12dV9uZXh0"},
                {"record": "metadata", "key": "platform_type", "value": "Ymln"}],
            "op_id": 0})

    async def open_floodgates(self):
        await self.send_json({"record": "msg_c2g_open_floodgates"})

    async def subscribe_to_chat(self, queue_name: str):
        await self.send_json({
            "record": "msg_c2g_subscribe",
            "queues_with_results": [{"record": "subscription",
                                     "name": queue_name,
                                     "op_id": self.get_next_op_id()}]})
        self.sig_chat.emit("system", f"تم الاشتراك في القناة: {queue_name}")

    async def unsubscribe_from_queue(self, queue_name: str):
        if queue_name:
            await self.send_json({"record": "msg_c2g_unsubscribe",
                                  "queues": [queue_name]})
            self.sig_chat.emit("system", f"تم إلغاء الاشتراك من القناة: {queue_name}")

    async def unsubscribe_chat(self):
        if self.target_imq_queue:
            await self.send_json({
                "record": "msg_c2g_unsubscribe",
                "queues": [self.target_imq_queue,
                           f"inv:/chat/chat-{self.target_chat_id}"]})
            self.sig_part_clear.emit()
            try:
                headers = {"Cookie": self.config.get(
                    "cookies", f"osCsid={self.config['osCsid']}"),
                    "X-Imvu-Sauce": self.config["sauce"]}
                del_url = (f"https://api.imvu.com/chat/chat-"
                           f"{self.target_chat_id}/participants/"
                           f"user-{self.config['user_id']}")
                await asyncio.to_thread(requests.delete, del_url,
                                        headers=headers, timeout=5)
            except Exception:
                pass

    async def send_system_msg(self, text: str):
        chat_id = self.target_imq_queue.split("/")[-1]
        payload = {"chatId": chat_id, "message": text, "to": 0,
                   "userId": self.config["user_id"]}
        payload_b64 = base64.b64encode(json.dumps(
            payload, separators=(',', ':')).encode('utf-8')).decode('utf-8')
        await self.send_json({"record": "msg_c2g_send_message",
                              "queue": self.target_imq_queue,
                              "mount": "messages", "message": payload_b64,
                              "op_id": self.get_next_op_id()})

    async def send_chat_message(self, text: str):
        if not self.is_connected or not self.target_imq_queue:
            self.sig_chat.emit("error", "تعذّر الإرسال: لا يوجد اتصال.")
            return
        await self.send_system_msg(text)
        self.sig_chat.emit("self", text)

    async def spawn_avatar(self):
        await self.send_system_msg("*imvu:isPureUser")
        await asyncio.sleep(0.2)
        await self.send_system_msg(
            f"*msg SeatAssignment 0 {self.config['user_id']} 0 0")

    async def send_ping(self):
        while self.is_running:
            await asyncio.sleep(10)
            if self.is_connected:
                await self.send_json({"record": "msg_c2g_ping"})

    async def spy_room(self, target_chat_id: str):
        self.sig_chat.emit("system",
                           f"محاولة قراءة معرّف قناة الغرفة {target_chat_id}…")
        if not self.is_connected:
            self.sig_chat.emit("error",
                               "البوت غير متصل. ادخل إلى غرفة أولاً.")
            return
        headers = self.api_headers(
            {"Accept": "application/json; charset=utf-8",
             "Origin": "https://www.imvu.com"})
        url = f"https://api.imvu.com/chat/chat-{target_chat_id}"
        res = await asyncio.to_thread(requests.get, url, headers=headers,
                                      timeout=10)
        if res.status_code == 200:
            data = res.json()
            chat_data = data.get("denormalized", {}).get(url, {})
            imq_queue = chat_data.get("data", {}).get("imq_queue")
            if not imq_queue:
                self.sig_chat.emit("error", "تعذّر العثور على قناة الغرفة.")
                return
            self.sig_chat.emit("system",
                               f"تم العثور على القناة: {imq_queue}. جارٍ الاشتراك…")
            await self.subscribe_to_chat(imq_queue)
            await self.subscribe_to_chat(f"inv:/chat/chat-{target_chat_id}")
            chat_id = imq_queue.split("/")[-1]
            payload1 = {"chatId": chat_id, "message": "*imvu:isPureUser",
                        "to": 0, "userId": self.config["user_id"]}
            b64_1 = base64.b64encode(json.dumps(
                payload1, separators=(',', ':')).encode()).decode()
            await self.send_json({"record": "msg_c2g_send_message",
                                  "queue": imq_queue, "mount": "messages",
                                  "message": b64_1,
                                  "op_id": self.get_next_op_id()})
            await asyncio.sleep(0.5)
            payload2 = {"chatId": chat_id,
                        "message": f"*msg SeatAssignment 0 "
                                   f"{self.config['user_id']} 1 0",
                        "to": 0, "userId": self.config["user_id"]}
            b64_2 = base64.b64encode(json.dumps(
                payload2, separators=(',', ':')).encode()).decode()
            await self.send_json({"record": "msg_c2g_send_message",
                                  "queue": imq_queue, "mount": "messages",
                                  "message": b64_2,
                                  "op_id": self.get_next_op_id()})
            self.sig_chat.emit("system",
                               f"تم تفعيل الاستماع للغرفة "
                               f"{target_chat_id}…")
        else:
            self.sig_chat.emit("error", f"خطأ في واجهة IMVU: {res.status_code}")

    async def test_api_request(self, url: str):
        self.sig_chat.emit("system", f"اختبار طلب API: {url}")
        if not self.config:
            self.sig_chat.emit("error", "لا يوجد تسجيل دخول (config.json).")
            return
        headers = self.api_headers(
            {"Accept": "application/json; charset=utf-8",
             "Origin": "https://www.imvu.com"})
        try:
            res = await asyncio.to_thread(requests.get, url,
                                          headers=headers, timeout=10)
            self.sig_chat.emit("system", f"الحالة: {res.status_code}")
            text = res.text
            for i in range(0, min(len(text), 1500), 500):
                self.sig_chat.emit("node", text[i:i + 500])
        except Exception as e:
            self.sig_chat.emit("error", f"خطأ في الطلب: {e}")

    async def message_handler(self, message_str: str):
        try:
            data = json.loads(message_str)
        except Exception:
            return
        self._log_packet("IN", data)
        record = data.get("record")

        if record == "msg_g2c_result":
            if data.get("op_id") == 0 and data.get("status") == 0:
                self.is_connected = True
                self.sig_state.emit(True, str(self.target_chat_id))
                await self.open_floodgates()
                await self.subscribe_to_chat(self.target_imq_queue)
                await self.subscribe_to_chat(
                    f"inv:/chat/chat-{self.target_chat_id}")
                await self.spawn_avatar()
                await self.fetch_participants()
                self.sig_chat.emit("system",
                                   "تم دخول الغرفة بنجاح! في انتظار الرسائل…")

        elif record == "msg_g2c_send_message":
            mount = data.get("mount")
            encoded = data.get("message", "")
            if not encoded:
                return
            try:
                decoded = base64.b64decode(encoded).decode('utf-8')
            except Exception:
                decoded = encoded if isinstance(encoded, str) else json.dumps(encoded)

            if mount == "messages":
                try:
                    payload = json.loads(decoded)
                    sender_id = str(payload.get('userId', 'غير معروف'))
                    text = payload.get('message', '')
                    if not text.startswith("*") and \
                            sender_id != self.config.get("user_id"):
                        info = await self.get_user_info(sender_id)
                        parts = info.split("|")
                        uname = parts[0]
                        dname = parts[1] if len(parts) > 1 else ""
                        who = f"{uname} ({dname})" if dname else uname
                        self.sig_chat.emit("chat", f"{who}|{text}")
                except Exception:
                    pass

            elif mount == "edge:participants":
                try:
                    payload = json.loads(decoded)
                    action = payload.get("action")
                    objects = payload.get("objects", [])
                    if not objects:
                        return
                    m = (re.search(r'participants/user-(\d+)', objects[0])
                         or re.search(r'/user/user-(\d+)', objects[0]))
                    if not m:
                        return
                    user_id = m.group(1)
                    if action == "created":
                        info = await self.get_user_info(user_id)
                        p = info.split("|")
                        uname = p[0]
                        dname = p[1] if len(p) > 1 else ""
                        img = p[2] if len(p) > 2 else ""
                        who = f"{uname} ({dname})" if dname else uname
                        self.sig_chat.emit("enter", f"➡ {who} دخل الغرفة.")
                        self.sig_part_add.emit(user_id, uname, dname, img)
                    elif action == "deleted":
                        info = self.user_cache.get(user_id,
                                                   f"ID:{user_id}||")
                        p = info.split("|")
                        who = p[0]
                        if len(p) > 1 and p[1]:
                            who = f"{p[0]} ({p[1]})"
                        self.sig_chat.emit("leave", f"⬅ {who} غادر الغرفة.")
                        self.sig_part_remove.emit(user_id)
                    elif action == "updated":
                        self.user_cache.pop(user_id, None)
                        info = await self.get_user_info(user_id)
                        p = info.split("|")
                        uname = p[0]
                        dname = p[1] if len(p) > 1 else ""
                        img = p[2] if len(p) > 2 else ""
                        who = f"{uname} ({dname})" if dname else uname
                        self.sig_chat.emit("update", f"🔄 {who} حدّث مظهره.")
                        self.sig_part_update.emit(user_id, uname, dname, img)
                except Exception:
                    pass

            elif mount == "node":
                try:
                    payload = json.loads(decoded) \
                        if not isinstance(decoded, dict) else decoded
                    self.sig_chat.emit("node", str(payload))
                except Exception:
                    pass

    async def listen(self):
        try:
            async for message in self.ws:
                if not self.is_running:
                    break
                await self.message_handler(message)
        except Exception:
            pass

    async def run(self, target_chat_id: str):
        self.target_chat_id = target_chat_id
        self.loop = asyncio.get_running_loop()

        self.target_imq_queue = self.join_room_api()
        if not self.target_imq_queue:
            return False

        while self.is_running:
            try:
                if not await self.connect_ws():
                    break
                await self.send_connect()
                listen_task = asyncio.create_task(self.listen())
                ping_task = asyncio.create_task(self.send_ping())
                keep_task = asyncio.create_task(self.send_presence_keepalive())
                done, pending = await asyncio.wait(
                    {listen_task, ping_task, keep_task},
                    return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
                if not self.is_running:
                    break
                self.is_connected = False
                self.sig_state.emit(False, str(self.target_chat_id))
                self.sig_chat.emit("system", "إعادة الاتصال بعد 5 ثوانٍ…")
                await asyncio.sleep(5)
            except Exception as e:
                self.sig_chat.emit("error", f"خطأ غير متوقع: {e}")
                await asyncio.sleep(5)

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.sig_state.emit(False, str(self.target_chat_id))
        return True



def sync_login(username: str, password: str, twofa: str | None = None):
    url = "https://api.imvu.com/login"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Imvu-Application": "welcome/1",
        "Accept": "application/json; charset=utf-8",
        "Origin": "https://secure.imvu.com",
        "Referer": "https://secure.imvu.com/",
        "User-Agent": DEFAULT_UA,
    }
    payload = {"username": username, "password": password,
               "gdpr_cookie_acceptance": False}
    if twofa:
        payload["2fa_code"] = twofa
        payload["remember_device"] = True

    try:
        session = requests.Session()
        response = session.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()

        if response.status_code == 202 and data.get("error") == "LOGIN-017" \
                and not twofa:
            email = data.get("details", {}).get("email_address", "بريدك الإلكتروني")
            return ("need2fa",
                    f"مطلوب رمز التحقق. تم إرساله إلى: {email}", None)

        if response.status_code in [200, 201]:
            denorm_key = list(data["denormalized"].keys())[0]
            session_data = data["denormalized"][denorm_key]["data"]
            sauce = session_data.get("sauce")
            user_url = session_data.get("user", {}).get("id", "")
            user_id = user_url.split("cid/")[-1] if "cid/" in user_url else None
            osCsid = session.cookies.get("osCsid")
            if sauce and user_id and osCsid:
                cookies = "; ".join(
                    f"{k}={v}" for k, v in session.cookies.items())
                config = {
                    "user_id": user_id, "sauce": sauce, "osCsid": osCsid,
                    "cookies": cookies,
                    "imq_endpoint": IMQ_ENDPOINT,
                    "imq_cookie_b64": base64.b64encode(
                        osCsid.encode()).decode(),
                    "user_queue": f"inv:/user/user-{user_id}",
                    "user_agent": headers["User-Agent"],
                }
                return ("ok",
                        f"تم تسجيل الدخول بنجاح! معرّف المستخدم: {user_id}", config)
            return ("fail", "تعذّر استخراج البيانات من ردّ الخادم.",
                    None)
        return ("fail",
                f"خطأ HTTP {response.status_code}: "
                f"{data.get('message', response.text[:150])}", None)
    except Exception as e:
        return ("fail", f"حدث خطأ أثناء تسجيل الدخول: {e}", None)


def load_config() -> dict | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)



class BotController(QObject):
    sig_chat = Signal(str, str)
    sig_auth = Signal(str, str)
    sig_log = Signal(str, str)
    sig_part_clear = Signal()
    sig_part_add = Signal(str, str, str, str)
    sig_part_remove = Signal(str)
    sig_part_update = Signal(str, str, str, str)
    sig_state = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.bot: ImvuBot | None = None

    def ensure_loop(self):
        if self.loop and self.thread and self.thread.is_alive():
            return
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever,
                                       daemon=True, name="bot-asyncio")
        self.thread.start()

    def _schedule(self, coro):
        self.ensure_loop()
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def _attach(self, bot: ImvuBot):
        bot.sig_chat.connect(self.sig_chat.emit)
        bot.sig_auth.connect(self.sig_auth.emit)
        bot.sig_log.connect(self.sig_log.emit)
        bot.sig_part_clear.connect(self.sig_part_clear.emit)
        bot.sig_part_add.connect(self.sig_part_add.emit)
        bot.sig_part_remove.connect(self.sig_part_remove.emit)
        bot.sig_part_update.connect(self.sig_part_update.emit)
        bot.sig_state.connect(self.sig_state.emit)

    def enter_room(self, room_id: str):
        if self.bot and self.bot.is_running:
            self.sig_chat.emit(
                "error", "اخرج من الغرفة الحالية أولاً (زر «مغادرة»).")
            return
        cfg = load_config()
        if not cfg:
            self.sig_chat.emit(
                "error", "ملف config.json غير موجود. انتقل إلى تبويب «تسجيل الدخول».")
            return
        bot = ImvuBot(cfg)
        self._attach(bot)
        self.bot = bot
        self.sig_chat.emit("system", f"جارٍ الدخول إلى الغرفة: {room_id}…")
        self._schedule(bot.run(room_id))

    def leave_room(self):
        bot = self.bot
        if not bot or not bot.is_running:
            return
        self.sig_chat.emit("system", "جارٍ مغادرة الغرفة…")
        if bot.loop:
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    bot.unsubscribe_chat(), bot.loop)
                fut.result(timeout=3)
            except Exception:
                pass
        bot.is_running = False
        if bot.ws and bot.loop:
            try:
                asyncio.run_coroutine_threadsafe(bot.ws.close(), bot.loop)
            except Exception:
                pass
        self.bot = None
        self.sig_state.emit(False, "")

    def send_message(self, text: str):
        if self.bot and self.bot.is_connected:
            self._schedule(self.bot.send_chat_message(text))
        else:
            self.sig_chat.emit("error", "البوت غير متصل — ادخل إلى غرفة.")

    def subscribe(self, queue: str):
        if self.bot and self.bot.is_connected:
            self._schedule(self.bot.subscribe_to_chat(queue))
        else:
            self.sig_chat.emit("error", "البوت غير متصل. ادخل إلى غرفة أولاً.")

    def unsubscribe(self, queue: str):
        if self.bot and self.bot.is_connected:
            self._schedule(self.bot.unsubscribe_from_queue(queue))
        else:
            self.sig_chat.emit("error", "البوت غير متصل. ادخل إلى غرفة أولاً.")

    def spy_room(self, room_id: str):
        if self.bot and self.bot.is_connected:
            self._schedule(self.bot.spy_room(room_id))
        else:
            self.sig_chat.emit("error", "البوت غير متصل. ادخل إلى غرفة أولاً.")

    def test_api(self, url: str):
        target = self.bot if (self.bot and self.bot.config) else \
            ImvuBot(load_config())
        if target.config:
            self._attach(target)
            self._schedule(target.test_api_request(url))
        else:
            self.sig_chat.emit("error", "لا يوجد تسجيل دخول (config.json).")

    def login(self, username: str, password: str, twofa: str = ""):
        def _worker():
            kind, msg, cfg = sync_login(
                username, password, twofa or None)
            if cfg:
                save_config(cfg)
            self.sig_auth.emit(kind, msg)
        threading.Thread(target=_worker, daemon=True).start()

    def shutdown(self):
        self.leave_room()
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)


CHAT_COLORS = {
    "system": "#9aa0b5",
    "chat":   "#e6e8f0",
    "self":   "#3ddc84",
    "error":  "#f4547c",
    "enter":  "#3ddc84",
    "leave":  "#f0a45c",
    "update": "#d7b15c",
    "node":   "#8f95a8",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("SingleFileApps", "ImvuChatBot")
        self.controller = BotController()
        self.participants: dict[str, QListWidgetItem] = {}

        self.setWindowTitle("بوت دردشة IMVU")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setWindowIcon(make_app_icon())
        self.resize(880, 640)
        self.setMinimumSize(720, 520)
        geo = self.settings.value("geometry")
        if geo is not None:
            try:
                self.restoreGeometry(geo)
            except Exception:
                pass

        self._build_tabs()
        self._build_statusbar()
        self._connect_controller()
        self._build_shortcuts()

        self.leave_btn.setEnabled(False)
        cfg = load_config()
        if cfg:
            self.auth_status.setText(
                f"تم تحميل config.json (معرّف المستخدم: {cfg.get('user_id')}). "
                f"يمكنك الآن دخول غرفة.")
            self.user_label.setText(f"ID: {cfg.get('user_id')}")
        else:
            self.auth_status.setText(
                "لم يتم العثور على config.json — سجّل الدخول من تبويب «تسجيل الدخول».")

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._build_chat_tab()
        self._build_participants_tab()
        self._build_debug_tab()
        self._build_auth_tab()

    def _build_chat_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        room_row = QHBoxLayout()
        room_row.setSpacing(8)
        self.room_input = QLineEdit()
        self.room_input.setLayoutDirection(Qt.LeftToRight)
        self.room_input.setPlaceholderText(
            "أدخل رابط الغرفة أو معرّفها (111111-1111)…")
        last = self.settings.value("last_room", "")
        if last:
            self.room_input.setText(str(last))
        self.room_input.returnPressed.connect(self.enter_room)
        self.enter_btn = QPushButton("دخول")
        self.enter_btn.setProperty("variant", "primary")
        self.enter_btn.clicked.connect(self.enter_room)
        self.leave_btn = QPushButton("مغادرة")
        self.leave_btn.setProperty("variant", "danger")
        self.leave_btn.clicked.connect(self.controller.leave_room)
        room_row.addWidget(self.room_input, 1)
        room_row.addWidget(self.enter_btn)
        room_row.addWidget(self.leave_btn)
        lay.addLayout(room_row)

        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setPlaceholderText(
            "ستظهر رسائل الغرفة هنا…")
        lay.addWidget(self.chat_view, 1)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText(
            "اكتب رسالتك هنا…")
        self.chat_input.returnPressed.connect(self.send_chat)
        lay.addWidget(self.chat_input)

        hint = QLabel("اضغط Enter للإرسال. الرسائل التي تبدأ بـ «*» أوامر نظام خاصة بـ IMVU.")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

        self.tabs.addTab(tab, "💬  الدردشة")

    def _build_participants_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.part_list = QListWidget()
        self.part_list.setIconSize(QSize(AVATAR_SIZE, AVATAR_SIZE))
        self.part_list.setViewMode(QListWidget.IconMode)
        self.part_list.setResizeMode(QListWidget.Adjust)
        self.part_list.setMovement(QListWidget.Static)
        self.part_list.setDragEnabled(False)
        self.part_list.setGridSize(QSize(AVATAR_SIZE + 26, AVATAR_SIZE + 46))
        self.part_list.setUniformItemSizes(True)
        self.part_list.setSpacing(10)
        self.part_list.setWordWrap(True)
        lay.addWidget(self.part_list)
        self.part_hint = QLabel("عدد المشاركين: 0")
        self.part_hint.setObjectName("Hint")
        lay.addWidget(self.part_hint)
        self.tabs.addTab(tab, "👥  المشاركون")

    def _build_debug_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        filter_row = QHBoxLayout()
        self.debug_filter = QLineEdit()
        self.debug_filter.setPlaceholderText(
            "تصفية البيانات (معرّف المستخدم أو نوع الرسالة)…")
        self.debug_filter.textChanged.connect(self._apply_debug_filter)
        clear_btn = QPushButton("مسح السجل")
        clear_btn.clicked.connect(self._clear_debug)
        filter_row.addWidget(self.debug_filter, 1)
        filter_row.addWidget(clear_btn)
        lay.addLayout(filter_row)

        sub_row = QHBoxLayout()
        self.sub_input = QLineEdit()
        self.sub_input.setLayoutDirection(Qt.LeftToRight)
        self.sub_input.setPlaceholderText(
            "القناة (inv:/user/user-123) أو معرّف الغرفة (123-1)…")
        self.sub_input.returnPressed.connect(self.subscribe_clicked)
        b_sub = QPushButton("اشتراك")
        b_sub.clicked.connect(self.subscribe_clicked)
        b_unsub = QPushButton("إلغاء الاشتراك")
        b_unsub.clicked.connect(self.unsubscribe_clicked)
        sub_row.addWidget(self.sub_input, 1)
        sub_row.addWidget(b_sub)
        sub_row.addWidget(b_unsub)
        lay.addLayout(sub_row)

        splitter = QSplitter(Qt.Vertical)
        self.packet_list = QListWidget()
        self.packet_list.itemClicked.connect(self._packet_clicked)
        self.packet_details = QTextEdit()
        self.packet_details.setReadOnly(True)
        self.packet_details.setLayoutDirection(Qt.LeftToRight)
        self.packet_details.setProperty("mono", True)
        self.packet_details.setPlaceholderText(
            "اضغط على سجل لعرض بيانات JSON كاملة…")
        splitter.addWidget(self.packet_list)
        splitter.addWidget(self.packet_details)
        splitter.setSizes([320, 160])
        lay.addWidget(splitter, 1)

        self.tabs.addTab(tab, "🛠  سجل الاتصال")

    def _build_auth_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        panel = QFrame()
        panel.setObjectName("Panel")
        form_wrap = QVBoxLayout(panel)
        form_wrap.setContentsMargins(18, 18, 18, 18)
        form_wrap.setSpacing(10)

        title = QLabel("تسجيل الدخول إلى IMVU")
        title.setObjectName("Big")
        form_wrap.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("اسم المستخدم")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("كلمة المرور")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.twofa_input = QLineEdit()
        self.twofa_input.setPlaceholderText("رمز التحقق الثنائي (اتركه فارغاً إن لم يكن مفعّلاً)")
        form.addRow("اسم المستخدم:", self.login_input)
        form.addRow("كلمة المرور:", self.password_input)
        form.addRow("التحقق الثنائي:", self.twofa_input)
        form_wrap.addLayout(form)

        self.auth_btn = QPushButton("تسجيل الدخول")
        self.auth_btn.setProperty("variant", "primary")
        self.auth_btn.clicked.connect(self.auth_clicked)
        self.password_input.returnPressed.connect(self.auth_clicked)
        self.twofa_input.returnPressed.connect(self.auth_clicked)
        form_wrap.addWidget(self.auth_btn)

        self.auth_status = QLabel("أدخل بيانات تسجيل الدخول")
        self.auth_status.setWordWrap(True)
        form_wrap.addWidget(self.auth_status)
        lay.addWidget(panel)
        lay.addStretch(1)

        cfg_row = QHBoxLayout()
        self.user_label = QLabel("غير مسجّل الدخول")
        self.user_label.setObjectName("Hint")
        b_show_cfg = QPushButton("عرض ملف config.json")
        b_show_cfg.clicked.connect(self._show_config)
        cfg_row.addWidget(self.user_label, 1)
        cfg_row.addWidget(b_show_cfg)
        lay.addLayout(cfg_row)

        self.tabs.addTab(tab, "🔑  تسجيل الدخول")

    def _build_statusbar(self):
        self.lbl_state = QLabel("⚪  لست داخل غرفة")
        self.lbl_user = QLabel("")
        sb = self.statusBar()
        sb.addWidget(self.lbl_state, 0)
        sb.addPermanentWidget(self.lbl_user)

    def _connect_controller(self):
        c = self.controller
        c.sig_chat.connect(self.on_chat)
        c.sig_auth.connect(self.on_auth)
        c.sig_log.connect(self.on_packet)
        c.sig_part_clear.connect(self.on_part_clear)
        c.sig_part_add.connect(self.on_part_add)
        c.sig_part_remove.connect(self.on_part_remove)
        c.sig_part_update.connect(self.on_part_update)
        c.sig_state.connect(self.on_state)

    def _build_shortcuts(self):
        for i in range(4):
            sc = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            idx = i
            sc.activated.connect(lambda: self.tabs.setCurrentIndex(idx))

    def enter_room(self):
        text = self.room_input.text()
        room_id = parse_room_id(text)
        if not room_id:
            self.append_chat("error",
                             "لم أتمكن من التعرّف على المعرّف. أدخل المعرّف (111-111) "
                             "أو رابطاً بهذا الشكل …/room-111-111/.")
            return
        self.settings.setValue("last_room", self.room_input.text().strip())
        self.controller.enter_room(room_id)

    def send_chat(self):
        text = self.chat_input.text().strip()
        if not text:
            return
        low = text.lower()
        if low.startswith(("test_api ", "subscribe ", "unsubscribe ")):
            self.append_chat("system", f"[أمر] {text}")
            if low.startswith("test_api "):
                self.controller.test_api(text[len("test_api "):].strip())
            elif low.startswith("subscribe "):
                self.controller.subscribe(text[len("subscribe "):].strip())
            elif low.startswith("unsubscribe "):
                self.controller.unsubscribe(
                    text[len("unsubscribe "):].strip())
        else:
            self.controller.send_message(text)
        self.chat_input.clear()

    def auth_clicked(self):
        user = self.login_input.text().strip()
        pwd = self.password_input.text().strip()
        twofa = self.twofa_input.text().strip()
        if not user or not pwd:
            self.auth_status.setText("أدخل اسم المستخدم وكلمة المرور")
            return
        if requests is None:
            self.auth_status.setText("مكتبة requests غير مثبّتة.")
            return
        self.auth_status.setText(
            "جارٍ إرسال رمز التحقق…" if twofa else "جارٍ إرسال الطلب…")
        self.controller.login(user, pwd, twofa)

    def subscribe_clicked(self):
        q = self.sub_input.text().strip()
        if q:
            self.controller.subscribe(q)

    def unsubscribe_clicked(self):
        q = self.sub_input.text().strip()
        if q:
            self.controller.unsubscribe(q)

    def spy_clicked(self):
        q = self.sub_input.text().strip()
        rid = parse_room_id(q)
        if rid:
            self.controller.spy_room(rid)
        elif q:
            self.controller.spy_room(q)

    def on_chat(self, kind: str, text: str):
        if kind == "chat" and "|" in text:
            who, msg = text.split("|", 1)
            stamp = datetime.now().strftime("%H:%M")
            self.chat_view.append(
                f"<span style='color:#7d8296;font-size:11px'>{stamp}</span> "
                f"<span style='color:#c93cd0;font-weight:700'>{who}:</span> "
                f"<span style='color:#e6e8f0'>{msg}</span>")
        else:
            self.append_chat(kind, text)

    def append_chat(self, kind: str, text: str):
        color = CHAT_COLORS.get(kind, "#e6e8f0")
        stamp = datetime.now().strftime("%H:%M")
        self.chat_view.append(
            f"<span style='color:#7d8296;font-size:11px'>{stamp}</span> "
            f"<span style='color:{color}'>{text}</span>")

    def on_auth(self, kind: str, message: str):
        if kind == "need2fa":
            self.auth_status.setText(message)
            self.tabs.setCurrentWidget(self.tabs.widget(3))
        elif kind == "ok":
            self.auth_status.setText(message)
            cfg = load_config()
            if cfg:
                self.user_label.setText(f"ID: {cfg.get('user_id')}")
            self.tabs.setCurrentIndex(0)
            self.append_chat("system",
                             "تم تسجيل الدخول بنجاح. أدخل رابط الغرفة واضغط «دخول».")
        else:
            self.auth_status.setText(message)

    def on_packet(self, direction: str, json_str: str):
        filt = self.debug_filter.text().strip().lower()
        if filt and filt not in json_str.lower():
            return
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        short = json_str[:100] + ("…" if len(json_str) > 100 else "")
        item = QListWidgetItem(f"[{ts}] [{direction}] {short}")
        item.setData(Qt.UserRole, json_str)
        item.setData(Qt.UserRole + 1, f"[{ts}] [{direction}] {short}")
        item.setForeground(QColor("#3ddc84" if direction == "IN" else "#f0a45c"))
        self.packet_list.addItem(item)
        while self.packet_list.count() > MAX_PACKETS:
            self.packet_list.takeItem(0)
        self.packet_list.scrollToBottom()

    def on_part_clear(self):
        self.part_list.clear()
        self.participants.clear()
        self._update_part_count()

    def on_part_add(self, uid: str, uname: str, dname: str, img_b64: str):
        if uid in self.participants:
            return
        label = f"{uname} ({dname})" if dname else uname
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, uid)
        item.setTextAlignment(Qt.AlignHCenter)
        item.setToolTip(f"{uname}\nID: {uid}")
        if img_b64:
            pm = self._pixmap_from_b64(img_b64)
            if pm:
                item.setIcon(QIcon(pm))
        self.part_list.addItem(item)
        self.participants[uid] = item
        self._update_part_count()

    def on_part_remove(self, uid: str):
        item = self.participants.pop(uid, None)
        if item:
            row = self.part_list.row(item)
            self.part_list.takeItem(row)
            self._update_part_count()

    def on_part_update(self, uid: str, uname: str, dname: str, img_b64: str):
        item = self.participants.get(uid)
        if not item:
            self.on_part_add(uid, uname, dname, img_b64)
            return
        item.setText(f"{uname} ({dname})" if dname else uname)
        if img_b64:
            pm = self._pixmap_from_b64(img_b64)
            if pm:
                item.setIcon(QIcon(pm))

    def on_state(self, connected: bool, room_id: str):
        self.leave_btn.setEnabled(connected)
        self.enter_btn.setEnabled(not connected)
        if connected:
            self.lbl_state.setText(f"🟢  داخل الغرفة {room_id}")
        else:
            self.lbl_state.setText("⚪  لست داخل غرفة")

    @staticmethod
    def _pixmap_from_b64(img_b64: str) -> QPixmap | None:
        try:
            data = base64.b64decode(img_b64)
            img = QImage.fromData(data)
            if img.isNull():
                return None
            pm = QPixmap.fromImage(img)
            return pm.scaled(AVATAR_SIZE, AVATAR_SIZE,
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except Exception:
            return None

    def _update_part_count(self):
        self.part_hint.setText(f"عدد المشاركين: {self.part_list.count()}")

    def _packet_clicked(self, item: QListWidgetItem):
        raw = item.data(Qt.UserRole)
        try:
            pretty = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
        except Exception:
            pretty = raw
        self.packet_details.setPlainText(pretty)

    def _clear_debug(self):
        self.packet_list.clear()
        self.packet_details.clear()

    def _apply_debug_filter(self):
        filt = self.debug_filter.text().strip().lower()
        keep = []
        for i in range(self.packet_list.count()):
            it = self.packet_list.item(i)
            raw = it.data(Qt.UserRole)
            display = it.data(Qt.UserRole + 1) or raw[:100]
            if not filt or filt in raw.lower():
                keep.append((raw, display, it.foreground()))
        self.packet_list.blockSignals(True)
        self.packet_list.clear()
        for raw, display, color in keep:
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, raw)
            item.setData(Qt.UserRole + 1, display)
            item.setForeground(color)
            self.packet_list.addItem(item)
        self.packet_list.blockSignals(False)

    def _show_config(self):
        cfg = load_config()
        if not cfg:
            QMessageBox.information(self, "config.json", "لم يتم العثور على الملف.")
            return
        QMessageBox.information(
            self, "config.json",
            json.dumps(cfg, indent=2, ensure_ascii=False))

    def closeEvent(self, ev):
        self.settings.setValue("geometry", self.saveGeometry())
        self.controller.shutdown()
        super().closeEvent(ev)



def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)
    app.setApplicationName("بوت دردشة IMVU")
    app.setOrganizationName("SingleFileApps")
    app.setStyleSheet(make_qss())

    missing = []
    if requests is None:
        missing.append(f"requests ({_REQ_ERR})")
    if websockets is None:
        missing.append(f"websockets ({_WS_ERR})")
    if missing:
        QMessageBox.critical(
            None, "مكتبات مطلوبة غير موجودة",
            "ثبّت المكتبات التالية:\n\n"
            "pip install PySide6 requests websockets\n\n"
            + "\n".join(missing))
        return 1

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
