# Guía del Proyecto Final — Una aplicación de datos completa

**Programación Aplicada · Ciencia de Datos**

En este proyecto conviertes los datos limpios de tu segundo corte en una
**aplicación completa**: una base de datos en la nube, un backend que la sirve
y un frontend con el que cualquiera interactúa.

```
MongoDB Atlas  ──>  API (FastAPI)  ──>  Dashboard (Streamlit)
  los datos          el backend            el frontend
```

Todo tu código, además, vivirá en **GitHub**.

---

## Antes de empezar: lo que debes tener instalado

1. **Python 3.11+** — `python --version`
2. **VS Code** con la extensión de Python
3. **Git** — `git --version`
   - Windows: instala *Git for Windows* desde `git-scm.com` (o `winget install Git.Git`).
   - Mac: escribe `git --version` en la Terminal y acepta instalar las *Command Line Tools* (o `brew install git`).
   - Ojo: **VS Code no trae Git**; hay que instalarlo aparte. Reinicia VS Code después.
4. Una cuenta gratis en **MongoDB Atlas** y otra en **GitHub**.

Configura Git una sola vez:
```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu@correo.com"
```

---

## Estructura del proyecto

```
mi-proyecto/
├── api.py             # El backend (FastAPI)
├── dashboard.py       # El frontend (Streamlit)
├── requirements.txt   # Librerías
├── .env               # Tu MONGO_URI (NUNCA se sube a GitHub)
├── .env.example       # Plantilla de .env
└── .gitignore         # Lista de lo que no se sube
```

---

## Fase 0 — Preparar el entorno

```bash
# 1. Crea y activa el entorno virtual
py -m venv venv                 # Windows   (Mac: python3 -m venv venv)
.\venv\Scripts\Activate.ps1     # Windows   (Mac: source venv/bin/activate)

# 2. Instala las librerías
py -m pip install -r requirements.txt

# 3. Crea tu archivo de secretos
copy .env.example .env          # Windows   (Mac: cp .env.example .env)
```

Debes ver `(venv)` al inicio de la línea. Esa marca tiene que estar presente
en **toda** terminal donde instales o ejecutes algo.

---

## Fase 1 — La base de datos (MongoDB Atlas)

1. En Atlas, confirma que tienes tu **base de datos** y tu **colección** con los
   datos ya limpios del segundo corte.
2. Copia tu cadena de conexión (**Connect → Drivers**) y pégala en `.env`:
   ```
   MONGO_URI=mongodb+srv://usuario:clave@cluster0.xxxxx.mongodb.net/?appName=Cluster0
   ```
3. En **Network Access**, permite tu IP (para clase puedes usar `0.0.0.0/0`).
   Sin esto, la API no podrá conectarse.

> **Regla de oro:** la contraseña vive solo en `.env`, **nunca** dentro del código.

---

## Fase 2 — Git y GitHub

```bash
# Dentro de la carpeta del proyecto, con el .gitignore ya presente
git init
git add .
git commit -m "primer commit: estructura del proyecto"
```

Luego en **github.com**: *New repository* → nombre → **Create** (sin README).
GitHub te muestra estos comandos para conectar tu repo local:

```bash
git remote add origin <url-de-tu-repo>
git branch -M main
git push -u origin main
```

De ahí en adelante, cada avance:
```bash
git add .
git commit -m "describe lo que hiciste"
git push
```

> Verifica que tu `.gitignore` incluya `.env` y `venv/`. Abre tu repo en GitHub
> y confirma que **el archivo `.env` NO aparece**. Si aparece, cambia tu
> contraseña de Atlas de inmediato.

---

## Fase 3 — El backend (API con FastAPI)

En `api.py`, ajusta el nombre de tu base de datos y colección (busca el 👈).
La API ya trae tres endpoints:

| Método | Endpoint | Qué hace |
|---|---|---|
| GET | `/datos` | Lista documentos; filtra con `?campo=...&valor=...&limite=...` |
| GET | `/estadisticas` | Agrupa y suma: `?agrupar_por=sucursal&sumar=total` |
| POST | `/datos` | Crea un documento nuevo (valida con Pydantic) |

