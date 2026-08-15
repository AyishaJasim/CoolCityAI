import os
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np

# ============================================================
# OPTIONAL LIBRARIES
# ============================================================

try:
    import ee
    EE_AVAILABLE = True
except Exception:
    EE_AVAILABLE = False

try:
    from streamlit_geolocation import streamlit_geolocation
    GEOLOCATION_AVAILABLE = True
except Exception:
    GEOLOCATION_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="CoolCity AI",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 1.5rem;
    }

    .hero {
        padding: 25px;
        border-radius: 20px;
        border: 1px solid rgba(128,128,128,0.25);
        margin-bottom: 25px;
    }

    .risk-card {
        padding: 25px;
        border-radius: 20px;
        border: 1px solid rgba(128,128,128,0.25);
        margin: 10px 0 20px 0;
    }

    .recommendation {
        padding: 16px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,0.20);
        margin-bottom: 12px;
    }

    .section-title {
        font-size: 1.7rem;
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "latitude": None,
    "longitude": None,
    "location_source": None,
    "satellite": None,
    "photo_results": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🌍 CoolCity AI</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR — LOCATION
# ============================================================

st.sidebar.title("📍 Location")

st.sidebar.write(
    "Choose the area you want CoolCity AI to analyse."
)

# ------------------------------------------------------------
# AUTOMATIC LOCATION
# ------------------------------------------------------------

st.sidebar.subheader("Automatic location")

if GEOLOCATION_AVAILABLE:

    st.sidebar.caption(
        "Click the location button below and allow browser location access."
    )

    with st.sidebar:
        location = streamlit_geolocation()

    if location:

        detected_lat = location.get("latitude")
        detected_lon = location.get("longitude")

        if (
            detected_lat is not None
            and detected_lon is not None
        ):

            st.session_state.latitude = float(
                detected_lat
            )

            st.session_state.longitude = float(
                detected_lon
            )

            st.session_state.location_source = (
                "Browser GPS"
            )

            st.sidebar.success(
                "📍 Location detected"
            )

else:

    st.sidebar.error(
        "Location component is not installed."
    )

# ------------------------------------------------------------
# MANUAL COORDINATES
# ------------------------------------------------------------

st.sidebar.subheader("Manual coordinates")

manual_lat = st.sidebar.number_input(
    "Latitude",
    min_value=-90.0,
    max_value=90.0,
    value=25.285400,
    format="%.6f",
)

manual_lon = st.sidebar.number_input(
    "Longitude",
    min_value=-180.0,
    max_value=180.0,
    value=51.531000,
    format="%.6f",
)

if st.sidebar.button(
    "Use these coordinates",
    width="stretch",
):

    st.session_state.latitude = manual_lat
    st.session_state.longitude = manual_lon
    st.session_state.location_source = "Manual"

    st.session_state.satellite = None
    st.session_state.photo_results = None

# ------------------------------------------------------------
# CURRENT LOCATION
# ------------------------------------------------------------

if (
    st.session_state.latitude is not None
    and st.session_state.longitude is not None
):

    st.sidebar.divider()

    st.sidebar.subheader(
        "Current location"
    )

    st.sidebar.write(
        f"**Latitude:** "
        f"{st.session_state.latitude:.6f}"
    )

    st.sidebar.write(
        f"**Longitude:** "
        f"{st.session_state.longitude:.6f}"
    )

    st.sidebar.caption(
        f"Source: {st.session_state.location_source}"
    )

else:

    st.sidebar.info(
        "Choose a location to begin."
    )


# ============================================================
# CURRENT LOCATION VARIABLES
# ============================================================

lat = st.session_state.latitude
lon = st.session_state.longitude


# ============================================================
# WEATHER
# ============================================================

@st.cache_data(ttl=600)
def get_weather(latitude, longitude):

    if not REQUESTS_AVAILABLE:
        return None

    try:

        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "apparent_temperature,"
                "wind_speed_10m"
            ),
            "timezone": "auto",
        }

        response = requests.get(
            url,
            params=params,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()

    except Exception:
        return None


# ============================================================
# EARTH ENGINE
# ============================================================

def initialize_earth_engine():

    if not EE_AVAILABLE:

        return False, (
            "Google Earth Engine is not installed."
        )

    try:

        project = os.environ.get(
            "EE_PROJECT",
            "coolcity-ai-505519",
        )

        ee.Initialize(
            project=project
        )

        return True, "Earth Engine connected."

    except Exception as error:

        return False, str(error)


# ============================================================
# SATELLITE ANALYSIS
# ============================================================

@st.cache_data(ttl=3600)
def get_satellite_data(
    latitude,
    longitude,
):

    success, message = initialize_earth_engine()

    if not success:

        return {
            "success": False,
            "message": message,
        }

    try:

        point = ee.Geometry.Point(
            [
                longitude,
                latitude,
            ]
        )

        region = point.buffer(500)

        start_date = (
            datetime.utcnow()
            - timedelta(days=365)
        )

        end_date = datetime.utcnow()

        # ----------------------------------------------------
        # SENTINEL-2
        # ----------------------------------------------------

        sentinel_collection = (
            ee.ImageCollection(
                "COPERNICUS/S2_SR_HARMONIZED"
            )
            .filterBounds(region)
            .filterDate(
                start_date,
                end_date,
            )
            .filter(
                ee.Filter.lt(
                    "CLOUDY_PIXEL_PERCENTAGE",
                    20,
                )
            )
        )

        sentinel_count = (
            sentinel_collection
            .size()
            .getInfo()
        )

        ndvi_value = None

        if sentinel_count > 0:

            sentinel = (
                sentinel_collection
                .median()
            )

            ndvi = (
                sentinel
                .normalizedDifference(
                    [
                        "B8",
                        "B4",
                    ]
                )
                .rename("NDVI")
            )

            ndvi_value = (
                ndvi.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=region,
                    scale=20,
                    maxPixels=1e8,
                )
                .get("NDVI")
                .getInfo()
            )

        # ----------------------------------------------------
        # LANDSAT 8
        # ----------------------------------------------------

        landsat_8 = (
            ee.ImageCollection(
                "LANDSAT/LC08/C02/T1_L2"
            )
            .filterBounds(region)
            .filterDate(
                start_date,
                end_date,
            )
            .filter(
                ee.Filter.lt(
                    "CLOUD_COVER",
                    40,
                )
            )
        )

        # ----------------------------------------------------
        # LANDSAT 9
        # ----------------------------------------------------

        landsat_9 = (
            ee.ImageCollection(
                "LANDSAT/LC09/C02/T1_L2"
            )
            .filterBounds(region)
            .filterDate(
                start_date,
                end_date,
            )
            .filter(
                ee.Filter.lt(
                    "CLOUD_COVER",
                    40,
                )
            )
        )

        landsat = (
            landsat_8
            .merge(landsat_9)
        )

        landsat_count = (
            landsat
            .size()
            .getInfo()
        )

        lst_value = None

        if landsat_count > 0:

            image = ee.Image(
                landsat
                .sort("CLOUD_COVER")
                .first()
            )

            lst = (
                image
                .select("ST_B10")
                .multiply(0.00341802)
                .add(149.0)
                .subtract(273.15)
            )

            lst_value = (
                lst.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=region,
                    scale=100,
                    maxPixels=1e8,
                )
                .get("ST_B10")
                .getInfo()
            )

        return {
            "success": True,
            "ndvi": ndvi_value,
            "lst": lst_value,
            "sentinel_images": sentinel_count,
            "landsat_images": landsat_count,
        }

    except Exception as error:

        return {
            "success": False,
            "message": str(error),
        }


