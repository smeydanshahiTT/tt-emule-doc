# SPDX-FileCopyrightText: © 2026 Tenstorrent USA, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""TSan self-test / positive control, pytest edition.

The Python mirror of test_tsan_data_race.cpp. It validates the *pytest* TSan
pipeline -- i.e. that running pytests with the TSan runtime preloaded
(LD_PRELOAD of libclang_rt.tsan + an instrumented extension) actually catches
data races -- the same way the gtest validates it for native binaries.

Why it is built this way: a pure-Python data race will NOT trip TSan. The GIL
serializes Python bytecode, and CPython's own internals are benign/suppressed.
The race has to happen in TSan-instrumented C running on real threads. ctypes
RELEASES the GIL during a foreign-function call, so two Python threads each
calling a racy function in a TSan-built .so run its loop truly concurrently ->
genuine data race on a C global -> TSan reports it. This is the same shape as
Python driving the instrumented ttnn/_ttnn extension.

`g_counter` is `volatile` so the increment is a real load+store every iteration
(otherwise -O1 folds the loop to a single add and the race window is too small
to observe reliably).

To run (must be under the TSan python env -- LD_PRELOAD the tsan runtime +
TSAN_OPTIONS set, per the TSan run steps). Use -s so pytest does not swallow the
TSan report on stderr:

    python_env/bin/python -m pytest \
        tests/tt_metal/tt_metal/api/test_tsan_data_race.py -s

Expected: stderr shows "WARNING: ThreadSanitizer: data race" from
test_data_race_positive_control, and nothing from test_no_race_negative_control.

Auto-skipped when not running under ThreadSanitizer (e.g. a normal Release
pytest run) or when clang is unavailable, so it is inert in regular CI.
"""

import ctypes
import shutil
import subprocess
import threading

import pytest

N_THREADS = 4
ITERATIONS = 2_000_000

# Deliberately racy (and deliberately safe) C, compiled with -fsanitize=thread.
_RACE_C = r"""
#include <pthread.h>

/* volatile -> a real load+store every iteration so the race window stays wide
   even at -O1 (otherwise the loop folds to a single add). */
static volatile long g_counter = 0;
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;

/* No synchronization: a data race when called from multiple threads. */
void racy_increment(long n) {
    for (long i = 0; i < n; ++i) {
        g_counter = g_counter + 1;
    }
}

/* Mutex-guarded: no race. */
void safe_increment(long n) {
    for (long i = 0; i < n; ++i) {
        pthread_mutex_lock(&g_lock);
        g_counter = g_counter + 1;
        pthread_mutex_unlock(&g_lock);
    }
}
"""


def _running_under_tsan() -> bool:
    try:
        with open("/proc/self/maps") as f:
            maps = f.read()
    except OSError:
        return False
    return "libclang_rt.tsan" in maps or "libtsan" in maps


pytestmark = pytest.mark.skipif(
    not _running_under_tsan(),
    reason="requires a ThreadSanitizer run (LD_PRELOAD the tsan runtime)",
)


@pytest.fixture(scope="module")
def race_lib(tmp_path_factory):
    """Compile the racy helper as a TSan-instrumented .so and load it via ctypes.

    The .so does not link the tsan runtime itself (shared libs leave the
    __tsan_* symbols undefined); they resolve against the runtime already
    preloaded into this process, which is exactly why the skip guard above
    requires running under TSan.
    """
    clang = shutil.which("clang-20") or shutil.which("clang")
    if clang is None:
        pytest.skip("clang not found to build the TSan race helper")

    d = tmp_path_factory.mktemp("tsan_race")
    src = d / "race.c"
    so = d / "librace.so"
    src.write_text(_RACE_C)
    subprocess.run(
        [clang, "-std=c11", "-O1", "-g", "-fsanitize=thread", "-fPIC", "-shared", str(src), "-o", str(so)],
        check=True,
    )

    lib = ctypes.CDLL(str(so))  # CDLL releases the GIL during calls
    lib.racy_increment.argtypes = [ctypes.c_long]
    lib.safe_increment.argtypes = [ctypes.c_long]
    return lib


def _hammer(fn):
    threads = [threading.Thread(target=fn, args=(ITERATIONS,)) for _ in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_data_race_positive_control(race_lib):
    # ctypes drops the GIL, so these run concurrently in instrumented C ->
    # TSan must print "WARNING: ThreadSanitizer: data race" to stderr.
    _hammer(race_lib.racy_increment)


def test_no_race_negative_control(race_lib):
    # Mutex-guarded: TSan must stay silent.
    _hammer(race_lib.safe_increment)
