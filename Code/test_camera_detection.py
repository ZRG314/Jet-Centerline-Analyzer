#!/usr/bin/env python
"""Quick test of camera detection without running full GUI."""

import cv2
import sys

print("Testing Camera Detection...")
print("=" * 60)

# Test WMI detection
print("\n1. WMI Camera Detection:")
try:
    import wmi
    w = wmi.WMI()
    cameras = w.query("SELECT Name, Description FROM Win32_PnPDevice WHERE ClassGuid='{6bdd1fc6-810f-11d0-bec7-08002be2092f}' OR (Name LIKE '%camera%' OR Name LIKE '%webcam%' OR Name LIKE '%droid%')")
    for idx, camera in enumerate(cameras):
        device_name = camera.Name if hasattr(camera, 'Name') and camera.Name else camera.Description if hasattr(camera, 'Description') else f"Camera {idx}"
        print(f"   [{idx}] {device_name}")
    
    if len(list(cameras)) == 0:
        print("   No cameras found via WMI")
except Exception as e:
    print(f"   WMI failed: {e}")

# Test OpenCV detection
print("\n2. OpenCV Camera Detection (trying 0-9):")
detected = []
for idx in range(10):
    cap = cv2.VideoCapture(idx)
    if cap.isOpened():
        ret, _ = cap.read()
        cap.release()
        if ret:
            detected.append(idx)
            print(f"   [OK] Camera {idx} - DETECTED")

if not detected:
    print("   No cameras detected via OpenCV")

print("\n" + "=" * 60)
print(f"Summary: Found {len(detected)} camera(s)")
print("=" * 60)
