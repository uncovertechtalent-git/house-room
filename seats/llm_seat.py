#!/usr/bin/env python3
"""The local-model seat: a model behind an OpenAI-compatible endpoint.

Joins the channel, answers only lines that address it, and calls
/v1/chat/completions with a bearer key read from a file. No tools, no
actions. Standard library only.

Environment:
  HOUSE_IRC_HOST, HOUSE_IRC_PORT   the IRC server
  HOUSE_LLM_URL                  base URL of the model server, e.g. http://host:1234
  HOUSE_LLM_KEY_FILE             file holding the bearer key (mode 600)
  HOUSE_NICK                       default llm
  HOUSE_CHANNEL                    default #house
  HOUSE_LLM_MODEL                default google/gemma-4-e4b
  HOUSE_SEAT_NICKS                 comma list of other seats (also learned from the bot tag)
"""
import json
import os
import stat
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import irc  # noqa: E402
import rails  # noqa: E402


def make_answer(base_url, key_file, model):
    url = base_url.rstrip("/").removesuffix("/v1") + "/v1/chat/completions"

    def answer(system, user):
        with open(key_file, encoding="utf-8") as fh:
            key = fh.read().strip()
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 300,
            "temperature": 0.7,
            "reasoning_effort": "none",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)["choices"][0]["message"]["content"] or ""

    return answer


def main():
    key_file = os.path.expanduser(rails.env("HOUSE_LLM_KEY_FILE"))
    if os.stat(key_file).st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise SystemExit("key file must be mode 600")
    nick = os.environ.get("HOUSE_NICK", "llm")
    channel = os.environ.get("HOUSE_CHANNEL", "#house")
    answer = make_answer(
        rails.env("HOUSE_LLM_URL"), key_file, os.environ.get("HOUSE_LLM_MODEL", "google/gemma-4-e4b")
    )
    seat = rails.Seat(nick, channel, answer, os.environ.get("HOUSE_SEAT_NICKS", "").split(","))
    client = irc.Client(rails.env("HOUSE_IRC_HOST"), int(rails.env("HOUSE_IRC_PORT", "6667")), nick, channel, log=rails.log)
    client.run(seat.handle)


if __name__ == "__main__":
    main()
