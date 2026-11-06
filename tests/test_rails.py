import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seats"))
import irc  # noqa: E402
import rails  # noqa: E402


class ParseTests(unittest.TestCase):
    def test_privmsg_with_tags(self):
        tags, nick, cmd, params = irc.parse("@bot;time=2026-11-06T10:00:00.000Z :ann!u@h PRIVMSG #room :hi: there")
        self.assertEqual((nick, cmd, params), ("ann", "PRIVMSG", ["#room", "hi: there"]))
        self.assertIn("bot", tags)

    def test_ping(self):
        self.assertEqual(irc.parse("PING :abc")[2:], ("PING", ["abc"]))


class AddressTests(unittest.TestCase):
    def test_forms(self):
        for text in ("robin: hi", "robin, hi", "@robin hi", "@robin: hi", "  Robin: hi"):
            self.assertEqual(rails.address(text, "robin"), "hi", text)

    def test_not_addressed(self):
        for text in ("hi robin", "robin hi", "robinbot: hi", "@robinbot hi", "talk to robin: later"):
            self.assertIsNone(rails.address(text, "robin"), text)


class SplitTests(unittest.TestCase):
    def test_limits(self):
        lines = rails.split_reply("word " * 500, "ann: ")
        self.assertEqual(len(lines), rails.MAX_LINES)
        self.assertTrue(all(len(x.encode()) < 400 for x in lines))
        self.assertTrue(lines[0].startswith("ann: "))

    def test_multibyte_boundary(self):
        lines = rails.split_reply("é" * 600)
        self.assertTrue(all(len(x.encode()) <= 400 for x in lines))
        self.assertTrue(all(set(x) <= {"é", " ", "."} for x in lines))

    def test_control_characters_cannot_inject_commands(self):
        lines = rails.split_reply("hello\r\nQUIT :bye\x00\x03\x02")
        self.assertFalse(any(set(x) & set("\r\n\x00\x03\x02") for x in lines))

    def test_never_addresses_a_seat(self):
        lines = rails.split_reply("meeseeks: do the thing", "ann: ", bots={"meeseeks"})
        self.assertEqual(lines, ["ann: do the thing"])


class RoomTests(unittest.TestCase):
    def room(self):
        return rails.Room("meeseeks", ["robin", "scribe"])

    def test_human_request_is_answered(self):
        self.assertIsNotNone(self.room().hear("ann", "meeseeks: hi", {}, now=1000))

    def test_context_is_kept_but_not_answered(self):
        r = self.room()
        self.assertIsNone(r.hear("ann", "just talking", {}, now=1000))
        hit = r.hear("ann", "meeseeks: hi", {}, now=1001)
        self.assertEqual(hit[2], [("ann", "just talking")])

    def test_seat_to_seat_needs_a_human_first(self):
        r = self.room()
        self.assertIsNone(r.hear("robin", "meeseeks: ping", {"bot": ""}, now=1000))

    def test_seat_to_seat_after_human_trigger(self):
        r = self.room()
        r.hear("ann", "robin: ask meeseeks something", {}, now=1000)
        self.assertIsNotNone(r.hear("robin", "meeseeks: question", {"bot": ""}, now=1010))

    def test_trigger_expires(self):
        r = self.room()
        r.hear("ann", "robin: ask meeseeks something", {}, now=1000)
        self.assertIsNone(r.hear("robin", "meeseeks: question", {"bot": ""}, now=1100))

    def test_ping_pong_stops(self):
        r = self.room()
        r.hear("ann", "robin: start", {}, now=1000)
        results = [r.hear("robin" if i % 2 == 0 else "scribe", "meeseeks: x", {"bot": ""}, now=1001 + i) for i in range(5)]
        self.assertIsNotNone(results[0])
        self.assertIsNone(results[-1])

    def test_unknown_bot_learned_from_tag(self):
        r = self.room()
        self.assertIsNone(r.hear("newbot", "meeseeks: hi", {"bot": ""}, now=1000))
        self.assertIn("newbot", r.bots)

    def test_own_lines_never_trigger(self):
        self.assertIsNone(self.room().hear("meeseeks", "meeseeks: hi", {}, now=1000))


class PacerTests(unittest.TestCase):
    def test_gap_and_hourly_cap(self):
        p = rails.Pacer(gap=5, per_hour=2)
        self.assertTrue(p.ready(100))
        p.mark(100)
        self.assertFalse(p.ready(102))
        self.assertTrue(p.ready(106))
        p.mark(106)
        self.assertFalse(p.ready(200))
        self.assertTrue(p.ready(4000))


if __name__ == "__main__":
    unittest.main()
