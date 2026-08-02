import pytest

from quickphrase.engine import ExpansionEngine


PHRASES = {
    "brb": "be right back",
    "b": "bee",
    "omw": "on my way!",
    "sig": "Best,\nRob",
}


def type_string(engine, text):
    """Feed a string char by char, return list of expansions fired."""
    fired = []
    for ch in text:
        result = engine.feed_char(ch)
        if result:
            fired.append(result)
    return fired


@pytest.fixture
def engine():
    return ExpansionEngine(PHRASES, prefix=";")


def test_simple_expansion(engine):
    fired = type_string(engine, ";omw")
    assert len(fired) == 1
    assert fired[0].text == "on my way!"
    assert fired[0].backspaces == 4  # ";omw"


def test_no_expansion_without_prefix(engine):
    assert type_string(engine, "omw brb sig") == []


def test_unknown_trigger_resets(engine):
    assert type_string(engine, ";xyz") == []
    # After the miss, a fresh trigger still works.
    fired = type_string(engine, ";omw")
    assert len(fired) == 1


def test_prefix_conflict_longer_wins(engine):
    # "b" is a prefix of "brb": typing ;brb must yield the long expansion.
    fired = type_string(engine, ";brb")
    assert len(fired) == 1
    assert fired[0].text == "be right back"
    assert fired[0].backspaces == 4


def test_prefix_conflict_shorter_fires_on_break(engine):
    # ;b followed by a space: the pending short match fires, space re-typed.
    fired = type_string(engine, ";b ")
    assert len(fired) == 1
    assert fired[0].text == "bee "
    assert fired[0].backspaces == 3  # ";b "


def test_pending_flush_preserves_tail(engine):
    # ;bx — "b" matched but "x" breaks "brb"; expansion keeps the x.
    fired = type_string(engine, ";bx")
    assert len(fired) == 1
    assert fired[0].text == "beex"
    assert fired[0].backspaces == 3  # ";bx"


def test_backspace_edits_buffer(engine):
    type_string(engine, ";omq")  # typo, engine reset? "omq" not a prefix -> reset
    engine.reset()
    for ch in ";om":
        engine.feed_char(ch)
    engine.feed_backspace()  # ";o"
    fired = type_string(engine, "mw")
    assert len(fired) == 1
    assert fired[0].text == "on my way!"


def test_backspace_over_prefix_disarms(engine):
    engine.feed_char(";")
    engine.feed_backspace()  # buffer empty, still armed
    engine.feed_backspace()  # over the prefix: disarm
    assert not engine.armed
    assert type_string(engine, "omw") == []


def test_reset_clears_state(engine):
    type_string(engine, ";om")
    engine.reset()
    assert type_string(engine, "w") == []


def test_reprefix_restarts_trigger(engine):
    # ";xy;omw" -> the second ";" starts a fresh trigger.
    fired = type_string(engine, ";xy;omw")
    assert len(fired) == 1
    assert fired[0].text == "on my way!"
    assert fired[0].backspaces == 4


def test_multiline_replacement(engine):
    fired = type_string(engine, ";sig")
    assert fired[0].text == "Best,\nRob"


def test_triggers_stored_with_prefix_are_normalized():
    engine = ExpansionEngine({";hi": "hello"}, prefix=";")
    fired = type_string(engine, ";hi")
    assert len(fired) == 1
    assert fired[0].text == "hello"


def test_consecutive_expansions(engine):
    fired = type_string(engine, ";omw and ;brb")
    assert len(fired) == 2
    assert fired[0].text == "on my way!"
    assert fired[1].text == "be right back"


def test_pending_then_reprefix(engine):
    # ";b;omw": pending "b" flushed when ";" re-arms, then omw fires.
    fired = type_string(engine, ";b;omw")
    assert len(fired) == 2
    assert fired[0].text == "bee;"
    assert fired[0].backspaces == 3  # ";b;"
    assert fired[1].text == "on my way!"
