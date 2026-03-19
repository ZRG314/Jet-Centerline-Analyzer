#!/usr/bin/env python3
"""Simplified test for all reset button functionality (single instance)"""

from gui import JetAnalysisGUI, DEFAULTS
import tkinter as tk

def run_all_tests():
    """Run all reset tests with a single GUI instance"""
    root = tk.Tk()
    app = JetAnalysisGUI(root)
    
    print("\n" + "="*70)
    print("TESTING ALL RESET BUTTONS (Single Instance)")
    print("="*70)
    
    results = {}
    
    # TEST 1: reset_threshold_tab
    print("\nTEST 1: reset_threshold_tab()")
    print("-" * 70)
    print("Initial multi-threshold value labels:", [label.cget('text') for label in app.multi_threshold_value_labels])
    
    # Modify
    app.threshold_offset_var.set(25)
    for i, var in enumerate(app.multi_threshold_offsets):
        var.set(10 + i*5)
    
    print("After modification:", [label.cget('text') for label in app.multi_threshold_value_labels])
    print("Expected after reset:", [str(v) for v in DEFAULTS["multi_threshold_offsets"]])
    
    # Reset
    app.reset_threshold_tab()
    
    print("After reset:       ", [label.cget('text') for label in app.multi_threshold_value_labels])
    
    labels_match = [label.cget('text') for label in app.multi_threshold_value_labels] == \
                   [str(v) for v in DEFAULTS["multi_threshold_offsets"]]
    offset_match = app.threshold_offset_var.get() == DEFAULTS["threshold_offset"]
    
    if labels_match and offset_match:
        results['threshold_tab'] = 'PASS'
        print("✓ PASS: Threshold values and labels reset correctly")
    else:
        results['threshold_tab'] = 'FAIL'
        print("✗ FAIL: Threshold reset issue detected")
        if not labels_match:
            print(f"  - Labels don't match defaults")
        if not offset_match:
            print(f"  - Offset doesn't match defaults")
    
    # TEST 2: reset_basic_tab
    print("\nTEST 2: reset_basic_tab()")
    print("-" * 70)
    print("Initial output name:", app.output_name_entry.get())
    
    # Modify
    app.output_name_entry.delete(0, tk.END)
    app.output_name_entry.insert(0, "test_output")
    print("After modification:", app.output_name_entry.get())
    
    # Reset
    app.reset_basic_tab()
    print("After reset:       ", app.output_name_entry.get())
    print("Expected:          ", DEFAULTS["output_name"])
    
    if app.output_name_entry.get() == DEFAULTS["output_name"]:
        results['basic_tab'] = 'PASS'
        print("✓ PASS: Basic tab output name reset correctly")
    else:
        results['basic_tab'] = 'FAIL'
        print("✗ FAIL: Basic tab output name not reset properly")
    
    # TEST 3: reset_advanced_tab
    print("\nTEST 3: reset_advanced_tab()")
    print("-" * 70)
    print("Initial pixels_per_col:", app.pixel_entry.get())
    print("Initial stdevs:        ", app.stdev_entry.get())
    
    # Modify
    app.pixel_entry.delete(0, tk.END)
    app.pixel_entry.insert(0, "5")
    app.stdev_entry.delete(0, tk.END)
    app.stdev_entry.insert(0, "3")
    print("After modification - pixels_per_col:", app.pixel_entry.get())
    print("After modification - stdevs:        ", app.stdev_entry.get())
    
    # Reset
    app.reset_advanced_tab()
    print("After reset - pixels_per_col:", app.pixel_entry.get())
    print("After reset - stdevs:        ", app.stdev_entry.get())
    print("Expected - pixels_per_col:  ", DEFAULTS["pixels_per_col"])
    print("Expected - stdevs:          ", DEFAULTS["stdevs"])
    
    if (int(app.pixel_entry.get()) == DEFAULTS["pixels_per_col"] and 
        int(app.stdev_entry.get()) == DEFAULTS["stdevs"]):
        results['advanced_tab'] = 'PASS'
        print("✓ PASS: Advanced tab reset correctly")
    else:
        results['advanced_tab'] = 'FAIL'
        print("✗ FAIL: Advanced tab not reset properly")
    
    # TEST 4: reset_calibration_tab
    print("\nTEST 4: reset_calibration_tab()")
    print("-" * 70)
    print("Initial calibration_units:", app.calibration_units_var.get())
    
    # Modify
    app.calibration_distance_var.set("100")
    app.calibration_units_var.set("inches")
    print("After modification - calibration_units:", app.calibration_units_var.get())
    print("After modification - calibration_distance:", app.calibration_distance_var.get())
    
    # Reset
    app.reset_calibration_tab()
    print("After reset - calibration_units:       ", app.calibration_units_var.get())
    print("After reset - calibration_distance:    ", app.calibration_distance_var.get())
    print("Expected - calibration_units:          ", DEFAULTS["calibration_units"])
    print("Expected - calibration_distance:       ", "")
    
    if (app.calibration_units_var.get() == DEFAULTS["calibration_units"] and
        app.calibration_distance_var.get() == ""):
        results['calibration_tab'] = 'PASS'
        print("✓ PASS: Calibration tab reset correctly")
    else:
        results['calibration_tab'] = 'FAIL'
        print("✗ FAIL: Calibration tab not reset properly")
    
    # TEST 5: reset_graph_tab
    print("\nTEST 5: reset_graph_tab()")
    print("-" * 70)
    print("Initial graph_stdevs:    ", app.graph_stdevs_var.get())
    print("Initial graph_fit_degree:", app.graph_fit_degree_var.get())
    print("Initial show_best_fit:   ", app.show_best_fit_var.get())
    
    # Modify
    app.graph_stdevs_var.set("3")
    app.graph_fit_degree_var.set("1")
    app.show_best_fit_var.set(False)
    print("After modification - graph_stdevs:    ", app.graph_stdevs_var.get())
    print("After modification - graph_fit_degree:", app.graph_fit_degree_var.get())
    print("After modification - show_best_fit:  ", app.show_best_fit_var.get())
    
    # Reset
    app.reset_graph_tab()
    print("After reset - graph_stdevs:    ", app.graph_stdevs_var.get())
    print("After reset - graph_fit_degree:", app.graph_fit_degree_var.get())
    print("After reset - show_best_fit:   ", app.show_best_fit_var.get())
    print("Expected - graph_stdevs:       ", app.app_defaults["graph_stdevs"])
    print("Expected - graph_fit_degree:   ", app.app_defaults["graph_fit_degree"])
    print("Expected - show_best_fit:      ", app.app_defaults["show_best_fit"])
    print("(Note: Resets to saved app_defaults, not hardcoded DEFAULTS)")
    
    if (app.graph_stdevs_var.get() == app.app_defaults["graph_stdevs"] and
        app.graph_fit_degree_var.get() == app.app_defaults["graph_fit_degree"] and
        app.show_best_fit_var.get() == app.app_defaults["show_best_fit"]):
        results['graph_tab'] = 'PASS'
        print("✓ PASS: Graph tab reset correctly to saved defaults")
    else:
        results['graph_tab'] = 'FAIL'
        print("✗ FAIL: Graph tab not reset properly")
    
    root.destroy()
    
    # SUMMARY
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for test_name, status in results.items():
        symbol = "✓" if status == "PASS" else "✗"
        print(f"  {symbol} {test_name}: {status}")
    
    passed = sum(1 for s in results.values() if s == "PASS")
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All reset buttons working correctly!")
        return True
    else:
        print(f"\n✗ {total - passed} test(s) failed - please review details above")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
