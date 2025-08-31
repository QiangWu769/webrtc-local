
import struct

def get_tbs_index_string(tbs_index):
    """Convert TBS index to string"""
    TBS_MAP = {
        0: "TBS_Index_0", 1: "TBS_Index_1", 2: "TBS_Index_2", 3: "TBS_Index_3",
        4: "TBS_Index_4", 5: "TBS_Index_5", 6: "TBS_Index_6", 7: "TBS_Index_7",
        8: "TBS_Index_8", 9: "TBS_Index_9", 10: "TBS_Index_10", 11: "TBS_Index_11",
        12: "TBS_Index_12", 13: "TBS_Index_13", 14: "TBS_Index_14", 15: "TBS_Index_15",
        16: "TBS_Index_16", 17: "TBS_Index_17", 18: "TBS_Index_18", 19: "TBS_Index_19",
        20: "TBS_Index_20", 21: "TBS_Index_21", 22: "TBS_Index_22", 23: "TBS_Index_23",
        24: "TBS_Index_24", 25: "TBS_Index_25", 26: "TBS_Index_26", 27: "TBS_Index_26A",
        28: "TBS_Index_27", 29: "TBS_Index_28", 30: "TBS_Index_29", 31: "TBS_Index_30",
        32: "TBS_Index_31", 33: "TBS_Index_32", 34: "TBS_Index_32A", 35: "TBS_Index_33"
    }
    if tbs_index not in TBS_MAP:
        print("  DEBUG: Invalid TBS index value: {} (0x{:02X})".format(tbs_index, tbs_index))
    return TBS_MAP.get(tbs_index, "invalid")

# Test with a value that should produce invalid
print("Testing TBS extraction:")
print("="*40)

# Simulate what happens with common invalid values
for test_val in [36, 40, 48, 56, 60, 63]:
    result = get_tbs_index_string(test_val)
    print("TBS index {} -> '{}'".format(test_val, result))
