import json
import time
import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import folium
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="Acceso a Servicios de Salud - Costa Rica")

# -------------------------
# Utilitarios
# -------------------------
def detectar_columna_poblacion(df):
    """Detecta la columna de población en un GeoDataFrame y devuelve su nombre."""
    for c in df.columns:
        low = c.lower()
        if "pob" in low or "poblac" in low:
            return c
    return None

@st.cache_data
def cargar_datos(ruta_poblacion="datos/Poblacion_por_Canton.geojson",
                 ruta_hospitales="datos/costa-rica_hxl.geojson",
                 ruta_cantones="datos/cantones.gpkg"):
    """Carga y normaliza los datasets (devuelve: final, hospitales, poblacion, cantones)."""
    poblacion = gpd.read_file(ruta_poblacion)
    hospitales = gpd.read_file(ruta_hospitales)
    cantones = gpd.read_file(ruta_cantones)

    # Renombrar columnas en poblacion
    pobl_aliados = {
        'NOM_CANT': 'CANTON',
        'NOM_PROV': 'PROVINCIA',
        'PoblaciónCensada2011': 'POB_2011',
        'PoblaciónEstimada2015': 'POB_2015'
    }
    poblacion = poblacion.rename(columns={k: v for k, v in pobl_aliados.items() if k in poblacion.columns})

    # Renombrar columnas en cantones para homogeneizar
    cant_aliados = {
        'CÓDIGO': 'CODIGO',
        'CÓDIGO_CANTÓN': 'CODIGO_CANTON',
        'CANTÓN': 'CANTON',
        'CÓDIGO_DE_PROVINCIA ': 'CODIGO_DE_PROVINCIA'
    }
    cantones = cantones.rename(columns={k: v for k, v in cant_aliados.items() if k in cantones.columns})

    # Asegurar CRS común
    poblacion = poblacion.to_crs(epsg=4326)
    cantones = cantones.to_crs(epsg=4326)
    hospitales = hospitales.to_crs(epsg=4326)

    # Filtrar hospitales: excluir categorías no relevantes
    categorias_excluir = [
        'pharmacy', 'physiotherapist', '', 'dentist',
        'laboratory', 'alternative', 'optometrist',
        'blood_donation', 'rehabilitation'
    ]
    hospitales = hospitales[hospitales["#meta+healthcare"].notna()]
    hospitales = hospitales[~hospitales["#meta+healthcare"].isin(categorias_excluir)]
    hospitales = hospitales.reset_index(drop=True)

    # Unión espacial: hospitales dentro de cada cantón (usa .sjoin)
    join = gpd.sjoin(hospitales, cantones, how="inner", predicate="within")

    # Conteo de hospitales por cantón
    hospitales_por_canton = join.groupby("CANTON").size().reset_index(name="TOTAL_HOSPITALES")

    # Unir con datos de población
    final = cantones.merge(
        poblacion[["CANTON", "POB_2015"]],
        on="CANTON", how="left"
    ).merge(hospitales_por_canton, on="CANTON", how="left")

    # Reemplazar nulos
    final["TOTAL_HOSPITALES"] = final["TOTAL_HOSPITALES"].fillna(0)
    final["POB_2015"] = final["POB_2015"].fillna(0)

    # Calcular area_km2 y densidad poblacional
    final["area_km2"] = final.to_crs(epsg=3857).geometry.area / 10**6
    final["densidad"] = final.apply(lambda r: (r["POB_2015"] / r["area_km2"]) if r["area_km2"] > 0 else 0, axis=1)

    # Calcular habitantes por hospital (presión) — None si no hay hospitales
    final["HAB_POR_HOSP"] = final.apply(
        lambda x: (x["POB_2015"] / x["TOTAL_HOSPITALES"]) if x["TOTAL_HOSPITALES"] > 0 else pd.NA, axis=1
    )

    hospitales = hospitales.rename(columns={'addr:city': 'addr_city'})
    return final, hospitales, poblacion, cantones

# Cargar datos
with st.spinner("Cargando datos..."):
    final, hospitales, poblacion, cantones = cargar_datos()
mensaje = st.empty()
mensaje.success("Datos cargados correctamente")

# -------------------------
# Sidebar - filtros y opciones
# -------------------------
st.sidebar.header("Filtros y opciones")

# Lista de provincias
lista_provincias = sorted(final['PROVINCIA'].dropna().unique())
provincia_sel = st.sidebar.selectbox("Seleccionar provincia", options=["(Todas)"] + lista_provincias, index=0)

# Lista de cantones dinámica
if provincia_sel == "(Todas)":
    lista_cantones = sorted(final['CANTON'].dropna().unique())
else:
    lista_cantones = sorted(final[final['PROVINCIA'] == provincia_sel]['CANTON'].dropna().unique())
