"""Camera discovery and capture helpers for OpenCV and FLIR/Teledyne cameras."""

import contextlib
import json
import os
import platform
import subprocess
import tempfile

import cv2


DEFAULT_OPENCV_CAMERA_COUNT = 10
WINDOWS_CAMERA_CLASS_GUIDS = {
    "{6bdd1fc6-810f-11d0-bec7-08002be2092f}",  # Image devices
    "{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}",  # Camera devices
}


@contextlib.contextmanager
def _suppress_native_stderr():
    """Temporarily suppress native stderr output from noisy camera probes."""
    stderr_fd = None
    saved_stderr_fd = None
    sink = None
    try:
        stderr_fd = sys_stderr_fd = 2
        saved_stderr_fd = os.dup(sys_stderr_fd)
        sink = tempfile.TemporaryFile()
        os.dup2(sink.fileno(), sys_stderr_fd)
        yield
    finally:
        if saved_stderr_fd is not None:
            os.dup2(saved_stderr_fd, stderr_fd)
            os.close(saved_stderr_fd)
        if sink is not None:
            sink.close()


def _safe_label(base_label, backend, used_labels):
    label = base_label
    suffix = 2
    while label in used_labels:
        label = f"{base_label} ({backend} {suffix})"
        suffix += 1
    used_labels.add(label)
    return label


def _dedupe_labels(names):
    unique_names = []
    seen = set()
    for name in names:
        cleaned = str(name).strip()
        lowered = cleaned.lower()
        if not cleaned or lowered in seen:
            continue
        seen.add(lowered)
        unique_names.append(cleaned)
    return unique_names


def _looks_like_spinnaker_camera(name):
    lowered = str(name or "").strip().lower()
    if not lowered:
        return False
    return any(token in lowered for token in ("blackfly", "flir", "teledyne"))


def _try_import_pyspin():
    try:
        import PySpin  # type: ignore
        return PySpin
    except Exception:
        return None


def _get_pyspin_camera(cam_list, index):
    if hasattr(cam_list, "GetByIndex"):
        return cam_list.GetByIndex(index)
    return cam_list[index]


def _read_pyspin_string(PySpin, nodemap, node_name):
    try:
        node = PySpin.CStringPtr(nodemap.GetNode(node_name))
        if PySpin.IsAvailable(node) and PySpin.IsReadable(node):
            return node.GetValue()
    except Exception:
        pass
    return ""


def _read_pyspin_int(PySpin, nodemap, node_name):
    try:
        node = PySpin.CIntegerPtr(nodemap.GetNode(node_name))
        if PySpin.IsAvailable(node) and PySpin.IsReadable(node):
            return int(node.GetValue())
    except Exception:
        pass
    return 0


def _list_windows_camera_names():
    """Return camera-like device names reported by Windows, if available."""
    if platform.system() != "Windows":
        return []

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
            "Name LIKE '%blackfly%')"
        )
        names.extend(getattr(device, "Name", "") for device in devices)
    except Exception:
        pass

    if names:
        return _dedupe_labels(names)

    try:
        script = """
$devices = Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.Name -and (
        $_.PNPClass -eq 'Camera' -or
        $_.PNPClass -eq 'Image' -or
        $_.ClassGuid -eq '{6bdd1fc6-810f-11d0-bec7-08002be2092f}' -or
        $_.ClassGuid -eq '{ca3e7ab9-b4c3-4ae6-8251-579ef933890f}' -or
        $_.Name -match 'camera|webcam|droid|blackfly'
    )
} | Select-Object -ExpandProperty Name -Unique
$devices | ConvertTo-Json -Compress
""".strip()
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        raw_output = completed.stdout.strip()
        if raw_output:
            parsed = json.loads(raw_output)
            if isinstance(parsed, str):
                names.append(parsed)
            elif isinstance(parsed, list):
                names.extend(parsed)
    except Exception:
        pass

    return _dedupe_labels(names)


