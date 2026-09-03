#  Gangotri Glacier Melt Analysis Using Remote Sensing


##  Overview

This project analyzes long-term changes in **Gangotri Glacier, Uttarakhand, India**, using Landsat satellite imagery and Google Earth Engine.

The workflow generates annual post-monsoon composites, calculates the **Normalized Difference Snow Index (NDSI)**, estimates snow/ice-covered area, and creates a temporal animation showing changes from **1990–2025**.

##  Objectives

* Monitor long-term changes in Gangotri Glacier.
* Estimate annual snow/ice extent using NDSI.
* Analyze temporal changes from 1990–2025.
* Visualize spatial and temporal glacier changes.
* Generate an automated research-style animation.

##  Data

| Parameter       | Details                       |
| --------------- | ----------------------------- |
| Study Area      | Gangotri Glacier, Uttarakhand |
| Period          | 1993–2025                     |
| Sensors         | Landsat 5 TM & Landsat 8 OLI  |
| Resolution      | 30 m                          |
| Platform        | Google Earth Engine           |
| Index           | NDSI                          |
| Seasonal Window | 15 September–31 October       |

### Earth Engine Collections

```text
LANDSAT/LT05/C02/T1_L2
LANDSAT/LC08/C02/T1_L2
```

##  Methodology

The workflow follows:

```text
Landsat Imagery
      ↓
Cloud Filtering
      ↓
Surface Reflectance Scaling
      ↓
Annual Post-Monsoon Composite
      ↓
NDSI Calculation
      ↓
NDSI > 0.4
      ↓
Snow/Ice Area Calculation
      ↓
Annual Time Series
      ↓
Animation
```

### NDSI

$$
NDSI = \frac{Green-SWIR1}{Green+SWIR1}
$$

Pixels with **NDSI > 0.4** are used to estimate snow/ice-covered area.

##  Output

The project produces an MP4 animation containing:

* Landsat RGB imagery
* NDSI overlay
* Annual snow/ice extent
* Estimated area in km²
* Temporal trend graph
* Map coordinates and landmarks

Output:

```text
gangotri_glacier_melt.mp4
```

## 💻 Run the Project

Install dependencies:

```bash
pip install -r requirements.txt
```

Authenticate with Google Earth Engine:

```python
ee.Authenticate()
ee.Initialize(project='YOUR_GEE_PROJECT_ID')
```

Then run:

```text
gangotri_glacier_animation.py
```


## ⚠️ Limitations

NDSI-based classification can also detect seasonal snow outside the glacier and may miss debris-covered ice. Therefore, the estimated area should be considered **NDSI-derived snow/ice extent** and should be validated with glacier boundaries or additional datasets for publication-quality analysis.


## 👨‍💻 Author

**Aditya Pal**
Department of Geography (VISVA-BHARATI)

