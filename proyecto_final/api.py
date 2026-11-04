"""
API del Proyecto Final - Programacion Aplicada
===============================================
Backend (FastAPI) que consulta y administra los datos del proyecto,
guardados en MongoDB.

Como ejecutar (en una terminal, dentro de esta carpeta):
    pip install -r requirements.txt
    uvicorn api:app --reload

Luego abre en el navegador:  http://localhost:8000/docs
(ahi puedes probar todos los endpoints sin escribir nada de codigo)

IMPORTANTE - Seguridad:
    La cadena de conexion a Mongo NUNCA se escribe en este archivo.
    Se lee de una variable de entorno llamada MONGO_URI (mira .env.example).
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# Si existe un archivo .env, carga sus variables (opcional pero recomendado)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# 1. CONFIGURACION   👈 AJUSTA ESTOS NOMBRES A TU PROYECTO
# ---------------------------------------------------------------------------
NOMBRE_BD = "earthquake_project"            # 👈 tu base de datos en Atlas
NOMBRE_COLECCION = "earthquakes"   # 👈 tu coleccion con los datos ya limpios

# ---------------------------------------------------------------------------
# 2. CONEXION A MONGODB (segura: la clave viene de una variable de entorno)
# ---------------------------------------------------------------------------
MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError(
        "Falta la variable de entorno MONGO_URI. "
        "Crea un archivo .env con tu cadena de conexion de Atlas (mira el README)."
    )

cliente = MongoClient(MONGO_URI)
coleccion = cliente[NOMBRE_BD][NOMBRE_COLECCION]

# ---------------------------------------------------------------------------
# 3. LA APLICACION
# ---------------------------------------------------------------------------
app = FastAPI(
    title="API Proyecto Final",
    description="Consulta y administra los datos del proyecto.",
)


def _a_json(doc):
    """El _id de Mongo es un objeto especial; lo pasamos a texto para el JSON."""
    doc["_id"] = str(doc["_id"])
    return doc


@app.get("/")
def inicio():
    """Mensaje de bienvenida y lista de endpoints."""
    return {
        "mensaje": "API del Proyecto Final - ve a /docs para probarla",
        "endpoints": ["GET /datos", "GET /estadisticas", "POST /datos", "/docs"],
    }


# ==== LEER =================================================================
@app.get("/datos")
def listar(campo: Optional[str] = None, valor: Optional[str] = None, limite: int = 20):
    """Lista documentos. Opcionalmente filtra por un campo = valor.

    Ejemplos:
        /datos?limite=50
        /datos?campo=sucursal&valor=Norte
    """
    filtro = {campo: valor} if campo and valor else {}
    documentos = [_a_json(d) for d in coleccion.find(filtro).limit(limite)]
    return {"cantidad": len(documentos), "datos": documentos}


@app.get("/estadisticas")
def estadisticas(agrupar_por: str, sumar: str):
    """Agrupa por un campo y suma otro (agregacion de MongoDB).

    Ejemplo:
        /estadisticas?agrupar_por=sucursal&sumar=total
    """
    pipeline = [
        {
            "$group": {
                "_id": f"${agrupar_por}",
                "suma": {"$sum": f"${sumar}"},
                "conteo": {"$sum": 1},
            }
        },
        {"$sort": {"suma": -1}},
    ]
    grupos = [
        {agrupar_por: r["_id"], "suma": r["suma"], "conteo": r["conteo"]}
        for r in coleccion.aggregate(pipeline)
    ]
    return {"grupos": grupos}


# ==== CREAR ================================================================
# 👈 CAMBIA estos campos por los de TU coleccion (mismos nombres y tipos).


class NuevoRegistro(BaseModel):

    # Información principal del terremoto
    event_id: str
    magnitude: float
    place: str
    time: int
    depth_km: float
    latitude: float
    longitude: float
    significance: int

    # Información que puede contener valores nulos
    magnitude_type: Optional[str] = None
    distance: Optional[float] = None
    alert: Optional[str] = None
    status: Optional[str] = None
    network: Optional[str] = None

    # Información adicional del USGS
    tsunami: int = 0
    updated: Optional[int] = None
    felt: Optional[int] = None
    cdi: Optional[float] = None
    mmi: Optional[float] = None
    code: Optional[str] = None
    stations: Optional[int] = None
    rms: Optional[float] = None
    gap: Optional[float] = None
    event_type: str = "earthquake"
    url: Optional[str] = None
    detail_url: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "prueba-001",
                "magnitude": 4.5,
                "place": "10 km N of ejemplo",
                "time": 1735697312976,
                "depth_km": 15.0,
                "latitude": 4.71,
                "longitude": -74.07,
                "significance": 250,
                "magnitude_type": "mb",
                "distance": 0.12,
                "tsunami": 0,
                "alert": None,
                "status": "reviewed",
                "network": "us",
                "updated": 1735697314000,
                "event_type": "earthquake"
            }
        }
    }





@app.post("/datos", status_code=201)
def crear(registro: NuevoRegistro):
    """Inserta un nuevo terremoto en MongoDB."""

    doc = registro.model_dump()

    try:
        resultado = coleccion.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Ya existe un terremoto con ese event_id"
        )

    return {
        "mensaje": "Terremoto registrado correctamente",
        "id": str(resultado.inserted_id)
    }

