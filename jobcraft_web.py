import os
import streamlit as st
import json
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import gspread # <--- Importación para Google Sheets

# =========================================================
# 1. DEFINICIÓN DEL ESQUEMA DE SALIDA (El Contrato JSON)
# =========================================================
class JobDescription(BaseModel):
    """Esquema de la descripción de puesto de trabajo generado por el agente JobCraft AI."""
    titulo_puesto: str = Field(description="Título completo y claro del puesto.")
    nivel: str = Field(description="Nivel de experiencia (Ej: Junior, Intermedio, Senior, Manager).")
    resumen_puesto: str = Field(description="Descripción concisa y atractiva del rol y su impacto.")
    responsabilidades_clave: list[str] = Field(description="Lista de 5 a 7 responsabilidades principales del rol.")
    requisitos_minimos: list[str] = Field(description="Lista de 5 requisitos técnicos y de habilidades blandas indispensables.")
    competencias_deseables: list[str] = Field(description="Lista de 2 a 3 competencias o certificaciones que añaden valor.")
    palabras_clave_seo_rrhh: list[str] = Field(description="Lista de 3 a 5 palabras clave optimizadas para búsquedas de empleo.")

# =========================================================
# CONFIGURACIÓN DE GOOGLE SHEETS
# =========================================================
# ¡AJUSTA ESTO! Reemplaza 'jobcraft-sheets-api-a8e30825c2cd.json' con el ID real de tu hoja de competencias
GOOGLE_SHEET_ID = "TU_SHEET_ID_AQUÍ"
# Nombre del archivo de credenciales (debe coincidir con el nombre del archivo local)
CREDENTIALS_FILE = "credentials.json"

# =========================================================
# 2. FUNCIÓN DE CONEXIÓN A GOOGLE SHEETS
# =========================================================

@st.cache_data(ttl=3600) # Cachea los datos por 1 hora
def get_competencias(worksheet_name: str = "Diccionario Competencias"):
    """Lee y devuelve los datos del diccionario de competencias desde Google Sheets."""
    
    try:
        # Nota: gspread leerá las credenciales desde secrets.toml en la nube
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        return df, None
        
    except Exception as e:
        # Devuelve un mensaje de error útil si falla la conexión
        return None, f"Error de conexión con Google Sheets. Verifica: 1) ID de la hoja; 2) Que la cuenta de servicio tenga acceso (Lector); 3) Credenciales configuradas en Streamlit Cloud. Detalle: {e}"


# =========================================================
# 3. FUNCIÓN PRINCIPAL DEL AGENTE (Función limpia con estandarización)
# =========================================================

def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str, competencias_df: pd.DataFrame):
    """Función que ejecuta el Agente JobCraft AI y devuelve el JSON con competencias estandarizadas."""
    
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return f"Error de conexión: No se pudo conectar a Gemini. {e}", None

    # --- Preprocesamiento de Competencias (Asume que usas las columnas 'Familia' y 'COREES_Definición_Core_N1_Inicial') ---
    competencias_list = "\n".join(
        # ¡Asegúrate de que estos nombres de columna coincidan exactamente con tu hoja de cálculo!
        [f"-{row['Familia']}:{row['COREES_Definición_Core_N1_Inicial']}" for index, row in competencias_df.iterrows()]
    )

    # --- El Prompt Maestro MODIFICADO para usar el diccionario ---
    prompt = f"""
        Eres JobCraft AI, un agente especializado en Recursos Humanos cuya única función es generar descripciones de puestos de trabajo de alta calidad.
        Tu salida debe ser ÚNICA y EXCLUSIVAMENTE el JSON que sigue el esquema proporcionado. No debes incluir ningún texto explicativo ni formato Markdown adicional (como `json` antes del bloque).

        **Contexto de la Tarea:**
        1. **Puesto Requerido:** Genera la descripción para un puesto de "{title}" con un nivel de experiencia "{level}".
        2. **Habilidad Crítica:** Enfócate en la habilidad clave de "{critical_skill}".
        3. **Estándares de Competencias:** DEBES usar y referenciar el siguiente listado de competencias estandarizadas para elegir las más adecuadas para los requisitos y competencias deseables. NUNCA inventes competencias que no estén en la lista.

        **Diccionario de Competencias Estandarizadas (Formato: Familia:Definición):**
        ---
        {competencias_list}
        ---

        **Instrucciones de Generación:**
        * **Título y Nivel:** Usa los inputs proporcionados.
        * **Requisitos/Competencias:** Selecciona ÚNICAMENTE las competencias del diccionario que son relevantes. Si una competencia no existe en el diccionario, NO la uses.
        * **Formato de Salida:** Respeta estrictamente el esquema JSON.
    """
    
    # ... (El código continúa con la llamada a la API, pero nos detenemos aquí
    # ya que la parte principal de la interfaz y la lógica de Sheets está arriba.
    # Si la vez anterior te di el resto del código, pégalo también.
    # Si solo tenías hasta el prompt, es suficiente por ahora para corregir el error.)
    # Asumamos que el resto del código es lo que ya tenías antes, solo necesitamos
    # el bloque de gspread y la limpieza de los docstrings.

    # -------------------------------------------------------------
    # (Si no tienes el resto del código para completar la función
    # run_jobcraft_ai, te lo proporcionaré después de este paso)
    # -------------------------------------------------------------
    
    # -------------------------------------------------------------
    # SIMULACIÓN DEL RESTO DEL CÓDIGO (Si lo tenías)
    # -------------------------------------------------------------
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=JobDescription,
    )

    # st.info(f"Prompt enviado: {prompt}") # Línea de debug, puedes comentarla

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=config,
    )

    # La respuesta es un string JSON que ya cumple con el esquema
    try:
        # Parsear el JSON para convertirlo a objeto Python
        job_data = json.loads(response.text)
        return None, JobDescription(**job_data) # Devuelve el objeto pydantic
    except Exception as e:
        return f"Error al procesar la respuesta JSON de Gemini: {e}. Respuesta: {response.text}", None

