import os
import glob
import sqlite3
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, render_template
from werkzeug.utils import secure_filename
from fit_to_csv import converti_fit_in_csv
from openai import OpenAI

app = Flask(__name__)

def get_client_config(provider, api_key):
    if provider == 'gemini':
        client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=api_key
        )
        return client, "gemini-3.5-flash", "text-embedding-004"
    else:
        client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=api_key,
        )
        return client, "gpt-4o", "text-embedding-3-small"


# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'fit')
app.config['CSV_FOLDER'] = os.path.join(os.path.dirname(__file__), 'csv')
app.config['NOTES_FILE'] = os.path.join(os.path.dirname(__file__), 'coach_notes.txt')
app.config['DB_FILE'] = os.path.join(os.path.dirname(__file__), 'embeddings.db')
app.config['TEMPLATES_AUTO_RELOAD'] = True

COACH_SYSTEM_INSTRUCTION = """Sei un preparatore atletico professionista esperto di ciclismo (cycling coach).
Il tuo obiettivo è analizzare i dati degli allenamenti e fornire consigli utili.
Mantieni un tono analitico, fai finta di essere un umano che parla direttamente al suo atleta e non uscire mai dal tuo personaggio di cycling coach.

**Profilo dell'Atleta:**
- Altezza: 1.78 m
- Peso: 70 kg
- Frequenza Cardiaca: Max 195 bpm, Riposo 40 bpm
- Setup Bici: Corone 50-34, Pignone 11-30

INSTRUZIONE IMPORTANTE SUL FORMATO DI RISPOSTA:
DEVI rispondere SOLO e UNICAMENTE con un oggetto JSON valido. Non usare blocchi markdown (come ```json) attorno alla tua risposta.
L'oggetto JSON deve avere ESATTAMENTE la seguente struttura:
{
  "response": "La tua risposta formattata in markdown da mostrare all'atleta.",
  "notes": "Un riassunto aggiornato per il tuo taccuino (debolezze, progressi, compiti in terza persona). Se non c'è nulla da aggiornare o è il primo messaggio, restituisci una stringa vuota o gli appunti attuali."
}"""

