#!/bin/bash
#
# JIT Liquidity Opportunity Detector Wrapper
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  JIT Liquidity Opportunity Detector"
echo "=========================================="
echo ""
echo "Monitors flashblocks for Just-In-Time"
echo "liquidity opportunities on Uniswap V3"
echo ""
echo "Usage:"
echo "  ./jit_detector.sh [duration_minutes]"
echo ""
echo "Examples:"
echo "  ./jit_detector.sh 30  - Monitor for 30 minutes"
echo "  ./jit_detector.sh 120 - Monitor for 2 hours"
echo ""

DURATION=${1:-60}

echo "Starting JIT detector for ${DURATION} minutes..."
echo ""

python3 "${SCRIPT_DIR}/jit_opportunity_detector.py" "${DURATION}"
