from adapters.db.chroma_adapter import (
    _chunk_by_lines,
    _chunk_by_speaker_turn,
    _chunk_by_time_window,
)

ALICE = "[00:00:01][SPK][Alice] Hello"
ALICE2 = "[00:00:02][SPK][Alice] World"
BOB = "[00:00:03][SPK][Bob] Hi"
BOB2 = "[00:00:04][SPK][Bob] There"
LATE = "[00:01:35][SPK][Alice] Late line"  # 95 seconds in


def test_chunk_by_lines_basic():
    lines = [ALICE, ALICE2, BOB, BOB2]
    chunks = _chunk_by_lines(lines, chunk_size=2)
    assert len(chunks) == 2
    assert chunks[0] == (0, [ALICE, ALICE2])
    assert chunks[1] == (2, [BOB, BOB2])


def test_chunk_by_lines_remainder():
    lines = [ALICE, ALICE2, BOB]
    chunks = _chunk_by_lines(lines, chunk_size=2)
    assert len(chunks) == 2
    assert chunks[1] == (2, [BOB])


def test_chunk_by_speaker_turn_groups_same_speaker():
    lines = [ALICE, ALICE2, BOB, BOB2]
    chunks = _chunk_by_speaker_turn(lines)
    assert len(chunks) == 2
    assert len(chunks[0][1]) == 2   # Alice's two lines
    assert len(chunks[1][1]) == 2   # Bob's two lines


def test_chunk_by_speaker_turn_single_speaker():
    lines = [ALICE, ALICE2]
    chunks = _chunk_by_speaker_turn(lines)
    assert len(chunks) == 1
    assert chunks[0][1] == [ALICE, ALICE2]


def test_chunk_by_speaker_turn_alternating():
    lines = [ALICE, BOB, ALICE2, BOB2]
    chunks = _chunk_by_speaker_turn(lines)
    assert len(chunks) == 4   # each turn is its own chunk


def test_chunk_by_time_window_30s():
    lines = [ALICE, ALICE2, BOB, BOB2, LATE]
    chunks = _chunk_by_time_window(lines, window_secs=30)
    # ALICE (1s), ALICE2 (2s), BOB (3s), BOB2 (4s) are within 30s window
    # LATE (95s) starts a new window
    assert len(chunks) == 2
    first_lines = chunks[0][1]
    assert ALICE in first_lines
    assert LATE not in first_lines
    last_lines = chunks[1][1]
    assert LATE in last_lines


def test_chunk_by_time_window_includes_all_lines():
    lines = [ALICE, ALICE2, BOB]
    chunks = _chunk_by_time_window(lines, window_secs=60)
    all_lines = [l for _, chunk in chunks for l in chunk]
    assert set(all_lines) == set(lines)


def test_chunk_by_lines_empty():
    assert _chunk_by_lines([], chunk_size=30) == []


def test_chunk_by_speaker_turn_empty():
    assert _chunk_by_speaker_turn([]) == []


def test_chunk_by_time_window_empty():
    assert _chunk_by_time_window([], window_secs=30) == []
