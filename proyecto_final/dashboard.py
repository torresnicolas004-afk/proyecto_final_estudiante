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

API = "http://localhost:8000"  # 👈 si despliegas la API en la nube, cambia esta URL

st.set_page_config(page_title="Proyecto Final", page_icon="📊", layout="wide")
st.title("📊 Dashboard del Proyecto Final")


# --- Funciones que hablan con la API ---------------------------------------
@st.cache_data(ttl=30)
def listar(campo=None, valor=None, limite=200):
    params = {"limite": limite}
    if campo and valor:
        params.update({"campo": campo, "valor": valor})
    r = requests.get(f"{API}/datos", params=params, timeout=10)
    r.raise_for_status()
    return pd.DataFrame(r.json()["datos"])


@st.cache_data(ttl=30)
def estadisticas(agrupar_por, sumar):
    r = requests.get(
        f"{API}/estadisticas",
        params={"agrupar_por": agrupar_por, "sumar": sumar},
        timeout=10,
    )
    r.raise_for_status()
    return pd.DataFrame(r.json()["grupos"])


# --- Verifica que la API este arriba ---------------------------------------
try:
    df = listar()
except Exception:
    st.error(
        f"No pude conectarme a la API en {API}. "
        f"Revisa que este corriendo:  uvicorn api:app --reload"
    )
    st.stop()

if df.empty:
    st.warning("La coleccion esta vacia.")
    st.stop()

columnas = [c for c in df.columns if c != "_id"]
numericas = df.select_dtypes("number").columns.tolist()

# --- Filtro en la barra lateral --------------------------------------------
st.sidebar.header("Filtros")
campo = st.sidebar.selectbox("Filtrar por campo", ["(todos)"] + columnas)
if campo != "(todos)":
    opciones = sorted(df[campo].dropna().astype(str).unique())
    valor = st.sidebar.selectbox("Valor", opciones)
    df = listar(campo=campo, valor=valor)

# --- Metricas ---------------------------------------------------------------
c1, c2 = st.columns(2)
c1.metric("Registros", len(df))
if numericas:
    # 👈 elige una columna con sentido (p. ej. 'total', no 'venta_id')
    col_metrica = numericas[-1]
    c2.metric(f"Suma de {col_metrica}", int(df[col_metrica].sum()))

# --- Estadisticas (usa la agregacion de la API) ----------------------------
st.subheader("Estadisticas")
categoricas = [c for c in columnas if c not in numericas]
if categoricas and numericas:
    a1, a2 = st.columns(2)
    agrupar = a1.selectbox("Agrupar por", categoricas)
    sumar = a2.selectbox("Sumar", numericas)
    if st.button("Calcular"):
        g = estadisticas(agrupar, sumar)
        st.bar_chart(g.set_index(agrupar)["suma"])
        st.dataframe(g, use_container_width=True)

# --- Tabla de datos ---------------------------------------------------------
st.subheader("Datos")
st.dataframe(df, use_container_width=True)

# --- Agregar un registro (POST a la API) -----------------------------------
# 👈 CAMBIA estos campos por los de TU coleccion (mismos nombres que en la API).
st.subheader("➕ Agregar registro")
with st.form("nuevo"):
    sucursal = st.text_input("sucursal")
    producto = st.text_input("producto")
    cantidad = st.number_input("cantidad", min_value=0, step=1)
    total = st.number_input("total", min_value=0, step=1000)
    medio_pago = st.text_input("medio_pago")
    enviar = st.form_submit_button("Guardar")

if enviar:
    payload = {
        "sucursal": sucursal,
        "producto": producto,
        "cantidad": int(cantidad),
        "total": int(total),
        "medio_pago": medio_pago,
    }
    r = requests.post(f"{API}/datos", json=payload, timeout=10)
    if r.ok:
        st.success(f"Guardado con id {r.json()['id']}")
        st.cache_data.clear()  # refresca la tabla
    else:
        st.error(f"Error de la API: {r.text}")
