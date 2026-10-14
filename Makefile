CC := /usr/bin/clang
OUT ?= ../work/bin/nsp-dawrin
BUILD ?= ../work/build/obj
OCR_BIN ?= ../work/bin
CFLAGS := -O1 -g -Wall -Wno-unused-function -Wno-unused-variable -Isrc/host -Isrc/third_party/openmax-interface -Isrc/gfx/nvn/include -fobjc-arc -mmacosx-version-min=26.0
SRC := $(sort $(wildcard src/macos/*.c src/macos/*.m src/host/*.c src/host/*.S src/gfx/*.c src/gfx/nvn/*.c src/gfx/nvn/*.m src/gfx/nvn/*.S src/gfx/tex/*.c src/gfx/tex/*.m))
OBJ := $(addprefix $(BUILD)/,$(addsuffix .o,$(notdir $(SRC))))
VPATH := src/macos:src/host:src/gfx:src/gfx/nvn:src/gfx/tex
LIBS := -framework Cocoa -framework QuartzCore -framework Metal -framework ImageIO -framework UniformTypeIdentifiers -framework AudioToolbox -framework GameController -framework VideoToolbox -framework CoreMedia -framework CoreVideo
.DEFAULT_GOAL := all
-include $(OBJ:.o=.d)

.PHONY: all
all: $(OUT) $(OCR_BIN)/switch-ocr $(OCR_BIN)/ocr-mask $(OCR_BIN)/warm-metal $(OCR_BIN)/crash-report

$(OCR_BIN)/crash-report: tools/crash_report.m
	@mkdir -p $(OCR_BIN)
	$(CC) -fobjc-arc $< -framework Cocoa -o $@

$(OCR_BIN)/warm-metal: tools/warm_metal.m
	@mkdir -p $(OCR_BIN)
	$(CC) -fobjc-arc $< -framework Foundation -framework Metal -o $@

$(OCR_BIN)/switch-ocr: tools/ocr.swift
	@mkdir -p $(OCR_BIN)
	/usr/bin/swiftc $< -o $@

$(OCR_BIN)/ocr-mask: tools/ocr-mask.swift
	@mkdir -p $(OCR_BIN)
	/usr/bin/swiftc $< -o $@

$(OUT): $(OBJ)
	@mkdir -p $(dir $(OUT))
	$(CC) $(OBJ) $(LIBS) -o $@
	codesign -s - -f $@

$(BUILD)/%.o: % Makefile
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -MMD -MP -MF $(@:.o=.d) -c $< -o $@

.PHONY: clean
clean:
	rm -f $(OUT) $(OBJ) $(OBJ:.o=.d) $(OCR_BIN)/switch-ocr $(OCR_BIN)/ocr-mask $(OCR_BIN)/warm-metal $(OCR_BIN)/crash-report
