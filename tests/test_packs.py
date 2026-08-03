import json
import os

import pytest

from quickphrase import packs


@pytest.fixture
def sample():
    return {
        "hello": {"text": "Hello there!", "category": "General", "favorite": False},
        "bye": {"text": "Goodbye!", "category": "General", "favorite": True},
    }


def test_save_load_roundtrip(tmp_path, sample):
    path = str(tmp_path / "pack.json")
    packs.save_pack(path, "Test pack", sample)
    name, loaded = packs.load_pack(path)
    assert name == "Test pack"
    assert loaded["hello"]["text"] == "Hello there!"
    assert loaded["bye"]["category"] == "General"
    # favorites are not exported (they're personal)
    assert loaded["bye"]["favorite"] is False


def test_load_rejects_non_pack(tmp_path):
    path = str(tmp_path / "bad.json")
    json.dump({"just": "stuff"}, open(path, "w"))
    with pytest.raises(packs.PackError):
        packs.load_pack(path)
    path2 = str(tmp_path / "worse.json")
    open(path2, "w").write("not json{")
    with pytest.raises(packs.PackError):
        packs.load_pack(path2)


def test_merge_adds_new_keeps_existing(sample):
    incoming = {"new": {"text": "N", "category": "X", "favorite": False},
                "hello": {"text": "DIFFERENT", "category": "General",
                          "favorite": False}}
    merged, applied, conflicts = packs.merge(sample, incoming, overwrite=False)
    assert applied == 1 and conflicts == 1
    assert merged["hello"]["text"] == "Hello there!"   # kept
    assert merged["new"]["text"] == "N"                # added


def test_merge_overwrite_keeps_favorite_flag(sample):
    incoming = {"bye": {"text": "See ya!", "category": "Casual",
                        "favorite": False}}
    merged, applied, conflicts = packs.merge(sample, incoming, overwrite=True)
    assert applied == 1 and conflicts == 1
    assert merged["bye"]["text"] == "See ya!"
    assert merged["bye"]["favorite"] is True           # personal flag survives


def test_identical_incoming_is_not_a_conflict(sample):
    merged, applied, conflicts = packs.merge(sample, dict(sample),
                                             overwrite=False)
    assert applied == 0 and conflicts == 0


def test_builtin_ortho_pack_is_valid():
    path = packs.builtin_pack_path("orthopedics")
    assert os.path.exists(path)
    name, phrases = packs.load_pack(path)
    assert "Orthopedics" in name
    assert len(phrases) == 130
    categories = {e["category"] for e in phrases.values()}
    assert len(categories) == 13
    for trigger, entry in phrases.items():
        assert entry["text"].strip()
        assert not any(c.isspace() for c in trigger)
