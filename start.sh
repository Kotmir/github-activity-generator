#!/usr/bin/env sh
# GitHub Activity Generator — launcher (author: kotmir)
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    exec python3 run.py "$@"
elif command -v python >/dev/null 2>&1; then
    exec python run.py "$@"
fi
echo "[RU] Python не найден. Установите Python 3.8+ (https://www.python.org/downloads/)"
echo "[EN] Python not found. Install Python 3.8+ (https://www.python.org/downloads/)"
exit 1
