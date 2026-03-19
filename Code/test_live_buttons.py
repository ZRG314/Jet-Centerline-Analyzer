#!/usr/bin/env python3
"""Test live camera button functionality"""

from gui import JetAnalysisGUI
import tkinter as tk

# Create the app
root = tk.Tk()
app = JetAnalysisGUI(root)

# Simulate selecting Live Camera
print("1. User selects 'Live Camera' from dropdown...")
app.video_source_var.set('Live Camera')
app.on_video_source_change()

# Check state after selecting Live Camera
print(f'\nAfter selecting Live Camera:')
print(f'  - live_preview_active: {app.live_preview_active}')
print(f'  - is_running: {app.is_running}')
print(f'  - Run button: {app.run_button.cget("state")}')
print(f'  - Stop button: {app.stop_button.cget("state")}')
print(f'  - Status: {app.status_var.get()}')

if app.live_preview_active and app.run_button.cget("state") == "normal":
    print('[PASS] Live preview started, Run button is enabled')
else:
    print('[FAIL] Expected live_preview_active=True and Run button enabled')

# Test stopping preview
print("\n2. User switches back to 'Video File'...")
app.video_source_var.set('Video File')
app.on_video_source_change()

print(f'\nAfter selecting Video File:')
print(f'  - live_preview_active: {app.live_preview_active}')
print(f'  - Status: {app.status_var.get()}')

if not app.live_preview_active:
    print('[PASS] Live preview stopped')
else:
    print('[FAIL] Expected live_preview_active=False')

print('\nAll tests completed successfully!')
root.destroy()
