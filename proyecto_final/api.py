"""
API del Proyecto Final - Programacion Aplicada
===============================================
Backend (FastAPI) que consulta, analiza y registra terremotos del catalogo
USGS guardados en MongoDB Atlas (base `earthquake_project`, coleccion
`earthquakes`, cargada en el segundo corte).

Como ejecutar (en una terminal con el venv activo, dentro de esta carpeta):
    pip install -r requirements.txt
    python -m uvicorn api:app --reload

Luego abre en el navegador:  http://localhost:8000/docs

Endpoints
---------
    GET  /                              estado de la API y de la base de datos
    GET  /datos                         lista terremotos (filtros, orden, paginacion)
    GET  /datos/{event_id}              un terremoto por su identificador (404 si no existe)
    POST /datos                         registra un terremoto nuevo (201 / 409 / 422)
    GET  /resumen                       indicadores generales (total, promedios, maximo...)
    GET  /estadisticas                  agrupa por una categoria y resume una variable
    GET  /estadisticas/tiempo           serie de tiempo por anio o por mes
    GET  /estadisticas/correlacion      correlacion de Pearson entre dos variables
    GET  /muestra                       muestra aleatoria (para dispersion, cajas y mapa)

Todos los endpoints de lectura aceptan los mismos filtros:
    mag_min, mag_max, anio_desde, anio_hasta, magnitude_type, alert,
    network, tsunami, lugar

Limpieza del segundo corte
--------------------------
En el segundo corte la limpieza se hizo en pandas; en Atlas quedaron los
registros tal como los entrega el USGS. Esta API aplica las MISMAS reglas
al consultar, sin modificar los datos originales:
    - alert nulo         -> "sin alerta" (el USGS no emitio alerta)
    - zona               -> texto despues de la ultima coma de `place`, en minusculas
    - categoria_profundidad -> superficial (<70 km), intermedio (70-300), profundo (>300)
    - anio / mes         -> derivados de `time` (milisegundos UTC)
    - felt, cdi, mmi, stations... nulos se dejan nulos (no se inventan ceros)
Los registros nuevos (POST) se normalizan igual antes de guardarlos.

Seguridad
---------
La cadena de conexion NUNCA se escribe en este archivo: se lee de la variable
de entorno MONGO_URI (archivo .env en local, "Environment" en Render).
"""

import math
import os
import re
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

# Si existe un archivo .env, carga sus variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# ===========================================================================
# 1. CONFIGURACION
# ===========================================================================
NOMBRE_BD = "earthquake_project"
NOMBRE_COLECCION = "earthquakes"

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError(
        "Falta la variable de entorno MONGO_URI. "
        "Crea un archivo .env con tu cadena de conexion de Atlas (mira .env.example)."
    )

cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
coleccion = cliente[NOMBRE_BD][NOMBRE_COLECCION]

# Indice unico sobre event_id: MongoDB rechaza terremotos repetidos.
# (Ya se creo en el segundo corte; volver a pedirlo no hace nada si existe.)
try:
    coleccion.create_index("event_id", unique=True)
    # Indices de apoyo: aceleran el orden por fecha/magnitud y los filtros
    coleccion.create_index("time")
    coleccion.create_index("magnitude")
except PyMongoError as e:  # la API arranca igual; GET / mostrara el problema
    print(f"[aviso] No se pudo verificar el indice de event_id: {e}")


# ===========================================================================
# 2. CAMPOS DEL DATASET
# ===========================================================================
# Variables numericas que se pueden promediar, sumar o correlacionar
CAMPOS_NUMERICOS = [
    "magnitude", "depth_km", "significance", "felt", "cdi", "mmi",
    "stations", "distance", "rms", "gap", "latitude", "longitude", "tsunami",
]
CampoNumerico = Literal[
    "magnitude", "depth_km", "significance", "felt", "cdi", "mmi",
    "stations", "distance", "rms", "gap", "latitude", "longitude", "tsunami",
]

# Categorias por las que se puede agrupar. Las ultimas son DERIVADAS
# (se calculan dentro de MongoDB con las reglas de limpieza del segundo corte).
CampoAgrupable = Literal[
    "magnitude_type", "alert", "status", "network", "tsunami",
    "zona", "anio", "mes", "categoria_profundidad",
]

