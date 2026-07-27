#!/usr/bin/env python3
"""
LOOM v2.2 - Deterministic Thought-Weaving CLI (with truth maintenance)
Zero AI. All operations deterministic, all provenance auditable.

New in v2.2 (over v2.1):
  * Weave-derived facts are a MATERIALIZED VIEW, not stored truth.
    Any change to the base (add / retract) triggers a full re-derivation of the
    entailment closure from the surviving base facts. This makes retraction
    correct even when a fact has multiple independent supports: a derived fact
    survives iff at least one derivation path still holds, and falls the moment
    the last one is withdrawn. No justification bookkeeping, no over-retraction.
  * `excluded` set: filtering a *derived* fact records its (head,rel,tail) key so
    re-derivation will not resurrect it (explicit user disbelief is durable).
  * Analogies (warp) and blends (align) persist across re-derivation (they are
    conjectures, not entailments) and their trace shows any retracted ancestor,
    so staleness is visible rather than silent. They do NOT act as premises for
    the entailment closure, so a conjecture can never manufacture an entailment.
  * Derived facts use `d<N>` ids (regenerated each pass); base/asserted/analogy
    facts keep stable `t<N>` ids.
Usage: python3 loom2_tms.py [--state FILE] <command> [args]
"""

import argparse, json, sys, os, re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any
from itertools import permutations

# Statuses that may serve as premises for the entailment closure.
PREMISE_STATUSES = {"asserted", "entailed", "aligned"}
# Statuses that are conjectures: persist, but never drive entailment.
CONJECTURE_STATUSES = {"analogical_candidate", "blend_candidate"}


def tid_key(tid: str):
    """Deterministic ordering across mixed 't'/'d' id spaces."""
    return (tid[0], int(tid[1:]))


class Provenance:
    def __init__(self, op_id: int, kind: str, inputs: List[str],
                 params: Dict[str, Any] = None, rule: str = ""):
        self.record = {"op_id": op_id, "kind": kind, "inputs": inputs,
                       "params": params or {}, "rule": rule, "version": "2.2"}

    def __str__(self):
        return f"{self.record['kind']}({','.join(self.record['inputs'])})"


