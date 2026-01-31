# Blender Fast Earth Importer (Earth 2 MSFS)
An ultra-fast, hybrid GLTF importer for Blender designed specifically for massive-scale 3D map tile imports downloaded via **Earth 2 MSFS**. By bypassing Blender’s standard overhead-heavy GLTF module, this script reduces import times for 10,000+ tiles from 7 hours to under 5 minutes (a 98.81% decrease). See how to use E2MSFS here -> https://www.youtube.com/watch?v=eug3NGpmv-0

Google Earth Decoder: https://flightsim.to/file/39900/gogole-earth-decoder-update


## Required Directory Structure
For the script to function correctly, organize your project folder as shown below. You must manually create the cache and progress directories.

```text
- My_Project_Name/
  ├── modelLib/                 # Exported from 'Earth 2 MSFS'
  │   ├── texture/              # All .png / .dds texture files
  │   ├── *.gltf                # Geometry files
  │   ├── *.bin                 # Binary data files
  │   └── *.xml                 # MSFS metadata
  ├── scene/                    # MSFS scene definition folder
  ├── cache/                    # [REQUIRED] Create this folder for .pkl data
  └── progress/                 # [REQUIRED] Create this folder for .json logs
```

## Getting Started
1. Installation
    - Open Blender (Recommended: 3.6 LTS or 4.0+).
    - Start a new, clean file.
    - Switch to the Scripting workspace and click + New.
    - Paste the content of hybrid_fast_importer.py into the editor.

2. Configuration
- At the top of the script, update the absolute paths to match your local machine:
```python
# 1. PATH TO YOUR GLTF FILES
GLTF_FOLDER = r"C:\Users\...\project-name\modelLib"

# 2. PATH TO YOUR TEXTURES
TEXTURE_FOLDER = r"C:\Users\...\project-name\modelLib\texture"

# 3. CACHE LOCATIONS (Delete these files to force a rebuild!)
CACHE_FILE = r"C:\Users\...\project-name\cache\gltf_cache.pkl"
PROGRESS_FILE = r"C:\Users\...\project-name\progress\import_progress.json"
```

3. Execution
    - Press the Run Script (Play) button.
    - Check the System Console (Window > Toggle System Console) to view real-time progress.
    - Go over to the 3D Viewport in Material Preview or Rendered mode to see textures.


## Features
  - Low-Level Parsing: Directly extracts vertex and index data from binary buffers, skipping heavy Python-to-Blender API calls.
  - Intelligent UV Mapping: Automatically flips V-coordinates to match Blender's coordinate system and maps them to face loops.
  - Shader Automation: Bulk-creates Principled BSDF materials and links texture maps automatically.
  - Material Instancing: Identifies duplicate textures to prevent memory bloat, ensuring each unique texture is only loaded into VRAM once.
  - Collection Organization: Automatically sorts imported tiles into collections based on their filename for easy management.

|Metric	| Native Blender GLTF |	Ultrafast GLTF Importer|
|----|----|----|
|10,000 Tiles (LOD-0)	| ~7 Hours	| < 5 Minutes|
|Speed	| 1x |	84x faster|
|Stability |	High risk of crash/hang	| Low memory overhead|

## Notes
- Cache Rebuild: If you change your textures or move the project, delete the .pkl file inside the cache folder to force the script to re-scan the geometry.
- MSFS Specifics: This script is optimized for the output format of Earth 2 MSFS. While it may work for general GLTF files, it is tuned for the specific buffer arrangements found in Google Earth 3D tiles.

- Feel free to clone this repo and improve it, or make a push request.

Disclaimer: this script was created with the assistance of Claude AI, it went through multiple iterations until it worked as I wished.
