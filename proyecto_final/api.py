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
    sucursal: str
    producto: str
    cantidad: int
    total: int
    medio_pago: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "sucursal": "Norte",
                "producto": "Cafe",
                "cantidad": 2,
                "total": 15000,
                "medio_pago": "Tarjeta",
            }
        }
    }


@app.post("/datos")
def crear(registro: NuevoRegistro):
    """Inserta un nuevo documento en la coleccion."""
    doc = registro.model_dump()
    resultado = coleccion.insert_one(doc)
    return {"mensaje": "Registro creado", "id": str(resultado.inserted_id)}
