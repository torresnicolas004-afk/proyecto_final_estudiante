"""
Dashboard del Proyecto Final - Programacion Aplicada
=====================================================
Frontend (Streamlit) que consume la API (api.py): lista, filtra, grafica
y permite agregar registros nuevos.

Como ejecutar (en OTRA terminal, con la API ya corriendo):
    streamlit run dashboard.py

La API debe estar activa en http://localhost:8000
"""


import pandas as pd
import requests
import streamlit as st

from datetime import datetime, timezone


# ============================================================
# 1. CONFIGURACION
# ============================================================

API = "https://proyecto-final-estudiante-271721.onrender.com"

st.set_page_config(
    page_title="USGS Earthquake Dashboard",
    page_icon="🌎",
    layout="wide"
)

st.title("🌎 Dashboard de Terremotos - USGS")
st.caption("Consulta, análisis y registro de eventos sísmicos")


# ============================================================
# 2. FUNCIONES PARA CONSUMIR LA API
# ============================================================

@st.cache_data(ttl=30)
def listar(campo=None, valor=None, limite=200):

    params = {"limite": limite}

    if campo and valor is not None:
        params.update({
            "campo": campo,
            "valor": valor
        })

    r = requests.get(
        f"{API}/datos",
        params=params,
        timeout=10
    )

    r.raise_for_status()

    return pd.DataFrame(r.json()["datos"])


@st.cache_data(ttl=30)
def estadisticas(agrupar_por, sumar):

    r = requests.get(
        f"{API}/estadisticas",
        params={
            "agrupar_por": agrupar_por,
            "sumar": sumar
        },
        timeout=10
    )

    r.raise_for_status()

    return pd.DataFrame(r.json()["grupos"])


# ============================================================
# 3. CONEXION CON LA API
# ============================================================

try:
    df = listar()

except requests.RequestException as e:

    st.error(
        f"No pude conectarme a la API en {API}. "
        "Verifica que FastAPI esté funcionando."
    )

    st.stop()


if df.empty:
    st.warning("No hay terremotos registrados actualmente.")


# ============================================================
# 4. FILTROS
# ============================================================

st.sidebar.header("🔎 Filtros")

campos_filtro = [
    c for c in [
        "magnitude_type",
        "alert",
        "status",
        "network",
        "event_type"
    ]
    if c in df.columns
]

if not df.empty and campos_filtro:

    campo = st.sidebar.selectbox(
        "Filtrar por categoría",
        ["(todos)"] + campos_filtro
    )

    if campo != "(todos)":

        opciones = sorted(
            df[campo].dropna().astype(str).unique()
        )

        if opciones:

            valor = st.sidebar.selectbox(
                "Selecciona el valor",
                opciones
            )

            df = listar(
                campo=campo,
                valor=valor
            )


# ============================================================
# 5. METRICAS PRINCIPALES
# ============================================================

st.subheader("📊 Indicadores generales")

if not df.empty:

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Terremotos mostrados",
        len(df)
    )

    c2.metric(
        "Magnitud promedio",
        round(df["magnitude"].mean(), 2)
    )

    c3.metric(
        "Profundidad promedio (km)",
        round(df["depth_km"].mean(), 2)
    )


# ============================================================
# 6. ESTADISTICAS Y GRAFICAS
# ============================================================

st.subheader("📈 Estadísticas de los terremotos")

if not df.empty:

    categoricas = [
        c for c in [
            "magnitude_type",
            "alert",
            "status",
            "network",
            "event_type"
        ]
        if c in df.columns
    ]

    numericas = [
        c for c in [
            "magnitude",
            "depth_km",
            "significance",
            "felt",
            "stations",
            "distance"
        ]
        if c in df.columns
    ]

    if categoricas and numericas:

        a1, a2 = st.columns(2)

        agrupar = a1.selectbox(
            "Agrupar por",
            categoricas
        )

        indice = (
            numericas.index("magnitude")
            if "magnitude" in numericas else 0
        )

        sumar = a2.selectbox(
            "Variable numérica",
            numericas,
            index=indice
        )

        if st.button("Calcular estadísticas"):

            try:

                g = estadisticas(agrupar, sumar)

                if not g.empty:

                    st.write(
                        "Cantidad de terremotos por categoría:"
                    )

                    st.bar_chart(
                        g.set_index(agrupar)["conteo"]
                    )

                    st.write("Tabla de resultados:")

                    st.dataframe(
                        g,
                        use_container_width=True
                    )

                else:
                    st.warning("No se encontraron resultados.")

            except requests.RequestException as e:

                st.error(f"Error al consultar estadísticas: {e}")


