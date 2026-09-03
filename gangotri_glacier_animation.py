# ---- 1. Install & imports 
!pip install -q earthengine-api geemap imageio imageio-ffmpeg

import ee
import requests
import io
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patheffects as pe
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from IPython.display import Video, display

# ---- 2. Authenticate & initialize 
ee.Authenticate()
ee.Initialize(project='promising-idea-432505-i4')   # change to your GEE project id if different

# ---- 3. AOI: Gangotri Glacier, Uttarakhand 
LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = 78.95, 30.85, 79.30, 31.05
AOI = ee.Geometry.Rectangle([LON_MIN, LAT_MIN, LON_MAX, LAT_MAX])

# Landmarks (approximate published coordinates, for on-frame labelling only)
LANDMARKS = [
    ('Gaumukh (Terminus)', 79.0817, 30.9929),
        ('Bhagirathi Peaks',   79.0231, 30.9092),
    ('Kedar Dome',         79.0667, 30.9167),
    ('Meru Peak',          78.9875, 30.8964),
]

# ---- 4. Year range & sensor selection 
START_YEAR = 1990
END_YEAR   = 2025
YEARS = list(range(START_YEAR, END_YEAR + 1))
DOY_START, DOY_END = '09-15', '10-31'  # post-monsoon, minimal seasonal snow

def sensor_for_year(y):
    # Landsat 5 TM operated through 2011; Landsat 8 OLI from 2013 onward.
    # Only these two sensors are used - no Landsat 7 or 9.
    return 'LANDSAT/LT05/C02/T1_L2' if y <= 2011 else 'LANDSAT/LC08/C02/T1_L2'

def band_map(sensor_id):
    if 'LC08' in sensor_id:
        return {'Blue':'SR_B2','Green':'SR_B3','Red':'SR_B4','NIR':'SR_B5',
                'SWIR1':'SR_B6','SWIR2':'SR_B7'}
    return {'Blue':'SR_B1','Green':'SR_B2','Red':'SR_B3','NIR':'SR_B4',
            'SWIR1':'SR_B5','SWIR2':'SR_B7'}

def scale_sr(img):
    optical = img.select('SR_B.').multiply(0.0000275).add(-0.2)
    return img.addBands(optical, None, True)

def get_year_composite(y):
    sensor_id = sensor_for_year(y)
    coll = ee.ImageCollection(sensor_id).filterBounds(AOI) \
        .filterDate(f'{y}-{DOY_START}', f'{y}-{DOY_END}') \
        .filter(ee.Filter.lt('CLOUD_COVER', 40))
    coll = coll.map(scale_sr)
    bm = band_map(sensor_id)
    composite = coll.median().clip(AOI)
    return composite.select(
        [bm['Blue'], bm['Green'], bm['Red'], bm['NIR'], bm['SWIR1'], bm['SWIR2']],
        ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
    )

def get_fallback_composite(y):
    """Whole-year, looser-cloud-filter composite used ONLY to patch small
    no-data gaps (e.g. WRS-2 path/row swath edges) left by the tighter
    seasonal composite above. Fixes black corner/triangle artifacts without
    changing the glacier-area statistic, which uses the seasonal composite."""
    sensor_id = sensor_for_year(y)
    coll = ee.ImageCollection(sensor_id).filterBounds(AOI) \
        .filterDate(f'{y}-01-01', f'{y}-12-31') \
        .filter(ee.Filter.lt('CLOUD_COVER', 60))
    coll = coll.map(scale_sr)
    bm = band_map(sensor_id)
    composite = coll.median().clip(AOI)
    return composite.select(
        [bm['Blue'], bm['Green'], bm['Red'], bm['NIR'], bm['SWIR1'], bm['SWIR2']],
        ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
    )

def ndsi_band(composite):
    return composite.normalizedDifference(['Green', 'SWIR1']).rename('NDSI')

def glacier_area_km2(ndsi):
    glacier_mask = ndsi.gt(0.4).selfMask()
    area_img = glacier_mask.multiply(ee.Image.pixelArea())
    stats = area_img.reduceRegion(reducer=ee.Reducer.sum(), geometry=AOI,
                                   scale=30, maxPixels=1e10)
    return ee.Number(stats.get('NDSI')).divide(1e6)

