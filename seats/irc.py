"""Minimal IRC client loop for the house room seats. Standard library only.

One Client = one connection to the server, one channel. run() never returns:
it connects, registers, joins, reads, and on any failure reconnects with
backoff. The handler is called from the reading thread, so it must return
quickly; slow work (a model call) belongs on its own thread.
"""
import random
import socket
import threading
import time


def parse(line):
    """Split one IRC line into (tags, nick, command, params)."""
    tags = {}
    if line.startswith("@"):
        raw, _, line = line.partition(" ")
        for kv in raw[1:].split(";"):
            k, _, v = kv.partition("=")
            tags[k] = v
    nick = ""
    if line.startswith(":"):
        prefix, _, line = line.partition(" ")
        nick = prefix[1:].split("!", 1)[0]
    head, sep, trailing = line.partition(" :")
    params = head.split()
    if sep:
        params.append(trailing)
    command = params.pop(0).upper() if params else ""
    return tags, nick, command, params


class Client:
    def __init__(self, host, port, nick, channel, realname="house-room seat", log=print):
        self.host, self.port, self.nick, self.channel = host, port, nick, channel
        self.realname, self.log = realname, log
        self.sock = None
        self.lock = threading.Lock()

    def send(self, line):
        """Send one raw line; CR, LF and NUL can never be smuggled in."""
        clean = line.replace("\r", " ").replace("\n", " ").replace("\0", " ")
        with self.lock:
            if self.sock:
                self.sock.sendall(clean.encode("utf-8", "replace")[:510] + b"\r\n")

    def say(self, text, target=None):
        self.send(f"PRIVMSG {target or self.channel} :{text}")

    def run(self, handler):
        delay = 2.0
        while True:
            started = time.time()
            try:
                self._session(handler)
            except (OSError, ConnectionError) as exc:
                self.log(f"disconnected: {exc}")
            finally:
                with self.lock:
                    if self.sock:
                        self.sock.close()
                    self.sock = None
            delay = 2.0 if time.time() - started > 120 else min(delay * 2, 60.0)
            wait = delay + random.uniform(0, delay / 4)
            self.log(f"reconnecting in {wait:.0f}s")
            time.sleep(wait)

    def _session(self, handler):
        sock = socket.create_connection((self.host, self.port), timeout=15)
        sock.settimeout(30)
        with self.lock:
            self.sock = sock
        self.log(f"connected to {self.host}:{self.port} as {self.nick}")
        self.send("CAP REQ :message-tags")
        self.send(f"NICK {self.nick}")
        self.send(f"USER {self.nick} 0 * :{self.realname}")
        buf, last_rx, last_ping = b"", time.time(), time.time()
        while True:
            try:
                data = sock.recv(4096)
                if not data:
                    raise ConnectionError("closed by server")
                buf += data
                last_rx = time.time()
            except socket.timeout:
                if time.time() - last_rx > 240:
                    raise ConnectionError("no data for 240s")
            if time.time() - last_ping > 90:
                self.send(f"PING :{int(time.time())}")
                last_ping = time.time()
            *lines, buf = buf.split(b"\r\n")
            for raw in lines:
                self._dispatch(raw.decode("utf-8", "replace"), handler)

    def _dispatch(self, line, handler):
        tags, nick, command, params = parse(line)
        if command == "PING":
            self.send("PONG :" + (params[0] if params else ""))
        elif command == "CAP" and len(params) > 1 and params[1] in ("ACK", "NAK"):
            self.send("CAP END")
        elif command == "001":
            self.send(f"MODE {self.nick} +B")
            self.send(f"JOIN {self.channel}")
        elif command == "433":
            raise ConnectionError("nick in use")
        elif command == "ERROR":
            raise ConnectionError("server error: " + " ".join(params))
        elif command == "KICK" and len(params) > 1 and params[1].lower() == self.nick.lower():
            raise ConnectionError("kicked")
        elif command:
            try:
                handler(self, tags, nick, command, params)
            except Exception as exc:  # a bad line must not take the seat down
                self.log(f"handler error: {exc!r}")