# =========================================================
# 4. FUNCIÓN PARA GUARDAR LOS DATOS (¡NUEVO!)
# =========================================================

def guardar_datos_en_sheets(titulo_puesto: str, nivel: str, critical_skill: str):
    """Guarda los inputs del usuario en la hoja de seguimiento."""
    try:
        # Autenticación (usa las mismas credenciales que get_competencias)
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        # Ajusta este nombre si tu hoja de seguimiento tiene otro nombre
        worksheet = spreadsheet.worksheet("Seguimiento Generaciones") 

        # Datos a guardar
        timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        row_data = [timestamp, titulo_puesto, nivel, critical_skill, os.getenv("USERNAME", "N/A")]

        # Inserta la nueva fila al final
        worksheet.append_row(row_data) 
        return True, None
        
    except Exception as e:
        return False, f"Error al guardar en la hoja de seguimiento: {e}"


# =========================================================
# 5. INTERFAZ DE STREAMLIT (La parte que el usuario ve)
# =========================================================

# --- Configuración de la página ---
st.set_page_config(page_title="JobCraft AI", layout="wide")
st.title("JobCraft AI 🤖 Generador de Puestos Estandarizados")


# --- Validación de API Key ---
# Leemos la API Key desde las variables de entorno o desde el input de Streamlit
api_key = os.getenv("GEMINI_API_KEY") 

if not api_key:
    # Si la API Key no está en la variable de entorno, pide al usuario
    st.warning("¡Falta la clave API! Ingresa tu clave de Gemini API para continuar.")
    api_key_input = st.text_input("Ingresa tu clave de Gemini API:", type="password")
    
    if api_key_input:
        api_key = api_key_input
    else:
        st.stop()
        
# --- Cargar Diccionario de Competencias ---
competencias_df, error_sheet = get_competencias()

if error_sheet:
    st.error(error_sheet)
    st.stop() # Detiene la ejecución si hay un error de conexión

# st.success("Diccionario de competencias cargado correctamente.") # Puedes descomentar esto para debug


# --- Formulario de Entrada ---
with st.form("jobcraft_form"):
    st.header("Define el Puesto")
    
    col1, col2 = st.columns(2)
    
    with col1:
        title_input = st.text_input("Título del Puesto (Ej: Ingeniero de Datos)", value="Analista Financiero")
    
    with col2:
        level_input = st.selectbox(
            "Nivel de Experiencia", 
            ["Junior", "Intermedio", "Senior", "Lider/Manager"], 
            index=1
        )
        
    critical_skill_input = st.text_area(
        "Habilidad o Experiencia Crítica del Puesto",
        "Experiencia en Modelado Financiero avanzado (DCF, WACC) y dominio de Power BI.",
        height=100
    )
    
    submitted = st.form_submit_button("Generar Descripción de Puesto")


# --- Procesamiento de la Solicitud ---
if submitted:
    
    # 1. Ejecutar el Agente AI
    with st.spinner("🚀 Generando descripción con JobCraft AI..."):
        error_ai, job_description_output = run_jobcraft_ai(
            api_key, 
            title_input, 
            level_input, 
            critical_skill_input, 
            competencias_df
        )

    # 2. Mostrar Resultado o Error
    if error_ai:
        st.error(error_ai)
    elif job_description_output:
        
        st.success(f"✅ ¡Descripción generada para: {job_description_output.titulo_puesto}!")
        
        # 3. Guardar en Hoja de Seguimiento
        success_save, error_save = guardar_datos_en_sheets(
            job_description_output.titulo_puesto,
            job_description_output.nivel,
            critical_skill_input
        )
        
        if success_save:
            st.toast("💾 Datos de generación guardados en Google Sheets.", icon="✅")
        else:
            st.warning(f"⚠️ Error al guardar en Sheets: {error_save}")
            
        
        # 4. Mostrar la Descripción formateada
        st.subheader(job_description_output.titulo_puesto)
        st.markdown(f"**Nivel:** {job_description_output.nivel}")
        
        st.markdown("---")
        
        st.markdown("**Resumen del Puesto**")
        st.write(job_description_output.resumen_puesto)
        
        st.markdown("**Responsabilidades Clave**")
        st.markdown("\n".join([f"* {r}" for r in job_description_output.responsabilidades_clave]))
        
        st.markdown("**Requisitos Mínimos**")
        st.markdown("\n".join([f"* {r}" for r in job_description_output.requisitos_minimos]))
        
        st.markdown("**Competencias Deseables**")
        st.markdown("\n".join([f"* {r}" for r in job_description_output.competencias_deseables]))
        
        st.caption(f"Palabras clave RRHH: {', '.join(job_description_output.palabras_clave_seo_rrhh)}")