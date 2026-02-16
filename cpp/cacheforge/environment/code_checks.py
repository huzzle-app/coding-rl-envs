#!/usr/bin/env python3
"""
CacheForge Code Correctness Checks

Source-level pattern checks for 11 bugs that were previously untested.
Each check reads the relevant source file and returns True if the bug
appears FIXED.

Usage:
    python3 environment/code_checks.py /path/to/cacheforge
"""

import os
import re
import sys


def _read_file(cwd: str, rel_path: str) -> str:
    path = os.path.join(cwd, rel_path)
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def check_l2_signal_handler(cwd: str) -> bool:
    """L2: Signal handler must not call spdlog (not async-signal-safe)."""
    src = _read_file(cwd, "src/main.cpp")
    if not src:
        return False
    pos = src.find("signal_handler")
    if pos == -1:
        return False
    brace = src.find("{", pos)
    if brace == -1:
        return False
    handler_body = src[brace : brace + 500]
    return "spdlog::" not in handler_body


def check_a1_connection_count(cwd: str) -> bool:
    """A1: connection_count() must have lock/mutex."""
    src = _read_file(cwd, "src/server/server.cpp")
    if not src:
        return False
    pos = src.find("connection_count")
    if pos == -1:
        return False
    func_area = src[pos : pos + 200]
    return "lock" in func_area or "mutex" in func_area


def check_a1_broadcast(cwd: str) -> bool:
    """A1: broadcast() must have lock/mutex."""
    src = _read_file(cwd, "src/server/server.cpp")
    if not src:
        return False
    pos = src.find("Server::broadcast")
    if pos == -1:
        return False
    func_area = src[pos : pos + 300]
    return "lock" in func_area or "mutex" in func_area


def check_a5_accepting_atomic(cwd: str) -> bool:
    """A5: accepting_ must be std::atomic<bool>, not volatile bool."""
    src = _read_file(cwd, "src/server/server.h")
    if not src:
        return False
    return "volatile bool accepting_" not in src


def check_b2_string_view(cwd: str) -> bool:
    """B2: as_string_view should not return string_view (dangling hazard)."""
    src = _read_file(cwd, "src/data/value.h")
    if not src:
        return False
    return not bool(re.search(r"string_view\s+as_string_view", src))


def check_c3_const_buffer(cwd: str) -> bool:
    """C3: get_buffer_raw should return const char*."""
    src = _read_file(cwd, "src/server/connection.h")
    if not src:
        return False
    has_non_const = bool(re.search(r"\bchar\s*\*\s*get_buffer_raw", src))
    has_const = bool(re.search(r"const\s+char\s*\*\s*get_buffer_raw", src))
    return not has_non_const or has_const


def check_c4_make_unique(cwd: str) -> bool:
    """C4: save_snapshot must use make_unique, not raw new."""
    src = _read_file(cwd, "src/persistence/snapshot.cpp")
    if not src:
        return False
    return "new SnapshotWriter" not in src


def check_d1_use_after_move(cwd: str) -> bool:
    """D1: enqueue must not access event.key after std::move(event)."""
    src = _read_file(cwd, "src/replication/replicator.cpp")
    if not src:
        return False
    pos = src.find("Replicator::enqueue")
    if pos == -1:
        return False
    func_body = src[pos : pos + 400]
    move_pos = func_body.find("std::move(event)")
    if move_pos == -1:
        return True  # No move found — no use-after-move possible
    after_move = func_body[move_pos + 16 :]
    return "event.key" not in after_move


def check_d2_reinterpret_cast(cwd: str) -> bool:
    """D2: fast_integer_parse must use memcpy, not reinterpret_cast."""
    src = _read_file(cwd, "src/data/value.cpp")
    if not src:
        return False
    return (
        "reinterpret_cast<const int64_t*>" not in src
        and "reinterpret_cast<int64_t*>" not in src
    )


def check_d3_unsigned_counter(cwd: str) -> bool:
    """D3: sequence_counter_ must be uint64_t, not int64_t."""
    src = _read_file(cwd, "src/replication/replicator.h")
    if not src:
        return False
    has_signed = "int64_t sequence_counter_" in src
    has_unsigned = "uint64_t sequence_counter_" in src
    return not has_signed or has_unsigned


def check_d4_move_parameter(cwd: str) -> bool:
    """D4: make_moved_value must take non-const ref to actually move."""
    src = _read_file(cwd, "src/data/value.h")
    if not src:
        return False
    # Bug: const Value& prevents actual move
    return "make_moved_value(const Value&" not in src


def check_e2_format_string(cwd: str) -> bool:
    """E2: No user data as spdlog format string."""
    src = _read_file(cwd, "src/server/connection.cpp")
    if not src:
        return False
    return not bool(re.search(r"spdlog::\w+\(\s*msg\s*\)", src))


# All checks in order
ALL_CHECKS = [
    ("L2", "signal_handler_no_spdlog", check_l2_signal_handler),
    ("A1a", "connection_count_synchronized", check_a1_connection_count),
    ("A1b", "broadcast_synchronized", check_a1_broadcast),
    ("A5", "accepting_is_atomic", check_a5_accepting_atomic),
    ("B2", "string_view_safe", check_b2_string_view),
    ("C3", "get_buffer_returns_const", check_c3_const_buffer),
    ("C4", "snapshot_uses_make_unique", check_c4_make_unique),
    ("D1", "no_use_after_move", check_d1_use_after_move),
    ("D2", "no_reinterpret_cast", check_d2_reinterpret_cast),
    ("D3", "unsigned_sequence_counter", check_d3_unsigned_counter),
    ("D4", "move_parameter_non_const", check_d4_move_parameter),
    ("E2", "no_format_string_vuln", check_e2_format_string),
]


def code_correctness_score(cwd: str) -> float:
    """
    Calculate code correctness score (0.0 to 1.0).
    Returns the fraction of checks that pass (bug is fixed).
    """
    if not cwd:
        return 0.0
    total = len(ALL_CHECKS)
    fixed = sum(1 for _, _, check in ALL_CHECKS if check(cwd))
    return fixed / total if total > 0 else 0.0


def main():
    cwd = sys.argv[1] if len(sys.argv) > 1 else "."
    total = len(ALL_CHECKS)
    fixed = 0

    for bug_id, name, check in ALL_CHECKS:
        result = check(cwd)
        status = "FIXED" if result else "PRESENT"
        print(f"  [{status}] {bug_id}: {name}")
        if result:
            fixed += 1

    score = fixed / total if total > 0 else 0.0
    print(f"\nCode correctness: {fixed}/{total} bugs fixed")
    print(f"{score:.4f}")


if __name__ == "__main__":
    main()
