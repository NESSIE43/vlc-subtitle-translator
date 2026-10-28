#!/bin/sh
# Linux başlatıcı / Linux launcher
cd "$(dirname "$0")" || exit 1
exec python3 vlc_subtitle_translator.py "$@"
