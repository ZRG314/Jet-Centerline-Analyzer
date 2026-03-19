# Jet Centerline Analyzer — Quick GUI Guide (for students)

This guide explains how to use the application from the graphical interface only. It assumes you are operating the program via its windows and buttons — no programming or terminal steps are required.

## What this app does (short)

- Loads a video or live camera feed and locates the jet centerline in each frame.
- Produces an annotated analysis video and summary graphs/data (exportable as image and CSV).

## General workflow (what you'll do)

1. Choose or capture a video in the **Basic** tab.
2. (Optional) Crop the preview so the image contains only the jet region.
3. Select a frame range to analyze (or use the full video).
4. Adjust a small set of processing options (simple defaults are provided).
5. Click **Run** to analyze; watch the progress and preview.
6. Open the **Graphs** tab to view and export results.

## Basic Tab — essential controls (what each item does)

- **Video Source**: Pick `Video File` to analyze a file, or `Live Camera` to use a connected camera.
- **Select Video**: Opens a file chooser to pick a recorded video (only shown for file mode).
- **Output File Name**: Base name for the analysis video the app will create.
- **Output Directory**: Folder where the analysis video and exports are saved.
- **Preview Mode**: Choose what shows during processing:
  - *Analysis Preview* — annotated centerline overlay shown on frames.
  - *Threshold Preview* — binary/threshold view useful for tuning parameters.
  - *No Preview* — turns off live preview to speed up processing.
- **Threshold Offset**: Small integer that shifts the threshold used to detect jet pixels. Higher = stricter (fewer detected pixels). A reasonable default is shown.
- **Progress / Elapsed**: Shows progress, elapsed time and current frame.
- **Run / Stop**: Start or stop analysis. If you stop, the app attempts a graceful stop and saves partial results if available.

## Advanced Tab — frame range and sampling

- **Frame Range Slider**: Drag the red handles to choose the start/end frames to analyze. The numeric Start/End entries update as you drag.
- **Use full video**: Quickly select the entire video for processing.
- **Pixels per Column**: Controls horizontal sampling density. Smaller numbers sample more points across the jet (higher detail, slower). Larger numbers run faster but are coarser.
- **Standard Deviations**: Controls the width of the confidence band shown around the mean centerline on the graph.

## Crop Tab — isolate the jet area

1. Click the **Crop** tab and then click **Save Crop** to enter crop mode.
2. Drag the red rectangle to position it over the jet region. Resize by dragging the red corners.
3. When the box covers only the jet and excludes bright background regions, click **Save Crop** again to apply it.

Why crop? Cropping removes background and reduces false detections, improving accuracy and speed.

## Calibration Tab — convert pixels to real units

- **Set Calibration Line**: Draw a line over a feature of known real-world length (e.g., a ruler in the image).
- Enter the real distance and choose units (mm, cm, in), then click **Apply Calibration**. Graph axes and exported data will use these units.
- **Set Nozzle Origin**: Click the nozzle exit point on the preview so graphs can reference distances from the nozzle.

Use calibration when you need measurements in physical units instead of pixels.

## Graphs Tab — view and export results

- The graph shows the mean centerline and a confidence band (standard deviation).
- Options let you change axis labels, set axis bounds, choose polynomial fit degree, and toggle the best-fit line.
- **Save Graph Image** produces a copy of the plotted graph for reports.
- **Save Graph Data (CSV)** writes numerical columns (X position, mean, std, and fitted values) for downstream analysis.

## Preview modes and what to watch for

- **Analysis Preview**: Look for a smooth centerline following the jet. If it jumps or appears noisy, consider cropping more tightly or adjusting threshold/pixels-per-column.
- **Threshold Preview**: Shows the binary image used for centerline extraction — useful for tuning the Threshold Offset.
- **No Preview**: Turn this on for faster processing on long or high-resolution videos.

## Recommended starting values (students)

- Threshold Offset: 15 (good starting point)
- Pixels per Column: 3 (balance between speed and resolution)
- Standard Deviations (graph): 2

These are sensible defaults; small adjustments may improve results for specific videos.

## Example simple workflow (one-paragraph)

Open the app, select your recorded video in the Basic tab, then go to Crop and draw a tight box around the jet (exclude background lights). In Advanced select the full video or a sub-range you want analyzed. Leave the default processing values, then click Run. Watch the Analysis Preview to confirm the centerline looks reasonable; after the run, open the Graphs tab to save the graph image and CSV for your report.

## Troubleshooting (student-focused)

- If the centerline is noisy or jumps:
  - Tighten the crop to exclude background light or nozzle reflections.
  - Switch to **Threshold Preview** and increase the **Threshold Offset** slightly until the jet appears as a clean region.
  - Increase **Pixels per Column** to smooth short-wavelength noise (at the cost of speed).
- If the app reports it cannot save results or exports are missing:
  - Check the **Output Directory** shown in the Basic tab and choose a different folder using the Browse button.
- If live camera preview is blank:
  - Ensure the camera is connected and not used by another application; try switching back to Video File and re-selecting your recorded sample.

## What you will get after an analysis

- An annotated analysis video (saved to the Output Directory with the name you provided).
- A graph image showing mean centerline and confidence band.
- A CSV file with numeric columns you can import into Excel or MATLAB for plotting or further analysis.

## Support

If you need help while using the GUI, note the settings you used (crop on/off, Threshold Offset, Pixels per Column, frame range) and show a screenshot of the preview and the Graphs tab to your instructor or project lead.

---

This guide is focused purely on using the graphical interface. Tell me if you want a second page with annotated screenshots or a one-page cheat-sheet for lab handouts.

---

This file is a starting point; I can expand any section (parameter reference, sample outputs, troubleshooting examples) next. Suggestion: add a `requirements.txt` and an example output snapshot directory under `results/` for user reference.
