import json
import os
import random
import socket
import string
import sys
import threading
import time


def get_base_dir():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.abspath(".")


def load_env_file():
    env_path = os.path.join(get_base_dir(), ".env")
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.abspath("."), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


load_env_file()

HOST = os.getenv("RELAY_HOST", "0.0.0.0")
PORT = int(os.getenv("RELAY_PORT", "5555"))
USERS_DB_FILE = os.path.join(os.path.abspath("."), "users.json")


def generate_friend_code(existing_codes):
    while True:
        digits = "".join(random.choices(string.digits, k=4))
        letters = "".join(random.choices(string.ascii_uppercase, k=2))
        code = f"BR-{digits}{letters}"
        if code not in existing_codes:
            return code


class RelayServer:
    def __init__(self, host=HOST, port=PORT, db_file=USERS_DB_FILE):
        self.host = host
        self.port = port
        self.db_file = db_file
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.lock = threading.Lock()
        self.users_by_code = {}
        self.clients_by_conn = {}
        self.matches = {}
        self.next_match_id = 1
        self.load_users_db()

    def load_users_db(self):
        if not os.path.exists(self.db_file):
            return
        try:
            with open(self.db_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return
            for code, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                self.users_by_code[code] = {
                    "code": code,
                    "name": (entry.get("name") or "Player")[:16],
                    "conn": None,
                    "online": False,
                    "friends": set(entry.get("friends") or []),
                    "pending_invites": [],
                    "match_id": None,
                    "player_slot": None,
                }
        except (OSError, json.JSONDecodeError):
            pass

    def save_users_db_unlocked(self):
        serializable = {}
        for code, user in self.users_by_code.items():
            serializable[code] = {
                "name": user["name"],
                "friends": sorted(list(user["friends"])),
            }
        try:
            with open(self.db_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
        except OSError:
            pass

    def send_msg(self, conn, payload):
        try:
            raw = (json.dumps(payload) + "\n").encode("utf-8")
            conn.sendall(raw)
        except OSError:
            pass

    def broadcast_friends_update(self, user):
        with self.lock:
            friend_list = []
            for f_code in user["friends"]:
                f_user = self.users_by_code.get(f_code)
                if f_user:
                    friend_list.append({
                        "code": f_user["code"],
                        "name": f_user["name"],
                        "online": f_user["online"],
                        "in_match": f_user["match_id"] is not None,
                    })
            conn = user["conn"]
            is_online = user["online"]
        if conn and is_online:
            self.send_msg(conn, {"type": "friends_list", "friends": friend_list})

    def notify_all_friends(self, user):
        with self.lock:
            friend_codes = list(user["friends"])
        for f_code in friend_codes:
            f_user = self.users_by_code.get(f_code)
            if f_user and f_user["online"]:
                self.broadcast_friends_update(f_user)

    def handle_client(self, conn, addr):
        buf = ""
        current_user = None
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    mtype = msg.get("type")

                    if mtype == "register":
                        name = (msg.get("name") or "Player").strip()[:16] or "Player"
                        requested_code = (msg.get("code") or "").strip().upper()
                        with self.lock:
                            if requested_code and requested_code in self.users_by_code:
                                current_user = self.users_by_code[requested_code]
                                current_user["name"] = name
                                current_user["conn"] = conn
                                current_user["online"] = True
                            else:
                                code = requested_code if requested_code else generate_friend_code(self.users_by_code)
                                current_user = {
                                    "code": code,
                                    "name": name,
                                    "conn": conn,
                                    "online": True,
                                    "friends": set(),
                                    "pending_invites": [],
                                    "match_id": None,
                                    "player_slot": None,
                                }
                                self.users_by_code[code] = current_user
                            self.clients_by_conn[conn] = current_user
                            self.save_users_db_unlocked()

                        self.send_msg(conn, {
                            "type": "registered",
                            "code": current_user["code"],
                            "name": current_user["name"],
                        })
                        self.broadcast_friends_update(current_user)
                        self.notify_all_friends(current_user)

                    elif mtype == "set_name" and current_user:
                        new_name = (msg.get("name") or current_user["name"]).strip()[:16]
                        if new_name:
                            with self.lock:
                                current_user["name"] = new_name
                                self.save_users_db_unlocked()
                            self.send_msg(conn, {"type": "name_updated", "name": new_name})
                            self.notify_all_friends(current_user)

                    elif mtype == "add_friend" and current_user:
                        target_code = (msg.get("friend_code") or "").strip().upper()
                        with self.lock:
                            if target_code == current_user["code"]:
                                self.send_msg(conn, {"type": "status_msg", "text": "You cannot add your own code."})
                            elif target_code not in self.users_by_code:
                                self.send_msg(conn, {"type": "status_msg", "text": f"Friend code '{target_code}' not found."})
                            else:
                                current_user["friends"].add(target_code)
                                target_user = self.users_by_code[target_code]
                                target_user["friends"].add(current_user["code"])
                                self.save_users_db_unlocked()
                                self.send_msg(conn, {"type": "status_msg", "text": f"Added {target_user['name']} ({target_code})!"})
                        self.broadcast_friends_update(current_user)
                        target_user = self.users_by_code.get(target_code)
                        if target_user and target_user["online"]:
                            self.broadcast_friends_update(target_user)

                    elif mtype == "refresh_friends" and current_user:
                        self.broadcast_friends_update(current_user)

                    elif mtype == "send_invite" and current_user:
                        target_code = (msg.get("target_code") or "").strip().upper()
                        with self.lock:
                            target_user = self.users_by_code.get(target_code)
                            if not target_user or not target_user["online"] or not target_user["conn"]:
                                self.send_msg(conn, {"type": "status_msg", "text": "Friend is currently offline."})
                            else:
                                invite = {
                                    "from_code": current_user["code"],
                                    "from_name": current_user["name"],
                                    "sent_at": time.time(),
                                }
                                target_user["pending_invites"].append(invite)
                                self.send_msg(target_user["conn"], {"type": "invite_received", "invite": invite})
                                self.send_msg(conn, {"type": "status_msg", "text": f"Invite sent to {target_user['name']}!"})

                    elif mtype == "respond_invite" and current_user:
                        from_code = (msg.get("from_code") or "").strip().upper()
                        accept = bool(msg.get("accept"))
                        with self.lock:
                            current_user["pending_invites"] = [
                                inv for inv in current_user["pending_invites"] if inv["from_code"] != from_code
                            ]
                            host_user = self.users_by_code.get(from_code)
                            if not accept:
                                if host_user and host_user["online"] and host_user["conn"]:
                                    self.send_msg(host_user["conn"], {
                                        "type": "status_msg",
                                        "text": f"{current_user['name']} declined your match invite.",
                                    })
                            elif not host_user or not host_user["online"] or not host_user["conn"]:
                                self.send_msg(conn, {"type": "status_msg", "text": "Inviting friend went offline."})
                            else:
                                match_id = f"match_{self.next_match_id}"
                                self.next_match_id += 1
                                p1_char, p2_char = random.choice([
                                    ("warrior", "wizard"),
                                    ("wizard", "warrior"),
                                ])

                                host_user["match_id"] = match_id
                                host_user["player_slot"] = 1
                                current_user["match_id"] = match_id
                                current_user["player_slot"] = 2

                                match_info = {
                                    "match_id": match_id,
                                    "p1_code": host_user["code"],
                                    "p2_code": current_user["code"],
                                    "p1_name": host_user["name"],
                                    "p2_name": current_user["name"],
                                    "p1_char": p1_char,
                                    "p2_char": p2_char,
                                }
                                self.matches[match_id] = match_info

                                self.send_msg(host_user["conn"], {
                                    "type": "match_start",
                                    "your_slot": 1,
                                    **match_info,
                                })
                                self.send_msg(current_user["conn"], {
                                    "type": "match_start",
                                    "your_slot": 2,
                                    **match_info,
                                })

                    elif mtype == "relay" and current_user:
                        match_id = current_user.get("match_id")
                        if match_id and match_id in self.matches:
                            m = self.matches[match_id]
                            other_code = m["p2_code"] if current_user["code"] == m["p1_code"] else m["p1_code"]
                            other_user = self.users_by_code.get(other_code)
                            if other_user and other_user["online"] and other_user["conn"]:
                                self.send_msg(other_user["conn"], {
                                    "type": "relay",
                                    "from_slot": current_user.get("player_slot"),
                                    "data": msg.get("data", {}),
                                })

                    elif mtype == "leave_match" and current_user:
                        with self.lock:
                            mid = current_user.get("match_id")
                            current_user["match_id"] = None
                            current_user["player_slot"] = None
                            if mid and mid in self.matches:
                                m = self.matches[mid]
                                other_code = m["p2_code"] if current_user["code"] == m["p1_code"] else m["p1_code"]
                                other_user = self.users_by_code.get(other_code)
                                if other_user:
                                    other_user["match_id"] = None
                                    other_user["player_slot"] = None
                                    if other_user["online"] and other_user["conn"]:
                                        self.send_msg(other_user["conn"], {"type": "opponent_left"})
                                del self.matches[mid]
                        self.notify_all_friends(current_user)

        except (ConnectionResetError, BrokenPipeError, json.JSONDecodeError):
            pass
        finally:
            with self.lock:
                if conn in self.clients_by_conn:
                    del self.clients_by_conn[conn]
                if current_user and current_user.get("conn") is conn:
                    current_user["online"] = False
                    current_user["conn"] = None
                    mid = current_user.get("match_id")
                    current_user["match_id"] = None
                    current_user["player_slot"] = None
                    if mid and mid in self.matches:
                        m = self.matches[mid]
                        other_code = m["p2_code"] if current_user["code"] == m["p1_code"] else m["p1_code"]
                        other_user = self.users_by_code.get(other_code)
                        if other_user:
                            other_user["match_id"] = None
                            other_user["player_slot"] = None
                            if other_user["online"] and other_user["conn"]:
                                self.send_msg(other_user["conn"], {"type": "opponent_left"})
                        del self.matches[mid]
            if current_user:
                self.notify_all_friends(current_user)
            try:
                conn.close()
            except OSError:
                pass

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(32)
        print(f"[Brawler Relay Server] Listening on {self.host}:{self.port}")
        while True:
            conn, addr = self.sock.accept()
            t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    RelayServer().start()