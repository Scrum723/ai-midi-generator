#!/bin/bash
# Build script for complete packaged macOS .app
# Part of the plan to deliver "complete packaged program"

set -e

cd "$(dirname "$0")"

echo "Ensuring py2app is installed..."
source .venv/bin/activate
pip install py2app --quiet

echo "Cleaning previous builds..."
rm -rf build dist

echo "Building .app bundle..."
python setup.py py2app

echo "Build complete!"
echo "App is in: dist/AI-MIDI-Generator.app"
echo ""
echo "To create a DMG (optional, requires hdiutil or create-dmg tool):"
echo "  hdiutil create -volname AI-MIDI-Generator -srcfolder dist/AI-MIDI-Generator.app -ov -format UDZO AI-MIDI-Generator.dmg"
echo ""
echo "For VST plugin part, see vst/README.md (requires full Xcode + JUCE for real binary)."