def init_db():
    conn = sqlite3.connect(app.config['DB_FILE'])
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rides_embeddings (
            filename TEXT PRIMARY KEY,
            summary TEXT,
            embedding BLOB
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_summary(path):
    full_path = os.path.join(app.config['CSV_FOLDER'], path)
    if not os.path.exists(full_path):
        return f"No data for {path}"
        
    df = pd.read_csv(full_path)
    if df.empty or 'timestamp' not in df.columns:
        return f"No data for {path}"
        
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    duration_sec = (df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]).total_seconds()
    
    dist = df['distance'].max() / 1000 if 'distance' in df.columns else 0
    
    speed_col = 'enhanced_speed' if 'enhanced_speed' in df.columns else 'speed' if 'speed' in df.columns else None
    moving_mask = (df[speed_col] * 3.6 > 2) if speed_col else pd.Series(True, index=df.index)
    moving_time_sec = moving_mask.sum()
    
    avg_speed = df.loc[moving_mask, speed_col].mean() * 3.6 if speed_col and moving_mask.any() else 0
    max_speed = df[speed_col].max() * 3.6 if speed_col else 0
    
    avg_hr = df['heart_rate'].mean() if 'heart_rate' in df.columns else 0
    
    cadence_mask = (df['cadence'] > 0) if 'cadence' in df.columns else pd.Series(False, index=df.index)
    avg_cad = df.loc[cadence_mask, 'cadence'].mean() if 'cadence' in df.columns and cadence_mask.any() else 0
    
    elevation = 0
    alt_col = 'enhanced_altitude' if 'enhanced_altitude' in df.columns else 'altitude' if 'altitude' in df.columns else None
    if alt_col:
        diffs = df[alt_col].diff()
        elevation = diffs[diffs > 0].sum()
        
    zones = {"Z1": 0, "Z2": 0, "Z3": 0, "Z4": 0, "Z5": 0}
    if 'heart_rate' in df.columns:
        hr = df['heart_rate'].dropna()
        zones["Z1"] = len(hr[hr < 133]) // 60
        zones["Z2"] = len(hr[(hr >= 133) & (hr < 148)]) // 60
        zones["Z3"] = len(hr[(hr >= 148) & (hr < 164)]) // 60
        zones["Z4"] = len(hr[(hr >= 164) & (hr < 179)]) // 60
        zones["Z5"] = len(hr[hr >= 179]) // 60
        
    cad_zones = {"Z1": 0, "Z2": 0, "Z3": 0, "Z4": 0}
    if 'cadence' in df.columns:
        cad = df['cadence'].dropna()
        cad = cad[cad > 0] # exclude coasting
        cad_zones["Z1"] = len(cad[cad < 70]) // 60
        cad_zones["Z2"] = len(cad[(cad >= 70) & (cad < 85)]) // 60
        cad_zones["Z3"] = len(cad[(cad >= 85) & (cad < 100)]) // 60
        cad_zones["Z4"] = len(cad[cad >= 100]) // 60
    
    return f"""
### Allenamento: {path}
**Statistiche Riassuntive (In movimento):**
- Distanza: {dist:.2f} km
- Dislivello Positivo: {elevation:.0f} m
- Tempo Totale: {int(duration_sec // 60)} min
- Tempo in Movimento: {int(moving_time_sec // 60)} min
- Velocità Media: {avg_speed:.1f} km/h (Max: {max_speed:.1f} km/h)
- Battito Medio: {avg_hr:.0f} bpm
- Cadenza Media: {avg_cad:.0f} rpm

**Tempo nelle Zone Cardio (Formula di Karvonen):**
- Z1 (Recupero, <133 bpm): {zones['Z1']} min
- Z2 (Fondo, 133-148 bpm): {zones['Z2']} min
- Z3 (Ritmo, 148-164 bpm): {zones['Z3']} min
- Z4 (Soglia, 164-179 bpm): {zones['Z4']} min
- Z5 (VO2 Max, >179 bpm): {zones['Z5']} min

**Distribuzione della Cadenza (escluso ruota libera):**
- Bassa (< 70 rpm, salita dura o rapporto lungo): {cad_zones['Z1']} min
- Media (70-85 rpm, ritmo di fondo): {cad_zones['Z2']} min
- Ottimale (85-100 rpm, alta agilità): {cad_zones['Z3']} min
- Alta (> 100 rpm, fuorigiri o sprint): {cad_zones['Z4']} min
"""

def ensure_embeddings(provider, api_key):
    """
    Scans the CSV_FOLDER for files.
    If a file is not in SQLite, generates its summary and embedding, and saves it.
    """
    client, _, embed_model = get_client_config(provider, api_key)
    conn = sqlite3.connect(app.config['DB_FILE'])
    cursor = conn.cursor()
    
    # Get all existing files from DB
    cursor.execute("SELECT filename FROM rides_embeddings")
    existing_files = {row[0] for row in cursor.fetchall()}
    
    # Find all current CSVs
    current_files = []
    for root, dirs, files in os.walk(app.config['CSV_FOLDER']):
        for file in files:
            if file.endswith('.csv'):
                rel_path = os.path.relpath(os.path.join(root, file), app.config['CSV_FOLDER'])
                current_files.append(rel_path)
                
    for path in current_files:
        if path not in existing_files:
            summary = get_summary(path)
            # Fetch embedding from OpenAI (GitHub Models)
            try:
                result = client.embeddings.create(
                    model=embed_model,
                    input=summary
                )
                embedding = result.data[0].embedding # List of floats
                # Convert to numpy array and serialize
                emb_array = np.array(embedding, dtype=np.float32)
                emb_blob = emb_array.tobytes()
                
                cursor.execute(
                    "INSERT INTO rides_embeddings (filename, summary, embedding) VALUES (?, ?, ?)",
                    (path, summary, emb_blob)
                )
            except Exception as e:
                print(f"Failed to embed {path}: {e}")
                
    conn.commit()
    conn.close()

