// SPDX-FileCopyrightText: © 2026 Tenstorrent USA, Inc.
//
// SPDX-License-Identifier: Apache-2.0

// TSan self-test / positive control.
//
// Unlike the ASAN emule checks (which call abort() and are asserted with
// EXPECT_DEATH), this validates that a *ThreadSanitizer* build is actually
// instrumenting and running. Stock TSan does not abort on a race by default --
// it prints "WARNING: ThreadSanitizer: data race ..." to stderr and continues.
// So the proof that your run used TSan is: the PositiveControl test emits that
// warning, and the NegativeControl test does not.
//
// Requires a TSan build (cmake -DCMAKE_BUILD_TYPE=TSan, i.e.
// build_metal.sh --build-type TSan). On a non-TSan build it just passes silently
// with no warning -- which is itself the tell that TSan was NOT active.
//
// To run (native gtest binary is linked with the TSan runtime directly -- no
// LD_PRELOAD needed, that is only for the Python ttnn extension):
//
//   # see the race report and keep running:
//   $ROOT/tt-metal/build_TSan/test/tt_metal/unit_tests_api \
//       --gtest_filter="TSanSelfTest.*"
//
//   # turn a detected race into a hard, non-zero-exit failure:
//   TSAN_OPTIONS="halt_on_error=1" \
//   $ROOT/tt-metal/build_TSan/test/tt_metal/unit_tests_api \
//       --gtest_filter="TSanSelfTest.DataRace_PositiveControl"
//
// Standalone quick check (no metal build at all):
//   clang++ -std=c++20 -O1 -g -fsanitize=thread test_tsan_data_race.cpp \
//       -lgtest -lgtest_main -pthread && ./a.out

#include <gtest/gtest.h>

#include <atomic>
#include <cstdint>
#include <mutex>
#include <thread>
#include <vector>

namespace {

constexpr int kThreads = 4;
constexpr int kIterations = 200000;

// POSITIVE CONTROL: two+ threads read-modify-write the same plain (non-atomic)
// memory with no synchronization. This is a textbook data race; TSan must report
// it. The arithmetic result is intentionally ignored -- the value under TSan is
// the warning on stderr, not the sum.
TEST(TSanSelfTest, DataRace_PositiveControl) {
    int shared_counter = 0;  // deliberately NOT atomic, NOT lock-guarded

    std::vector<std::thread> threads;
    threads.reserve(kThreads);
    for (int t = 0; t < kThreads; ++t) {
        threads.emplace_back([&shared_counter]() {
            for (int i = 0; i < kIterations; ++i) {
                shared_counter = shared_counter + 1;  // racy RMW
            }
        });
    }
    for (auto& th : threads) {
        th.join();
    }

    // Touch the result so the compiler cannot optimize the race away.
    EXPECT_GE(shared_counter, kIterations);
    // Under TSan you will also see, on stderr:
    //   WARNING: ThreadSanitizer: data race (pid=...)
    //     ... on `shared_counter` ...
    // If you set TSAN_OPTIONS=halt_on_error=1, the process exits non-zero here.
}

// NEGATIVE CONTROL: identical workload, but every access is serialized by a
// mutex. A correctly instrumented TSan run prints NOTHING for this test. If you
// see a race warning here, the test (or TSan) is misbehaving.
TEST(TSanSelfTest, NoRace_NegativeControl) {
    int shared_counter = 0;
    std::mutex mu;

    std::vector<std::thread> threads;
    threads.reserve(kThreads);
    for (int t = 0; t < kThreads; ++t) {
        threads.emplace_back([&shared_counter, &mu]() {
            for (int i = 0; i < kIterations; ++i) {
                std::lock_guard<std::mutex> lock(mu);
                shared_counter = shared_counter + 1;
            }
        });
    }
    for (auto& th : threads) {
        th.join();
    }

    // With full mutual exclusion the count is exact and there is no race.
    EXPECT_EQ(shared_counter, kThreads * kIterations);
}

}  // namespace
