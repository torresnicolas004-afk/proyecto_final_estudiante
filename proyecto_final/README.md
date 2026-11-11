# 🌎 Terremotos USGS — Proyecto Final de Programación Aplicada

Aplicación completa sobre los terremotos de magnitud 4.0 o más registrados por
el USGS desde 2020 (≈107.000 eventos, cargados a MongoDB Atlas en el segundo corte).

```
MongoDB Atlas  ──>  API (FastAPI)  ──>  Dashboard (Streamlit)
earthquake_project     api.py              dashboard.py
  .earthquakes       (Render)        (Streamlit Community Cloud)
```

- **API pública:** https://proyecto-final-estudiante-271721.onrender.com/docs
  (la capa gratis de Render se duerme; la primera petición puede tardar ~1 minuto)

## Archivos

| Archivo | Qué hace |
|---|---|
| `api.py` | Backend: filtra, agrega, calcula correlación, devuelve muestras y registra terremotos. |
| `dashboard.py` | Frontend: indicadores, las 4 preguntas con sus gráficas, mapa, explorador, tabla y formulario. |
| `requirements.txt` | Librerías necesarias. |
| `.env.example` | Plantilla del archivo `.env` (la contraseña real NUNCA se sube). |

## Cómo ejecutar en local

```bash
py -m venv venv                       # Mac: python3 -m venv venv
.\venv\Scripts\Activate.ps1           # Mac: source venv/bin/activate
py -m pip install -r requirements.txt
copy .env.example .env                # Mac: cp .env.example .env   → pega tu MONGO_URI
```

Terminal 1 — API:
```bash
python -m uvicorn api:app --reload
```
Abre http://localhost:8000/docs

Terminal 2 — Dashboard (apuntando a la API local):
```powershell
$env:API_URL="http://localhost:8000"; python -m streamlit run dashboard.py
```
(Mac: `API_URL=http://localhost:8000 python -m streamlit run dashboard.py`.
Sin `API_URL`, el dashboard usa la API de Render.)

## Endpoints

| Método | Endpoint | Qué hace | Códigos |
|---|---|---|---|
| GET | `/` | Estado de la API y de la conexión a MongoDB | 200 |
| GET | `/datos` | Lista con filtros, orden y paginación (`limite`, `saltar`, `ordenar_por`, `orden`, `campo`+`valor`) | 200, 400, 422 |
| GET | `/datos/{event_id}` | Un terremoto por su identificador | 200, 404 |
| POST | `/datos` | Registra un terremoto (validado con Pydantic) | **201**, **409** repetido, **422** inválido |
| GET | `/resumen` | Total, magnitud promedio/máx., profundidad promedio, tsunamis, terremoto más fuerte | 200 |
| GET | `/estadisticas` | `$group` por categoría: conteo, %, suma, promedio, mín., máx. | 200, 422 |
| GET | `/estadisticas/tiempo` | Serie por mes o por año (pregunta 1) | 200 |
| GET | `/estadisticas/correlacion` | Pearson sobre todos los registros (pregunta 3) | 200, 400, 404 |
| GET | `/muestra` | Muestra aleatoria con `$sample` (dispersión, cajas y mapa) | 200 |

Todos los endpoints de lectura aceptan los mismos filtros:
`mag_min`, `mag_max`, `anio_desde`, `anio_hasta`, `magnitude_type`, `alert`
(incluye `sin alerta`), `network`, `tsunami`, `lugar` (texto dentro de `place`).

`/estadisticas?agrupar_por=` acepta campos originales (`magnitude_type`, `alert`,
`status`, `network`, `tsunami`) y **derivados**, calculados dentro de MongoDB con
las mismas reglas de limpieza del segundo corte: `zona`, `anio`, `mes`,
`categoria_profundidad`.

Ejemplos:
```
/datos?lugar=Colombia&mag_min=5&ordenar_por=magnitude
/estadisticas?agrupar_por=zona&top=10
/estadisticas?agrupar_por=categoria_profundidad&sumar=magnitude
/estadisticas/correlacion?x=magnitude&y=depth_km
/estadisticas/tiempo?periodo=anio&tsunami=1
```

## Decisiones técnicas (para la sustentación)

- **Limpieza al consultar, no sobre los datos.** En Atlas están los registros tal
  como los entrega el USGS. La API aplica las reglas del segundo corte en cada
  consulta (`alert` nulo → "sin alerta", zona = texto tras la última coma,
  rangos de profundidad <70 / 70–300 / >300 km). Así no se pierde el dato original.
- **Los cálculos se hacen en MongoDB, no en el navegador.** Los indicadores y las
  gráficas de barras/líneas usan agregaciones sobre los ~107.000 registros; solo
  la dispersión, las cajas y el mapa usan una muestra (`$sample`), igual que en el notebook.
- **Correlación exacta en la base de datos:** se calculan las sumas Σx, Σy, Σxy, Σx², Σy²
  con `$group` y la API aplica la fórmula de Pearson.
- **Validación:** Pydantic revisa tipos y rangos (magnitud 0–10, latitud ±90,
  longitud ±180, profundidad −10 a 800 km, fecha no futura, campos desconocidos
  prohibidos). El índice único sobre `event_id` impide duplicados (409).
- **Seguridad:** `MONGO_URI` se lee de `.env` (local) o de *Environment* (Render).
  `.env` está en `.gitignore`.
