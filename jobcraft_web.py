import os
import streamlit as st 
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
# 2. FUNCIÓN PRINCIPAL DEL AGENTE (Función limpia)
# =========================================================

def run_jobcraft_ai(api_key: str, title: str, level: str, critical_skill: str):
    """Función que ejecuta el Agente JobCraft AI y devuelve el JSON."""
    
    try:
        # El cliente ahora usa la clave que le pasa la interfaz web
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return f"Error de conexión: No se pudo conectar a Gemini. {e}", None

    # --- El Prompt Maestro ---
    prompt = f"""
    Eres el Agente de Diseño de Puestos de Trabajo Inteligente (JobCraft AI). 
    Tu objetivo es generar una descripción de puesto completa, atractiva y estructurada 
    para el sector de Recursos Humanos. El resultado debe ser 100% libre de sesgos.
    
    **ENTRADAS DEL USUARIO:**
    1.  Título del Puesto: {title}
    2.  Nivel Requerido: {level}
    3.  Habilidad Crítica de Enfoque: {critical_skill}
    
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
        return f"Error al generar contenido (Clave inválida o límite excedido): {e}", None

# =========================================================
# 3. INTERFAZ WEB CON STREAMLIT (Con validación de Clave)
# =========================================================

st.set_page_config(page_title="JobCraft AI - Generador Web de Puestos", layout="wide")

st.title("✨ JobCraft AI - Generador Web de Puestos")
st.markdown("Crea descripciones de trabajo optimizadas para RR. HH. al instante, impulsado por Gemini.")

# --- BARRA LATERAL PARA LA CLAVE ---
# La clave se obtiene del usuario, NO está codificada en el código
api_key = st.sidebar.text_input("🔑 Ingresa tu API Key de Gemini", type="password", help="Necesaria para pagar el uso del modelo de IA.")

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

# --- Lógica de Procesamiento y Validación ---
if submitted:
    
    # 🚨 Validar la clave API antes de hacer cualquier cosa
    if not api_key or not api_key.startswith("AIza"):
        st.error("🚨 ERROR: Por favor, ingresa una API Key válida de Google Gemini en la barra lateral para continuar.")
        
    else:
        # Mostrar Spinner mientras procesa
        with st.spinner('Procesando solicitud con Gemini... ⏳'):
            
            # Llamar a la función principal con la clave proporcionada por el usuario
            error, result_json_text = run_jobcraft_ai(
                api_key, # Pasa la clave de la barra lateral
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