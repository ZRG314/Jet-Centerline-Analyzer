"""Quick diagnostic for Blackfly/Spinnaker camera visibility in Jet Analyzer."""

import platform
import sys


def print_header(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def list_windows_camera_names():
    names = []

    try:
        import wmi  # type: ignore

        w = wmi.WMI()
        devices = w.query(
            "SELECT Name, PNPClass, ClassGuid FROM Win32_PnPEntity "
            "WHERE Name IS NOT NULL AND ("
            "PNPClass='Camera' OR "
            "PNPClass='Image' OR "
            "ClassGuid='{6bdd1fc6-810f-11d0-bec7-08002be2092f}' OR "
            "ClassGuid='{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}' OR "
            "Name LIKE '%camera%' OR "
            "Name LIKE '%webcam%' OR "
            "Name LIKE '%droid%' OR "
            "Name LIKE '%blackfly%' OR "
            "Name LIKE '%flir%' OR "
            "Name LIKE '%teledyne%')"
        )
        for device in devices:
            name = str(getattr(device, "Name", "")).strip()
            if name:
                names.append(name)
    except Exception as exc:
        print(f"WMI query failed: {exc}")

    deduped = []
    seen = set()
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(name)
    return deduped


def main():
    print_header("Python")
    print(f"Executable: {sys.executable}")
    print(f"Version:    {sys.version.splitlines()[0]}")
    print(f"Platform:   {platform.platform()}")

    print_header("PySpin Import")
    try:
        import PySpin  # type: ignore

        print("PySpin import: OK")
        print(f"PySpin module: {getattr(PySpin, '__file__', 'unknown')}")
    except Exception as exc:
        print(f"PySpin import: FAILED")
        print(f"Reason: {exc}")
        PySpin = None

    print_header("Spinnaker Enumeration")
    if PySpin is None:
        print("Skipped because PySpin could not be imported.")
    else:
        system = None
        cam_list = None
        try:
            system = PySpin.System.GetInstance()
            cam_list = system.GetCameras()
            count = cam_list.GetSize()
            print(f"Detected cameras via Spinnaker: {count}")
            for idx in range(count):
                cam = cam_list.GetByIndex(idx) if hasattr(cam_list, "GetByIndex") else cam_list[idx]
                tl_nodemap = cam.GetTLDeviceNodeMap()
                try:
                    vendor_node = PySpin.CStringPtr(tl_nodemap.GetNode("DeviceVendorName"))
                    model_node = PySpin.CStringPtr(tl_nodemap.GetNode("DeviceModelName"))
                    serial_node = PySpin.CStringPtr(tl_nodemap.GetNode("DeviceSerialNumber"))
                    vendor = vendor_node.GetValue() if PySpin.IsAvailable(vendor_node) and PySpin.IsReadable(vendor_node) else ""
                    model = model_node.GetValue() if PySpin.IsAvailable(model_node) and PySpin.IsReadable(model_node) else ""
                    serial = serial_node.GetValue() if PySpin.IsAvailable(serial_node) and PySpin.IsReadable(serial_node) else ""
                    print(f"[{idx}] {vendor} {model} S/N={serial}".strip())
                except Exception as exc:
                    print(f"[{idx}] Camera found, but metadata query failed: {exc}")
        except Exception as exc:
            print(f"Spinnaker enumeration failed: {exc}")
        finally:
            if cam_list is not None:
                try:
                    cam_list.Clear()
                except Exception:
                    pass
            if system is not None:
                try:
                    system.ReleaseInstance()
                except Exception:
                    pass

    print_header("Windows Camera Devices")
    names = list_windows_camera_names()
    if names:
        for idx, name in enumerate(names):
            print(f"[{idx}] {name}")
    else:
        print("No camera-like devices found through WMI.")

    print_header("Interpretation")
    print("If PySpin import fails, Jet Analyzer cannot use Blackfly through Spinnaker in this Python.")
    print("If PySpin imports but Spinnaker sees 0 cameras while SpinView sees one, the PySpin/SDK/Python versions likely do not match.")
    print("If Spinnaker sees the camera here, Jet Analyzer should be able to list it after restart.")


if __name__ == "__main__":
    main()