EXPRESIONES_AGRUPACION = {
    "magnitude_type": {"$ifNull": ["$magnitude_type", "unknown"]},
    "alert": {"$ifNull": ["$alert", "sin alerta"]},
    "status": {"$ifNull": ["$status", "unknown"]},
    "network": {"$ifNull": ["$network", "unknown"]},
    "tsunami": "$tsunami",
    "zona": {
        "$toLower": {
            "$trim": {
                "input": {
                    "$arrayElemAt": [
                        {"$split": [{"$ifNull": ["$place", "unknown"]}, ","]},
                        -1,
                    ]
                }
            }
        }
    },
    "anio": {"$year": {"$toDate": "$time"}},
    "mes": {"$month": {"$toDate": "$time"}},
    "categoria_profundidad": {
        "$switch": {
            "branches": [
                {"case": {"$lt": ["$depth_km", 70]}, "then": "superficial"},
                {"case": {"$gt": ["$depth_km", 300]}, "then": "profundo"},
            ],
            "default": "intermedio",
        }
    },
}

# Campos de texto que se pueden usar en el filtro generico ?campo=...&valor=...
CAMPOS_TEXTO = [
    "event_id", "place", "alert", "status", "network", "code",
    "magnitude_type", "event_type",
]


# ===========================================================================
# 3. LA APLICACION
# ===========================================================================
app = FastAPI(
    title="API de Terremotos USGS - Proyecto Final",
    description=(
        "Consulta, analiza y registra terremotos de magnitud 4.0 o mas "
        "(catalogo USGS, 2020 a la fecha) guardados en MongoDB Atlas."
    ),
    version="2.0",
)


@app.exception_handler(PyMongoError)
def error_base_de_datos(request, exc):
    """Si MongoDB no responde, se devuelve 503 en lugar de un 500 generico."""
    return JSONResponse(
        status_code=503,
        content={"detail": f"La base de datos no esta disponible: {type(exc).__name__}"},
    )


def _a_json(doc):
    """El _id de Mongo es un objeto especial; lo pasamos a texto para el JSON."""
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def _redondear(valor, decimales=3):
    if isinstance(valor, float):
        return None if math.isnan(valor) else round(valor, decimales)
    return valor