canton_sel = st.sidebar.selectbox("Seleccionar cantón", options=["(Todos)"] + lista_cantones, index=0)

# Variables para mapa
opciones_mapa = {
    "Habitantes por hospital": "HAB_POR_HOSP",
    "Población total (2015)": "POB_2015",
    "Densidad poblacional": "densidad"
}
opcion_label = st.sidebar.selectbox(
    "Seleccione variable para mostrar en el mapa:",
    options=list(opciones_mapa.keys()),
    index=0
)
var_mapa = opciones_mapa[opcion_label]

paletas_colores = {
    "Amarillo a rojo (calor)": "YlOrRd",
    "Verde a azul (suave)": "YlGnBu",
    "Naranja a rojo": "OrRd",
    "Púrpura a azul": "PuBu",
    "Multicolor (Viridis)": "Viridis"
}
paleta_label = st.sidebar.selectbox(
    "Paleta de color:",
    options=list(paletas_colores.keys()),
    index=0
)
paleta = paletas_colores[paleta_label]

# Tipo de gráfico
tipos_grafico = {
    "Barras (por cantón)": "Barras (por cantón)",
    "Top 10 - Habitantes por hospital": "Top 10 - HAB_POR_HOSP"
}
tipo_label = st.sidebar.selectbox(
    "Tipo de gráfico:",
    options=list(tipos_grafico.keys()),
    index=0
)
tipo_grafico = tipos_grafico[tipo_label]

# Umbral para marcar posibles cantones saturados (habitantes por hospital)
umbral_saturacion = st.sidebar.number_input("Umbral saturación (hab/hosp) - marcar cantones", min_value=1000, max_value=1000000, value=10000, step=1000)

# -------------------------
# Filtrado de datos
# -------------------------
df = final.copy()
if provincia_sel != "(Todas)":
    df = df[df['PROVINCIA'] == provincia_sel]
if canton_sel != "(Todos)":
    df = df[df['CANTON'] == canton_sel]

# Hospitales filtrados por canton/provincia (para marcadores)
hosp = hospitales.copy()
if provincia_sel != "(Todas)":
    hosp = hosp.merge(cantones[['CANTON', 'PROVINCIA']], left_on='addr_city', right_on='CANTON', how='left')
    hosp = hosp[hosp['PROVINCIA'] == provincia_sel]
if canton_sel != "(Todos)":
    hosp = hosp[hosp['addr_city'] == canton_sel]

# -------------------------
# Layout principal
# -------------------------
st.title("Acceso a servicios de salud — Costa Rica")
st.markdown("Análisis de población, densidad y cobertura hospitalaria por cantón.")

# -------------------------
# resumen rápido
# -------------------------
st.markdown("---")
st.subheader("Resumen rápido")
total_hosp = int(final['TOTAL_HOSPITALES'].sum())
total_pop = int(final['POB_2015'].sum())
st.write(f"Total hospitales (registro espacial): **{total_hosp}**")
st.write(f"Total población (suma POB_2015): **{total_pop:,}**")