# ============================================================
# 7. TABLA DE TERREMOTOS
# ============================================================

st.subheader("🌍 Registros de terremotos")

if not df.empty:

    df_mostrar = df.copy()

    # Convertir la fecha de milisegundos a fecha legible
    if "time" in df_mostrar.columns:

        df_mostrar["fecha_utc"] = pd.to_datetime(
            df_mostrar["time"],
            unit="ms",
            utc=True,
            errors="coerce"
        )

    st.dataframe(
        df_mostrar,
        use_container_width=True
    )


# ============================================================
# 8. AGREGAR UN NUEVO TERREMOTO
# ============================================================

st.subheader("➕ Registrar un nuevo terremoto")

with st.form("nuevo_terremoto"):

    col1, col2 = st.columns(2)

    with col1:

        event_id = st.text_input(
            "Identificador del evento (event_id)"
        )

        magnitude = st.number_input(
            "Magnitud",
            min_value=0.0,
            max_value=10.0,
            value=4.5,
            step=0.1
        )

        place = st.text_input("Lugar del terremoto")

        fecha = st.date_input("Fecha del evento (UTC)")

        hora = st.time_input("Hora del evento (UTC)")

        depth_km = st.number_input(
            "Profundidad (km)",
            min_value=0.0,
            value=10.0,
            step=1.0
        )

    with col2:

        latitude = st.number_input(
            "Latitud",
            min_value=-90.0,
            max_value=90.0,
            value=0.0,
            format="%.5f"
        )

        longitude = st.number_input(
            "Longitud",
            min_value=-180.0,
            max_value=180.0,
            value=0.0,
            format="%.5f"
        )

        significance = st.number_input(
            "Significancia",
            min_value=0,
            value=0,
            step=1
        )

        magnitude_type = st.text_input(
            "Tipo de magnitud",
            value="mb"
        )

        tsunami = st.selectbox(
            "Indicador de tsunami",
            [0, 1],
            format_func=lambda x: "Sí (1)" if x == 1 else "No (0)"
        )

    alert = st.text_input(
        "Nivel de alerta (opcional)"
    )

    status = st.text_input(
        "Estado del registro (opcional)"
    )

    network = st.text_input(
        "Red sísmica (opcional)"
    )

    tiene_distance = st.checkbox(
        "Tengo el valor de distance (dmin)"
    )

    if tiene_distance:

        distance = st.number_input(
            "Distancia dmin (grados)",
            min_value=0.0,
            value=0.1,
            step=0.01
        )

    else:

        distance = None

    enviar = st.form_submit_button(
        "Guardar terremoto"
    )


# ============================================================
# 9. ENVIAR REGISTRO A LA API
# ============================================================

if enviar:

    if not event_id.strip() or not place.strip():

        st.error(
            "Debes ingresar el identificador y el lugar."
        )

    else:

        # Convertir la fecha y hora a milisegundos UTC
        fecha_hora = datetime.combine(
            fecha,
            hora
        ).replace(tzinfo=timezone.utc)

        time_ms = int(
            fecha_hora.timestamp() * 1000
        )

        # Construir el documento que recibirá FastAPI
        payload = {

            "event_id": event_id.strip(),
            "magnitude": magnitude,
            "place": place,
            "time": time_ms,
            "depth_km": depth_km,
            "latitude": latitude,
            "longitude": longitude,
            "significance": int(significance),

            "magnitude_type": magnitude_type.strip() or None,
            "distance": distance,
            "tsunami": int(tsunami),
            "alert": alert.strip() or None,
            "status": status.strip() or None,
            "network": network.strip() or None

        }

        try:

            r = requests.post(
                f"{API}/datos",
                json=payload,
                timeout=10
            )

            if r.ok:

                st.success(
                    f"Terremoto registrado correctamente. "
                    f"ID: {r.json()['id']}"
                )

                st.cache_data.clear()

            else:

                try:
                    detalle = r.json().get("detail", r.text)
                except ValueError:
                    detalle = r.text

                st.error(
                    f"Error de la API: {detalle}"
                )

        except requests.RequestException as e:

            st.error(
                f"No se pudo conectar con la API: {e}"
            )
