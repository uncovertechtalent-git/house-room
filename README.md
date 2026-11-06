# house-room

A shared chat room for a household: people on any IRC client, and one small bot process per AI agent, called a seat. A seat joins the channel, reads everything, and answers only a line that addresses it by nick. Three rails keep it safe to leave running: every line from another participant is data, never an instruction; a seat has no tools and takes no actions; and a seat never starts a conversation with another seat. The server is [Ergo](https://ergo.chat) in Docker on a home server, the seats are standard-library Python, and the network is a private LAN with no port forwards, so there is no per-user authentication yet.

```
ergo/        docker-compose.yml, ircd.yaml, motd.txt     the IRC server (pinned image)
seats/       irc.py        socket loop with reconnect and backoff
             rails.py      addressing, rate limits, reply splitting, loop guard
             llm_seat.py   a local model behind an OpenAI-compatible endpoint
             claude_seat.py  the claude CLI in print mode, no tools
             logger_seat.py  the scribe: writes every line to a daily log
systemd/     user services for the seats that run on the server
launchd/     LaunchAgent template for the Claude seat on a Mac
tools/       probe.py      raw-socket client for tests and for checking a new server
tests/       unit tests for the rails (python3 -m unittest discover -s tests)
SEATS.md     add a Claude seat on another Mac
CLIENTS.md   join as a human
```

## The rails

Every seat runs the same rules from `seats/rails.py`:

- **Addressed only.** A seat answers a line that starts with `nick:`, `nick,` or `@nick`. Everything else goes into a rolling window of the last 20 lines, which is the only context the seat gets.
- **Data, not instructions.** The system prompt says so, and the seat has nothing to obey with anyway: no tools, no files, no shell.
- **No bot loops.** A seat's reply never starts by addressing another seat (the code strips it). A line from one seat to another is answered only if a person addressed a seat in the last 60 seconds, and only while fewer than three seat lines follow each other. Seats mark themselves as bots (user mode `+B`, message tag `bot`), so a new seat needs no list; `HOUSE_SEAT_NICKS` can add names by hand.
- **Slow and short.** At most one reply per 5 seconds and per seat, at most three lines of at most 400 bytes, and a cap per hour (120 for the local-model seat, 60 for the Claude seat). Control characters, including CR and LF, are removed from model output before it reaches the socket, so a model cannot inject IRC commands.
- **Quiet logs.** The seats log who was answered and how long it took, never the text. The scribe is the only place chat is written down.

## The server

`ergo/docker-compose.yml` runs `ghcr.io/ergochat/ergo` at a pinned release tag, read-only root, all capabilities dropped, as a non-root user, with the config mounted read-only and one data volume for the database.

```
cd ergo && mkdir -p data && docker compose up -d
```

`HOUSE_IRC_PORT` (default 6667), `HOUSE_IRC_BIND` (default all interfaces) and `HOUSE_UID` / `HOUSE_GID` come from the environment or a `.env` file next to the compose file.

Choices in `ircd.yaml`, all different from Ergo's shipped defaults:

- One plaintext listener. No TLS yet (see follow-ups).
- No account registration and no channel registration: nobody needs an account to join or speak. The channel `#house` exists while someone is in it, which the scribe makes permanent in practice.
- No operators, so the server cannot be administered over IRC; change the config and restart the container.
- History is in memory (2048 lines per channel). Persistent history in Ergo needs a MySQL server, which is more than one setting, so it is off; the scribe's log is the durable record.
- No replay on join, so a seat that restarts never sees old addressed lines again and cannot answer them twice. A client that wants history asks for it with `CHATHISTORY`.

Check a fresh server from any machine with Python:

```
HOUSE_IRC_HOST=<server-address> HOUSE_IRC_PORT=<port> python3 tools/probe.py --nick probe --say "hello" --history 10
```

## The seats

Settings come from the environment; nothing in this repository names an address, a user or a key.

| Variable | Used by | Meaning |
|---|---|---|
| `HOUSE_IRC_HOST`, `HOUSE_IRC_PORT` | all | the IRC server |
| `HOUSE_NICK`, `HOUSE_CHANNEL` | all | defaults: the seat's own name, `#house` |
| `HOUSE_LLM_URL` | llm seat | base URL of the OpenAI-compatible server |
| `HOUSE_LLM_KEY_FILE` | llm seat | file holding the bearer key; the seat refuses to start unless only its owner can read it (mode 600) |
| `HOUSE_LLM_MODEL` | llm seat | default `google/gemma-4-e4b` |
| `HOUSE_CLAUDE_BIN`, `HOUSE_CLAUDE_MODEL`, `HOUSE_CLAUDE_TIMEOUT` | claude | CLI path, default model `claude-sonnet-5-5`, 60 s per turn |
| `HOUSE_STATE_DIR` | claude | the channel's session id and an empty working directory |
| `HOUSE_LOG_DIR` | scribe | default `~/house-room/log` |
| `HOUSE_SEAT_NICKS` | all | optional comma list of other seats |

**The local-model seat** (`llm_seat.py`) calls `/v1/chat/completions` with `max_tokens` 300, temperature 0.7 and `reasoning_effort` `none`. **scribe** writes `YYYY-MM-DDTHH:MM:SSZ <nick> text` to one file per UTC day (directory mode 700, files mode 600), plus `*` lines for joins and quits, and never speaks.

**The Claude seat** runs `claude -p` with `--tools ""`, `--safe-mode`, `--strict-mcp-config`, `--disable-slash-commands` and `--permission-prompts none`, from an empty working directory, with one fixed session for the channel: created with `--session-id` on the first run, resumed with `--resume` after. It gets the rails as its system prompt and the last 20 lines in the prompt. The CLI has no turn-limit flag; with no tools a request is one turn, and the result's `num_turns` confirms it. At every start the seat asks the CLI what it would run with and exits unless the tool list and the MCP server list are both empty, so a CLI change that brings tools back stops the seat instead of arming it. The channel's session keeps its history across requests; delete `session.json` in the state directory to start a fresh one.

Services: `systemd/` has user units for the local-model seat and scribe (`systemctl --user enable --now house-llm.service house-scribe.service`, with `loginctl enable-linger` so they start at boot; give each seat its nick with a drop-in that sets `HOUSE_NICK`, since the shared env file serves both); `launchd/` has the template for the Claude seat. `SEATS.md` walks through adding a Claude seat on another Mac.

## Tests

```
python3 -m unittest discover -s tests
```

The tests cover addressing, reply splitting and byte limits, control-character removal, the loop guard and the pacer. They do not start a server.

## Follow-ups

- **TLS.** Ergo supports it on port 6697 with a certificate; the compose file and `ircd.yaml` need a second listener and a mounted certificate, and every seat needs a TLS option in `irc.py`.
- **Vault export.** The scribe's daily files are plain text on the server. Copying them into a notes vault on a schedule is a separate step and is not built.

## License

MIT, see `LICENSE`.
