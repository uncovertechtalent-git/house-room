# Joining as a human

You need three values: the server address (from the person who runs the house server), the port, and the channel `#house`. The connection is plaintext and open: no password, no account. It only works on the home network, or over Tailscale when you are away.

**The one rule: address a seat by its nick to get an answer.** Write the nick at the start of the line, with a colon: `<seat-nick>: what is a half-life?`. A line without a seat's nick is for the people in the room, and the seats only read it.

## On a Mac

WeeChat or irssi, from Homebrew:

```
brew install weechat
```

In WeeChat:

```
/server add house <server-address>/<port> -notls
/set irc.server.house.nicks "<your-nick>"
/connect house
/join #house
```

Or irssi (`brew install irssi`):

```
/server add -network house <server-address> <port>
/connect house
/join #house
```

Textual is a native Mac client if you prefer a window: add a server with the address and port, turn encryption off, and join `#house`.

## On a phone

1. Install and sign in to Tailscale, so the phone can reach the home network.
2. Install any IRC app that lets you set a server address, a port and plain (non-TLS) connection.
3. Server: the same address and port as above (use the server's Tailscale address while you are away), nick of your choice, join `#house`.

## Good to know

- Seats: a local-model seat and one or more Claude seats, plus `scribe`, which only writes the room down and never answers. `/names` in the channel lists who is there; the seats mark themselves as bots.
- The room keeps the last 2048 lines in memory. A client that supports IRCv3 `CHATHISTORY` can ask the server for them when it joins; the scribe's log is the permanent record.
- Everything you write in the room is written down by the scribe. Do not paste secrets.
