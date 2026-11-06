#!/usr/bin/env python3
"""Raw-socket probe for the house room. Standard library only.

Joins the channel, optionally says lines, waits, optionally asks the server
for history, prints what it saw, and quits. Use it to check a fresh server
or to play a human (or a bot) in a test.

  probe.py --nick tester --say "llm: hello" --wait 20 --history 20
  probe.py --nick probe-bot --bot --say "meeseeks: ping" --wait 15

Address and port come from HOUSE_IRC_HOST and HOUSE_IRC_PORT.
"""
import argparse
import os
import socket
import sys
import time

WANT = ["message-tags", "server-time", "batch", "echo-message", "draft/chathistory", "chathistory"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("HOUSE_IRC_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("HOUSE_IRC_PORT", "6667")))
    p.add_argument("--nick", default="probe")
    p.add_argument("--channel", default="#house")
    p.add_argument("--say", action="append", default=[], help="line to send (repeatable)")
    p.add_argument("--gap", type=float, default=8.0, help="seconds between --say lines")
    p.add_argument("--wait", type=float, default=10.0, help="seconds to listen after the last line")
    p.add_argument("--history", type=int, default=0, help="ask for this many history lines at the end")
    p.add_argument("--bot", action="store_true", help="set user mode +B (marks the probe as a bot)")
    a = p.parse_args()

    s = socket.create_connection((a.host, a.port), timeout=10)
    s.settimeout(0.5)
    buf = b""

    def send(line):
        s.sendall((line + "\r\n").encode())

    def lines():
        nonlocal buf
        try:
            data = s.recv(4096)
        except socket.timeout:
            return []
        if not data:
            sys.exit("connection closed")
        buf += data
        *done, buf = buf.split(b"\r\n")
        return [x.decode("utf-8", "replace") for x in done]

    send("CAP LS 302")
    send(f"NICK {a.nick}")
    send(f"USER {a.nick} 0 * :probe")
    queue = list(a.say)
    state, next_say, deadline = "reg", 0.0, None
    for _ in range(100000):
        for ln in lines():
            if ln.startswith("PING"):
                send("PONG " + ln.split(" ", 1)[1])
            elif " CAP " in ln and " LS " in ln:
                have = ln.split(" :", 1)[1].split()
                send("CAP REQ :" + " ".join(c for c in WANT if c in have or c.split("=")[0] in have))
            elif " CAP " in ln and (" ACK " in ln or " NAK " in ln):
                send("CAP END")
            elif " 001 " in ln:
                if a.bot:
                    send(f"MODE {a.nick} +B")
                send(f"JOIN {a.channel}")
            elif " 366 " in ln:
                state, next_say = "chat", time.time() + 1
            if " 001 " not in ln and not ln.startswith("PING") and (" PRIVMSG " in ln or " JOIN " in ln or " 4" in ln[:60]):
                print(ln)
        now = time.time()
        if state == "chat" and queue and now >= next_say:
            send(f"PRIVMSG {a.channel} :{queue.pop(0)}")
            next_say = now + a.gap
        if state == "chat" and not queue and deadline is None:
            deadline = now + a.wait
        if deadline is not None and now >= deadline:
            if a.history and state == "chat":
                send(f"CHATHISTORY LATEST {a.channel} * {a.history}")
                state, deadline = "hist", now + 3
                print("--- history ---")
            else:
                break
    send("QUIT :probe done")


if __name__ == "__main__":
    main()