with st.expander("📘 Documentación del Proyecto — Análisis Geográfico de la Infraestructura Sanitaria en Costa Rica"):
    st.markdown("""
# Análisis Geográfico de la Infraestructura Sanitaria en Costa Rica

## Descripción general

El proyecto emplea tres conjuntos de datos complementarios:

- **Centros de salud (HOTOSM / OpenStreetMap):** registra la ubicación geográfica de hospitales y centros de salud en Costa Rica.  
- **Población por cantón (ArcGIS Hub):** contiene la población total por cantón, permitiendo estimar densidades y analizar la relación entre habitantes y servicios médicos.  
- **Límites cantonales (IGN / SNIT):** delimita los cantones con precisión geoespacial, facilitando el análisis territorial.  

En conjunto, estos datos permiten **evaluar la equidad en el acceso a la atención de salud** en el territorio costarricense.

---

## Descripción de las principales variables

### 1. Población por Cantón (`Poblacion_por_Canton.geojson`)

**Fuente:** Portal ArcGIS Hub  
Contiene información demográfica actualizada a nivel cantonal.

**Variables relevantes:**
- `COD_PROV`, `COD_CANT`: identificadores administrativos únicos para provincia y cantón.  
- `NOM_PROV`, `NOM_CANT`: nombres oficiales de la provincia y cantón.  
- `PoblaciónCensada2011`, `PoblaciónEstimada2015`: cifras reportadas y proyectadas por el INEC.  
- `geometry`: polígono georreferenciado que representa el área territorial del cantón.

---

### 2. Centros de Salud (`costa-rica_hxl.geojson`)

**Fuente:** HOTOSM (Humanitarian OpenStreetMap Team)  
Registra la infraestructura sanitaria georreferenciada del país.

**Variables destacadas:**
- `#loc +name`: nombre del centro de salud u hospital.  
- `#loc+amenity`, `#meta+healthcare`: tipo de servicio médico (hospital, clínica, farmacia, etc.).  
- `#meta+operator`, `#meta+operator_type`: entidad responsable (CCSS, cooperativa o privada).  
- `geometry`: ubicación geográfica (punto o polígono) de cada instalación.

---

### 3. Límites Cantonales (`cantones.gpkg`)

**Fuente:** Instituto Geográfico Nacional (IGN) — Sistema Nacional de Información Territorial (SNIT).  
Define los límites geoespaciales oficiales de los cantones.

**Variables relevantes:**
- `CÓDIGO_CANTÓN`: identificador administrativo único del cantón.  
- `CANTÓN`, `PROVINCIA`: nombres oficiales.  
- `SHAPE.AREA`, `SHAPE.LEN`: área y perímetro del cantón en metros.  
- `geometry`: polígonos multiparte con la delimitación territorial exacta.

---

## Preguntas de investigación / Problemas a resolver

1. ¿Existe equilibrio entre la distribución de población y la cantidad de hospitales o centros de salud por cantón o provincia?  
2. ¿Qué cantones muestran alta densidad poblacional con baja cobertura sanitaria?  
3. ¿Qué provincias concentran la mayor parte de la infraestructura hospitalaria en relación con su población total?  
4. ¿Cómo se distribuyen espacialmente los centros de salud dentro de los límites cantonales oficiales, y dónde podrían existir zonas potencialmente desatendidas?

---

## Objetivo general

Evaluar la **equidad en la distribución y accesibilidad de los servicios de salud** en Costa Rica mediante análisis espacial y datos geográficos abiertos.
    """)


st.markdown("Repositorio público: https://github.com/raullunab12/hosp_por_cant_cr")

col1, col2 = st.columns([3, 4])

# -------------------------
# Tabla interactiva + descarga
# -------------------------
with col1:
    nombres_amigables = {
        "PROVINCIA": "Provincia",
        "CANTON": "Cantón",
        "POB_2015": "Población (2015)",
        "area_km2": "Área (km²)",
        "densidad": "Densidad poblacional",
        "TOTAL_HOSPITALES": "Total de hospitales",
        "HAB_POR_HOSP": "Habitantes por hospital"
    }
    st.header("Tabla (cantonal)")
    mostrar_cols = ['PROVINCIA', 'CANTON', 'POB_2015', 'area_km2', 'densidad', 'TOTAL_HOSPITALES', 'HAB_POR_HOSP']
    df_mostrar = df[mostrar_cols].rename(columns=nombres_amigables)
    st.dataframe(df_mostrar.fillna("N/A").sort_values(by="Población (2015)", ascending=False), height=450)

    csv = df_mostrar.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar CSV (filtrado)", csv, file_name="datos_cantones_filtrados.csv", mime="text/csv")

    # Mostrar lista de cantones potencialmente saturados
    saturados = df[(df['HAB_POR_HOSP'].notna()) & (df['HAB_POR_HOSP'] >= umbral_saturacion)]
    st.markdown("**Cantones potencialmente saturados** (según umbral):")
    if not saturados.empty:
        st.table(
            saturados[['PROVINCIA', 'CANTON', 'POB_2015', 'TOTAL_HOSPITALES', 'HAB_POR_HOSP']]
            .rename(columns=nombres_amigables)
            .sort_values(by='Habitantes por hospital', ascending=False)
        )
    else:
        st.write("No hay cantones que superen el umbral seleccionado.")

# -------------------------
# Gráficos
# -------------------------
with col2:
    st.header("Gráfico interactivo")
    if tipo_grafico == "Barras (por cantón)":
        # Gráfico: número de hospitales por cantón (en la provincia seleccionada)
        graf_df = final.copy()
        if provincia_sel != "(Todas)":
            graf_df = graf_df[graf_df['PROVINCIA'] == provincia_sel]
        graf_df = graf_df.sort_values('TOTAL_HOSPITALES', ascending=False)

        fig = px.bar(graf_df, x='CANTON', y='TOTAL_HOSPITALES',
                     title=f"Hospitales por cantón {'en '+provincia_sel if provincia_sel!='(Todas)' else ''}",
                     labels={'TOTAL_HOSPITALES': 'Hospitales', 'CANTON': 'Cantón'},
                     color='TOTAL_HOSPITALES', color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)

    else:
        # Top 10 cantones con mayor HAB_POR_HOSP
        graf_df = final.copy()
        if provincia_sel != "(Todas)":
            graf_df = graf_df[graf_df['PROVINCIA'] == provincia_sel]
        graf_df = graf_df[graf_df['HAB_POR_HOSP'].notna()].nlargest(10, 'HAB_POR_HOSP')
        if graf_df.empty:
            st.write("No hay datos de HAB_POR_HOSP para mostrar.")
        else:
            fig = px.bar(graf_df[::-1], x='HAB_POR_HOSP', y='CANTON', orientation='h',
                         title="Top 10 cantones con más habitantes por hospital",
                         labels={'HAB_POR_HOSP': 'Habitantes por hospital', 'CANTON': 'Cantón'},
                         color='HAB_POR_HOSP', color_continuous_scale='OrRd')
            st.plotly_chart(fig, use_container_width=True)

