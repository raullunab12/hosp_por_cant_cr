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

## 🗺️ Objetivo general

Evaluar la **equidad en la distribución y accesibilidad de los servicios de salud** en Costa Rica mediante análisis espacial y datos geográficos abiertos.
