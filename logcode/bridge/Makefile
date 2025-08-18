CC := $(ANDROID_NDK_HOME)/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android21-clang
CFLAGS := -std=c99 -Werror -fPIE -pie

diag_bridge: diag_bridge.c
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -f diag_bridge

.PHONY: clean
