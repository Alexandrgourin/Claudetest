#!/bin/bash
#
# Мониторинг мемпула на Base через reth ноду
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "  Мониторинг мемпула Base (Reth)"
echo "=========================================="
echo ""
echo "Доступные режимы:"
echo "  1. Тест всех методов:     ./monitor_mempool.sh test"
echo "  2. Мониторинг (10 итераций): ./monitor_mempool.sh"
echo "  3. Мониторинг N итераций: ./monitor_mempool.sh <интервал> <итерации>"
echo ""

if [ "$1" == "test" ]; then
    echo "Запуск тестирования всех методов..."
    python3 "${SCRIPT_DIR}/monitor_mempool.py" test
else
    INTERVAL=${1:-5}
    ITERATIONS=${2:-10}
    echo "Запуск мониторинга: интервал ${INTERVAL}с, ${ITERATIONS} итераций"
    echo ""
    python3 "${SCRIPT_DIR}/monitor_mempool.py" "${INTERVAL}" "${ITERATIONS}"
fi
