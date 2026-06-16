"""
setup.py for building the AI MIDI Generator as a macOS .app bundle using py2app.

Usage:
    pip install py2app
    python setup.py py2app

This will produce dist/AI-MIDI-Generator.app

For a DMG, you can use additional tools after.

The app uses the gui.app as entry point.
Includes the midi_generator package.

Note: This is for the standalone program part of the plan.
For VST, see vst/ directory.
"""

from setuptools import setup
import os

APP = ['gui/app.py']
DATA_FILES = [
    'resources',
    # Add any other data like soundfonts if bundled, but preview downloads on demand.
]
OPTIONS = {
    'argv_emulation': False,
    'packages': [
        'midi_generator', 'customtkinter', 'tkinter',
        'charset_normalizer', 'requests',  # fix requests char detection warning (use modern pure-python one)
    ],
    'includes': [
        'mido', 'rtmidi', 'openai', 'anthropic', 'instructor', 'pydantic',
        'tkinter', 'tkinter.filedialog', 'tkinter.messagebox',
        'charset_normalizer',
    ],
    # Do NOT exclude tkinter - customtkinter depends on it heavily.
    # 'excludes': ['tkinter'],
    'plist': {
        'CFBundleName': 'AI-MIDI-Generator',
        'CFBundleDisplayName': 'AI MIDI Generator',
        'CFBundleIdentifier': 'com.aimidi.generator',
        'CFBundleVersion': '0.3.0',
        'CFBundleShortVersionString': '0.3.0',
        'NSHighResolutionCapable': True,
    },
    'iconfile': 'resources/icon.icns' if os.path.exists('resources/icon.icns') else None,
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    name='AI-MIDI-Generator',
    version='0.3.0',
    description='AI-powered MIDI generator with multi-track editing, preview, batch, and DAW integration.',
    author='Grok + User',
)