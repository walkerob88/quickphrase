import datetime

from quickphrase.placeholders import plan, render_dynamic


def test_plain_text_passthrough():
    p = plan("hello world")
    assert p.text == "hello world"
    assert p.left_moves == 0
    assert p.tab_stops == []


def test_date_time_render():
    now = datetime.datetime.now()
    p = plan("today is {{date}}")
    assert now.strftime("%Y-%m-%d") in p.text
    assert render_dynamic("{{time}}") == now.strftime("%H:%M")


def test_cursor_positioning():
    p = plan("Hi {{cursor}}, thanks!")
    assert p.text == "Hi , thanks!"
    assert p.left_moves == len(", thanks!")
    assert p.tab_stops == []


def test_single_blank():
    p = plan("Dear {{blank}}, hello.")
    assert p.text == "Dear , hello."
    assert p.left_moves == len(", hello.")
    assert p.tab_stops == [len(", hello.")]


def test_multiple_blanks():
    # "Hi {{blank}}, re: {{blank}}. Bye"
    p = plan("Hi {{blank}}, re: {{blank}}. Bye")
    assert p.text == "Hi , re: . Bye"
    # Caret to first blank: skip over ", re: " and ". Bye"
    assert p.left_moves == len(", re: ") + len(". Bye")
    # Tab 1: over ", re: " to second blank; Tab 2: over ". Bye" to the end.
    assert p.tab_stops == [len(", re: "), len(". Bye")]


def test_blank_at_end():
    p = plan("Amount: {{blank}}")
    assert p.text == "Amount: "
    assert p.left_moves == 0
    assert p.tab_stops == [0]


def test_blank_overrides_cursor():
    p = plan("A {{blank}} B {{cursor}} C")
    assert "{{cursor}}" not in p.text
    assert p.tab_stops == [len(" B  C")]


def test_multiline_blanks():
    p = plan("Hi {{blank}},\n\nsee {{blank}}.\nBye")
    assert p.text == "Hi ,\n\nsee .\nBye"
    assert p.tab_stops == [len(",\n\nsee "), len(".\nBye")]
