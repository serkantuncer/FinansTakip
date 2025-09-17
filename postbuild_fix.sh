#!/bin/bash

APP_PATH="dist/FinansTakipSistemi.app/Contents/MacOS"

echo "🔁 .dylib dosyalarının path'leri düzeltiliyor..."

for dylib in "$APP_PATH"/*.dylib; do
    name=$(basename "$dylib")
    echo "➡️  $name için install_name_tool çalıştırılıyor..."
    install_name_tool -id "@executable_path/$name" "$dylib"
done

echo "✅ Tüm .dylib dosyalarının ID'leri ayarlandı."