def _ms_inicio_anio(anio: int) -> int:
    return int(datetime(anio, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)


# ===========================================================================
# 4. FILTROS COMUNES (los usan todos los endpoints de lectura)
# ===========================================================================
def filtros_comunes(
    mag_min: Optional[float] = Query(None, ge=0, le=10, description="Magnitud minima"),
    mag_max: Optional[float] = Query(None, ge=0, le=10, description="Magnitud maxima"),
    anio_desde: Optional[int] = Query(None, ge=1900, le=2100, description="Anio inicial (incluido)"),
    anio_hasta: Optional[int] = Query(None, ge=1900, le=2100, description="Anio final (incluido)"),
    magnitude_type: Optional[str] = Query(None, max_length=20, description="Ej: mb, mww, ml"),
    alert: Optional[Literal["green", "yellow", "orange", "red", "sin alerta"]] = Query(
        None, description="Nivel de alerta del USGS"
    ),
    network: Optional[str] = Query(None, max_length=10, description="Red sismica, ej: us, ak"),
    tsunami: Optional[int] = Query(None, ge=0, le=1, description="1 = con indicador de tsunami"),
    lugar: Optional[str] = Query(
        None, min_length=2, max_length=100, description="Texto dentro de `place`, ej: Colombia"
    ),
) -> dict:
    """Convierte los parametros de la URL en un filtro de MongoDB."""
    if mag_min is not None and mag_max is not None and mag_min > mag_max:
        raise HTTPException(400, "mag_min no puede ser mayor que mag_max")
    if anio_desde is not None and anio_hasta is not None and anio_desde > anio_hasta:
        raise HTTPException(400, "anio_desde no puede ser mayor que anio_hasta")

    filtro = {}

    if mag_min is not None or mag_max is not None:
        filtro["magnitude"] = {}
        if mag_min is not None:
            filtro["magnitude"]["$gte"] = mag_min
        if mag_max is not None:
            filtro["magnitude"]["$lte"] = mag_max

    if anio_desde is not None or anio_hasta is not None:
        filtro["time"] = {}
        if anio_desde is not None:
            filtro["time"]["$gte"] = _ms_inicio_anio(anio_desde)
        if anio_hasta is not None:
            filtro["time"]["$lt"] = _ms_inicio_anio(anio_hasta + 1)

    if magnitude_type:
        filtro["magnitude_type"] = magnitude_type.strip().lower()

    if alert == "sin alerta":
        filtro["alert"] = None  # en Mongo esto encuentra los nulos y los que no tienen el campo
    elif alert:
        filtro["alert"] = alert

    if network:
        filtro["network"] = network.strip().lower()

    if tsunami is not None:
        filtro["tsunami"] = tsunami

    if lugar:
        # re.escape evita que caracteres especiales rompan la busqueda
        filtro["place"] = {"$regex": re.escape(lugar.strip()), "$options": "i"}

    return filtro


Filtro = Annotated[dict, Depends(filtros_comunes)]


# ===========================================================================
# 5. ESTADO
# ===========================================================================
@app.get("/", tags=["Estado"])
def inicio():
    """Estado de la API y de la conexion con MongoDB."""
    try:
        cliente.admin.command("ping")
        base = "conectada"
    except PyMongoError:
        base = "sin conexion"
    return {
        "mensaje": "API de terremotos USGS - ve a /docs para probarla",
        "base_de_datos": base,
        "endpoints": [
            "GET /datos", "GET /datos/{event_id}", "POST /datos", "GET /resumen",
            "GET /estadisticas", "GET /estadisticas/tiempo",
            "GET /estadisticas/correlacion", "GET /muestra", "/docs",
        ],
    }


# ===========================================================================
# 6. LEER
# ===========================================================================
@app.get("/datos", tags=["Leer"])
def listar(
    filtro: Filtro,
    campo: Optional[str] = Query(None, description="Filtro generico: nombre del campo"),
    valor: Optional[str] = Query(None, description="Filtro generico: valor exacto del campo"),
    limite: int = Query(50, ge=1, le=1000, description="Cuantos registros devolver"),
    saltar: int = Query(0, ge=0, description="Cuantos registros saltar (paginacion)"),
    ordenar_por: Literal["time", "magnitude", "depth_km", "significance"] = "time",
    orden: Literal["desc", "asc"] = "desc",
):
    """Lista terremotos con filtros, orden y paginacion.

    Ejemplos:
        /datos?limite=10&ordenar_por=magnitude
        /datos?lugar=Colombia&mag_min=5
        /datos?campo=network&valor=us
        /datos?campo=tsunami&valor=1
    """
    if campo or valor:
        if not (campo and valor):
            raise HTTPException(400, "Debes enviar campo y valor juntos")
        if campo in CAMPOS_NUMERICOS:
            try:
                numero = float(valor)
            except ValueError:
                raise HTTPException(400, f"'{campo}' es numerico; '{valor}' no es un numero")
            filtro[campo] = int(numero) if numero.is_integer() else numero
        elif campo in CAMPOS_TEXTO:
            filtro[campo] = valor
        else:
            raise HTTPException(
                400,
                f"Campo '{campo}' no valido. Usa uno de: {CAMPOS_TEXTO + CAMPOS_NUMERICOS}",
            )

    total = (
        coleccion.count_documents(filtro) if filtro else coleccion.estimated_document_count()
    )
    cursor = (
        coleccion.find(filtro)
        .sort(ordenar_por, DESCENDING if orden == "desc" else ASCENDING)
        .skip(saltar)
        .limit(limite)
    )
    documentos = [_a_json(d) for d in cursor]
    return {"total": total, "cantidad": len(documentos), "datos": documentos}


@app.get("/datos/{event_id}", tags=["Leer"])
def obtener(event_id: str = Path(..., min_length=3, max_length=40)):
    """Devuelve un terremoto por su event_id (404 si no existe)."""
    doc = coleccion.find_one({"event_id": event_id})
    if doc is None:
        raise HTTPException(404, f"No existe un terremoto con event_id '{event_id}'")
    return _a_json(doc)


@app.get("/resumen", tags=["Analizar"])
def resumen(filtro: Filtro):
    """Indicadores generales de los terremotos que cumplen el filtro."""
    pipeline = [
        {"$match": filtro},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "magnitud_promedio": {"$avg": "$magnitude"},
                "magnitud_maxima": {"$max": "$magnitude"},
                "magnitud_minima": {"$min": "$magnitude"},
                "profundidad_promedio": {"$avg": "$depth_km"},
                "con_tsunami": {"$sum": {"$cond": [{"$eq": ["$tsunami", 1]}, 1, 0]}},
                "con_alerta": {"$sum": {"$cond": [{"$ifNull": ["$alert", False]}, 1, 0]}},
                "primer_evento": {"$min": "$time"},
                "ultimo_evento": {"$max": "$time"},
            }
        },
    ]
    r = next(coleccion.aggregate(pipeline), None)
    if r is None:
        return {"total": 0}
    r.pop("_id")

    mas_fuerte = coleccion.find_one(
        filtro,
        {"_id": 0, "event_id": 1, "place": 1, "magnitude": 1, "time": 1, "depth_km": 1},
        sort=[("magnitude", DESCENDING)],
    )
    return {**{k: _redondear(v) for k, v in r.items()}, "mas_fuerte": mas_fuerte}