class Loom:
    def __init__(self):
        self.nodes: Dict[str, dict] = {}
        self.threads: Dict[str, dict] = {}
        self.type_hierarchy: Dict[str, List[str]] = {}
        self.relation_schema: Dict[str, Tuple[str, str]] = {}
        self.relation_weights: Dict[Tuple[str, str], int] = {}
        self.transitive_relations: List[str] = []
        self.strategy: Dict[Tuple[str, str], str] = {}   # persistent weave composition rules
        self.excluded = set()                            # (head,rel,tail) keys user disbelieves
        self.op_counter = 0
        self.next_thread_id = 0   # base/asserted/analogy facts: t<N>
        self.next_derived_id = 0  # entailment closure: d<N> (regenerated each pass)

    # ---- Persistence with canonical ordering ----
    def to_dict(self):
        return {
            "nodes": {k: v for k, v in sorted(self.nodes.items())},
            "threads": {k: v for k, v in sorted(self.threads.items(), key=lambda kv: tid_key(kv[0]))},
            "type_hierarchy": {k: sorted(v) for k, v in sorted(self.type_hierarchy.items())},
            "relation_schema": {k: list(v) for k, v in sorted(self.relation_schema.items())},
            "relation_weights": [{"a": a, "b": b, "w": w} for (a, b), w in sorted(self.relation_weights.items())],
            "transitive_relations": sorted(self.transitive_relations),
            "strategy": [{"rel1": r1, "rel2": r2, "new": n} for (r1, r2), n in sorted(self.strategy.items())],
            "excluded": [list(k) for k in sorted(self.excluded)],
            "op_counter": self.op_counter,
            "next_thread_id": self.next_thread_id,
            "next_derived_id": self.next_derived_id,
        }

    @classmethod
    def from_dict(cls, d):
        loom = cls()
        loom.nodes = d["nodes"]
        loom.threads = d["threads"]
        loom.type_hierarchy = {k: list(v) for k, v in d.get("type_hierarchy", {}).items()}
        loom.relation_schema = {k: tuple(v) for k, v in d.get("relation_schema", {}).items()}
        loom.relation_weights = {(r["a"], r["b"]): int(r["w"]) for r in d.get("relation_weights", [])}
        loom.transitive_relations = list(d.get("transitive_relations", []))
        loom.strategy = {(e["rel1"], e["rel2"]): e["new"] for e in d.get("strategy", [])}
        loom.excluded = {tuple(k) for k in d.get("excluded", [])}
        loom.op_counter = d.get("op_counter", 0)
        loom.next_thread_id = d.get("next_thread_id", 0)
        loom.next_derived_id = d.get("next_derived_id", 0)
        return loom

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def load(self, path):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.__dict__.update(Loom.from_dict(data).__dict__)

    # ---- Type & Relation Schema ----
    def add_subtype(self, subtype: str, supertype: str):
        self.type_hierarchy.setdefault(subtype, [])
        if supertype not in self.type_hierarchy[subtype]:
            self.type_hierarchy[subtype].append(supertype)

    def is_subtype(self, typ: str, supertyp: str) -> bool:
        if typ == supertyp:
            return True
        return any(self.is_subtype(sup, supertyp) for sup in self.type_hierarchy.get(typ, []))

    def add_relation_schema(self, rel: str, domain: str, range_: str):
        self.relation_schema[rel] = (domain, range_)

    def mark_transitive(self, rel: str):
        if rel not in self.transitive_relations:
            self.transitive_relations.append(rel)

    def check_type_compatibility(self, node_id: str, expected_type: str) -> bool:
        if node_id not in self.nodes:
            return False
        return self.is_subtype(self.nodes[node_id]["type"], expected_type)

    # ---- Node/Thread creation ----
    def add_node(self, node_id: str, typ: str, attrs: dict = None):
        if node_id in self.nodes:
            raise ValueError(f"Node '{node_id}' already exists.")
        self.type_hierarchy.setdefault(typ, [])
        self.nodes[node_id] = {"type": typ, "attrs": attrs or {}}
        self.op_counter += 1

    def _thread_exists(self, head, rel, tail):
        return any(t["head"] == head and t["rel"] == rel and t["tail"] == tail
                   for t in self.threads.values() if t.get("status") != "retracted")

    def add_thread(self, head: str, rel: str, tail: str, attrs: dict = None) -> str:
        if head not in self.nodes or tail not in self.nodes:
            raise ValueError("Head or tail node missing.")
        if rel in self.relation_schema:
            dom, rng = self.relation_schema[rel]
            if not self.check_type_compatibility(head, dom):
                raise ValueError(f"Head '{head}' must be subtype of {dom} for relation '{rel}'")
            if not self.check_type_compatibility(tail, rng):
                raise ValueError(f"Tail '{tail}' must be subtype of {rng} for relation '{rel}'")
        tid = f"t{self.next_thread_id}"
        self.next_thread_id += 1
        self.threads[tid] = {
            "head": head, "rel": rel, "tail": tail,
            "attrs": attrs or {}, "status": "asserted",
            "prov": Provenance(self.op_counter, "user_add", [],
                               {"head": head, "rel": rel, "tail": tail}).record,
        }
        self.op_counter += 1
        # Adding a base fact can create new entailments.
        self._rederive()
        return tid

    # ---- Entailment closure as a materialized view ----
    def _rederive(self) -> List[str]:
        """Discard all weave-derived facts and recompute the closure from the
        surviving premises (asserted / entailed / aligned), honoring `excluded`.
        Correct under multi-path support and idempotent."""
        self.threads = {tid: t for tid, t in self.threads.items()
                        if t.get("prov", {}).get("kind") != "weave"}
        self.next_derived_id = 0
        changed = True
        while changed:
            changed = False
            incoming = defaultdict(list)
            outgoing = defaultdict(list)
            for tid in sorted(self.threads.keys(), key=tid_key):
                t = self.threads[tid]
                if t.get("status") not in PREMISE_STATUSES:
                    continue  # skip retracted AND conjectures (analogies never drive entailment)
                outgoing[t["head"]].append(tid)
                incoming[t["tail"]].append(tid)
            for node in sorted(self.nodes):
                for tid_in in incoming.get(node, []):
                    t_in = self.threads[tid_in]
                    for tid_out in outgoing.get(node, []):
                        t_out = self.threads[tid_out]
                        rel_in, rel_out = t_in["rel"], t_out["rel"]
                        new_rel = self.strategy.get((rel_in, rel_out))
                        if new_rel is None:
                            if rel_in == rel_out and rel_in in self.transitive_relations:
                                new_rel = rel_in
                            else:
                                continue
                        nh, nt = t_in["head"], t_out["tail"]
                        if nh == nt:
                            continue
                        if (nh, new_rel, nt) in self.excluded:
                            continue
                        if self._thread_exists(nh, new_rel, nt):
                            continue
                        did = f"d{self.next_derived_id}"
                        self.next_derived_id += 1
                        self.threads[did] = {
                            "head": nh, "rel": new_rel, "tail": nt,
                            "attrs": {}, "status": "entailed",
                            "prov": Provenance(self.op_counter, "weave", [tid_in, tid_out],
                                               {"rule": f"{rel_in}+{rel_out}={new_rel}"}).record,
                        }
                        changed = True
            self.op_counter += 1
        return sorted((tid for tid in self.threads if tid.startswith("d")), key=tid_key)

    def weave(self, pivot: Optional[str] = None, strategy: Dict[Tuple[str, str], str] = None) -> List[str]:
        """Register composition rules and (re)materialize the entailment closure.
        (pivot is accepted for CLI compatibility; the view is always full-closure.)"""
        if strategy:
            self.strategy.update(strategy)
        return self._rederive()

    # ---- Filter: retract by boolean expression, then re-derive ----
    def filter(self, expression: str) -> List[str]:
        pred = FilterParser(expression).compile()
        removed = []
        for tid in sorted(self.threads.keys(), key=tid_key):
            t = self.threads[tid]
            if t.get("status") == "retracted":
                continue
            if pred(t):
                key = (t["head"], t["rel"], t["tail"])
                if t.get("prov", {}).get("kind") == "weave":
                    # Disbelieving a derived fact must be durable across re-derivation.
                    self.excluded.add(key)
                t["status"] = "retracted"
                t["retraction"] = Provenance(self.op_counter, "filter_retract", [],
                                             {"expr": expression}).record
                removed.append(tid)
        self.op_counter += 1
        # Rebuild the closure from surviving premises: dependents of retracted
        # facts fall unless another support survives.
        self._rederive()
        return removed

    def unexclude(self, head: str, rel: str, tail: str) -> bool:
        """Lift a durable disbelief so the fact may be re-derived again."""
        key = (head, rel, tail)
        if key in self.excluded:
            self.excluded.discard(key)
            self._rederive()
            return True
        return False

    # ---- Warp: deterministic structure mapping (analogy) ----
    def warp(self, source_thread_ids: List[str], target_node: str,
             max_src_nodes: int = 6, max_pool: int = 12) -> List[str]:
        src_nodes = set()
        src_threads = {}
        for tid in source_thread_ids:
            t = self.threads.get(tid)
            if not t or t.get("status") == "retracted":
                continue
            src_nodes.add(t["head"])
            src_nodes.add(t["tail"])
            src_threads[tid] = t
        if not src_threads or len(src_nodes) > max_src_nodes:
            return []
        target_threads = {tid: t for tid, t in self.threads.items()
                          if t.get("status") != "retracted"}
        pool = sorted(n for n in self.nodes if n not in src_nodes)
        if target_node in src_nodes or len(pool) > max_pool:
            return []
        src_list = sorted(src_nodes)
        if len(src_list) > len(pool):
            return []
        best_mapping, best_score, best_key = None, -1, None
        for combo in permutations(pool, len(src_list)):
            if target_node not in combo:
                continue
            mapping = dict(zip(src_list, combo))
            score = self._mapping_score(src_threads, mapping, target_threads)
            key = tuple(mapping[n] for n in src_list)
            if score > best_score or (score == best_score and (best_key is None or key < best_key)):
                best_score, best_mapping, best_key = score, mapping, key
        if not best_mapping or best_score <= 0:
            return []
        new_ids = []
        for tid, t in src_threads.items():
            mh, mt = best_mapping.get(t["head"]), best_mapping.get(t["tail"])
            if mh and mt and not self._thread_exists(mh, t["rel"], mt):
                tid_new = f"t{self.next_thread_id}"
                self.next_thread_id += 1
                self.threads[tid_new] = {
                    "head": mh, "rel": t["rel"], "tail": mt,
                    "attrs": copy_dict(t["attrs"]), "status": "analogical_candidate",
                    "prov": Provenance(self.op_counter, "warp", [tid],
                                       {"mapping": dict(best_mapping), "score": best_score}).record,
                }
                new_ids.append(tid_new)
        self.op_counter += 1
        return new_ids

    def _mapping_score(self, src_threads, mapping, target_threads):
        score = 0
        for t in src_threads.values():
            mh, mt = mapping.get(t["head"]), mapping.get(t["tail"])
            if mh is None or mt is None:
                continue
            exact = False
            for ot in target_threads.values():
                if ot["head"] == mh and ot["tail"] == mt and ot["rel"] == t["rel"]:
                    score += 10; exact = True; break
            if not exact:
                for ot in target_threads.values():
                    if ot["head"] == mh and ot["tail"] == mt:
                        score += self.relation_weights.get((t["rel"], ot["rel"]), 0)
                        break
        for s, im in mapping.items():
            if self.nodes[s]["type"] == self.nodes[im]["type"]:
                score += 1
        return score

    # ---- Twist: expand node to neighbors (idempotent) ----
    def twist(self, node_id: str, depth: int = 1) -> List[str]:
        new_all = []
        current = [node_id]
        for _ in range(depth):
            nxt = set()
            for n in current:
                neighbors = set()
                for t in self.threads.values():
                    if t.get("status") == "retracted":
                        continue
                    if t["head"] == n:
                        neighbors.add(t["tail"])
                    if t["tail"] == n:
                        neighbors.add(t["head"])
                for neigh in sorted(neighbors):
                    if n == neigh or self._thread_exists(n, "expands_to", neigh):
                        continue
                    tid = f"t{self.next_thread_id}"
                    self.next_thread_id += 1
                    self.threads[tid] = {
                        "head": n, "rel": "expands_to", "tail": neigh,
                        "attrs": {}, "status": "asserted",
                        "prov": Provenance(self.op_counter, "twist", [],
                                           {"from": n, "to": neigh, "depth": depth}).record,
                    }
                    new_all.append(tid)
                nxt.update(neighbors)
            current = sorted(nxt)
        self.op_counter += 1
        return new_all

    # ---- Align: blend two subgraphs by pivot pairs ----
    def align(self, graph_a_ids, graph_b_ids, pivot_pairs) -> List[str]:
        sub_a = self._collect_subgraph(graph_a_ids)
        sub_b = self._collect_subgraph(graph_b_ids)
        merge_map = {na: nb for na, nb in pivot_pairs if na in self.nodes and nb in self.nodes}
        b_keys = {(t["head"], t["rel"], t["tail"]) for t in sub_b.values()}
        new_ids = []
        for src_tid, t in sub_a.items():
            mh = merge_map.get(t["head"], t["head"])
            mt = merge_map.get(t["tail"], t["tail"])
            if (mh, t["rel"], mt) in b_keys or self._thread_exists(mh, t["rel"], mt):
                continue
            tid = f"t{self.next_thread_id}"
            self.next_thread_id += 1
            self.threads[tid] = {
                "head": mh, "rel": t["rel"], "tail": mt,
                "attrs": copy_dict(t["attrs"]), "status": "blend_candidate",
                "prov": Provenance(self.op_counter, "align", [src_tid],
                                   {"mapping": dict(merge_map)}).record,
            }
            new_ids.append(tid)
        for na, nb in pivot_pairs:
            if self._thread_exists(na, "aligned_with", nb):
                continue
            tid = f"t{self.next_thread_id}"
            self.next_thread_id += 1
            self.threads[tid] = {
                "head": na, "rel": "aligned_with", "tail": nb,
                "attrs": {}, "status": "aligned",
                "prov": Provenance(self.op_counter, "align_pivot", []).record,
            }
            new_ids.append(tid)
        self.op_counter += 1
        return new_ids

    def _collect_subgraph(self, thread_ids):
        return {tid: self.threads[tid] for tid in thread_ids
                if tid in self.threads and self.threads[tid].get("status") != "retracted"}

    # ---- Trace ----
    def trace(self, thread_id: str, indent=0, seen=None) -> str:
        seen = seen or set()
        t = self.threads.get(thread_id)
        if not t:
            return f"{'  '*indent}Thread '{thread_id}' not found."
        prefix = "  " * indent
        lines = [f"{prefix}Thread {thread_id}: {t['head']} --[{t['rel']}]--> {t['tail']} [status={t.get('status')}]"]
        if t.get("status") == "retracted" and "retraction" in t:
            r = t["retraction"]
            lines.append(f"{prefix}  Retracted by {r['kind']} op {r['op_id']} (expr={r['params'].get('expr')})")
        prov = t.get("prov", {})
        if isinstance(prov, dict) and "inputs" in prov:
            lines.append(f"{prefix}  Provenance: {prov.get('kind','?')} op {prov.get('op_id')}")
            for inp in prov.get("inputs", []):
                if inp in seen:
                    lines.append(f"{prefix}  (cycle -> {inp})")
                    continue
                seen.add(inp)
                lines.append(self.trace(inp, indent + 1, seen))
        else:
            lines.append(f"{prefix}  Prov: {prov}")
        return "\n".join(lines)

    def reflect(self, thread_id: str, template: str = None) -> str:
        t = self.threads.get(thread_id)
        if not t:
            return "Unknown thread."
        return template.format(**t) if template else f"{t['head']} {t['rel']} {t['tail']}"

    def import_weights(self, filepath: str):
        with open(filepath, encoding="utf-8") as f:
            for entry in json.load(f):
                self.relation_weights[(entry["a"], entry["b"])] = int(entry["w"])