# ============================================================
# HEAT RISK CALCULATION
# ============================================================

def calculate_heat_risk(
    temperature=None,
    humidity=None,
    ndvi=None,
    lst=None,
    photo_results=None,
):

    score = 0
    factors = []

    # --------------------------------------------------------
    # AIR TEMPERATURE
    # --------------------------------------------------------

    if temperature is not None:

        if temperature >= 40:

            score += 30

            factors.append(
                "Very high air temperature"
            )

        elif temperature >= 35:

            score += 25

            factors.append(
                "High air temperature"
            )

        elif temperature >= 30:

            score += 15

        elif temperature >= 25:

            score += 7

    # --------------------------------------------------------
    # HUMIDITY
    # --------------------------------------------------------

    if humidity is not None:

        if humidity >= 75:

            score += 15

            factors.append(
                "High humidity"
            )

        elif humidity >= 60:

            score += 10

            factors.append(
                "Elevated humidity"
            )

        elif humidity >= 45:

            score += 5

    # --------------------------------------------------------
    # NDVI
    # --------------------------------------------------------

    if ndvi is not None:

        if ndvi < 0.15:

            score += 20

            factors.append(
                "Very low vegetation"
            )

        elif ndvi < 0.30:

            score += 15

            factors.append(
                "Low vegetation"
            )

        elif ndvi < 0.50:

            score += 8

    # --------------------------------------------------------
    # LAND SURFACE TEMPERATURE
    # --------------------------------------------------------

    if lst is not None:

        if lst >= 45:

            score += 25

            factors.append(
                "Very high land-surface temperature"
            )

        elif lst >= 40:

            score += 20

            factors.append(
                "High land-surface temperature"
            )

        elif lst >= 35:

            score += 12

            factors.append(
                "Elevated land-surface temperature"
            )

    # --------------------------------------------------------
    # PHOTO ANALYSIS
    # --------------------------------------------------------

    if photo_results:

        if photo_results.get(
            "low_vegetation"
        ):

            score += 5

            factors.append(
                "Low visible vegetation in uploaded image"
            )

        if photo_results.get(
            "high_brightness"
        ):

            score += 3

            factors.append(
                "Large bright/exposed surface areas detected in image"
            )

    score = min(
        int(score),
        100,
    )

    if score >= 75:

        level = "VERY HIGH"
        priority = "URGENT"

    elif score >= 55:

        level = "HIGH"
        priority = "HIGH"

    elif score >= 35:

        level = "MODERATE"
        priority = "MEDIUM"

    else:

        level = "LOW"
        priority = "LOW"

    return (
        score,
        level,
        priority,
        factors,
    )


