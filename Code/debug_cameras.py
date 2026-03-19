#!/usr/bin/env python
"""Debug script to check what cameras Windows detects."""

import cv2
import os

print("=" * 60)
print("CAMERA DETECTION DEBUG")
print("=" * 60)

# 1. Check OpenCV detection
print("\n1. OpenCV Camera Detection (checking indices 0-9):")
print("-" * 60)
detected_count = 0
for idx in range(10):
    cap = cv2.VideoCapture(idx)
    if cap.isOpened():
        # Try to read a frame
        ret, frame = cap.read()
        cap.release()
        if ret:
            print(f"   ✓ Camera {idx}: DETECTED (can read frames)")
            detected_count += 1
        else:
            print(f"   ? Camera {idx}: Device open but can't read (might be in use)")
    else:
        # Try to get properties without reading
        cap2 = cv2.VideoCapture(idx)
        try:
            # Check if we can set/get a property
            width = cap2.get(cv2.CAP_PROP_FRAME_WIDTH)
            if width > 0:
                print(f"   ~ Camera {idx}: Device might exist (can't read yet)")
        except:
            pass
        cap2.release()

print(f"\n   Total cameras found: {detected_count}")

# 2. Check WMI for device names
print("\n2. Windows WMI Camera Devices:")
print("-" * 60)
try:
    import wmi
    w = wmi.WMI()
    cameras = w.query("SELECT Name, DeviceID FROM Win32_PnPDevice WHERE (ClassGuid='{6994AD05-93D7-11D0-A43D-00A0C9223196}' OR Name LIKE '%camera%' OR Name LIKE '%camera%' OR Name LIKE '%droid%' OR Name LIKE '%webcam%')")
    
    if cameras:
        for camera in cameras:
            print(f"   • {camera.Name}")
            print(f"     Device ID: {camera.DeviceID}")
    else:
        print("   No cameras found in WMI query")
except ImportError:
    print("   WMI module not available")
except Exception as e:
    print(f"   Error querying WMI: {e}")

# 3. Check all PnP devices to see what DroidCam registered as
print("\n3. All PnP Video/Image Devices:")
print("-" * 60)
try:
    import wmi
    w = wmi.WMI()
    # Class GUID for imaging devices: 6bdd1fc6-810f-11d0-bec7-08002be2092f
    devices = w.query("SELECT Name FROM Win32_PnPDevice WHERE ClassGuid='{6bdd1fc6-810f-11d0-bec7-08002be2092f}'")
    
    if devices:
        for device in devices:
            print(f"   • {device.Name}")
    else:
        print("   No imaging devices found")
except Exception as e:
    print(f"   Error querying imaging devices: {e}")

# 4. Check registry for camera drivers
print("\n4. Checking Windows Registry for Camera Drivers:")
print("-" * 60)
try:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
            r"SYSTEM\CurrentControlSet\Services\usbvideo")
        print("   ✓ USB Video Driver (usbvideo) is installed")
        winreg.CloseKey(key)
    except:
        print("   ? USB Video Driver not found in expected location")
    
    # Check for DroidCam specifically
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services")
        subkeys = []
        i = 0
        while True:
            try:
                subkey = winreg.EnumKey(key, i)
                if 'droid' in subkey.lower() or 'droidcam' in subkey.lower():
                    print(f"   ✓ DroidCam service found: {subkey}")
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception as e:
        print(f"   Error checking services: {e}")
        
except ImportError:
    print("   winreg module not available (Windows only)")

print("\n" + "=" * 60)
print("RECOMMENDATIONS:")
print("=" * 60)
print("""
If DroidCam is not showing up:

1. Check if DroidCam app is running on your phone
2. Check if DroidCam is connected to the same network
3. Make sure Windows firewall allows DroidCam
4. Restart the DroidCam app on your phone
5. Try restarting the GUI (it detects cameras at startup)
6. Check Device Manager:
   - Open: devmgmt.msc
   - Look under "Imaging Devices" or "Cameras"
   - DroidCam should appear as a device

If you see it in Device Manager but not in our app:
- The GUI detects cameras when it starts
- You may need to restart the GUI after DroidCam connects
""")