> Si tus documentos tienen campos **anidados** (p. ej. `producto` es un objeto),
> ajusta la clase `NuevoRegistro` con una clase anidada, y consulta/agrupa esos
> campos con un punto: `producto.categoria`.

Levanta la API (en una terminal con `(venv)`):
```bash
python -m uvicorn api:app --reload
```
Abre **http://localhost:8000/docs** y prueba cada endpoint sin escribir código.

---

## Fase 4 — El frontend (dashboard con Streamlit)

En `dashboard.py`, revisa que la variable `API` apunte a tu backend:
```python
API = "http://localhost:8000"   # local
```
Levanta el dashboard en **otra** terminal (con `(venv)` y la API corriendo):
```bash
python -m streamlit run dashboard.py
```
Se abre en http://localhost:8501. Debe **listar tus datos, filtrarlos, graficar
estadísticas y permitir agregar un registro** (que viaja por `POST` a la API).

Con esto tienes el ciclo completo funcionando:
**dashboard ↔ API ↔ MongoDB**.

---

## Fase 5 — Desplegar en internet (bono, hasta +0.3)

- **API en Render** (gratis, sin tarjeta): conecta tu repo de GitHub → *New
  Web Service* → Build: `pip install -r requirements.txt`, Start:
  `uvicorn api:app --host 0.0.0.0 --port $PORT`, instancia **Free**. En
  *Environment* agrega la variable `MONGO_URI`. Obtienes una URL pública.
- **Dashboard en Streamlit Community Cloud** (gratis): conecta el mismo repo,
  elige `dashboard.py`, y cambia `API` por la URL pública de Render.

> La capa gratis de Render se duerme tras 15 min sin uso; la primera petición
> luego tarda ~1 minuto en despertar. Para una demo es aceptable.

---

## Entregables

| # | Entregable | Cuándo |
|---|-----------|--------|
| 1 | API que consulta (lectura + estadísticas) | Fin Semana 1 |
| 2 | API completa (con creación) y documentada en `/docs` | Fin Semana 2 |
| 3 | Dashboard funcional + repositorio en GitHub | Sesión final |
| 4 | Sustentación (demo de la app + defensa) | Sesión final |

## Rúbrica (sobre 5.0)

| Componente | Valor |
|---|---|
| API de lectura (filtros + agregación) | 1.2 |
| API de escritura (`POST`, validación, códigos de estado) | 1.0 |
| Dashboard (consume la API, filtros, gráfica, crear) | 1.4 |
| Integración + calidad de código y seguridad de credenciales | 0.8 |
| Sustentación / defensa | 0.6 |
| **Total** | **5.0** |

**Penalización:** credencial expuesta en el repo o en el código, −0.3 a −0.5.
**Bono (hasta +0.3):** despliegue en la nube con URL pública.

---

## Checklist final

- [ ] `git --version`, `python --version` y VS Code con extensión de Python
- [ ] `(venv)` activo e `pip install -r requirements.txt` sin errores
- [ ] `.env` con mi `MONGO_URI` y Atlas con Network Access abierto
- [ ] Repo en GitHub **sin** `.env` ni `venv/`
- [ ] `http://localhost:8000/docs` responde con mis datos
- [ ] El dashboard lista, filtra, grafica y agrega registros
- [ ] Cada integrante puede explicar una decisión técnica

## Errores comunes

| Lo que ves | Arreglo |
|---|---|
| `ModuleNotFoundError` | Instalaste sin `(venv)` activo. Actívalo y reinstala. |
| `streamlit` o `uvicorn` no se reconoce | Falta `(venv)`. Usa `python -m streamlit ...` / `python -m uvicorn ...`. |
| `RuntimeError: Falta MONGO_URI` | No creaste el `.env` o está vacío. |
| Timeout al conectar a Mongo | Network Access en Atlas: habilita tu IP (`0.0.0.0/0`). |
| `/datos` llega vacío | Revisa el nombre de la base y la colección en `api.py`. |
| El dashboard no conecta | La API no está corriendo, o `API` apunta a la URL equivocada. |
