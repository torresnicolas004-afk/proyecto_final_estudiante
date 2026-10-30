# Proyecto Final — Una aplicación completa sobre tus datos

Plantillas de arranque para convertir el proyecto del segundo corte (datos ya
limpios en MongoDB) en una **aplicación completa**: un backend que sirve y
administra los datos, y un frontend que los consume.

```
MongoDB (datos limpios) ──> API (FastAPI) ──> Dashboard (Streamlit)
                              backend            frontend
```

## Archivos

| Archivo | Que hace |
|---|---|
| `api.py` | Backend: consulta (`GET`), agrega (`/estadisticas`) y crea (`POST`) registros. |
| `dashboard.py` | Frontend: lista, filtra, grafica y agrega registros llamando a la API. |
| `requirements.txt` | Librerias necesarias. |
| `.env.example` | Plantilla para tu cadena de conexion (seguridad). |

Busca el simbolo **👈** en el codigo: marca los puntos que cada grupo debe
cambiar segun su propio dataset (base de datos, coleccion y nombres de campos).

## Paso 0 — Instalar y configurar la conexion (una sola vez)

```bash
pip install -r requirements.txt
cp .env.example .env        # en Windows:  copy .env.example .env
```

Abre `.env` y pega tu cadena real de MongoDB Atlas.
**La clave va solo en `.env`, nunca dentro del codigo.** Agrega `.env` al
`.gitignore` para no subirla por accidente.

## Paso 1 — Levantar la API (backend)

```bash
uvicorn api:app --reload
```

Abre http://localhost:8000/docs y prueba los endpoints sin escribir codigo:
- `GET /datos` — lista y filtra (`?campo=sucursal&valor=Norte`)
- `GET /estadisticas` — agrupa y suma (`?agrupar_por=sucursal&sumar=total`)
- `POST /datos` — crea un registro nuevo

## Paso 2 — Levantar el dashboard (frontend)

En **otra** terminal (dejando la API corriendo):

```bash
streamlit run dashboard.py
```

## Las dos rutas del proyecto

- **Ruta completa:** la API con lectura + agregacion + creacion, y el dashboard
  que filtra, grafica y agrega registros.
- **Ruta minima:** la API solo con `GET /datos` y el dashboard que lista y
  grafica (sin agregacion ni creacion). Tope de nota mas bajo, pero evita
  quedarse en cero.

## Bono (hasta +0.3)

Desplegar la API y/o el dashboard en la nube (Render, Railway o Streamlit
Community Cloud) y pasar la URL publica. Si despliegas la API, recuerda
cambiar la variable `API` en `dashboard.py`.
