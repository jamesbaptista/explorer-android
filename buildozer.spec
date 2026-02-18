[app]

# Application metadata
title = Explorer
package.name = explorer
package.domain = org.explorer

# Source
source.dir = .
source.include_exts = py,png,jpg,ttf
source.include_patterns = assets/*.ttf,gold_nugget.png
source.exclude_dirs = .git,.claude,bin,.buildozer,p4a-recipes

# Entry point — Buildozer looks for main.py by default
# (no need to set explicitly)

version = 1.0

# Requirements — use built-in pygame recipe (well-tested with p4a)
requirements = python3==3.10.12,pygame

# Orientation and display
orientation = portrait
fullscreen = 1

# Android SDK/NDK
android.minapi = 21
android.api = 33
android.ndk = 25.2.9519653
android.archs = arm64-v8a, armeabi-v7a

# p4a bootstrap — sdl2 is the standard bootstrap for pygame
p4a.bootstrap = sdl2
p4a.local_recipes = ./p4a-recipes

# Permissions (none required for this game)
# android.permissions =

# Icons / presplash (optional — uses default if not set)
# icon.filename = %(source.dir)s/icon.png
# presplash.filename = %(source.dir)s/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1
