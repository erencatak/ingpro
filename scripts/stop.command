#!/usr/bin/env bash
# Finder'da çift tıklanınca Terminal'de otomatik açılıp çalışır.
cd "$(dirname "$0")"
./stop.sh
echo
read -n 1 -s -r -p "Kapatmak için bir tuşa bas..."
echo
