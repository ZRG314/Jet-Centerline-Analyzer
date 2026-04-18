import threading
import cv2
import time
import numpy as np

from camera_capture import create_camera_capture
from analysis_engine import (
    threshold_frame,
    extract_centerline,
    draw_instantaneous_centerline,
    draw_confidence_region,
    compute_multi_thresholds,
    build_threshold_color_preview_filtered,
    draw_mean_centerline,
    RunningStats,
    create_video_writer,
    build_threshold_output_frame,
)


class LiveEngine:
    """Manages live webcam input with optional real-time jet analysis and output saving."""
    
    def __init__(self, gui, camera_source=None, analysis_config=None,
                 analysis_output_path=None, threshold_output_path=None):
        self.gui = gui
        self.display_controller = gui.display_controller
        self.camera_source = camera_source or {"backend": "opencv", "index": 0}
        self.analysis_config = analysis_config
        self.analysis_output_path = analysis_output_path
        self.threshold_output_path = threshold_output_path
        self.stop_event = threading.Event()
        self.thread = None
        self.is_open = False
        self.error_message = None
        
        # Analysis state
        self.running_stats = None
        self.frame_count = 0
        self.analyze = analysis_config is not None  # Flag to control whether to perform analysis
        self.analysis_writer = None
        self.threshold_writer = None
        self.final_mean = None
        self.final_std = None
        self.cap = None  # Store camera reference for quick release
        self.analysis_start_time = None  # Track when analysis started for progress display

    def start(self, analyze=False):
        """Start the live camera thread.
        
        Args:
            analyze: If True, perform jet analysis. If False, just preview.
        """
        self.stop_event.clear()
        self.error_message = None
        self.is_open = False
        self.frame_count = 0
        self.analyze = analyze
        self.analysis_start_time = None  # Reset timing for new run
        self.completed_naturally = False  # Reset completion flag
        
        # Initialize analysis state once the real camera resolution is known in _run()
        self.running_stats = None
        
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the live camera thread."""
        self.stop_event.set()
        # Release camera immediately to unblock any waiting read operations
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_open = False

    def _run(self):
        """Main loop for capturing, analyzing, and displaying frames from webcam."""
        cap = create_camera_capture(self.camera_source)
        self.cap = cap  # Store reference for quick release

        unavailable_reason = self.camera_source.get("unavailable_reason")
        if unavailable_reason:
            self.error_message = unavailable_reason
            self.gui.root.after(0, self._handle_camera_error)
            self.cap = None
            return

        try:
            opened = cap.open()
        except Exception as exc:
            opened = False
            self.error_message = str(exc)

        if not opened:
            if not self.error_message:
                camera_label = self.camera_source.get("display_name", "selected camera")
                self.error_message = f"Could not open {camera_label}. Make sure it is connected."
            self.gui.root.after(0, self._handle_camera_error)
            self.cap = None
            return

        # Get actual resolution (may differ from requested)
        actual_width = int(cap.get_width())
        actual_height = int(cap.get_height())
        self._normalize_default_crop(actual_width, actual_height)

        self.is_open = True
        
        # Initialize writers if analyzing - use cropped analysis resolution
        if self.analyze:
            crop_left = self.analysis_config.get('crop_left', 0)
            crop_right = self.analysis_config.get('crop_right', actual_width)
            crop_top = self.analysis_config.get('crop_top', 0)
            crop_bottom = self.analysis_config.get('crop_bottom', actual_height)
            cropped_width = max(1, crop_right - crop_left)
            cropped_height = max(1, crop_bottom - crop_top)
            self.running_stats = RunningStats(cropped_width)
            frame_stride = max(1, int(self.analysis_config.get('frame_stride', 1)))
            output_fps = max(1.0, 30.0 / frame_stride)
            try:
                if self.analysis_output_path:
                    self.analysis_writer = create_video_writer(
                        self.analysis_output_path,
                        output_fps,
                        (cropped_width, cropped_height)
                    )
                if self.threshold_output_path:
                    self.threshold_writer = create_video_writer(
                        self.threshold_output_path,
                        output_fps,
                        (cropped_width, cropped_height)
                    )
            except Exception as exc:
                if self.analysis_writer:
                    self.analysis_writer.release()
                    self.analysis_writer = None
                if self.threshold_writer:
                    self.threshold_writer.release()
                    self.threshold_writer = None
                self.error_message = str(exc)
                self.gui.root.after(0, self._handle_camera_error)
                cap.release()
                self.cap = None
                return
        
        frame_count = 0
        captured_frame_count = 0
        last_update_time = time.time()
        processing_time = 0
        consecutive_failures = 0
        first_frame_displayed = False  # Track if we've shown the first frame
        
        try:
            while not self.stop_event.is_set():
                # Try to read frame with retries for network cameras like DroidCam
                ret, frame = None, None
                retry_count = 3
                for attempt in range(retry_count):
                    ret, frame = cap.read()
                    if ret:
                        consecutive_failures = 0  # Reset counter on success
                        break
                    if attempt < retry_count - 1:
                        time.sleep(0.1)  # Short delay before retry
                
                if not ret:
                    consecutive_failures += 1
                    # Allow up to 5 consecutive failures (network glitch tolerance)
                    if consecutive_failures > 5:
                        self.error_message = "Camera connection lost. Could not recover after multiple retries."
                        self.gui.root.after(0, self._handle_camera_error)
                        break
                    else:
                        # Show warning on status but continue trying
                        self.gui.root.after(0, lambda: self.gui.set_status(
                            f"Warning: Camera not responding (attempt {consecutive_failures}/5)", "warning"))
                        time.sleep(0.2)
                        continue
                
                # Update status once first frame is received (preview mode only)
                if not first_frame_displayed and not self.analyze:
                    def update_ready_state():
                        self.gui.set_status("Live preview: Camera ready", "ready")
                        self.gui.refresh_run_state()
                    self.gui.root.after(0, update_ready_state)
                    first_frame_displayed = True
                
                # Process the frame based on mode
                display_frame = frame.copy()
                if self.analyze and self.analysis_config:
                    captured_frame_count += 1
                    frame_stride = max(1, int(self.analysis_config.get('frame_stride', 1)))
                    should_analyze_frame = ((captured_frame_count - 1) % frame_stride) == 0
                    if not should_analyze_frame:
                        if self.display_controller:
                            self.gui.root.after(0, lambda f=frame: setattr(self.gui, 'last_raw_frame', f.copy()))
                            self.gui.root.after(0, self.display_controller.display_frame, display_frame)
                        continue

                    # Full analysis mode - set start time on first analysis frame
                    if self.analysis_start_time is None:
                        self.analysis_start_time = time.time()
                        # Set status immediately when analysis starts
                        self.gui.root.after(0, self.gui.set_status, "Running analysis", "running")
                    frame_start = time.time()
                    analysis_frame, threshold_frame_bgr, display_frame = self._process_frame(frame)
                    processing_time = time.time() - frame_start
                    
                    if self.analysis_writer:
                        self.analysis_writer.write(analysis_frame)
                    if self.threshold_writer:
                        self.threshold_writer.write(threshold_frame_bgr)
                elif self.analysis_config:
                    # Preview-only mode (apply crop and show selected preview)
                    preview_mode = self.analysis_config.get('preview_mode', 'analysis')
                    
                    # Don't apply crop if user is actively editing crop settings
                    if not self.gui.crop_mode:
                        # Apply crop to preview
                        crop_left = self.analysis_config.get('crop_left', 0)
                        crop_right = self.analysis_config.get('crop_right', frame.shape[1])
                        crop_top = self.analysis_config.get('crop_top', 0)
                        crop_bottom = self.analysis_config.get('crop_bottom', frame.shape[0])
                        display_frame = frame[crop_top:crop_bottom, crop_left:crop_right].copy()
                    
                    if preview_mode == 'threshold':
                        # Show threshold preview (frame is already cropped if crop applied)
                        display_frame = self._get_threshold_preview(display_frame, already_cropped=not self.gui.crop_mode)
                    # For 'analysis' or 'none' modes, just show the raw frame
                
                # Display the frame
                if self.display_controller:
                    # Store raw uncropped frame for reset_crop functionality
                    self.gui.root.after(0, lambda f=frame: setattr(self.gui, 'last_raw_frame', f.copy()))
                    self.gui.root.after(0, self.display_controller.display_frame, display_frame)
                
                frame_count += 1
                self.frame_count += 1
                
                # Update progress bar for limited runs
                if self.analyze and self.analysis_config:
                    max_frames = self.analysis_config.get('max_frames', None)
                    if max_frames:
                        # Update progress bar
                        self.gui.root.after(0, lambda fc=self.frame_count: self.gui.progress.configure(value=fc))
                    
                    # Check if max frames reached
                    if max_frames and self.frame_count >= max_frames:
                        self.completed_naturally = True
                        break
                
                # Update progress label and status display
                current_time = time.time()
                
                # Update stats every frame during analysis, every 30 frames during preview
                should_update = (self.analyze and self.analysis_config) or (frame_count % 30 == 0)
                
                if should_update and (self.analyze and self.analysis_config or current_time > last_update_time):
                    fps = 30 / (current_time - last_update_time) if frame_count % 30 == 0 and current_time > last_update_time else 0
                    
                    # Only show frame count in status during analysis
                    if self.analyze and self.analysis_config:
                        # Update progress bar label with elapsed time, frame timing, and frame count (every frame during analysis)
                        if self.analysis_start_time is not None:
                            elapsed = current_time - self.analysis_start_time
                            max_frames = self.analysis_config.get('max_frames', None)
                            frames_display = f"{self.frame_count}/{max_frames}" if max_frames else f"{self.frame_count}"
                            time_label_text = f"{elapsed:.2f}s | {frames_display}"
                            self.gui.root.after(0, lambda text=time_label_text: self.gui.time_label.configure(text=text))
                    else:
                        # Preview mode - update every 30 frames
                        if frame_count % 30 == 0 and current_time > last_update_time:
                            status_text = f"Live: {fps:.1f} fps"
                            self.gui.root.after(0, self.gui.set_status, status_text, "normal")
                            last_update_time = current_time
                
                # Control frame rate
                time.sleep(1/60)  # Allow up to 60 fps
        
        finally:
            # Release camera if not already released
            if cap and cap.is_opened():
                cap.release()
            self.cap = None
            if self.analysis_writer:
                self.analysis_writer.release()
            if self.threshold_writer:
                self.threshold_writer.release()
            self.is_open = False
            
            # Store final profiles if analyzing
            if self.running_stats:
                self.final_mean, self.final_std = self.running_stats.get_mean_std()
            
            # Notify GUI if completed naturally
            if self.completed_naturally:
                self.gui.root.after(0, self.gui.on_live_analysis_complete)

    def _process_frame(self, frame):
        """Apply jet analysis to the frame."""
        config = self.analysis_config
        
        # Apply crop
        crop_left = config.get('crop_left', 0)
        crop_right = config.get('crop_right', frame.shape[1])
        crop_top = config.get('crop_top', 0)
        crop_bottom = config.get('crop_bottom', frame.shape[0])
        
        frame = frame[crop_top:crop_bottom, crop_left:crop_right]
        
        # Threshold the frame
        threshold_offset = config.get('threshold_offset', 15)
        binary, adjusted_thresh = threshold_frame(frame, threshold_offset)
        
        # Extract centerline
        pixels_per_col = config.get('pixels_per_col', 3)
        centerline = extract_centerline(binary, pixels_per_col)
        centerline_array = np.array(centerline, dtype=np.float64)
        
        # Update running statistics
        if self.running_stats:
            self.running_stats.update(centerline_array)
            running_avg, running_std = self.running_stats.get_mean_std()
        else:
            running_avg, running_std = centerline_array, np.full_like(centerline_array, np.nan)
        
        # Get preview mode and display accordingly
        preview_mode = config.get('preview_mode', 'analysis')
        show_analysis_overlay = config.get('show_analysis_overlay', True)
        
        analysis_frame = frame.copy()
        analysis_frame = draw_instantaneous_centerline(analysis_frame, centerline_array)

        show_confidence = config.get('show_confidence', True)
        if show_confidence:
            stdevs = config.get('stdevs', 2)
            confidence_mode = config.get('confidence_mode', 'band')
            analysis_frame = draw_confidence_region(
                analysis_frame,
                running_avg,
                running_std,
                stdevs,
                confidence_mode
            )

        avg_thickness = config.get('avg_line_thickness', 2)
        analysis_frame = draw_mean_centerline(
            analysis_frame,
            running_avg,
            avg_thickness
        )

        threshold_frame_bgr = build_threshold_output_frame(
            frame,
            binary,
            use_multi_threshold=config.get('use_multi_threshold', False),
            multi_threshold_offsets=config.get('multi_threshold_offsets', [15, 25, 35, 45, 55]),
            multi_threshold_colors=config.get('multi_threshold_colors', ["#000000", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd", "#1f77b4"]),
        )

        if preview_mode == 'threshold':
            display_frame = threshold_frame_bgr
        elif preview_mode == 'analysis':
            display_frame = analysis_frame if show_analysis_overlay else frame.copy()
        else:
            display_frame = frame.copy()

        return analysis_frame, threshold_frame_bgr, display_frame

    def _get_threshold_preview(self, frame, already_cropped=False):
        """Generate a threshold preview without full analysis."""
        if not self.analysis_config:
            return frame.copy()
        
        config = self.analysis_config
        
        # Apply crop only if not already cropped
        if not already_cropped:
            crop_left = config.get('crop_left', 0)
            crop_right = config.get('crop_right', frame.shape[1])
            crop_top = config.get('crop_top', 0)
            crop_bottom = config.get('crop_bottom', frame.shape[0])
            cropped_frame = frame[crop_top:crop_bottom, crop_left:crop_right]
        else:
            cropped_frame = frame
        
        # Check if multi-threshold is enabled
        use_multi = config.get('use_multi_threshold', False)
        
        if use_multi:
            # Use multi-threshold colored preview
            gray = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2GRAY) if cropped_frame.ndim == 3 else cropped_frame
            offsets = config.get('multi_threshold_offsets', [15, 25, 35, 45, 55])
            colors = config.get('multi_threshold_colors', ["#000000", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd", "#1f77b4"])
            thresholds, _ = compute_multi_thresholds(gray, offsets)
            region_count = len(thresholds) + 1
            preview_colors = colors[:region_count] if len(colors) >= region_count else colors + ["#000000"] * (region_count - len(colors))
            display_frame = build_threshold_color_preview_filtered(gray, thresholds, preview_colors)
        else:
            # Use single-threshold binary preview
            threshold_offset = config.get('threshold_offset', 15)
            binary, adjusted_thresh = threshold_frame(cropped_frame, threshold_offset)
            display_frame = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        
        return display_frame

    def _handle_camera_error(self):
        """Handle camera errors in the main GUI thread."""
        import tkinter.messagebox as messagebox
        if self.error_message:
            messagebox.showerror("Camera Error", self.error_message)
            self.gui.stop_analysis()

    def _normalize_default_crop(self, actual_width, actual_height):
        """Expand legacy live-camera defaults to the detected camera size."""
        if not self.analysis_config or actual_width <= 0 or actual_height <= 0:
            return

        crop_left = self.analysis_config.get('crop_left', 0)
        crop_right = self.analysis_config.get('crop_right', 1280)
        crop_top = self.analysis_config.get('crop_top', 0)
        crop_bottom = self.analysis_config.get('crop_bottom', 720)

        if crop_left == 0 and crop_top == 0 and crop_right == 1280 and crop_bottom == 720:
            self.analysis_config['crop_right'] = actual_width
            self.analysis_config['crop_bottom'] = actual_height
