import os
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import gspread 
import json # Solo se usa para procesar la respuesta de la IA, no para credenciales

# 1. ESQUEMA DE DATOS
class JobDescription(BaseModel):
    titulo_puesto: str = Field(description="Título del puesto.")
    nivel: str = Field(description="Experiencia.")
    resumen_puesto: str = Field(description="Resumen.")
    responsabilidades_clave: list[str] = Field(description="Lista responsabilidades.")
    requisitos_minimos: list[str] = Field(description="Lista requisitos.")
    competencias_deseables: list[str] = Field(description="Competencias.")
    palabras_clave_seo_rrhh: list[str] = Field(description="SEO.")

GOOGLE_SHEET_ID = "1QPJ1JoCW7XO-6sf-WMz8SvAtylKTAShuMr_yGBoF-Xg" 

# 2. CONEXIÓN A SHEETS (SIN json.loads)
@st.cache_data(ttl=3600)
# AQUI ESTA EL CAMBIO: Apunta a la hoja nueva "Diccionario_JobCraft"
def get_competencias(worksheet_name: str = "Diccionario_JobCraft"):
    try:
        # Accedemos directamente al diccionario de secretos
        creds = st.secrets["gspread"]["gcp_service_account_credentials"]
        gc = gspread.service_account_from_dict(creds)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data), None
    except Exception as e:
        return None, f"Error de conexión con Google Sheets. Detalle: {e}"

# 3. EJECUCIÓN DE IA
def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str, competencias_df: pd.DataFrame):
    try:
        client = genai.Client(api_key=api_key)
        # Aquí usa el nombre de columna "COREES_Definición_Core_N1_Inicial"
        competencias_list = "\n".join([f"-{row['Familia']}:{row['COREES_Definición_Core_N1_Inicial']}" for index, row in competencias_df.iterrows()])
        prompt = f"Genera descripción para {title} nivel {level}. Habilidad crítica: {critical_skill}. Usa estas competencias: {competencias_list}"
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=JobDescription)
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
        return None, JobDescription(**json.loads(response.text))
    except Exception as e:
        return f"Error AI: {e}", None

# 4. GUARDAR RESULTADOS
def guardar_datos_en_sheets(titulo_puesto: str, nivel: str, critical_skill: str):
    try:
        creds = st.secrets["gspread"]["gcp_service_account_credentials"]
        gc = gspread.service_account_from_dict(creds)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        # Asegúrate de tener esta hoja creada: "Seguimiento Generaciones"
        worksheet = spreadsheet.worksheet("Seguimiento Generaciones") 
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        worksheet.append_row([timestamp, titulo_puesto, nivel, critical_skill]) 
        return True, None
    except Exception as e:
        return False, f"Error al guardar: {e}"

# 5. INTERFAZ DE USUARIO
st.set_page_config(page_title="JobCraft AI")
st.title("JobCraft AI 🤖 Generador de Puestos")

api_key = st.secrets["GEMINI_API_KEY"] if "GEMINI_API_KEY" in st.secrets else None
if not api_key:
    st.error("Falta la GEMINI_API_KEY en los secretos.")
    st.stop()

df, err = get_competencias()
if err:
    st.error(err)
    st.stop()

with st.form("jobcraft_form"):
    t = st.text_input("Título del Puesto", value="Analista Financiero")
    l = st.selectbox("Nivel", ["Junior", "Intermedio", "Senior", "Lider/Manager"])
    s = st.text_area("Habilidad o Experiencia Crítica")
    btn = st.form_submit_button("Generar Descripción")

if btn:
    with st.spinner("🚀 JobCraft AI está trabajando..."):
        err_ai, res = run_jobcraft_ai(api_key, t, l, s, df)
        if err_ai: 
            st.error(err_ai)
        else:
            st.success("¡Descripción generada con éxito!")
            guardar_datos_en_sheets(res.titulo_puesto, res.nivel, s)
            
            # Mostrar resultados
            st.subheader(res.titulo_puesto)
            st.write(f"**Nivel:** {res.nivel}")
            st.write(res.resumen_puesto)
            st.markdown("**Responsabilidades:**")
            for item in res.responsabilidades_clave: st.write(f"- {item}")
