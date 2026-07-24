from song_agent.release_check.explicit_any_dataflow import ExplicitAnyDataFlow


def test_literal_unpack_preserves_object_identity() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))
    packed = flow.container((holder,))

    (reference,) = flow.unpack(packed, 1)

    assert reference.identities == holder.identities
    assert reference.origins == frozenset()


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