def list_available_cameras(max_opencv_indices=DEFAULT_OPENCV_CAMERA_COUNT):
    """Return available cameras as display-friendly descriptors."""
    descriptors = []
    used_labels = set()
    windows_camera_names = _list_windows_camera_names()
    pyspin_detected_any = False

    PySpin = _try_import_pyspin()
    if PySpin is not None:
        system = None
        cam_list = None
        try:
            system = PySpin.System.GetInstance()
            cam_list = system.GetCameras()
            for idx in range(cam_list.GetSize()):
                cam = _get_pyspin_camera(cam_list, idx)
                tl_nodemap = cam.GetTLDeviceNodeMap()
                model = _read_pyspin_string(PySpin, tl_nodemap, "DeviceModelName") or f"Spinnaker Camera {idx}"
                serial = _read_pyspin_string(PySpin, tl_nodemap, "DeviceSerialNumber")
                vendor = _read_pyspin_string(PySpin, tl_nodemap, "DeviceVendorName")
                prefix = vendor.strip() if vendor else "FLIR"
                base_label = f"{prefix} {model}".strip()
                if serial:
                    base_label = f"{base_label} (S/N {serial})"
                descriptors.append({
                    "id": f"spinnaker:{serial or idx}",
                    "backend": "spinnaker",
                    "display_name": _safe_label(base_label, "Spinnaker", used_labels),
                    "serial": serial,
                    "index": idx,
                })
                pyspin_detected_any = True
        except Exception:
            pass
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

    opencv_name_index = 0
    for idx in range(max_opencv_indices):
        cap = None
        try:
            with _suppress_native_stderr():
                cap = cv2.VideoCapture(idx)
                is_open = cap.isOpened()
                ret = False
                if is_open:
                    ret, _ = cap.read()
            if is_open and ret:
                device_name = ""
                if opencv_name_index < len(windows_camera_names):
                    device_name = windows_camera_names[opencv_name_index]
                base_label = f"{device_name} (Camera {idx})" if device_name else f"Camera {idx}"
                descriptors.append({
                    "id": f"opencv:{idx}",
                    "backend": "opencv",
                    "display_name": _safe_label(base_label, "OpenCV", used_labels),
                    "index": idx,
                })
                opencv_name_index += 1
        except Exception:
            pass
        finally:
            if cap is not None:
                cap.release()

    if PySpin is None:
        for idx, device_name in enumerate(windows_camera_names):
            if not _looks_like_spinnaker_camera(device_name):
                continue
            base_label = f"{device_name} (requires PySpin)"
            descriptors.append({
                "id": f"spinnaker-unavailable:{idx}",
                "backend": "spinnaker",
                "display_name": _safe_label(base_label, "Spinnaker", used_labels),
                "serial": None,
                "index": idx,
                "unavailable_reason": (
                    "PySpin is not installed in the Python environment running Jet Analyzer. "
                    "Install the matching Spinnaker PySpin wrapper for this Python version."
                ),
            })
    elif not pyspin_detected_any:
        for idx, device_name in enumerate(windows_camera_names):
            if not _looks_like_spinnaker_camera(device_name):
                continue
            base_label = f"{device_name} (Spinnaker unavailable)"
            descriptors.append({
                "id": f"spinnaker-undetected:{idx}",
                "backend": "spinnaker",
                "display_name": _safe_label(base_label, "Spinnaker", used_labels),
                "serial": None,
                "index": idx,
                "unavailable_reason": (
                    "Windows can see a FLIR/Blackfly camera, but PySpin did not enumerate it. "
                    "Check that the installed PySpin version matches the Spinnaker SDK and the Python version launching Jet Analyzer."
                ),
            })

    return descriptors