# ============================================================
# COOLING RECOMMENDATIONS
# ============================================================

def generate_recommendations(
    temperature,
    humidity,
    ndvi,
    lst,
    photo_results=None,
):

    recommendations = []

    # --------------------------------------------------------
    # SATELLITE-BASED
    # --------------------------------------------------------

    if lst is not None and lst >= 40:

        recommendations.append(
            (
                "🌳 Increase tree canopy",
                "Satellite land-surface temperatures are high. "
                "Additional shade and vegetation should be prioritized."
            )
        )

        recommendations.append(
            (
                "🏙️ Prioritize this area",
                "The measured surface heat makes this location "
                "a high-priority candidate for cooling interventions."
            )
        )

    if ndvi is not None and ndvi < 0.30:

        recommendations.append(
            (
                "🌱 Add vegetation",
                "The satellite-derived NDVI indicates limited vegetation."
            )
        )

        recommendations.append(
            (
                "🌿 Create green corridors",
                "Connect existing vegetation with shaded pedestrian "
                "routes and planted corridors."
            )
        )

    # --------------------------------------------------------
    # WEATHER-BASED
    # --------------------------------------------------------

    if temperature is not None and temperature >= 35:

        recommendations.append(
            (
                "🧊 Create cooling spaces",
                "High air temperature makes shaded or cooled public "
                "spaces especially valuable."
            )
        )

        recommendations.append(
            (
                "🚰 Improve water access",
                "Accessible drinking-water points can help people "
                "during periods of extreme heat."
            )
        )

    if humidity is not None and humidity >= 60:

        recommendations.append(
            (
                "🌬️ Improve airflow",
                "Elevated humidity can increase perceived heat. "
                "Urban design should avoid blocking natural airflow."
            )
        )

    # --------------------------------------------------------
    # PHOTO-BASED
    # --------------------------------------------------------

    if photo_results:

        if photo_results.get(
            "low_vegetation"
        ):

            recommendations.append(
                (
                    "🌳 Add visible shade and planting",
                    "The uploaded image shows limited visible vegetation. "
                    "Trees, planted areas and shade structures could "
                    "improve pedestrian comfort."
                )
            )

        if photo_results.get(
            "high_brightness"
        ):

            recommendations.append(
                (
                    "🏠 Consider reflective surfaces",
                    "The image contains highly bright/exposed surfaces. "
                    "Reflective or high-albedo materials may help reduce "
                    "heat absorption."
                )
            )

        if photo_results.get(
            "possible_paved_area"
        ):

            recommendations.append(
                (
                    "🚶 Shade paved pedestrian areas",
                    "The visual analysis suggests substantial exposed "
                    "hard surfaces. Prioritize shade along walking routes."
                )
            )

    # --------------------------------------------------------
    # GENERAL RECOMMENDATIONS
    # --------------------------------------------------------

    recommendations.append(
        (
            "🏠 Cool roofs",
            "Reflective roofing can reduce the amount of solar heat "
            "absorbed by buildings."
        )
    )

    recommendations.append(
        (
            "🚶 Shaded pedestrian routes",
            "Prioritize shade along frequently used walking routes."
        )
    )

    return recommendations