# ---- 5. Fetch thumbnails + area stats for every year 
RGB_VIS = {'bands': ['Red', 'Green', 'Blue'], 'min': 0.0, 'max': 0.35, 'gamma': 1.2}
NDSI_PALETTE = ['3a2a1a', '5b8fae', '39c6f0', 'aef1ff', 'ffffff']  # low -> high NDSI
THUMB_W, THUMB_H = 780, 520   # matches AOI bbox aspect ratio

frames_rgb, frames_area, valid_years = [], [], []

print('Fetching yearly composites from Earth Engine (this can take a few minutes)...')
for y in YEARS:
    try:
        comp = get_year_composite(y)
        ndsi = ndsi_band(comp)                       # area stat uses seasonal composite only
        area_km2 = glacier_area_km2(ndsi).getInfo()

        fallback = get_fallback_composite(y)
        neutral_fill = ee.Image.constant([0.12, 0.13, 0.14, 0.20, 0.15, 0.10]).rename(
            ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2'])
        comp_display = comp.unmask(fallback).unmask(neutral_fill)  # patch gaps for display only

        rgb_img = comp_display.visualize(**RGB_VIS)
        ndsi_vis = ndsi.updateMask(ndsi.gt(0.1)).visualize(
            min=0.1, max=0.9, palette=NDSI_PALETTE, opacity=0.75
        )
        blended = ee.ImageCollection([rgb_img, ndsi_vis]).mosaic()

        url = blended.getThumbURL({
            'region': AOI, 'dimensions': f'{THUMB_W}x{THUMB_H}', 'format': 'png'
        })
        resp = requests.get(url, timeout=60)
        img = np.array(Image.open(io.BytesIO(resp.content)).convert('RGB'))

        frames_rgb.append(img)
        frames_area.append(area_km2)
        valid_years.append(y)
        print(f'  {y}: area = {area_km2:.1f} km^2')
    except Exception as e:
        print(f'  {y}: skipped ({e})')

print(f'Collected {len(valid_years)} usable years.')

# ---- 6. Stretch frames to hit target duration at higher FPS 
MIN_DURATION_SEC = 15
FPS = 24
HOLD_FRAMES = max(1, int(np.ceil((MIN_DURATION_SEC * FPS) / max(1, len(valid_years)))))

expanded_rgb, expanded_area, expanded_years = [], [], []
for img, area, yr in zip(frames_rgb, frames_area, valid_years):
    for _ in range(HOLD_FRAMES):
        expanded_rgb.append(img)
        expanded_area.append(area)
        expanded_years.append(yr)

total_frames = len(expanded_rgb)
duration_sec = total_frames / FPS
print(f'Total frames: {total_frames}, FPS: {FPS}, duration: {duration_sec:.1f}s')

# ---- 7. Build the figure 
fig = plt.figure(figsize=(12.4, 6.9), facecolor='black')

ax_map   = fig.add_axes([0.05, 0.17, 0.59, 0.82])    # map frame
ax_cbar  = fig.add_axes([0.15, 0.065, 0.53, 0.03])    # colour ramp BELOW the frame, shifted right
ax_trend = fig.add_axes([0.74, 0.34, 0.23, 0.34])    # shorter trend box

black_outline = [pe.withStroke(linewidth=1.3, foreground='white')]

# -- map panel, plotted in lon/lat coordinates so graticule labels line up --
im_disp = ax_map.imshow(expanded_rgb[0], extent=[LON_MIN, LON_MAX, LAT_MIN, LAT_MAX],
                         origin='upper')
ax_map.set_xlim(LON_MIN, LON_MAX)
ax_map.set_ylim(LAT_MIN, LAT_MAX)

# Graticule LABELS only - no grid lines drawn over the imagery
lon_ticks = [79.00, 79.10, 79.20, 79.30]
lat_ticks = [30.85, 30.90, 30.95, 31.00, 31.05]
ax_map.set_xticks(lon_ticks)
ax_map.set_yticks(lat_ticks)
ax_map.set_xticklabels([f'{v:.2f}°E' for v in lon_ticks])
ax_map.set_yticklabels([f'{v:.2f}°N' for v in lat_ticks])
ax_map.grid(False)
ax_map.tick_params(colors='white', labelsize=8, length=3)
for spine in ax_map.spines.values():
    spine.set_color('white')
    spine.set_linewidth(0.8)

title_txt = ax_map.text(0.02, 0.96, '', transform=ax_map.transAxes, color='black',
                         fontsize=19, fontweight='bold', va='top',
                         path_effects=black_outline)
area_txt = ax_map.text(0.02, 0.06, '', transform=ax_map.transAxes, color='black',
                        fontsize=13, fontweight='bold', va='bottom',
                        path_effects=black_outline)

# static landmark labels (fixed lon/lat position, drawn once)
for name, lon, lat in LANDMARKS:
    if LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX:
        ax_map.plot(lon, lat, marker='^', markersize=7, color='yellow',
                    markeredgecolor='black', markeredgewidth=0.8)
        ax_map.text(lon + 0.004, lat, name, color='black', fontsize=9, fontweight='bold',
                    va='center', path_effects=black_outline)

# north arrow (black, white halo for legibility) - short, fixed in axes fraction coords
ax_map.annotate('', xy=(0.94, 0.90), xytext=(0.94, 0.82), xycoords='axes fraction',
                 arrowprops=dict(facecolor='black', edgecolor='white', width=3,
                                 headwidth=9, headlength=7))
ax_map.text(0.94, 0.925, 'N', transform=ax_map.transAxes, color='black', fontsize=13,
            fontweight='bold', ha='center', path_effects=black_outline)

# -- colour ramp (NDSI legend) below the map --
cmap = LinearSegmentedColormap.from_list('ndsi', ['#' + c for c in NDSI_PALETTE])
gradient = np.linspace(0, 1, 256).reshape(1, -1)
ax_cbar.imshow(gradient, aspect='auto', cmap=cmap, extent=[0.1, 0.9, 0, 1])
ax_cbar.set_yticks([])
ax_cbar.set_xticks([0.1, 0.5, 0.9])
ax_cbar.set_xticklabels(['0.1 (bare/rock)', 'NDSI', '0.9 (snow/ice)'],
                         color='white', fontsize=8)
for spine in ax_cbar.spines.values():
    spine.set_color('white')

# -- trend panel (shorter box); current value lives in the TITLE now so it
#    never sits on top of the line/point -----------------------------------
ax_trend.set_facecolor('black')
trend_title = ax_trend.set_title('Glacier area (km²)', color='white', fontsize=11,
                                  fontweight='bold')
ax_trend.set_xlim(START_YEAR, END_YEAR)
ax_trend.set_ylim(min(frames_area) * 0.9, max(frames_area) * 1.05)
ax_trend.tick_params(colors='white', labelsize=8)
for spine in ax_trend.spines.values():
    spine.set_color('white')
line, = ax_trend.plot([], [], color='#00e5ff', lw=2)
point, = ax_trend.plot([], [], 'o', color='white', markersize=6)

def init():
    line.set_data([], [])
    point.set_data([], [])
    trend_title.set_text('Glacier area (km²)')
    return im_disp, title_txt, area_txt, line, point, trend_title

def update(i):
    im_disp.set_data(expanded_rgb[i])
    yr = expanded_years[i]
    area_val = expanded_area[i]
    title_txt.set_text(f'Gangotri Glacier — {yr}')
    area_txt.set_text(f'Glacier extent: {area_val:.1f} km²')

    idx = valid_years.index(yr) + 1
    line.set_data(valid_years[:idx], frames_area[:idx])
    point.set_data([yr], [area_val])
    trend_title.set_text(f'Glacier area (km²)\n{yr}: {area_val:.1f} km²')
    return im_disp, title_txt, area_txt, line, point, trend_title

ani = animation.FuncAnimation(
    fig, update, frames=total_frames, init_func=init, blit=False, interval=1000 / FPS
)

fig.text(0.87, 0.15, 'Data Source:- Landsat 5 & Landsat 8', color='white',
          fontsize=9.5, ha='center')

OUTPUT_PATH = '/content/gangotri_glacier_melt.mp4'
writer = animation.FFMpegWriter(fps=FPS, bitrate=3500)
ani.save(OUTPUT_PATH, writer=writer, dpi=150)
plt.close(fig)

print(f'Saved animation to {OUTPUT_PATH} ({duration_sec:.1f}s)')

# ---- 8. Preview + download in Colab 
display(Video(OUTPUT_PATH, embed=True, width=880))

from google.colab import files
files.download(OUTPUT_PATH)
