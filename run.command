#!/bin/zsh
set -e
cd -- "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  printf 'Menyiapkan Tourguider untuk pertama kali…\n'
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else "Tourguider memerlukan Python 3.11 atau lebih baru.")'
  python3 -m venv .venv
fi
if [[ ! -f .venv/.temu-ready ]]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.temu-ready
fi
if [[ ! -f artifacts/model.joblib || ! -f artifacts/evaluation.json ]]; then
  .venv/bin/python -m backend.train
fi
printf '\nTourguider: http://127.0.0.1:8765\nTekan Control+C untuk menghentikan aplikasi.\n\n'
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