@app.get("/estadisticas", tags=["Analizar"])
def estadisticas(
    filtro: Filtro,
    agrupar_por: CampoAgrupable = Query(..., description="Categoria para agrupar"),
    sumar: CampoNumerico = Query("magnitude", description="Variable numerica a resumir"),
    ordenar_por: Literal["conteo", "promedio", "suma", "maximo", "grupo"] = "conteo",
    top: int = Query(20, ge=1, le=200, description="Cuantos grupos devolver"),
):
    """Agrupa por una categoria y resume una variable numerica (agregacion de MongoDB).

    Por cada grupo devuelve: conteo, porcentaje del total, suma, promedio,
    minimo y maximo de la variable elegida.

    Ejemplos:
        /estadisticas?agrupar_por=magnitude_type&sumar=magnitude
        /estadisticas?agrupar_por=zona&top=10
        /estadisticas?agrupar_por=categoria_profundidad&sumar=magnitude
    """
    campo_orden = "_id" if ordenar_por == "grupo" else ordenar_por
    direccion = 1 if ordenar_por == "grupo" else -1

    pipeline = [
        {"$match": filtro},
        {
            "$facet": {
                "grupos": [
                    {
                        "$group": {
                            "_id": EXPRESIONES_AGRUPACION[agrupar_por],
                            "conteo": {"$sum": 1},
                            "suma": {"$sum": f"${sumar}"},
                            "promedio": {"$avg": f"${sumar}"},
                            "minimo": {"$min": f"${sumar}"},
                            "maximo": {"$max": f"${sumar}"},
                        }
                    },
                    {"$sort": {campo_orden: direccion, "_id": 1}},
                    {"$limit": top},
                ],
                "total": [{"$count": "n"}],
                "cantidad_grupos": [
                    {"$group": {"_id": EXPRESIONES_AGRUPACION[agrupar_por]}},
                    {"$count": "n"},
                ],
            }
        },
    ]
    r = next(coleccion.aggregate(pipeline))
    total = r["total"][0]["n"] if r["total"] else 0
    cantidad_grupos = r["cantidad_grupos"][0]["n"] if r["cantidad_grupos"] else 0

    grupos = [
        {
            agrupar_por: g["_id"],
            "conteo": g["conteo"],
            "porcentaje": round(g["conteo"] / total * 100, 2) if total else 0,
            "suma": _redondear(g["suma"]),
            "promedio": _redondear(g["promedio"]),
            "minimo": _redondear(g["minimo"]),
            "maximo": _redondear(g["maximo"]),
        }
        for g in r["grupos"]
    ]
    return {
        "agrupar_por": agrupar_por,
        "variable": sumar,
        "total_registros": total,
        "cantidad_grupos": cantidad_grupos,
        "grupos": grupos,
    }


@app.get("/estadisticas/tiempo", tags=["Analizar"])
def serie_de_tiempo(
    filtro: Filtro,
    periodo: Literal["mes", "anio"] = Query("mes", description="Agrupar por mes o por anio"),
):
    """Cantidad de terremotos y magnitud promedio/maxima por periodo (orden cronologico).

    Responde a la pregunta 1: como varia la magnitud a lo largo del tiempo.
    """
    llave = {"anio": EXPRESIONES_AGRUPACION["anio"]}
    if periodo == "mes":
        llave["mes"] = EXPRESIONES_AGRUPACION["mes"]

    pipeline = [
        {"$match": filtro},
        {
            "$group": {
                "_id": llave,
                "conteo": {"$sum": 1},
                "magnitud_promedio": {"$avg": "$magnitude"},
                "magnitud_maxima": {"$max": "$magnitude"},
                "profundidad_promedio": {"$avg": "$depth_km"},
            }
        },
        {"$sort": {"_id.anio": 1, "_id.mes": 1}},
    ]
    serie = []
    for g in coleccion.aggregate(pipeline):
        anio, mes = g["_id"]["anio"], g["_id"].get("mes")
        serie.append({
            "periodo": f"{anio}-{mes:02d}" if mes else str(anio),
            "anio": anio,
            "mes": mes,
            "conteo": g["conteo"],
            "magnitud_promedio": _redondear(g["magnitud_promedio"]),
            "magnitud_maxima": _redondear(g["magnitud_maxima"]),
            "profundidad_promedio": _redondear(g["profundidad_promedio"]),
        })
    return {"periodo": periodo, "serie": serie}