def search_similar_rides(query, provider, api_key, top_k=3):
    client, _, embed_model = get_client_config(provider, api_key)
    
    # Embed query
    try:
        result = client.embeddings.create(
            model=embed_model,
            input=query
        )
        query_emb = np.array(result.data[0].embedding, dtype=np.float32)
    except Exception as e:
        print(f"Error embedding query: {e}")
        return []

    conn = sqlite3.connect(app.config['DB_FILE'])
    cursor = conn.cursor()
    cursor.execute("SELECT filename, summary, embedding FROM rides_embeddings")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return []
        
    scored_rides = []
    query_norm = np.linalg.norm(query_emb)
    
    for row in rows:
        filename, summary, emb_blob = row
        ride_emb = np.frombuffer(emb_blob, dtype=np.float32)
        ride_norm = np.linalg.norm(ride_emb)
        if ride_norm == 0 or query_norm == 0:
            sim = 0
        else:
            sim = np.dot(query_emb, ride_emb) / (query_norm * ride_norm)
        scored_rides.append((sim, filename, summary))
        
    scored_rides.sort(key=lambda x: x[0], reverse=True)
    return scored_rides[:top_k]

@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 0 seconds.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CSV_FOLDER'], exist_ok=True)

def semicircles_to_degrees(semicircles):
    if pd.isna(semicircles):
        return None
    return semicircles * (180.0 / (2**31))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/rides')
def list_rides():
    # Find all CSV files in the csv directory
    csv_files = []
    for root, dirs, files in os.walk(app.config['CSV_FOLDER']):
        for file in files:
            if file.endswith('.csv'):
                # Get path relative to the CSV_FOLDER
                rel_path = os.path.relpath(os.path.join(root, file), app.config['CSV_FOLDER'])
                csv_files.append(rel_path)
    # Sort files (e.g. by name/date)
    csv_files.sort(reverse=True)
    return jsonify(csv_files)

