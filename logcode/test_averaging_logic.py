#!/usr/bin/env python3
"""
Test script to verify the ConsistentRatioCalculator averaging logic
"""

# Simplified version of ConsistentRatioCalculator for testing
class ConsistentRatioCalculator:
    def __init__(self):
        self.first_nonzero_bsr = None
        self.group_buffer = []
        self.results = []  # For testing: store all results

    def get_averaged_ratio(self, tti, allocated, requested, individual_ratio):
        is_nonzero = requested > 0

        if is_nonzero:
            # Flush previous group if exists
            if len(self.group_buffer) > 0:
                self._flush_group_to_results()

            # Start new group with this non-zero BSR
            self.first_nonzero_bsr = (tti, allocated, requested, individual_ratio)
            self.group_buffer = [(tti, allocated, requested, individual_ratio)]

            return (individual_ratio, False)
        else:
            # Zero BSR - add to current group if there's a non-zero BSR before it
            if self.first_nonzero_bsr is not None:
                self.group_buffer.append((tti, allocated, requested, individual_ratio))
                return (individual_ratio, False)
            else:
                # No non-zero BSR yet, write this zero BSR immediately with its own ratio
                self.results.append((tti, allocated, requested, individual_ratio))
                return (individual_ratio, True)

    def _flush_group_to_results(self):
        if len(self.group_buffer) == 0:
            return

        # Calculate average ratio for the group
        total_ratio = sum(r for _, _, _, r in self.group_buffer)
        avg_ratio = total_ratio / len(self.group_buffer)

        # Store all entries in the group with the averaged ratio
        for tti, allocated, requested, _ in self.group_buffer:
            self.results.append((tti, allocated, requested, avg_ratio))

        # Clear the buffer
        self.group_buffer = []
        self.first_nonzero_bsr = None

    def finalize(self):
        if len(self.group_buffer) > 0:
            self._flush_group_to_results()


# Test with the user's example
print("Testing with user's example:")
print("TTI 4409: requested=376 (非零), ratio=0.000000")
print("TTI 4411: requested=0 (零), ratio=2.000000")
print("TTI 4416: requested=0 (零), ratio=2.000000")
print("TTI 4435: requested=67 (非零), ratio=1.567164")
print()

calc = ConsistentRatioCalculator()

# TTI 4409: non-zero, ratio=0.000000
ratio, should_write = calc.get_averaged_ratio(4409, 0, 376, 0.000000)
print(f"TTI 4409: ratio={ratio:.6f}, should_write={should_write}")

# TTI 4411: zero, ratio=2.000000
ratio, should_write = calc.get_averaged_ratio(4411, 253, 0, 2.000000)
print(f"TTI 4411: ratio={ratio:.6f}, should_write={should_write}")

# TTI 4416: zero, ratio=2.000000
ratio, should_write = calc.get_averaged_ratio(4416, 109, 0, 2.000000)
print(f"TTI 4416: ratio={ratio:.6f}, should_write={should_write}")

# TTI 4435: non-zero, ratio=1.567164 (this triggers flush of previous group)
ratio, should_write = calc.get_averaged_ratio(4435, 105, 67, 1.567164)
print(f"TTI 4435: ratio={ratio:.6f}, should_write={should_write}")

# Finalize to flush the last group
calc.finalize()

print("\n=== Expected Results ===")
print("TTI 4409: ratio = (0 + 2 + 2) / 3 = 1.333333")
print("TTI 4411: ratio = (0 + 2 + 2) / 3 = 1.333333")
print("TTI 4416: ratio = (0 + 2 + 2) / 3 = 1.333333")
print("TTI 4435: ratio = 1.567164 (own ratio)")

print("\n=== Actual Results (what will be written to file) ===")
for tti, allocated, requested, ratio in calc.results:
    print(f"TTI {tti}: allocated={allocated}, requested={requested}, ratio={ratio:.6f}")

# Verify correctness
expected = [
    (4409, 0, 376, 1.333333),
    (4411, 253, 0, 1.333333),
    (4416, 109, 0, 1.333333),
    (4435, 105, 67, 1.567164)
]

print("\n=== Verification ===")
all_correct = True
for i, (exp_tti, exp_allocated, exp_requested, exp_ratio) in enumerate(expected):
    if i < len(calc.results):
        act_tti, act_allocated, act_requested, act_ratio = calc.results[i]
        ratio_match = abs(act_ratio - exp_ratio) < 0.000001
        if exp_tti == act_tti and exp_allocated == act_allocated and exp_requested == act_requested and ratio_match:
            print(f"✓ TTI {exp_tti}: PASS")
        else:
            print(f"✗ TTI {exp_tti}: FAIL - Expected ({exp_tti}, {exp_allocated}, {exp_requested}, {exp_ratio:.6f}), "
                  f"Got ({act_tti}, {act_allocated}, {act_requested}, {act_ratio:.6f})")
            all_correct = False
    else:
        print(f"✗ TTI {exp_tti}: FAIL - Missing result")
        all_correct = False

if all_correct:
    print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
else:
    print("\n✗✗✗ SOME TESTS FAILED! ✗✗✗")