# -------------------------
# Mapa
# -------------------------
st.header("Mapa interactivo")
df = final[['CANTON', var_mapa, 'geometry']].dropna().copy()
hosp = hosp.copy()

# Serializar a GeoJSON (strings) para almacenamiento estable
df_geojson_str = df.to_json()
hosp_geojson_str = hosp[["#loc +name", "addr_city", "geometry"]].to_json()

# Control en session_state
if "map_html" not in st.session_state:
    st.session_state["map_html"] = None
if "last_var_mapa" not in st.session_state:
    st.session_state["last_var_mapa"] = None
if "paleta" not in st.session_state:
    st.session_state["paleta"] = None

# Nombre legible de la variable seleccionada
nombre_legible = next(
    (k for k, v in opciones_mapa.items() if v == var_mapa),
    var_mapa
)

# Regenerar sólo si var_mapa cambió o no hay mapa aún
if st.session_state["map_html"] is None or st.session_state["last_var_mapa"] != var_mapa or st.session_state["paleta"] != paleta:
    # Crear mapa base
    m = folium.Map(location=[9.7489, -83.7534], zoom_start=7, tiles='CartoDB positron')

    # Choropleth: usar geo_data como dict (no como GeoDataFrame directamente)
    geo_df = json.loads(df_geojson_str)
    folium.Choropleth(
        geo_data=geo_df,
        data=df,
        columns=['CANTON', var_mapa],
        key_on='feature.properties.CANTON',
        fill_color=paleta,
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=nombre_legible
    ).add_to(m)

    # Añadir marcadores de hospitales usando el GeoJSON serializado
    hosp_geo = json.loads(hosp_geojson_str)

    for feat in hosp_geo.get('features', []):
        props = feat.get('properties', {})
        geom = feat.get('geometry')
        if not geom:
            continue
        coords = None
        if geom['type'] == 'Point':
            coords = geom['coordinates']
        else:
            coords_list = geom.get('coordinates', [])
            if coords_list:
                first_ring = coords_list[0]
                if isinstance(first_ring[0][0], list):
                    coords = first_ring[0][0]
                else:
                    coords = first_ring[0]
        if coords is None:
            continue
        lon, lat = coords[0], coords[1]
        nombre = props.get('#loc +name') or props.get('name') or 'Hospital'
        ciudad = props.get('addr_city', '')
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            popup=f"{nombre} - {ciudad}",
            color='black',
            fill=True,
            fill_opacity=0.8
        ).add_to(m)

    # Añadir contornos de cantones saturados
    thresholds = []
    fc_saturados = {"type": "FeatureCollection", "features": []}
    try:
        for _, row in df.iterrows():
            habph = row.get('HAB_POR_HOSP')
            if pd.notna(habph) and habph >= umbral_saturacion:
                geom = row.geometry.__geo_interface__
                feature = {"type": "Feature", "properties": {"CANTON": row['CANTON']}, "geometry": geom}
                fc_saturados["features"].append(feature)
    except Exception:
        for feat in geo_df.get("features", []):
            props = feat.get("properties", {})
            habph = props.get("HAB_POR_HOSP")
            if habph is not None and habph >= umbral_saturacion:
                fc_saturados["features"].append(feat)

    if len(fc_saturados["features"]) > 0:
        folium.GeoJson(
            fc_saturados,
            style_function=lambda feature: {
                'fillColor': 'none',
                'color': 'red',
                'weight': 3,
                'dashArray': '5, 5'
            }
        ).add_to(m)

    # Generar HTML completo del mapa
    mapa_html = m.get_root().render()

    # Guardar en session_state
    st.session_state["map_html"] = mapa_html
    st.session_state["last_var_mapa"] = var_mapa
    st.session_state["paleta"] = paleta

# Renderizar el HTML del mapa
components.html(st.session_state["map_html"], width=1000, height=600, scrolling=True)

st.subheader("Lecciones aprendidas")

st.markdown("---")

st.subheader("Sugerencias para trabajo futuro")


time.sleep(2)
mensaje.empty()