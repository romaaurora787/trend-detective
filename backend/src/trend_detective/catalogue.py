"""The fixed list of variables ("suspects") the app may use.

The AI variable-finder may only pick ids from this list. Each entry was run
through the stats engine on real NASA POWER data on 14 Nov 2026.
Sources per the POWER parameter dictionary and response headers.
"""

CATALOGUE = [
    {
        "id": "T2M", "name": "Air temperature", "units": "°C", "source": "MERRA-2",
        "plain": "Average air temperature 2 metres above the ground.",
        "tags": ["city", "farm", "arctic", "desert", "rainforest", "coast", "any"],
        "caveat": "",
    },
    {
        "id": "T2M_MAX", "name": "Daytime highs", "units": "°C", "source": "MERRA-2 (via POWER)",
        "plain": "Average of each day's highest air temperature.",
        "tags": ["city", "desert", "farm"], "caveat": "",
    },
    {
        "id": "T2M_MIN", "name": "Night-time lows", "units": "°C", "source": "MERRA-2 (via POWER)",
        "plain": "Average of each day's lowest air temperature.",
        "tags": ["city", "farm", "arctic"], "caveat": "",
    },
    {
        "id": "TS", "name": "Ground (skin) temperature", "units": "°C", "source": "MERRA-2",
        "plain": "Temperature of the land or sea surface itself.",
        "tags": ["desert", "arctic", "coast"], "caveat": "",
    },
    {
        "id": "PRECTOTCORR", "name": "Rainfall", "units": "mm/day", "source": "MERRA-2 (gauge-corrected)",
        "plain": "Average rain and snow per day, corrected with rain-gauge observations.",
        "tags": ["farm", "rainforest", "desert", "any"],
        "caveat": "Rainfall varies a lot from year to year, so trends take decades to show.",
    },
    {
        "id": "GWETTOP", "name": "Topsoil wetness", "units": "fraction (0 dry – 1 saturated)", "source": "MERRA-2",
        "plain": "How wet the top 5 cm of soil is.",
        "tags": ["farm", "desert", "rainforest"], "caveat": "Model estimate, not a direct measurement.",
    },
    {
        "id": "GWETROOT", "name": "Root-zone soil wetness", "units": "fraction (0 dry – 1 saturated)", "source": "MERRA-2",
        "plain": "How wet the soil is down to about 1 metre, where crop roots are.",
        "tags": ["farm"], "caveat": "Model estimate, not a direct measurement. MERRA-2 production streams join in 1991, 2001 and 2011, which can make deep-soil jumps: check the instrument alibi.",
    },
    {
        "id": "QV2M", "name": "Humidity (water in the air)", "units": "g/kg", "source": "MERRA-2",
        "plain": "Grams of water vapour in each kilogram of air.",
        "tags": ["rainforest", "coast", "city", "any"], "caveat": "",
    },
    {
        "id": "RH2M", "name": "Relative humidity", "units": "%", "source": "MERRA-2 (via POWER)",
        "plain": "How close the air is to being saturated with water.",
        "tags": ["rainforest", "desert"], "caveat": "",
    },
    {
        "id": "WS2M", "name": "Wind speed", "units": "m/s", "source": "MERRA-2 (via POWER)",
        "plain": "Average wind speed 2 metres above the ground.",
        "tags": ["coast", "arctic"], "caveat": "",
    },
    {
        "id": "ALLSKY_SFC_SW_DWN", "name": "Sunshine reaching the ground", "units": "MJ/m²/day", "source": "CERES / GEWEX SRB",
        "plain": "Solar energy reaching the ground, including the effect of clouds and haze.",
        "tags": ["city", "farm", "desert"], "caveat": "Starts 1984. Data source changes in 2001 (GEWEX SRB to CERES): check the instrument alibi.",
    },
    {
        "id": "CLOUD_AMT", "name": "Cloud cover", "units": "%", "source": "CERES / GEWEX SRB",
        "plain": "Share of the sky covered by cloud.",
        "tags": ["coast", "rainforest", "any"], "caveat": "Starts 1984. Data source changes in 2001 (GEWEX SRB to CERES): at many places the 'trend' is this switch. Check the instrument alibi.",
    },
    {
        "id": "AOD_55", "name": "Haze (aerosol optical depth)", "units": "unitless", "source": "MERRA-2 aerosols",
        "plain": "How much dust, smoke and pollution particles dim the sunlight.",
        "tags": ["city", "desert"], "caveat": "Starts 2001. MERRA-2 stops using two aerosol satellites/networks in 2014: check the instrument alibi.",
    },
    {
        "id": "EVLAND", "name": "Evaporation from land", "units": "mm/day", "source": "MERRA-2",
        "plain": "Water evaporating from soil and plants each day.",
        "tags": ["farm", "rainforest", "desert"], "caveat": "Model estimate.",
    },
    {
        "id": "FROST_DAYS", "name": "Frost days", "units": "days/month", "source": "MERRA-2 (via POWER)",
        "plain": "Days in the month when the temperature fell below freezing.",
        "tags": ["arctic", "farm"],
        "caveat": "Mostly zero in summer; trend uses regression instead of Sen's slope.",
    },
    {
        "id": "SNODP", "name": "Snow depth", "units": "cm", "source": "MERRA-2 (via POWER)",
        "plain": "How deep the snow on the ground is, on average.",
        "tags": ["arctic"], "caveat": "Model estimate; zero for most of the year in mild places.",
    },
    {
        "id": "T2MDEW", "name": "Dew point (mugginess)", "units": "°C", "source": "MERRA-2 (via POWER)",
        "plain": "The temperature at which the air would form dew. Higher means stickier, more humid air.",
        "tags": ["city", "coast", "rainforest"], "caveat": "",
    },
    {
        "id": "T2M_RANGE", "name": "Day–night temperature range", "units": "°C", "source": "MERRA-2 (via POWER)",
        "plain": "How much warmer the day gets than the night, on average.",
        "tags": ["desert", "city", "farm"], "caveat": "",
    },
    {
        "id": "ALLSKY_SFC_LW_DWN", "name": "Heat radiation from the sky", "units": "MJ/m²/day", "source": "CERES / GEWEX SRB",
        "plain": "Infrared heat sent down to the ground by the air, clouds and greenhouse gases.",
        "tags": ["any"], "caveat": "Data source changes in 2001 (GEWEX SRB to CERES): check the instrument alibi.",
    },
    {
        "id": "VPD", "name": "Thirst of the air (vapour pressure deficit)", "units": "kPa",
        "source": "Computed from MERRA-2 temperature and dew point (via POWER)",
        "plain": "How strongly the air pulls water out of plants and soil. Rising VPD stresses crops and forests and feeds wildfires.",
        "tags": ["farm", "rainforest", "desert"],
        "caveat": "Computed from monthly averages, so it slightly understates the daytime peak.",
        "derived": True,
    },
    {
        "id": "NDVI", "name": "Vegetation greenness (NDVI)", "units": "NDVI (0–1)",
        "source": "NASA MODIS Terra MOD13Q1 v6.1 (250 m)",
        "plain": "How green the plants are, seen from space: near 0 bare ground, 0.3 grass or crops, 0.8 dense forest.",
        "tags": ["farm", "rainforest", "desert", "arctic"],
        "caveat": "Satellite record starts in 2000 (shorter than the others). Cloudy, snowy and sea pixels are left out. "
                  "First look at a new place takes a few minutes while the satellite images are read.",
        "satellite": True, "period": "2000–2025",
        "citation": "Didan, K. (2021). MOD13Q1 MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061. "
                    "NASA EOSDIS LP DAAC. doi:10.5067/MODIS/MOD13Q1.061 (read via Microsoft Planetary Computer)",
    },
    {
        "id": "LST_DAY", "name": "Ground heat by day (satellite)", "units": "°C",
        "source": "NASA MODIS Terra MOD11A2 v6.1 (1 km)",
        "plain": "How hot the land surface itself gets in the late morning, measured from space. Cities and bare ground run hottest.",
        "tags": ["city", "desert", "farm"],
        "caveat": "Satellite record starts in 2000. Only clear-sky days are seen, so it describes sunny days. "
                  "First look at a new place takes a few minutes.",
        "satellite": True, "period": "2000–2025",
        "citation": "Wan, Z., Hook, S., Hulley, G. (2021). MOD11A2 MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3 "
                    "Global 1km SIN Grid V061. NASA EOSDIS LP DAAC. doi:10.5067/MODIS/MOD11A2.061 (via Microsoft Planetary Computer)",
    },
    {
        "id": "LST_NIGHT", "name": "Ground heat at night (satellite)", "units": "°C",
        "source": "NASA MODIS Terra MOD11A2 v6.1 (1 km)",
        "plain": "How warm the land surface stays at night (about 10:30 pm). Cities hold heat at night: the urban heat island.",
        "tags": ["city", "arctic", "farm"],
        "caveat": "Satellite record starts in 2000. Only clear nights are seen. First look at a new place takes a few minutes.",
        "satellite": True, "period": "2000–2025",
        "citation": "Wan, Z., Hook, S., Hulley, G. (2021). MOD11A2 MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3 "
                    "Global 1km SIN Grid V061. NASA EOSDIS LP DAAC. doi:10.5067/MODIS/MOD11A2.061 (via Microsoft Planetary Computer)",
    },
]

BY_ID = {v["id"]: v for v in CATALOGUE}

PLACE_TYPES = {
    "city": "Big city", "farm": "Farmland", "coast": "Coast / estuary", "desert": "Desert",
    "rainforest": "Rainforest", "arctic": "Arctic / cold", "any": "Anywhere",
}