@app.get("/estadisticas/correlacion", tags=["Analizar"])
def correlacion(
    filtro: Filtro,
    x: CampoNumerico = "magnitude",
    y: CampoNumerico = "depth_km",
):
    """Correlacion de Pearson entre dos variables, calculada sobre TODOS los registros.

    Responde a la pregunta 3: relacion entre magnitud y profundidad.
    Solo usa los registros donde ambas variables tienen valor.
    """
    if x == y:
        raise HTTPException(400, "x e y deben ser variables distintas")

    # Ademas del filtro, ambas variables deben ser numeros (no nulos)
    condicion = dict(filtro)
    for campo in (x, y):
        previo = condicion.get(campo)
        if previo is None:
            condicion[campo] = {"$type": "number"}
        elif isinstance(previo, dict):  # ej: magnitude {"$gte": 5}
            condicion[campo] = {**previo, "$type": "number"}
        # si es un valor exacto (ej: tsunami = 1) ya es un numero

    pipeline = [
        {"$match": condicion},
        {
            "$group": {
                "_id": None,
                "n": {"$sum": 1},
                "sx": {"$sum": f"${x}"},
                "sy": {"$sum": f"${y}"},
                "sxx": {"$sum": {"$multiply": [f"${x}", f"${x}"]}},
                "syy": {"$sum": {"$multiply": [f"${y}", f"${y}"]}},
                "sxy": {"$sum": {"$multiply": [f"${x}", f"${y}"]}},
            }
        },
    ]
    s = next(coleccion.aggregate(pipeline), None)
    if not s or s["n"] < 3:
        raise HTTPException(404, "No hay suficientes datos para calcular la correlacion")

    n = s["n"]
    numerador = n * s["sxy"] - s["sx"] * s["sy"]
    denominador = math.sqrt(max(n * s["sxx"] - s["sx"] ** 2, 0)) * math.sqrt(
        max(n * s["syy"] - s["sy"] ** 2, 0)
    )
    if denominador == 0:
        raise HTTPException(400, "Una de las variables no varia; la correlacion no esta definida")

    r = numerador / denominador
    fuerza = abs(r)
    if fuerza < 0.1:
        texto = "prácticamente nula"
    elif fuerza < 0.3:
        texto = "débil"
    elif fuerza < 0.5:
        texto = "moderada"
    else:
        texto = "fuerte"
    sentido = "negativa" if r < 0 else "positiva"

    return {
        "x": x,
        "y": y,
        "n": n,
        "pearson": round(r, 4),
        "interpretacion": f"Relación {texto} y {sentido}",
    }


@app.get("/muestra", tags=["Analizar"])
def muestra(
    filtro: Filtro,
    n: int = Query(2000, ge=10, le=5000, description="Tamano de la muestra aleatoria"),
):
    """Muestra aleatoria de terremotos (con $sample de MongoDB).

    Con mas de 100.000 eventos no tiene sentido mandar todos al navegador para
    un grafico de dispersion o un mapa; igual que en el notebook, se usa una muestra.
    """
    pipeline = [
        {"$match": filtro},
        {"$sample": {"size": n}},
        {
            "$project": {
                "_id": 0,
                "event_id": 1,
                "magnitude": 1,
                "depth_km": 1,
                "latitude": 1,
                "longitude": 1,
                "place": 1,
                "time": 1,
                "magnitude_type": 1,
                "alert": EXPRESIONES_AGRUPACION["alert"],
                "categoria_profundidad": EXPRESIONES_AGRUPACION["categoria_profundidad"],
            }
        },
    ]
    datos = list(coleccion.aggregate(pipeline))
    return {"cantidad": len(datos), "datos": datos}


