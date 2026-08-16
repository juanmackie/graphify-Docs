from app.ingestion.selector import select_chunks


def test_short_documents_use_all_chunks():
    chunks = [f"Section {i}\n\nDistinct text about topic {i}." for i in range(5)]
    result = select_chunks(chunks, mode="balanced", minimum=12)
    assert result.indices == list(range(5))
    assert result.chunks == chunks


def test_balanced_selection_is_bounded_and_covers_document():
    chunks = [f"# Section {i}\n\nunique-term-{i} common context" for i in range(100)]
    result = select_chunks(chunks, mode="balanced", fraction=0.2, minimum=10, maximum=30)
    assert 10 <= len(result.indices) <= 30
    assert result.indices == sorted(result.indices)
    assert result.indices[0] < 20
    assert result.indices[-1] >= 80


def test_full_mode_keeps_every_chunk():
    chunks = [f"chunk {i}" for i in range(20)]
    result = select_chunks(chunks, mode="full", fraction=0.1)
    assert result.indices == list(range(20))


def test_fast_mode_caps_fraction():
    chunks = [f"chunk {i} with term-{i}" for i in range(100)]
    result = select_chunks(chunks, mode="fast", fraction=0.9, minimum=1, maximum=100)
    assert len(result.indices) <= 20