# ============================================================
# GET WEATHER
# ============================================================

weather = None

if lat is not None and lon is not None:

    weather = get_weather(
        lat,
        lon,
    )


# ============================================================
# MAIN DASHBOARD
# ============================================================

if lat is None or lon is None:

    st.markdown(
        """
        <div class="hero">
        <h2>Welcome to CoolCity AI 🌍</h2>
        <p>
        Select a location from the sidebar to begin your
        urban heat analysis.
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.subheader(
            "📍 Locate"
        )

        st.write(
            "Use your location or enter coordinates manually."
        )

    with c2:

        st.subheader(
            "🛰️ Analyse"
        )

        st.write(
            "Combine weather and satellite environmental data."
        )

    with c3:

        st.subheader(
            "💡 Act"
        )

        st.write(
            "Generate targeted urban cooling recommendations."
        )

else:

    # ========================================================
    # CURRENT WEATHER VALUES
    # ========================================================

    temperature = None
    humidity = None
    apparent_temperature = None
    wind_speed = None

    if weather:

        current = weather.get(
            "current",
            {},
        )

        temperature = current.get(
            "temperature_2m"
        )

        humidity = current.get(
            "relative_humidity_2m"
        )

        apparent_temperature = current.get(
            "apparent_temperature"
        )

        wind_speed = current.get(
            "wind_speed_10m"
        )

    # ========================================================
    # CURRENT SATELLITE VALUES
    # ========================================================

    satellite = st.session_state.satellite

    ndvi = None
    lst = None

    if satellite:

        ndvi = satellite.get(
            "ndvi"
        )

        lst = satellite.get(
            "lst"
        )

    # ========================================================
    # CALCULATE RISK
    # ========================================================

    score, level, priority, factors = (
        calculate_heat_risk(
            temperature,
            humidity,
            ndvi,
            lst,
            st.session_state.photo_results,
        )
    )

    # ========================================================
    # DASHBOARD HEADER
    # ========================================================

    st.markdown(
        f"""
        <div class="hero">
        <h2>📍 Location Analysis</h2>
        <p>
        {lat:.6f}, {lon:.6f}
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ========================================================
    # METRICS
    # ========================================================

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:

        st.metric(
            "🌡️ Air Temperature",
            (
                f"{temperature:.1f} °C"
                if temperature is not None
                else "—"
            ),
        )

    with c2:

        st.metric(
            "🌡️ Surface Temperature",
            (
                f"{lst:.1f} °C"
                if lst is not None
                else "—"
            ),
        )

    with c3:

        st.metric(
            "🌱 NDVI",
            (
                f"{ndvi:.3f}"
                if ndvi is not None
                else "—"
            ),
        )

    with c4:

        st.metric(
            "💧 Humidity",
            (
                f"{humidity:.0f}%"
                if humidity is not None
                else "—"
            ),
        )

    with c5:

        st.metric(
            "🔥 Risk Score",
            f"{score}/100",
        )

    st.divider()

    # ========================================================
    # HEAT RISK
    # ========================================================

    st.markdown(
        '<div class="section-title">🔥 Urban Heat Risk</div>',
        unsafe_allow_html=True,
    )

    st.progress(
        score / 100
    )

    st.markdown(
        f"""
        <div class="risk-card">
        <h1>{level}</h1>
        <h2>{score}/100</h2>
        <p>
        Intervention priority:
        <strong>{priority}</strong>
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if factors:

        st.subheader(
            "🔎 Factors influencing the assessment"
        )

        for factor in factors:

            st.write(
                f"• {factor}"
            )

    # ========================================================
    # MAP
    # ========================================================

    st.subheader(
        "🗺️ Analysis Location"
    )

    location_df = pd.DataFrame(
        {
            "latitude": [lat],
            "longitude": [lon],
        }
    )

    st.map(
        location_df,
        latitude="latitude",
        longitude="longitude",
        zoom=13,
    )


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🛰️ Satellite Intelligence",
        "📊 Environmental Data",
        "📷 Photo Analysis",
        "💡 Cooling Plan",
    ]
)


# ============================================================
# TAB 1 — SATELLITE
# ============================================================

with tab1:

    st.header(
        "🛰️ Satellite Intelligence"
    )

    if lat is None or lon is None:

        st.warning(
            "Select a location first."
        )

    else:

        st.write(
            """
            Analyse vegetation and land-surface temperature
            around the selected location using satellite imagery.
            """
        )

        if st.button(
            "🛰️ Run Satellite Analysis",
            width="stretch",
        ):

            with st.spinner(
                "Connecting to Google Earth Engine and analysing satellite imagery..."
            ):

                result = get_satellite_data(
                    lat,
                    lon,
                )

            if result["success"]:

                st.session_state.satellite = result

                st.success(
                    "Satellite analysis completed."
                )

                st.rerun()

            else:

                st.error(
                    "Satellite analysis failed."
                )

                st.code(
                    result["message"]
                )

        satellite = st.session_state.satellite

        if satellite:

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "🌱 NDVI",
                    (
                        f"{satellite['ndvi']:.3f}"
                        if satellite.get("ndvi") is not None
                        else "Unavailable"
                    ),
                )

            with c2:

                st.metric(
                    "🌡️ Land Surface Temperature",
                    (
                        f"{satellite['lst']:.1f} °C"
                        if satellite.get("lst") is not None
                        else "Unavailable"
                    ),
                )

            with c3:

                total_images = (
                    satellite.get(
                        "sentinel_images",
                        0,
                    )
                    +
                    satellite.get(
                        "landsat_images",
                        0,
                    )
                )

                st.metric(
                    "🛰️ Images Used",
                    total_images,
                )

            st.divider()

            if satellite.get("ndvi") is not None:

                ndvi_value = satellite["ndvi"]

                st.subheader(
                    "🌱 Vegetation"
                )

                if ndvi_value < 0.15:

                    st.error(
                        "Very low vegetation detected."
                    )

                elif ndvi_value < 0.30:

                    st.warning(
                        "Low vegetation detected."
                    )

                elif ndvi_value < 0.50:

                    st.info(
                        "Moderate vegetation detected."
                    )

                else:

                    st.success(
                        "Relatively high vegetation detected."
                    )

            if satellite.get("lst") is not None:

                lst_value = satellite["lst"]

                st.subheader(
                    "🌡️ Surface temperature"
                )

                if lst_value >= 45:

                    st.error(
                        "Very high land-surface temperature."
                    )

                elif lst_value >= 40:

                    st.warning(
                        "High land-surface temperature."
                    )

                elif lst_value >= 35:

                    st.info(
                        "Elevated land-surface temperature."
                    )

                else:

                    st.success(
                        "Surface temperature is comparatively lower."
                    )


# ============================================================
# TAB 2 — ENVIRONMENTAL DATA
# ============================================================

with tab2:

    st.header(
        "📊 Environmental Data"
    )

    if lat is None or lon is None:

        st.warning(
            "Select a location first."
        )

    else:

        if weather:

            st.subheader(
                "🌤️ Current Weather"
            )

            current = weather.get(
                "current",
                {},
            )

            weather_df = pd.DataFrame(
                {
                    "Measurement": [
                        "Air temperature",
                        "Feels like",
                        "Humidity",
                        "Wind speed",
                    ],
                    "Value": [
                        f"{current.get('temperature_2m', '—')} °C",
                        f"{current.get('apparent_temperature', '—')} °C",
                        f"{current.get('relative_humidity_2m', '—')} %",
                        f"{current.get('wind_speed_10m', '—')} km/h",
                    ],
                }
            )

            st.dataframe(
                weather_df,
                width="stretch",
                hide_index=True,
            )

        st.subheader(
            "🛰️ Satellite measurements"
        )

        satellite = st.session_state.satellite

        if satellite:

            satellite_df = pd.DataFrame(
                {
                    "Measurement": [
                        "NDVI",
                        "Land Surface Temperature",
                    ],
                    "Value": [
                        (
                            f"{satellite.get('ndvi'):.3f}"
                            if satellite.get("ndvi") is not None
                            else "Unavailable"
                        ),
                        (
                            f"{satellite.get('lst'):.2f} °C"
                            if satellite.get("lst") is not None
                            else "Unavailable"
                        ),
                    ],
                }
            )

            st.dataframe(
                satellite_df,
                width="stretch",
                hide_index=True,
            )

        else:

            st.info(
                "Run satellite analysis to populate this section."
            )


# ============================================================
# TAB 3 — PHOTO ANALYSIS
# ============================================================

with tab3:

    st.header(
        "📷 Environmental Photo Analysis"
    )

    st.write(
        """
        Upload a photo of the selected area to add visual
        environmental information to the overall analysis.
        """
    )

    uploaded = st.file_uploader(
        "Upload an urban-area photo",
        type=[
            "jpg",
            "jpeg",
            "png",
            "webp",
        ],
    )

    if uploaded:

        if not PIL_AVAILABLE:

            st.error(
                "Pillow is not installed."
            )

        else:

            image = Image.open(
                uploaded
            )

            st.image(
                image,
                caption="Uploaded image",
                width="stretch",
            )

            image_array = np.array(
                image.convert("RGB")
            ).astype(float)

            average_rgb = image_array.mean(
                axis=(0, 1)
            )

            brightness = float(
                average_rgb.mean()
            )

            green_strength = float(
                average_rgb[1]
                -
                (
                    average_rgb[0]
                    +
                    average_rgb[2]
                ) / 2
            )

            # ------------------------------------------------
            # BASIC VISUAL CLASSIFICATION
            # ------------------------------------------------

            low_vegetation = (
                green_strength <= 5
            )

            high_brightness = (
                brightness >= 180
            )

            possible_paved_area = (
                high_brightness
                and
                green_strength <= 10
            )

            if green_strength > 15:

                vegetation = (
                    "High visible vegetation"
                )

            elif green_strength > 5:

                vegetation = (
                    "Moderate visible vegetation"
                )

            else:

                vegetation = (
                    "Low visible vegetation"
                )

            photo_results = {
                "brightness": brightness,
                "green_strength": green_strength,
                "vegetation": vegetation,
                "low_vegetation": low_vegetation,
                "high_brightness": high_brightness,
                "possible_paved_area": possible_paved_area,
            }

            st.session_state.photo_results = (
                photo_results
            )

            # ------------------------------------------------
            # DISPLAY
            # ------------------------------------------------

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "Brightness",
                    f"{brightness:.1f}",
                )

            with c2:

                st.metric(
                    "Green Signal",
                    f"{green_strength:.1f}",
                )

            with c3:

                st.metric(
                    "Vegetation",
                    vegetation,
                )

            st.divider()

            st.subheader(
                "🔎 Visual findings"
            )

            if low_vegetation:

                st.warning(
                    "Limited visible vegetation was detected."
                )

            else:

                st.success(
                    "Visible vegetation was detected."
                )

            if high_brightness:

                st.info(
                    "The image contains substantial bright/exposed surfaces."
                )

            if possible_paved_area:

                st.warning(
                    "The visual characteristics may indicate exposed hard or paved surfaces."
                )

            st.success(
                "Photo findings have been added to the Cooling Plan."
            )

    elif st.session_state.photo_results:

        st.info(
            "Photo findings from your previous analysis are being used in the Cooling Plan."
        )


# ============================================================
# TAB 4 — COOLING PLAN
# ============================================================

with tab4:

    st.header(
        "💡 Cooling Plan"
    )

    if lat is None or lon is None:

        st.warning(
            "Select a location first."
        )

    else:

        # ----------------------------------------------------
        # GET CURRENT DATA
        # ----------------------------------------------------

        temperature = None
        humidity = None
        ndvi = None
        lst = None

        if weather:

            current = weather.get(
                "current",
                {},
            )

            temperature = current.get(
                "temperature_2m"
            )

            humidity = current.get(
                "relative_humidity_2m"
            )

        if st.session_state.satellite:

            ndvi = (
                st.session_state
                .satellite
                .get("ndvi")
            )

            lst = (
                st.session_state
                .satellite
                .get("lst")
            )

        photo_results = (
            st.session_state.photo_results
        )

        # ----------------------------------------------------
        # DATA STATUS
        # ----------------------------------------------------

        st.subheader(
            "🔬 Analysis used for this plan"
        )

        d1, d2, d3 = st.columns(3)

        with d1:

            if weather:

                st.success(
                    "🌤️ Weather data available"
                )

            else:

                st.warning(
                    "🌤️ Weather unavailable"
                )

        with d2:

            if st.session_state.satellite:

                st.success(
                    "🛰️ Satellite data available"
                )

            else:

                st.warning(
                    "🛰️ Satellite analysis not run"
                )

        with d3:

            if photo_results:

                st.success(
                    "📷 Photo analysis available"
                )

            else:

                st.info(
                    "📷 No photo uploaded"
                )

        st.divider()

        # ----------------------------------------------------
        # CALCULATE FINAL RISK
        # ----------------------------------------------------

        final_score, final_level, final_priority, final_factors = (
            calculate_heat_risk(
                temperature,
                humidity,
                ndvi,
                lst,
                photo_results,
            )
        )

        st.subheader(
            "🔥 Overall assessment"
        )

        st.progress(
            final_score / 100
        )

        st.markdown(
            f"""
            <div class="risk-card">
            <h2>{final_level} HEAT RISK</h2>
            <h3>{final_score}/100</h3>
            <p>
            Recommended intervention priority:
            <strong>{final_priority}</strong>
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # GENERATE PLAN
        # ----------------------------------------------------

        recommendations = (
            generate_recommendations(
                temperature,
                humidity,
                ndvi,
                lst,
                photo_results,
            )
        )

        st.subheader(
            "🎯 Recommended interventions"
        )

        for title, explanation in recommendations:

            st.markdown(
                f"""
                <div class="recommendation">
                <h4>{title}</h4>
                <p>{explanation}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()

        st.subheader(
            "📋 Decision summary"
        )

        if final_factors:

            st.write(
                "The recommendations were informed by:"
            )

            for factor in final_factors:

                st.write(
                    f"• {factor}"
                )

        else:

            st.write(
                "No major heat-risk factors were identified "
                "from the currently available measurements."
            )