# ===========================================================================
# 7. CREAR
# ===========================================================================
class NuevoTerremoto(BaseModel):
    """Terremoto nuevo. Mismos nombres y tipos que los documentos del USGS en la coleccion."""

    model_config = ConfigDict(
        extra="forbid",  # campos desconocidos -> 422
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "event_id": "prueba001",
                "magnitude": 4.5,
                "place": "10 km N of Bogota, Colombia",
                "time": 1735697312976,
                "depth_km": 15.0,
                "latitude": 4.71,
                "longitude": -74.07,
                "significance": 312,
                "magnitude_type": "mb",
                "distance": 0.12,
                "tsunami": 0,
                "alert": None,
                "status": "reviewed",
                "network": "us",
            }
        },
    )

    # Obligatorios
    event_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    magnitude: float = Field(ge=0, le=10, description="Magnitud (0 a 10)")
    place: str = Field(min_length=2, max_length=200)
    time: int = Field(gt=0, description="Fecha y hora en milisegundos desde 1970 (UTC)")
    depth_km: float = Field(ge=-10, le=800, description="Profundidad en km (puede ser levemente negativa)")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    significance: int = Field(ge=0, description="Importancia del evento segun el USGS")

    # Opcionales (en el USGS muchos vienen nulos)
    magnitude_type: Optional[str] = Field(None, max_length=15)
    tsunami: Literal[0, 1] = 0
    alert: Optional[Literal["green", "yellow", "orange", "red"]] = None
    status: Literal["automatic", "reviewed"] = "reviewed"
    network: Optional[str] = Field(None, max_length=10)
    felt: Optional[int] = Field(None, ge=0)
    cdi: Optional[float] = Field(None, ge=0, le=12)
    mmi: Optional[float] = Field(None, ge=0, le=12)
    stations: Optional[int] = Field(None, ge=0)
    distance: Optional[float] = Field(None, ge=0)
    rms: Optional[float] = Field(None, ge=0)
    gap: Optional[float] = Field(None, ge=0, le=360)
    code: Optional[str] = Field(None, max_length=40)
    url: Optional[str] = Field(None, max_length=300)
    detail_url: Optional[str] = Field(None, max_length=300)

    @field_validator("time")
    @classmethod
    def no_en_el_futuro(cls, v):
        ahora_ms = datetime.now(timezone.utc).timestamp() * 1000
        if v > ahora_ms + 86_400_000:  # 1 dia de tolerancia
            raise ValueError("la fecha del terremoto no puede estar en el futuro")
        return v

    @field_validator("magnitude_type", "network")
    @classmethod
    def a_minusculas(cls, v):
        # Misma normalizacion que en la limpieza del segundo corte
        return v.lower() if v else None


@app.post("/datos", status_code=201, tags=["Crear"])
def crear(registro: NuevoTerremoto):
    """Registra un terremoto nuevo.

    - 201: creado
    - 409: ya existe un terremoto con ese event_id
    - 422: datos invalidos (tipos, rangos o campos desconocidos)
    """
    if coleccion.find_one({"event_id": registro.event_id}, {"_id": 1}):
        raise HTTPException(409, f"Ya existe un terremoto con event_id '{registro.event_id}'")

    datos = registro.model_dump()
    ahora_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Mismo orden de campos que los documentos cargados en el segundo corte
    doc = {
        "event_id": datos["event_id"],
        "magnitude": datos["magnitude"],
        "place": datos["place"],
        "time": datos["time"],
        "updated": ahora_ms,
        "felt": datos["felt"],
        "cdi": datos["cdi"],
        "mmi": datos["mmi"],
        "alert": datos["alert"],
        "tsunami": datos["tsunami"],
        "significance": datos["significance"],
        "status": datos["status"],
        "network": datos["network"],
        "code": datos["code"],
        "stations": datos["stations"],
        "distance": datos["distance"],
        "rms": datos["rms"],
        "gap": datos["gap"],
        "magnitude_type": datos["magnitude_type"],
        "event_type": "earthquake",
        "longitude": datos["longitude"],
        "latitude": datos["latitude"],
        "depth_km": datos["depth_km"],
        "url": datos["url"],
        "detail_url": datos["detail_url"],
    }

    try:
        resultado = coleccion.insert_one(doc)
    except DuplicateKeyError:  # por si dos personas lo envian al mismo tiempo
        raise HTTPException(409, f"Ya existe un terremoto con event_id '{registro.event_id}'")

    return {
        "mensaje": "Terremoto registrado correctamente",
        "id": str(resultado.inserted_id),
        "event_id": registro.event_id,
    }
