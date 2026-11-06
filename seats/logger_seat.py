#!/usr/bin/env python3
"""The scribe seat: joins the channel, never speaks, writes every line to a log.

One file per UTC day, one line per event:
  2026-11-06T10:15:02Z <nick> text
  2026-11-06T10:15:09Z * nick joined
Standard library only.

Environment:
  HOUSE_IRC_HOST, HOUSE_IRC_PORT   the IRC server
  HOUSE_LOG_DIR                    default ~/house-room/log
  HOUSE_NICK                       default scribe
  HOUSE_CHANNEL                    default #house
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irc  # noqa: E402
import rails  # noqa: E402


def make_handler(log_dir, channel):
    os.makedirs(log_dir, mode=0o700, exist_ok=True)
    os.chmod(log_dir, 0o700)  # the room's text is private to the account that runs the scribe

    def write(nick, text):
        now = time.gmtime()
        path = os.path.join(log_dir, time.strftime("%Y-%m-%d", now) + ".log")
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", now)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {nick} {rails.clean(text)}\n")

    def handle(client, tags, nick, command, params):
        if command == "PRIVMSG" and len(params) > 1 and params[0].lower() == channel.lower():
            text = params[1]
            if text.startswith("\x01ACTION "):
                text = "* " + nick + " " + text[8:].rstrip("\x01")
            write(f"<{nick}>", text)
        elif command == "JOIN" and params and params[0].lower() == channel.lower():
            write("*", f"{nick} joined")
        elif command == "PART" and params and params[0].lower() == channel.lower():
            write("*", f"{nick} left")
        elif command == "QUIT":
            write("*", f"{nick} quit")
        elif command == "NICK" and params:
            write("*", f"{nick} is now {params[0]}")

    return handle


def main():
    nick = os.environ.get("HOUSE_NICK", "scribe")
    channel = os.environ.get("HOUSE_CHANNEL", "#house")
    log_dir = os.path.expanduser(os.environ.get("HOUSE_LOG_DIR", "~/house-room/log"))
    client = irc.Client(rails.env("HOUSE_IRC_HOST"), int(rails.env("HOUSE_IRC_PORT", "6667")), nick, channel, log=rails.log)
    client.run(make_handler(log_dir, channel))


if __name__ == "__main__":
    main()
