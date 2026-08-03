# ADR-034: Cross-Python Source Evidence

Status: accepted

Date: 2026-08-02

## Context

Wave 0 originally hashed `ast.dump()` output for package writer modules,
package discriminator scopes, and State Authority path expressions. Python
3.11 and Python 3.14 produce different AST shapes for the same source. The
approved files generated on Python 3.14 therefore produced 3,241 blockers when
verified on Python 3.11. Dynamic package site numbering also depended on those
hashes, so a hash change could reorder evidence identities.

## Decision

Wave 0 source evidence uses source schema 1:

- full modules use SHA-256 of UTF-8 source after CRLF and CR normalization to LF;
- expressions use SHA-256 of the exact normalized source fragment selected by
  AST source coordinates;
- source identities use path, line, column, end line, and end column;
- multiple analysis labels at one physical source position are stored as one
  sorted `candidate_kinds` set;
- runtime gates never hash or compare `ast.dump()` or `ast.unparse()` output.

The one-time migration decodes legacy expression text only to preserve the
manually approved capability owner. It is guarded by exact old document hashes,
has no bootstrap or force mode, and requires an exact target hash set before it
can write. Ambiguous legacy ownership selects the concrete authority,
projection, or evidence capability over a generic workflow or compatibility
adapter; equal-ranked ambiguity is a hard failure.

## Approved Migration

Old approved hashes:

- capability registry: `138acd5d01c7e3d8ceee6da246f9eb93bf0382185964cf58217822e9db25ce17`
- State Registry: `e08459a5939b824511bc834d4c3704cdcc1b90d8cecea5602fc787fc07def745`
- Package Registry: `0ad599a70b56d7e8eeeba160a8790a217dcd9192f979c225f5888ae5a4cfccfc`
- Wave 0 baseline: `d83b9c5638e2f445fcbaf7dc9b667bf8c01618b66a90d9cc04a4b6f614d544e0`
- waiver registry: `dd7f4d88165d58ea3ff7e3b7d2f144b561fbb92d66bc1c2f1dc3c30ced455aba`

Approved target hashes:

- capability registry: `2ae5c43eb8c7ad6d99600737132796700807e9e571d87b0295b8c60bd97b2d29`
- State Registry: `8d2c87d762d912e7effcebe2265898c2112d2d1b780105f2f94960e6079e5b0b`
- Package Registry: `d0dba235e083e70b4f94a92551b9882234471f14d827ae815b582507ed522d20`
- runtime Package Registry projection: `a6f8805e2dba2c74ef1944c6ce76c5ed58c2db10109270313d193821b5e81a0b`
- capability catalog: `9f8340ebd2c80c32287e3dbe0ab18ad094785eeebb6df242c56a8b43b7086ec5`
- Wave 0 baseline: `6899430a97dabce20158554d9cefaeb501d83173fdd88c0f1143590299c34787`
- dynamic package source positions: `2687`

The capability count, package type set, writer set, State Authority set, and
all quality ceilings remain unchanged. This migration changes evidence format
and removes synthetic duplicate site identities; it does not authorize a new
business surface.

After migration, self-review found that a consistently re-signed State
Registry, baseline, and runtime policy could still pass because those three
documents only proved each other. The follow-up migration is restricted to the
exact source-schema candidate hashes recorded in
`tools/migrate_v144_runtime_state_anchor.py`. It refreshes the one changed
source-evidence row, rebinds State Authority exceptions, and pins the final
runtime policy hash in immutable production code. The normal updater cannot
change this anchor.

Final Wave 0 candidate hashes after that hardening:

- capability registry: `2ae5c43eb8c7ad6d99600737132796700807e9e571d87b0295b8c60bd97b2d29`
- State Registry: `1f353dd270a47efe05a23db997558bbd88bf72e42ee3dc765340c1d6b145742d`
- Package Registry: `c1cf7d2a35580200d0ed3d9c23949451708b2040b3b97d50dedc84d9991bdcf5`
- runtime Package Registry projection: `45879327cf3444f1d9e4993c043d71bc495a0125596ef7791ec7bced312bfe69`
- runtime Package Writer policy: `e7b7674fcba0072ba7100e058edd915de7de83f7f9fff24082a0a28195e3d040`
- capability catalog: `2e83d96e1e6ae2c7921a09af40490c75ab10c4f0b3d7d90d714bcb557e61a2c0`
- Wave 0 baseline: `e8c1ec990d6f7f3330b7dd148e7abdbd6be45f37d74bf3ae671aebd3124f43e7`
- runtime State Authority policy: `21d23353bc5eb425bd66fdf1742035d8660e7df486d9183ac3b27811fa8cf967`
- dynamic package source positions: `2687`

A synchronized re-sign of the State Registry, baseline, exceptions, and
runtime policy must fail against the code anchor even when every embedded hash
is internally consistent.

## Verification

The same checked-in documents must pass, without regeneration, under real
Python 3.11 and Python 3.14 for:

1. `tools/update_v144_wave0_catalog.py --check`
2. `python -m song_agent.cli release-check --profile v14 --skip-tests --json`

CRLF, CR, and LF source fixtures must produce identical module and fragment
hashes. Source-position identities must not depend on hash sorting or analysis
label order.
