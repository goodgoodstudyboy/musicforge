from song_agent.release_check.explicit_any_dataflow import ExplicitAnyDataFlow


def test_literal_unpack_preserves_object_identity() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))
    packed = flow.container((holder,))

    (reference,) = flow.unpack(packed, 1)

    assert reference.identities == holder.identities
    assert reference.origins == frozenset()


def test_starred_literal_unpack_maps_suffix_from_the_end() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))
    packed = flow.container((flow.scalar(), flow.scalar(), flow.scalar(), holder))

    head, middle, reference = flow.unpack(packed, 3, starred_index=1)

    assert head.kind == "other"
    assert middle.identities
    assert reference.identities == holder.identities


def test_starred_literal_unpack_supports_first_and_last_positions() -> None:
    flow = ExplicitAnyDataFlow()
    first = flow.object()
    last = flow.object()
    packed = flow.container((first, flow.scalar(), last))

    leading, leading_suffix = flow.unpack(packed, 2, starred_index=0)
    trailing_prefix, trailing = flow.unpack(packed, 2, starred_index=1)

    assert leading.identities
    assert leading_suffix.identities == last.identities
    assert trailing_prefix.identities == first.identities
    assert trailing.identities


def test_unknown_starred_unpack_preserves_origins_and_fails_closed() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))
    escaped = flow.escape((holder,))

    rows = flow.unpack(escaped, 3, starred_index=1)

    assert all(row.kind == "unknown" for row in rows)
    assert all(holder.identities <= row.origins for row in rows)


def test_unresolved_escaped_object_is_distinguished_from_an_origin_bound_escape() -> None:
    flow = ExplicitAnyDataFlow()
    parameter = flow.object(escaped=True)
    holder = flow.container((flow.scalar(),))
    call_result = flow.escape((holder,))

    assert flow.has_unresolved_escape(parameter)
    assert not flow.has_unresolved_escape(call_result)


def test_exact_member_reads_preserve_identity() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))
    store = flow.container((holder,))

    reference = flow.read_member(store, ("index", "0"))

    assert reference.identities == holder.identities
    assert reference.escaped is False


def test_dynamic_escape_keeps_a_separate_result_and_source_provenance() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))

    result = flow.escape((holder,))

    assert result.identities.isdisjoint(holder.identities)
    assert result.origins == holder.identities
    assert flow.taint(result, "uncertain") == result.identities | holder.identities


def test_dynamic_result_does_not_taint_source_until_mutated() -> None:
    flow = ExplicitAnyDataFlow()
    source = flow.object()
    result = flow.escape((source,))

    unrelated = flow.object()
    assert source.identities.isdisjoint(unrelated.identities)
    assert flow.read_member(source, ("attr", "missing")).kind == "other"
    assert result.origins == source.identities


def test_rebinding_creates_an_independent_alias_group() -> None:
    flow = ExplicitAnyDataFlow()
    original = flow.container((flow.scalar(),))
    rebound = flow.container((flow.scalar(),))

    flow.write_member(rebound, ("index", "0"), flow.scalar("any"))
    affected = flow.taint(rebound, "uncertain")

    assert affected.isdisjoint(original.identities)
