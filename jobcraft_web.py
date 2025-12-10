import os
import streamlit as st # <-- Importamos Streamlit
import json
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

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
# 2. FUNCIÓN PRINCIPAL DEL AGENTE (SIMPLIFICADA PARA WEB)
# =========================================================

# **¡IMPORTANTE! PEGA TU CLAVE API DE GEMINI AQUÍ:**
MY_GEMINI_API_KEY = "AIzaSyAXPGgR5vposP7z-pIkyR89s0ksd27yk8o" 

def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str):
    """Función que ejecuta el Agente JobCraft AI y devuelve el JSON."""

    os.environ['GEMINI_API_KEY'] = api_key
    
    try:
        client = genai.Client()
    except Exception as e:
        return f"Error: No se pudo conectar a Gemini. Asegúrate de que la clave API es correcta. Error: {e}", None

    # --- El Prompt Maestro ---
    prompt = f"""
    Eres el Agente de Diseño de Puestos de Trabajo Inteligente (JobCraft AI). 
    Tu objetivo es generar una descripción de puesto completa, atractiva y estructurada 
    para el sector de Recursos Humanos. El resultado debe ser 100% libre de sesgos.
    
    **ENTRADAS DEL USUARIO:**
    1.  Título del Puesto: {title}
    2.  Nivel Requerido: {level}
    3.  Habilidad Crítica de Enfoque: {critical_skill}
    
    **REGLA DE SALIDA VITAL:** DEBES devolver la respuesta únicamente en el formato JSON que te indico, SIN añadir ningún texto explicativo o introducción.
    """

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=JobDescription,
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config
        )
        # Devolver el JSON directamente
        return None, response.text
        
    except Exception as e:
        return f"Error al generar contenido: {e}", None

# =========================================================
# 3. INTERFAZ WEB CON STREAMLIT
# =========================================================

st.set_page_config(page_title="JobCraft AI - Generador Web de Puestos", layout="wide")

st.title("✨ JobCraft AI - Generador Web de Puestos")
st.markdown("Crea descripciones de trabajo optimizadas para RR. HH. al instante, impulsado por Gemini.")

# --- Formulario de Entrada ---
with st.form("job_form"):
    st.header("1. Define el Puesto")
    
    # Campo 1: Título
    title_input = st.text_input(
        "Título del Puesto",
        value="Analista de Experiencia del Empleado",
        help="El título exacto que se usará para la publicación."
    )
    
    # Campo 2: Nivel (Dropdown Select Box)
    level_input = st.selectbox(
        "Nivel de Experiencia",
        options=["Junior", "Intermedio", "Senior", "Manager", "Director"],
        index=2, # Valor preseleccionado: Senior
        help="Nivel de responsabilidad y experiencia requerido."
    )
    
    # Campo 3: Habilidad Crítica
    skill_input = st.text_area(
        "Habilidad Crítica o Foco Estratégico",
        value="Uso de IA para personalizar planes de carrera y monitorear el bienestar emocional del equipo.",
        help="Una habilidad o tema que debe ser enfatizado en las responsabilidades clave."
    )
    
    # Botón de envío
    submitted = st.form_submit_button("🚀 Generar Descripción con IA")

# --- Lógica de Procesamiento ---
if submitted:
    if MY_GEMINI_API_KEY == "PEGA_TU_CLAVE_AQUI_A_PARTIR_DE_AIza...":
        st.error("🚨 ERROR DE CONFIGURACIÓN: Por favor, pega tu Clave API de Gemini en la línea 56 del código.")
    else:
        # Mostrar Spinner mientras procesa
        with st.spinner('Procesando solicitud con Gemini... ⏳'):
            error, result_json_text = run_jobcraft_ai(
                MY_GEMINI_API_KEY, 
                title_input, 
                level_input, 
                skill_input
            )
        
        # Manejo del resultado
        if error:
            st.error(f"❌ Error al ejecutar JobCraft AI: {error}")
        
        elif result_json_text:
            st.success("✅ Descripción Generada con Éxito")
            
            try:
                # Convertir el JSON de vuelta a un objeto Python para mostrarlo bonito
                data_dict = json.loads(result_json_text)
                
                # --- VISUALIZACIÓN EN LA WEB ---
                
                # 1. Mostrar el resultado de forma organizada
                st.subheader(data_dict.get('titulo_puesto', 'Puesto Generado'))
                
                st.markdown("**Resumen del Puesto:**")
                st.info(data_dict.get('resumen_puesto', 'N/A'))
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Nivel:**")
                    st.write(data_dict.get('nivel', 'N/A'))
                    st.markdown("**Palabras Clave SEO:**")
                    st.code(', '.join(data_dict.get('palabras_clave_seo_rrhh', [])))

                with col2:
                    st.markdown("**Responsabilidades Clave:**")
                    for resp in data_dict.get('responsabilidades_clave', []):
                        st.markdown(f"- {resp}")
                    
                    st.markdown("**Requisitos Mínimos:**")
                    for req in data_dict.get('requisitos_minimos', []):
                        st.markdown(f"- {req}")

                st.markdown("---")
                st.caption("Salida JSON Cruda (para copiar y pegar):")
                st.json(data_dict) # Mostrar el JSON crudo en un formato plegable

            except json.JSONDecodeError:
                st.error("❌ Error: La salida del modelo no fue un JSON válido.")
                st.code(result_json_text)
        else:
            st.error("No se recibió respuesta del modelo.")