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


def test_call_effect_connects_receiver_arguments_and_future_member_reads() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))
    store = flow.container(())

    flow.call_effect((store, holder))
    reference = flow.read_member(store, ("index", "0"))
    flow.taint(reference, "uncertain")

    assert flow.related(store, holder)
    assert flow.read_member(holder, ("index", "0")).kind == "uncertain"


def test_component_identities_preserve_pre_union_callable_lookup_keys() -> None:
    flow = ExplicitAnyDataFlow()
    callable_value = flow.object(callable_role="function")
    captured = flow.object()
    original = callable_value.identities

    flow.connect((captured, callable_value), expose_members=False)

    assert original <= flow.component_identities(callable_value)
    assert original <= flow.component_identities(captured)


def test_stored_values_expose_variadic_container_members() -> None:
    flow = ExplicitAnyDataFlow()
    first = flow.object()
    second = flow.object()
    positional = flow.container((first, second))
    keywords = flow.mapping(((repr("target"), first), (repr("value"), second)))

    assert flow.stored_values(positional) == (first, second)
    assert set(flow.stored_values(keywords)) == {first, second}


def test_stored_value_closure_preserves_nested_dynamic_expansion_participants() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.object()
    store = flow.object()
    packed = flow.container((flow.container((holder,)), store))

    closure = flow.stored_value_closure((packed,))

    assert packed in closure
    assert holder in closure
    assert store in closure


def test_call_effect_transports_nested_object_origins_without_eager_graph_cloning() -> None:
    flow = ExplicitAnyDataFlow()
    holder = flow.container((flow.scalar(),))
    argument = flow.container((holder,))
    store = flow.container(())

    flow.call_effect((store, argument))
    reference = flow.read_member(store, ("index", "0"))
    flow.taint(reference, "uncertain")

    assert flow.component_roots(holder) <= flow.taint_reachable(reference)
    assert flow.read_member(holder, ("index", "0")).kind == "uncertain"


def test_prior_component_excludes_function_local_analysis_objects() -> None:
    flow = ExplicitAnyDataFlow()
    captured = flow.container(())
    checkpoint = flow.checkpoint()
    parameter = flow.object(escaped=True)
    temporary = flow.object(escaped=True)

    flow.connect((captured, parameter, temporary), expose_members=True)

    prior = flow.prior_component(parameter, checkpoint)
    assert prior is not None
    assert flow.related(prior, captured)


def test_large_call_component_keeps_flow_values_compact() -> None:
    flow = ExplicitAnyDataFlow()
    values = tuple(flow.object() for _ in range(500))

    result = flow.call_effect(values)
    combined = flow.join((*values, result))

    assert len(result.origins) == 1
    assert len(combined.identities) == 1
    assert len(flow.component_roots(combined)) == 1
