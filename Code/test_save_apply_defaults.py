#!/usr/bin/env python3
"""Test save and apply startup defaults functionality"""

from gui import JetAnalysisGUI, DEFAULTS, load_app_defaults, save_app_defaults
import tkinter as tk
import json
import os

def test_save_and_apply():
    """Test that save + apply restores exact same values"""
    root = tk.Tk()
    app = JetAnalysisGUI(root)
    
    print("\n" + "="*70)
    print("TEST: Save and Apply Startup Defaults")
    print("="*70)
    
    # Modify some UI values
    print("\n1. Modifying UI values...")
    app.threshold_offset_var.set(42)
    app.output_name_entry.delete(0, tk.END)
    app.output_name_entry.insert(0, "test_output_name")
    app.output_dir.set("C:\\custom\\output\\path")
    app.graph_stdevs_var.set("5")
    app.pixel_entry.delete(0, tk.END)
    app.pixel_entry.insert(0, "7")
    
    print(f"  threshold_offset: {app.threshold_offset_var.get()}")
    print(f"  output_name: {app.output_name_entry.get()}")
    print(f"  output_dir: {app.output_dir.get()}")
    print(f"  graph_stdevs: {app.graph_stdevs_var.get()}")
    print(f"  pixels_per_col: {app.pixel_entry.get()}")

    print("\n1b. Setting non-persisted runtime state that apply should preserve...")
    app.project_path = "projects/test_project.json"
    app.calibration_distance_var.set("123.45")
    print(f"  project_path: {app.project_path}")
    print(f"  calibration_distance: {app.calibration_distance_var.get()}")
    
    # Save as startup defaults
    print("\n2. Saving current values as startup defaults...")
    app.save_current_as_startup_defaults()
    
    # Check what was saved to file
    print("\n3. Checking what was saved to file...")
    settings_path = app.settings_path
    if os.path.exists(settings_path):
        with open(settings_path, 'r') as f:
            saved_data = json.load(f)
        print(f"  File exists at: {settings_path}")
        print(f"  Saved threshold_offset: {saved_data.get('threshold_offset', 'MISSING')}")
        print(f"  Saved output_name: {saved_data.get('output_name', 'MISSING')}")
        print(f"  Saved output_dir: {saved_data.get('output_dir', 'MISSING')}")
        print(f"  Saved graph_stdevs: {saved_data.get('graph_stdevs', 'MISSING')}")
        print(f"  Saved pixels_per_col: {saved_data.get('pixels_per_col', 'MISSING')}")
    else:
        print(f"  ERROR: Settings file not found at {settings_path}")
        return False
    
    # Now change the UI values to something different
    print("\n4. Changing UI values to different values...")
    app.threshold_offset_var.set(15)
    app.output_name_entry.delete(0, tk.END)
    app.output_name_entry.insert(0, "different_name")
    app.output_dir.set("")
    app.graph_stdevs_var.set("2")
    app.pixel_entry.delete(0, tk.END)
    app.pixel_entry.insert(0, "3")
    
    print(f"  threshold_offset: {app.threshold_offset_var.get()}")
    print(f"  output_name: {app.output_name_entry.get()}")
    print(f"  output_dir: {app.output_dir.get()}")
    print(f"  graph_stdevs: {app.graph_stdevs_var.get()}")
    print(f"  pixels_per_col: {app.pixel_entry.get()}")
    
    # Apply startup defaults
    print("\n5. Applying startup defaults...")
    app.apply_startup_defaults_now()
    
    # Check what values are in the UI now
    print("\n6. Checking UI values after applying startup defaults...")
    current_threshold = app.threshold_offset_var.get()
    current_output_name = app.output_name_entry.get()
    current_output_dir = app.output_dir.get()
    current_stdevs = app.graph_stdevs_var.get()
    current_pixels = app.pixel_entry.get()
    current_project_path = app.project_path
    current_calibration_distance = app.calibration_distance_var.get()
    
    print(f"  threshold_offset: {current_threshold} (expected: 42)")
    print(f"  output_name: {current_output_name} (expected: test_output_name)")
    print(f"  output_dir: {current_output_dir} (expected: C:\\custom\\output\\path)")
    print(f"  graph_stdevs: {current_stdevs} (expected: 5)")
    print(f"  pixels_per_col: {current_pixels} (expected: 7)")
    print(f"  project_path: {current_project_path} (expected preserved: projects/test_project.json)")
    print(f"  calibration_distance: {current_calibration_distance} (expected preserved: 123.45)")
    
    # Verify
    threshold_match = current_threshold == 42
    output_name_match = current_output_name == "test_output_name"
    output_dir_match = current_output_dir == "C:\\custom\\output\\path"
    stdevs_match = current_stdevs == "5"
    pixels_match = current_pixels == "7"
    project_path_match = current_project_path == "projects/test_project.json"
    calibration_distance_match = current_calibration_distance == "123.45"
    
    print("\n" + "="*70)
    print("RESULTS:")
    print("="*70)
    
    all_match = (
        threshold_match and output_name_match and output_dir_match and stdevs_match and pixels_match
        and project_path_match and calibration_distance_match
    )
    
    if not threshold_match:
        print(f"  ✗ threshold_offset: {current_threshold} != 42")
    else:
        print(f"  ✓ threshold_offset matches")
    
    if not output_name_match:
        print(f"  ✗ output_name: '{current_output_name}' != 'test_output_name'")
    else:
        print(f"  ✓ output_name matches")
    
    if not output_dir_match:
        print(f"  ✗ output_dir: '{current_output_dir}' != 'C:\\custom\\output\\path'")
    else:
        print(f"  ✓ output_dir matches")
    
    if not stdevs_match:
        print(f"  ✗ graph_stdevs: '{current_stdevs}' != '5'")
    else:
        print(f"  ✓ graph_stdevs matches")
    
    if not pixels_match:
        print(f"  ✗ pixels_per_col: '{current_pixels}' != '7'")
    else:
        print(f"  ✓ pixels_per_col matches")

    if not project_path_match:
        print(f"  ✗ project_path: '{current_project_path}' != 'projects/test_project.json'")
    else:
        print(f"  ✓ project_path preserved")

    if not calibration_distance_match:
        print(f"  ✗ calibration_distance: '{current_calibration_distance}' != '123.45'")
    else:
        print(f"  ✓ calibration_distance preserved")
    
    if all_match:
        print("\n✓ SUCCESS: All values restored correctly!")
    else:
        print("\n✗ FAILURE: Some values were not restored correctly")
    
    root.destroy()
    return all_match

if __name__ == "__main__":
    success = test_save_and_apply()
    exit(0 if success else 1)
