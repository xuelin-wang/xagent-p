# Case Domain Records Stay Immutable

Symbol: ✅

Business records such as facts and case plans should be append-only and
separate from the execution ledger. Facts may be linked with immutable edges
like `derived_from` or `negates`; case plans should use latest-wins semantics
without plan-to-plan edges.

Why it matters:
- The runtime audit remains truthful and replayable.
- Business meaning can evolve without mutating prior records in place.

Future implication:
- Future case-data writes should emit new records, not edit existing ones.
- Use edges only where history or contradiction tracking adds value, especially
  for facts, not for case plans.