@app.route('/api/rides/<path:filename>')
def get_ride(filename):
    file_path = os.path.join(app.config['CSV_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
        
    try:
        df = pd.read_csv(file_path)
        
        # Convert coordinates if present
        if 'position_lat' in df.columns:
            df['lat'] = df['position_lat'].apply(semicircles_to_degrees)
        if 'position_long' in df.columns:
            df['lng'] = df['position_long'].apply(semicircles_to_degrees)
            
        from flask import Response
        return Response(df.to_json(orient='records'), mimetype='application/json')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return jsonify({"error": "No file part"}), 400
        
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({"error": "No selected files"}), 400
        
    successes = []
    errors = []
    
    for file in files:
        if file and file.filename.endswith('.fit'):
            # Save fit file temporarily
            temp_fit = os.path.join(app.config['UPLOAD_FOLDER'], "temp.fit")
            temp_csv = os.path.join(app.config['CSV_FOLDER'], "temp.csv")
            file.save(temp_fit)
            
            try:
                converti_fit_in_csv(temp_fit, temp_csv)
                if not os.path.exists(temp_csv):
                    errors.append(f"{file.filename}: Failed to convert or no tracking records found.")
                    continue
                    
                # Read first row to get date
                df = pd.read_csv(temp_csv, nrows=1)
                if 'timestamp' in df.columns and not df.empty:
                    first_timestamp = df['timestamp'].iloc[0]
                    dt = pd.to_datetime(first_timestamp)
                    month_folder = dt.strftime('%Y-%m')
                    base_filename = dt.strftime('%Y-%m-%d')
                else:
                    month_folder = "unknown"
                    base_filename = secure_filename(file.filename).replace('.fit', '')
                    
                # Create month folders
                csv_month_dir = os.path.join(app.config['CSV_FOLDER'], month_folder)
                fit_month_dir = os.path.join(app.config['UPLOAD_FOLDER'], month_folder)
                os.makedirs(csv_month_dir, exist_ok=True)
                os.makedirs(fit_month_dir, exist_ok=True)
                
                # Handle duplicates
                counter = 0
                new_filename = base_filename
                final_csv_path = os.path.join(csv_month_dir, new_filename + '.csv')
                
                while os.path.exists(final_csv_path):
                    counter += 1
                    new_filename = f"{base_filename} ({counter})"
                    final_csv_path = os.path.join(csv_month_dir, new_filename + '.csv')
                    
                final_fit_path = os.path.join(fit_month_dir, new_filename + '.fit')
                
                import shutil
                shutil.move(temp_csv, final_csv_path)
                shutil.move(temp_fit, final_fit_path)
                
                rel_path = f"{month_folder}/{new_filename}.csv"
                successes.append(rel_path)
            except Exception as e:
                errors.append(f"{file.filename}: {str(e)}")
        else:
            errors.append(f"{file.filename}: Invalid file format")

    return jsonify({
        "success": len(successes) > 0,
        "files_uploaded": successes,
        "errors": errors
    })

@app.route('/api/compare', methods=['POST'])
def compare_rides():
    data = request.json
    rides = data.get('rides', [])
    api_key = data.get('api_key')
    provider = data.get('provider', 'github')
    
    if not api_key:
        return jsonify({'error': 'API Key mancante. Configurala nelle impostazioni.'}), 401
        
    if len(rides) < 2:
        return jsonify({'error': 'At least two rides required'}), 400
        
    client, chat_model, _ = get_client_config(provider, api_key)
        
    try:
        # Utilizza la funzione get_summary definita globalmente

        summaries = [get_summary(r) for r in rides]
        all_summaries = "\n\n".join(summaries)
            
        prompt = f"""Analizza i dati riassuntivi e campionati di questi {len(rides)} allenamenti e fornisci un confronto dettagliato.\n\n"""
        if os.path.exists(app.config['NOTES_FILE']):
            with open(app.config['NOTES_FILE'], 'r', encoding='utf-8') as f:
                notes = f.read().strip()
                if notes:
                    prompt += f"\n**I TUOI APPUNTI PRECEDENTI SULL'ATLETA:**\n{notes}\n\n"
                    
        prompt += f"""Evidenzia:
1. I miglioramenti o le differenze nella velocità media e massima tra le sessioni.
2. L'efficienza cardiaca (rapporto velocità/battito cardiaco) considerando i bpm dell'atleta.
3. La costanza della cadenza (pedalate al minuto) tenendo conto dei rapporti (50-34 e 11-30).
4. Fornisci un consiglio finale per migliorare.

{all_summaries}
"""
        response = client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": COACH_SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        text = response.choices[0].message.content
        print(f"📊 [COMPARE] Token usati -> Prompt: {response.usage.prompt_tokens} | Risposta: {response.usage.completion_tokens} | Totale: {response.usage.total_tokens}")
        
        import json
        try:
            data = json.loads(text)
            analysis = data.get("response", "Errore nel parsing della risposta.")
            new_notes = data.get("notes", "")
            
            if new_notes.strip():
                with open(app.config['NOTES_FILE'], 'w', encoding='utf-8') as f:
                    f.write(new_notes.strip())
        except json.JSONDecodeError:
            analysis = text
            
        return jsonify({'analysis': analysis, 'prompt': prompt})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    history = data.get('history', [])
    api_key = data.get('api_key')
    provider = data.get('provider', 'github')
    
    if not api_key:
        return jsonify({'error': 'API Key mancante. Configurala nelle impostazioni.'}), 401
        
    if not history:
        return jsonify({'error': 'History required'}), 400
        
    client, chat_model, _ = get_client_config(provider, api_key)
        
    try:
        messages = [
            {"role": "system", "content": COACH_SYSTEM_INSTRUCTION}
        ]
        
        for msg in history[:-1]:
            content = msg['content']
            if msg['role'] == "assistant":
                import json
                content = json.dumps({"response": content, "notes": ""})
            messages.append({"role": msg['role'], "content": content})
            
        ensure_embeddings(provider, api_key)
        
        last_msg = history[-1]['content']
        
        # Recupera il contesto RAG pertinente rispetto all'ultimo messaggio
        prompt_lower = last_msg.lower()
        rag_context = ""
        
        if "ultim" in prompt_lower or "recent" in prompt_lower:
            # Ordina per filename (che inizia con YYYY-MM-DD) decrescente
            conn = sqlite3.connect(app.config['DB_FILE'])
            cursor = conn.cursor()
            cursor.execute("SELECT summary FROM rides_embeddings ORDER BY filename DESC LIMIT 3")
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                rag_context = "\n\n**CONTESTO FORNITO (ULTIMI ALLENAMENTI IN ORDINE CRONOLOGICO):**\n"
                for row in rows:
                    rag_context += row[0] + "\n"
        else:
            similar_rides = search_similar_rides(last_msg, provider, api_key, top_k=3)
            if similar_rides:
                rag_context = "\n\n**CONTESTO RECUPERATO DAL DATABASE ALLENAMENTI (RAG):**\n"
                rag_context += "Usa i dati sottostanti se pertinenti per rispondere alla domanda.\n"
                for score, filename, summary in similar_rides:
                    rag_context += summary + "\n"
        
        last_msg_with_context = last_msg + rag_context
        messages.append({"role": "user", "content": last_msg_with_context})
        
        response = client.chat.completions.create(
            model=chat_model,
            messages=messages,
            response_format={ "type": "json_object" }
        )
        text = response.choices[0].message.content
        print(f"📊 [CHAT] Token usati -> Prompt: {response.usage.prompt_tokens} | Risposta: {response.usage.completion_tokens} | Totale: {response.usage.total_tokens}")
        
        import json
        try:
            data = json.loads(text)
            reply = data.get("response", "Errore nel parsing della risposta.")
            new_notes = data.get("notes", "")
            
            if new_notes.strip():
                with open(app.config['NOTES_FILE'], 'w', encoding='utf-8') as f:
                    f.write(new_notes.strip())
        except json.JSONDecodeError:
            reply = text
            
        return jsonify({'reply': reply})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/notes', methods=['GET'])
def get_notes():
    if os.path.exists(app.config['NOTES_FILE']):
        with open(app.config['NOTES_FILE'], 'r', encoding='utf-8') as f:
            return jsonify({'notes': f.read().strip()})
    return jsonify({'notes': 'Il taccuino è vuoto. Fai un\'analisi e salva gli appunti!'})

@app.route('/api/notes/update', methods=['POST'])
def update_notes():
    data = request.json
    history = data.get('history', [])
    api_key = data.get('api_key')
    provider = data.get('provider', 'github')
    
    if not api_key:
        return jsonify({'error': 'API Key mancante.'}), 401
        
    if not history:
        return jsonify({'error': 'Nessuna cronologia trovata per fare il riassunto.'}), 400
        
    client, chat_model, _ = get_client_config(provider, api_key)
    
    existing_notes = ""
    if os.path.exists(app.config['NOTES_FILE']):
        with open(app.config['NOTES_FILE'], 'r', encoding='utf-8') as f:
            existing_notes = f.read().strip()
            
    prompt = "Di seguito c'è la cronologia della tua ultima conversazione con l'atleta.\n"
    if existing_notes:
        prompt += f"\nQUESTI ERANO I TUOI APPUNTI PRECEDENTI:\n{existing_notes}\n"
        
    prompt += "\nCRONOLOGIA DELLA CHAT RECENTE:\n"
    for msg in history:
        role = "Atleta" if msg['role'] == "user" else "Coach"
        prompt += f"{role}: {msg['content']}\n"
        
    prompt += "\nCOMPITO:\nScrivi un riassunto concentrato (massimo 150 parole) che diventerà il tuo NUOVO taccuino ufficiale su questo atleta. Devi includere: 1) Le sue debolezze attuali. 2) I progressi fatti. 3) I compiti/esercizi specifici che gli hai assegnato per i prossimi allenamenti. Parla in terza persona (es. 'L'atleta deve...'). Formatta in modo pulito e coinciso."
    
    try:
        response = client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": "Sei un Coach di ciclismo. Il tuo unico scopo è prendere la cronologia di chat fornita e restituire un riassunto concentrato degli appunti sull'atleta. Mantieni il tuo ruolo professionale."},
                {"role": "user", "content": prompt}
            ]
        )
        new_notes = response.choices[0].message.content.strip()
        print(f"📊 [APPUNTI] Token usati -> Prompt: {response.usage.prompt_tokens} | Risposta: {response.usage.completion_tokens} | Totale: {response.usage.total_tokens}")
        
        with open(app.config['NOTES_FILE'], 'w', encoding='utf-8') as f:
            f.write(new_notes)
            
        return jsonify({'success': True, 'notes': new_notes})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
