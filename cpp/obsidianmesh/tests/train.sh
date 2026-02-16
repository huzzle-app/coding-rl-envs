#!/bin/bash
# Training wrapper: uses sublinear dense rewards instead of sparse evaluation thresholds.
# Sublinear (pass_rate^0.7) rewards early progress more, giving stronger gradient signal
# for RL training compared to the 10-tier step function used in evaluation mode.
#
# Usage: TRAINING_MODE=sublinear bash tests/test.sh
#   or:  bash tests/train.sh  (this script)
#
# Available modes: linear (1:1), sublinear (x^0.7, recommended), smooth (Hermite S-curve)
export TRAINING_MODE="${TRAINING_MODE:-sublinear}"
exec bash "$(dirname "$0")/test.sh"
