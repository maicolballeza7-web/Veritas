import os
import requests
import sqlite3 # SQLite
from flask import Flask, render_template, request
from dotenv import load_dotenv
# AI assistance disclosure: used Gemini/DeepSeek during development for debugging
# HTTP status errors (401/404/503), endpoint formatting, JSON parsing, and prompt
# refinement for the binary VERDADERO/FALSO evaluator output.
# All application logic, SQLite schema, and routing written and understood by the author.

load_dotenv()
app = Flask(__name__)

# Función para conectar a la base de datos
def get_db():
    conn = sqlite3.connect("veritas.db")
    conn.row_factory = sqlite3.Row # Para que devuelva diccionarios
    return conn

@app.route("/", methods=["GET", "POST"])
def interfas():
    db = get_db()
    
    if request.method == "POST":
        texto_original = request.form.get("mensaje", "").strip()
        
        if len(texto_original) != 0:
            respuesta_generada = preguntar_a_la_ia(texto_original)
            veredicto = evalua_alucinaciones(texto_original, respuesta_generada)
            
            # Si hay un error en la API, que se vea en la pantalla
            if "Error" in veredicto:
                History = db.execute("SELECT * FROM users ORDER BY id DESC LIMIT 6").fetchall()
                return render_template("interfas.html", history=History, error=veredicto)
                
            # Buscamos la palabra VERDADERO dentro de la respuesta (por si viene con puntos o espacios)
            if "VERDADERO" in veredicto.upper():             
                # Cconsulta
                db.execute("INSERT INTO users (quest, answers) VALUES (?, ?)", (texto_original, respuesta_generada))
                db.commit() # Guardamos los cambios
                
                # Traemos el historial de la db
                History = db.execute("SELECT * FROM users ORDER BY id DESC LIMIT 6").fetchall()
                
                return render_template("interfas.html", history=History, pregunta=texto_original, respuesta=respuesta_generada, veredicto=veredicto)
            else:
                # Si es falso mostramos error
                History = db.execute("SELECT * FROM users ORDER BY id DESC LIMIT 6").fetchall()
                return render_template("interfas.html", history=History, error="Alucinación detectada. Intenta de nuevo.")
        else:
            History = db.execute("SELECT * FROM users ORDER BY id DESC LIMIT 6").fetchall()
            return render_template("interfas.html", history=History, error="Escribe algo válido")
            
    # Si es get traemos el historial y mostramos la página
    History = db.execute("SELECT * FROM users ORDER BY id DESC LIMIT 6").fetchall()
    return render_template("interfas.html", history=History)


def preguntar_a_la_ia(texto):
    api_key = os.getenv("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    datos = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "user", "content": f"Responde de forma clara, precisa y directa a lo siguiente: {texto}"}
        ]
    }
    
    try:
        respuesta = requests.post(url, headers=headers, json=datos)
        
        if respuesta.status_code != 200:
            print(f"DEBUG GROQ STATUS: {respuesta.status_code}")
            print(f"DEBUG GROQ TEXTO: {respuesta.text}")
            return f"Error en Groq: Código {respuesta.status_code}"
        print(f"DEBUG GROQ STATUS: {respuesta.json()}")    
        return respuesta.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Error en el generador: {e}"


def evalua_alucinaciones(texto_original, respuesta_generada):
    api_key = os.getenv("GEMINI_API_KEY")
    p1 = "generativelanguage"
    p2 = "googleapis.com"
    ruta = "v1beta/models/gemini-3.5-flash-lite:generateContent"
    url = f"https://{p1}.{p2}/{ruta}?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    prompt = f"Texto original: {texto_original}\n\nRespuesta generada: {respuesta_generada}\n\nextrae la información relevante y determina si la respuesta generada se basa en informacion veridica (VERDADERO) o es inventada (FALSO) y solo contesta con VERDADERO o FALSO, no agregues nada más."

    datos = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

  
    
    try:
        respuesta = requests.post(url, headers=headers, json=datos)
        
        if respuesta.status_code != 200:
            print(f"DEBUG STATUS: {respuesta.status_code}")
            print(f"DEBUG TEXTO: {respuesta.text}")
            return f"Error API: Código {respuesta.status_code}"
            
        veredicto = respuesta.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"DEBUG VEREDICTO: {veredicto}")
        return veredicto
        
    except Exception as e:
        print(f"DEBUG REAL - Fallo de conexión: {e}")
        return f"Error en el evaluador: {e}"