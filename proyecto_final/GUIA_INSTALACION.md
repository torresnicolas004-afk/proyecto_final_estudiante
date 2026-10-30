# Guía de instalación — Proyecto Final (hazla ANTES del miércoles)

El objetivo es que llegues a clase con el entorno ya montado y probado, para no
perder tiempo instalando. Son ~20 minutos. Sigue los pasos en orden.

> Al final hay una **lista de verificación** y una tabla de **errores comunes**.
> Si algo falla, mira esa tabla antes de frustrarte.

---

## Paso 1 — Instalar Python (3.11 o superior)

1. Entra a https://www.python.org/downloads/ y descarga la última versión.
2. Ejecuta el instalador.
   - **Windows:** en la primera pantalla, **marca la casilla "Add python.exe to
     PATH"** (abajo) ANTES de dar "Install Now". Es el error #1 si se te olvida.
   - **Mac:** instala normal (siguiente, siguiente).
3. Verifica que quedó instalado. Abre una terminal:
   - Windows: menú inicio → escribe **PowerShell** → Enter.
   - Mac: Spotlight (⌘+espacio) → escribe **Terminal** → Enter.
   Y escribe:
   ```bash
   python --version
   ```
   Debe responder algo como `Python 3.12.x`.
   *(En Windows, si no responde, prueba con `py --version`.)*

## Paso 2 — Instalar VS Code

1. Descarga desde https://code.visualstudio.com/ e instala.
2. Ábrelo. En el panel de la izquierda ve a **Extensions** (el ícono de cubos)
   e instala la extensión **Python** (de Microsoft).

## Paso 3 — Crear la carpeta del proyecto

1. Crea una carpeta en tu equipo, por ejemplo `proyecto-final`.
2. Copia dentro los archivos que te dio el profesor: `api.py`, `dashboard.py`,
   `requirements.txt`, `.env.example`.
3. En VS Code: **File → Open Folder…** y abre esa carpeta.

## Paso 4 — Crear el entorno virtual (venv)

Un *entorno virtual* es una "caja" donde instalas las librerías del proyecto sin
ensuciar el resto del sistema. En VS Code abre la terminal con
**Terminal → New Terminal** y escribe:

**Windows:**
```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
```

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Si funcionó, verás `(venv)` al inicio de la línea de la terminal. **Esa marca
`(venv)` debe estar siempre presente** cuando instales o ejecutes algo.

> **Windows — si sale un error rojo al activar** ("...no se puede cargar porque
> la ejecución de scripts está deshabilitada..."), ejecuta esto una sola vez y
> vuelve a activar:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

## Paso 5 — Instalar las librerías

Con `(venv)` activo:
```bash
pip install -r requirements.txt
```
Espera a que termine (descarga FastAPI, Streamlit, etc.).

## Paso 6 — Configurar tu conexión a MongoDB (seguro)

1. Copia el archivo de ejemplo y renómbralo como `.env`:
   - Windows: `copy .env.example .env`
   - Mac/Linux: `cp .env.example .env`
2. Abre `.env` en VS Code y pega tu cadena real de MongoDB Atlas en `MONGO_URI`.
3. **Tu clave vive solo en `.env`, nunca dentro del código.**
4. En Atlas, revisa **Network Access** y permite tu IP (para clase puedes usar
   `0.0.0.0/0`), o no podrás conectarte.

## Paso 7 — Probar que todo corre

**Prueba la API.** En la terminal (con `(venv)` activo):
```bash
uvicorn api:app --reload
```
Abre en el navegador: **http://localhost:8000/docs**
Deberías ver la documentación de la API. Para detenerla: `Ctrl + C`.

**Prueba el dashboard.** Abre una **segunda** terminal en VS Code
(ícono de split o Terminal → New Terminal), actívale el venv igual que en el
Paso 4, deja la API corriendo en la primera, y en la segunda:
```bash
streamlit run dashboard.py
```
Se abrirá solo en el navegador (http://localhost:8501).

---

## ✅ Lista de verificación (llega a clase con esto listo)

- [ ] `python --version` responde 3.11 o superior.
- [ ] VS Code instalado con la extensión de Python.
- [ ] Veo `(venv)` en mi terminal.
- [ ] `pip install -r requirements.txt` terminó sin errores.
- [ ] Tengo mi archivo `.env` con mi `MONGO_URI`.
- [ ] `uvicorn api:app --reload` me abre http://localhost:8000/docs.

---

## 🔧 Errores comunes

| Lo que ves | Qué significa / cómo se arregla |
|---|---|
| `python no se reconoce...` (Windows) | No marcaste "Add to PATH" al instalar. Prueba `py` en vez de `python`, o reinstala marcando la casilla. |
| Error rojo al activar el venv (Windows) | Ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activar. |
| No aparece `(venv)` | No activaste el entorno. Repite el Paso 4 en esta terminal. |
| `ModuleNotFoundError: fastapi` | Instalaste sin el venv activo. Actívalo y repite el Paso 5. |
| `RuntimeError: Falta la variable MONGO_URI` | No creaste el `.env` o está vacío. Repite el Paso 6. |
| No conecta a Mongo / timeout | Revisa **Network Access** en Atlas (permite tu IP) y que la cadena del `.env` sea correcta. |
| `address already in use` (puerto ocupado) | Ya tienes algo corriendo en ese puerto. Cierra la otra terminal o usa `uvicorn api:app --reload --port 8001`. |

Si después de la tabla sigue fallando, trae el **mensaje de error exacto** a
clase (captura de pantalla) y lo resolvemos.