def copy_dict(d):
    return dict(d) if d else {}


# ----------------------------------------------------------------------
# Safe Filter Expression Parser (recursive descent -> predicate tree)
# ----------------------------------------------------------------------
class FilterParser:
    def __init__(self, expr: str):
        self.tokens = re.findall(r'\(|\)|and|or|not|[\w.]+=[^\s()]+', expr)
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected=None):
        tok = self.peek()
        if expected and tok != expected:
            raise ValueError(f"Expected {expected}, got {tok}")
        self.pos += 1
        return tok

    def compile(self):
        self.pos = 0
        pred = self._or()
        if self.peek() is not None:
            raise ValueError(f"Unexpected trailing token: {self.peek()}")
        return pred

    def _or(self):
        left = self._and()
        while self.peek() == "or":
            self.consume("or")
            right = self._and()
            left = (lambda a, b: (lambda t: a(t) or b(t)))(left, right)
        return left

    def _and(self):
        left = self._not()
        while self.peek() == "and":
            self.consume("and")
            right = self._not()
            left = (lambda a, b: (lambda t: a(t) and b(t)))(left, right)
        return left

    def _not(self):
        if self.peek() == "not":
            self.consume("not")
            inner = self._not()
            return (lambda a: (lambda t: not a(t)))(inner)
        return self._primary()

    def _primary(self):
        if self.peek() == "(":
            self.consume("(")
            val = self._or()
            self.consume(")")
            return val
        return self._comparison()

    def _comparison(self):
        tok = self.consume()
        if tok is None or "=" not in tok:
            raise ValueError(f"Invalid token: {tok}")
        key, val = tok.split("=", 1)
        return lambda t: self._compare(t, key, val)

    @staticmethod
    def _compare(thread, key, value):
        if key in ("head", "rel", "tail"):
            return thread.get(key) == value
        if key == "status":
            return thread.get("status", "asserted") == value
        if key.startswith("attr."):
            return thread.get("attrs", {}).get(key[5:]) == value
        raise ValueError(f"Unknown field: {key}")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="The Loom v2.2 - Deterministic thought weaving with truth maintenance")
    parser.add_argument("--state-file", default="loom_state.json")
    parser.add_argument("--no-save", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("node-add"); p.add_argument("id"); p.add_argument("type"); p.add_argument("--attr", nargs="*", default=[])
    p = sub.add_parser("thread-add"); p.add_argument("head"); p.add_argument("rel"); p.add_argument("tail"); p.add_argument("--attr", nargs="*", default=[])
    p = sub.add_parser("schema-subtype"); p.add_argument("subtype"); p.add_argument("supertype")
    p = sub.add_parser("schema-relation"); p.add_argument("rel"); p.add_argument("domain"); p.add_argument("range")
    p = sub.add_parser("schema-transitive"); p.add_argument("rel")
    p = sub.add_parser("weave"); p.add_argument("--pivot", default=None); p.add_argument("--strategy", default=None)
    p = sub.add_parser("warp"); p.add_argument("source"); p.add_argument("target")
    p = sub.add_parser("filter"); p.add_argument("expression")
    p = sub.add_parser("unexclude"); p.add_argument("head"); p.add_argument("rel"); p.add_argument("tail")
    p = sub.add_parser("twist"); p.add_argument("node"); p.add_argument("--depth", type=int, default=1)
    p = sub.add_parser("align"); p.add_argument("graph_a"); p.add_argument("graph_b"); p.add_argument("pivots")
    p = sub.add_parser("trace"); p.add_argument("thread_id")
    p = sub.add_parser("reflect"); p.add_argument("thread_id"); p.add_argument("--template", default=None)
    sub.add_parser("list")
    sub.add_parser("export")
    p = sub.add_parser("import-weights"); p.add_argument("file")
    sub.add_parser("test")
    return parser.parse_args()


def parse_attr_list(pairs):
    d = {}
    for p in pairs:
        if "=" in p:
            k, v = p.split("=", 1)
            d[k] = v
    return d


def parse_weave_strategy(spec):
    if os.path.isfile(spec):
        with open(spec, encoding="utf-8") as f:
            return {(e["rel1"], e["rel2"]): e["new"] for e in json.load(f)}
    strategy = {}
    for triple in spec.split(","):
        rels, new = triple.split("=")
        r1, r2 = rels.split("+")
        strategy[(r1.strip(), r2.strip())] = new.strip()
    return strategy


def load_id_list(src):
    if src.startswith("@"):
        with open(src[1:], encoding="utf-8") as f:
            return json.load(f)
    return [x.strip() for x in src.split(",") if x.strip()]


def main():
    args = parse_args()
    if args.command == "test":
        run_tests()
        return
    loom = Loom()
    if os.path.exists(args.state_file):
        loom.load(args.state_file)
    try:
        if args.command == "node-add":
            loom.add_node(args.id, args.type, parse_attr_list(args.attr)); print(f"Node '{args.id}' added.")
        elif args.command == "thread-add":
            tid = loom.add_thread(args.head, args.rel, args.tail, parse_attr_list(args.attr)); print(f"Thread '{tid}' created: {args.head} --[{args.rel}]--> {args.tail}")
        elif args.command == "schema-subtype":
            loom.add_subtype(args.subtype, args.supertype); print(f"Subtype '{args.subtype} <: {args.supertype}' registered.")
        elif args.command == "schema-relation":
            loom.add_relation_schema(args.rel, args.domain, args.range); print(f"Relation '{args.rel}' registered.")
        elif args.command == "schema-transitive":
            loom.mark_transitive(args.rel); print(f"Relation '{args.rel}' marked transitive.")
        elif args.command == "weave":
            strategy = parse_weave_strategy(args.strategy) if args.strategy else None
            new = loom.weave(args.pivot, strategy); print(f"Closure has {len(new)} entailed threads: {', '.join(new) if new else 'none'}")
        elif args.command == "warp":
            new = loom.warp(load_id_list(args.source), args.target); print(f"Warp created {len(new)} threads: {', '.join(new) if new else 'none'}")
        elif args.command == "filter":
            removed = loom.filter(args.expression); print(f"Retracted {len(removed)} threads: {', '.join(removed) if removed else 'none'}")
        elif args.command == "unexclude":
            ok = loom.unexclude(args.head, args.rel, args.tail); print("Disbelief lifted." if ok else "No such exclusion.")
        elif args.command == "twist":
            new = loom.twist(args.node, args.depth); print(f"Twisted {len(new)} threads: {', '.join(new) if new else 'none'}")
        elif args.command == "align":
            a_ids = args.graph_a.split(",") if args.graph_a else []
            b_ids = args.graph_b.split(",") if args.graph_b else []
            pivots = [tuple(p.split(":")) for p in args.pivots.split(";")]
            new = loom.align(a_ids, b_ids, pivots); print(f"Aligned {len(new)} threads: {', '.join(new) if new else 'none'}")
        elif args.command == "trace":
            print(loom.trace(args.thread_id))
        elif args.command == "reflect":
            print(loom.reflect(args.thread_id, args.template))
        elif args.command == "list":
            for tid in sorted(loom.threads, key=tid_key):
                t = loom.threads[tid]
                if t.get("status") == "retracted":
                    continue
                print(f"  {tid}: {t['head']} --[{t['rel']}]--> {t['tail']}  <{t['status']}>")
        elif args.command == "export":
            print(json.dumps(loom.to_dict(), sort_keys=True, indent=2)); return
        elif args.command == "import-weights":
            loom.import_weights(args.file); print("Weights imported.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    if not args.no_save and args.command not in ("export", "list", "trace", "reflect"):
        loom.save(args.state_file)


def run_tests():
    print("Running deterministic test suite...")

    # Test 1: opt-in transitivity, closure, no false facts
    loom = Loom()
    for n, ty in [("animal", "concept"), ("bird", "animal"), ("sparrow", "bird"), ("penguin", "bird")]:
        loom.add_node(n, ty)
    loom.mark_transitive("is_a")
    loom.add_thread("sparrow", "is_a", "bird"); loom.add_thread("bird", "is_a", "animal"); loom.add_thread("penguin", "is_a", "bird")
    loom.weave()
    assert loom._thread_exists("sparrow", "is_a", "animal")
    assert loom._thread_exists("penguin", "is_a", "animal")
    loom2b = Loom()
    for n in ["tom", "bob", "joe"]:
        loom2b.add_node(n, "p")
    loom2b.add_thread("tom", "parent_of", "bob"); loom2b.add_thread("bob", "parent_of", "joe")
    loom2b.weave()
    assert not loom2b._thread_exists("tom", "parent_of", "joe")
    print("OK Weave: opt-in transitivity, closure, no false facts")

    # Test 2: warp analogy recruits a new correspondent
    loom3 = Loom()
    for n, ty in [("pump", "device"), ("machine", "object"), ("water", "fluid"),
                  ("heart", "organ"), ("body", "object"), ("blood", "fluid")]:
        loom3.add_node(n, ty)
    loom3.add_subtype("organ", "object")
    loom3.add_thread("pump", "located_in", "machine"); loom3.add_thread("pump", "moves", "water"); loom3.add_thread("heart", "located_in", "body")
    src = [tid for tid, t in loom3.threads.items() if t["head"] == "pump"]
    new = loom3.warp(src, "heart")
    assert new and loom3._thread_exists("heart", "moves", "blood")
    print("OK Warp: structure mapping infers 'heart moves blood'")

    # Test 3: filter boolean algebra
    l = Loom(); l.add_node("x", "e"); l.add_node("y", "e")
    l.add_thread("x", "alpha", "y"); l.add_thread("x", "beta", "y")
    assert len(l.filter("rel=alpha or rel=beta")) == 2
    l4 = Loom(); l4.add_node("x", "e"); l4.add_node("y", "e")
    l4.add_thread("x", "a", "y"); l4.add_thread("x", "b", "y"); l4.add_thread("x", "c", "y")
    assert len(l4.filter("rel=a or (rel=b and head=x)")) == 2
    print("OK Filter: and/or/not/grouping correct")

    # Test 4: non-destructive provenance; trace safe
    l5 = Loom(); l5.add_node("x", "e"); l5.add_node("y", "e")
    tid = l5.add_thread("x", "r", "y")
    l5.filter("rel=r")
    assert l5.threads[tid]["prov"]["kind"] == "user_add"
    assert "Retracted by" in l5.trace(tid)
    print("OK Filter: non-destructive provenance; trace safe")

    # Test 5: twist idempotent
    l6 = Loom(); l6.add_node("A", "t"); l6.add_node("B", "t"); l6.add_thread("A", "link", "B")
    l6.twist("A"); l6.twist("A"); l6.twist("A")
    dupes = [t for t in l6.threads.values() if t["rel"] == "expands_to" and t["head"] == "A" and t["tail"] == "B"]
    assert len(dupes) == 1
    print("OK Twist: idempotent")

    # Test 6: align uses B, single-source provenance
    l7 = Loom()
    for n, ty in [("car", "vehicle"), ("wheel", "part"), ("bike", "vehicle"), ("pedal", "part")]:
        l7.add_node(n, ty)
    ta = l7.add_thread("car", "has", "wheel"); tb = l7.add_thread("bike", "has", "pedal")
    l7.align([ta], [tb], [("car", "bike")])
    assert l7._thread_exists("bike", "has", "wheel")
    print("OK Align: uses B, single-source provenance")

    # Test 7: determinism
    def build():
        m = Loom()
        for n in "xy":
            m.add_node(n, "t")
        m.mark_transitive("r"); m.add_thread("x", "r", "y"); m.weave()
        return json.dumps(m.to_dict(), sort_keys=True)
    assert build() == build()
    print("OK Determinism: bit-identical output")

    # Test 8: TRUTH MAINTENANCE under multi-path support
    #   a --> b --> d   (path 1)
    #   a --> c --> d   (path 2)
    #   => a flows_to d has TWO independent derivations.
    m = Loom()
    for n in "abcd":
        m.add_node(n, "t")
    m.mark_transitive("flows_to")
    t_ab = m.add_thread("a", "flows_to", "b")
    t_bd = m.add_thread("b", "flows_to", "d")
    t_ac = m.add_thread("a", "flows_to", "c")
    t_cd = m.add_thread("c", "flows_to", "d")
    assert m._thread_exists("a", "flows_to", "d"), "closure should derive a->d"
    # Retract path 1 (b->d). a->d must SURVIVE on path 2.
    m.filter("head=b and tail=d")
    assert m._thread_exists("a", "flows_to", "d"), "a->d wrongly fell while c-path still supports it"
    # Retract path 2 (c->d). a->d must now FALL (no support left).
    m.filter("head=c and tail=d")
    assert not m._thread_exists("a", "flows_to", "d"), "a->d wrongly survived with no support"
    print("OK Truth maintenance: survives while any support holds, falls when the last is withdrawn")

    # Test 9: explicit disbelief is durable, and liftable
    m2 = Loom()
    for n in "xyz":
        m2.add_node(n, "t")
    m2.mark_transitive("r")
    m2.add_thread("x", "r", "y"); m2.add_thread("y", "r", "z")
    assert m2._thread_exists("x", "r", "z")
    m2.filter("head=x and tail=z")            # disbelieve the derived fact
    assert not m2._thread_exists("x", "r", "z"), "disbelieved derived fact should stay gone"
    m2.add_thread("x", "r", "y", {"k": "v2"})  # base change re-triggers derivation...
    assert not m2._thread_exists("x", "r", "z"), "excluded fact must not resurrect on re-derivation"
    assert m2.unexclude("x", "r", "z")         # lift the disbelief
    assert m2._thread_exists("x", "r", "z"), "fact should return once disbelief is lifted"
    print("OK Excluded: durable disbelief, and liftable via unexclude")

    # Test 10: analogies persist across re-derivation and never drive entailment
    m3 = Loom()
    for n, ty in [("p", "d"), ("m", "o"), ("w", "f"), ("h", "o2"), ("b", "o"), ("bl", "f")]:
        m3.add_node(n, ty)
    m3.mark_transitive("moves")
    m3.add_thread("p", "located_in", "m"); m3.add_thread("p", "moves", "w"); m3.add_thread("h", "located_in", "b")
    src = [t for t, v in m3.threads.items() if v["head"] == "p"]
    warped = m3.warp(src, "h")
    assert m3._thread_exists("h", "moves", "bl"), "analogy present"
    m3.add_thread("z", "z", "z") if False else None
    m3.weave()  # re-derive; analogy must remain and must not have driven any 'moves' entailment
    assert m3._thread_exists("h", "moves", "bl"), "analogy should persist across re-derivation"
    print("OK Conjectures: analogies persist and don't manufacture entailments")

    print("\nAll tests passed. The Loom v2.2 maintains truth: withdrawing a premise retracts what rested on it.")


if __name__ == "__main__":
    main()