class OpenCVCameraCapture:
    """Thin wrapper around cv2.VideoCapture with a shared interface."""

    def __init__(self, camera_index):
        self.camera_index = int(camera_index)
        self.cap = None

    def open(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            return False
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return True

    def is_opened(self):
        return self.cap is not None and self.cap.isOpened()

    def isOpened(self):
        """Compatibility alias for code that still uses OpenCV naming."""
        return self.is_opened()

    def read(self):
        if self.cap is None:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def get_width(self):
        if self.cap is None:
            return 0
        return int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    def get_height(self):
        if self.cap is None:
            return 0
        return int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


class SpinnakerCameraCapture:
    """Capture frames from Teledyne/FLIR cameras through PySpin."""

    def __init__(self, camera_index=0, serial=None):
        self.camera_index = int(camera_index)
        self.serial = serial
        self.system = None
        self.cam_list = None
        self.camera = None
        self.processor = None
        self.PySpin = None
        self.acquiring = False

    def _select_camera(self):
        if self.serial:
            for idx in range(self.cam_list.GetSize()):
                cam = _get_pyspin_camera(self.cam_list, idx)
                tl_nodemap = cam.GetTLDeviceNodeMap()
                serial = _read_pyspin_string(self.PySpin, tl_nodemap, "DeviceSerialNumber")
                if serial == self.serial:
                    return cam
        if self.cam_list.GetSize() == 0:
            return None
        if self.camera_index >= self.cam_list.GetSize():
            return _get_pyspin_camera(self.cam_list, 0)
        return _get_pyspin_camera(self.cam_list, self.camera_index)

    def _set_enum_by_name(self, nodemap, node_name, entry_name):
        try:
            enum_node = self.PySpin.CEnumerationPtr(nodemap.GetNode(node_name))
            if not self.PySpin.IsAvailable(enum_node) or not self.PySpin.IsWritable(enum_node):
                return
            entry = self.PySpin.CEnumEntryPtr(enum_node.GetEntryByName(entry_name))
            if not self.PySpin.IsAvailable(entry) or not self.PySpin.IsReadable(entry):
                return
            enum_node.SetIntValue(entry.GetValue())
        except Exception:
            pass

    def open(self):
        self.PySpin = _try_import_pyspin()
        if self.PySpin is None:
            raise RuntimeError(
                "PySpin is not installed. Install the Teledyne/FLIR Spinnaker SDK and Python wrapper to use Blackfly cameras."
            )

        self.system = self.PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        self.camera = self._select_camera()
        if self.camera is None:
            return False

        self.camera.Init()
        nodemap = self.camera.GetNodeMap()
        stream_nodemap = self.camera.GetTLStreamNodeMap()
        self._set_enum_by_name(stream_nodemap, "StreamBufferHandlingMode", "NewestOnly")
        self._set_enum_by_name(nodemap, "AcquisitionMode", "Continuous")

        self.processor = self.PySpin.ImageProcessor()
        try:
            self.processor.SetColorProcessing(
                self.PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR
            )
        except Exception:
            pass

        self.camera.BeginAcquisition()
        self.acquiring = True
        return True

    def is_opened(self):
        return self.camera is not None

    def isOpened(self):
        """Compatibility alias for code that still uses OpenCV naming."""
        return self.is_opened()

    def read(self):
        if self.camera is None:
            return False, None

        image = None
        try:
            image = self.camera.GetNextImage(1000)
            if image.IsIncomplete():
                return False, None

            try:
                converted = self.processor.Convert(image, self.PySpin.PixelFormat_BGR8)
                frame = converted.GetNDArray().copy()
            except Exception:
                converted = self.processor.Convert(image, self.PySpin.PixelFormat_Mono8)
                frame = converted.GetNDArray().copy()
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            return True, frame
        except Exception:
            return False, None
        finally:
            if image is not None:
                try:
                    image.Release()
                except Exception:
                    pass

    def release(self):
        if self.camera is not None:
            try:
                if self.acquiring:
                    self.camera.EndAcquisition()
            except Exception:
                pass
            try:
                self.camera.DeInit()
            except Exception:
                pass
            self.camera = None
            self.acquiring = False

        if self.cam_list is not None:
            try:
                self.cam_list.Clear()
            except Exception:
                pass
            self.cam_list = None

        if self.system is not None:
            try:
                self.system.ReleaseInstance()
            except Exception:
                pass
            self.system = None

    def get_width(self):
        if self.camera is None:
            return 0
        return _read_pyspin_int(self.PySpin, self.camera.GetNodeMap(), "Width")

    def get_height(self):
        if self.camera is None:
            return 0
        return _read_pyspin_int(self.PySpin, self.camera.GetNodeMap(), "Height")


def create_camera_capture(camera_source):
    """Build a camera capture object from a source descriptor."""
    if camera_source is None:
        return OpenCVCameraCapture(0)

    backend = camera_source.get("backend", "opencv")
    if backend == "spinnaker":
        return SpinnakerCameraCapture(
            camera_index=camera_source.get("index", 0),
            serial=camera_source.get("serial"),
        )
    return OpenCVCameraCapture(camera_source.get("index", 0))
