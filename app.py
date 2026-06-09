import os
import glob
import pandas as pd
from flask import Flask, jsonify, request, render_template
from werkzeug.utils import secure_filename
from fit_to_csv import converti_fit_in_csv
import google.generativeai as genai

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'fit')
app.config['CSV_FOLDER'] = os.path.join(os.path.dirname(__file__), 'csv')
app.config['NOTES_FILE'] = os.path.join(os.path.dirname(__file__), 'coach_notes.txt')
app.config['TEMPLATES_AUTO_RELOAD'] = True

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
    
    if not api_key:
        return jsonify({'error': 'API Key mancante. Configurala nelle impostazioni.'}), 401
        
    if len(rides) < 2:
        return jsonify({'error': 'At least two rides required'}), 400
        
    genai.configure(api_key=api_key)
        
    try:
        def get_summary(path):
            full_path = os.path.join(app.config['CSV_FOLDER'], path)
            df = pd.read_csv(full_path)
            if df.empty or 'timestamp' not in df.columns:
                return f"No data for {path}"
                
            duration = len(df)
            dist = df['distance'].max() / 1000 if 'distance' in df.columns else 0
            
            speed_col = 'enhanced_speed' if 'enhanced_speed' in df.columns else 'speed' if 'speed' in df.columns else None
            avg_speed = df[speed_col].mean() * 3.6 if speed_col else 0
            max_speed = df[speed_col].max() * 3.6 if speed_col else 0
            
            avg_hr = df['heart_rate'].mean() if 'heart_rate' in df.columns else 0
            avg_cad = df['cadence'].mean() if 'cadence' in df.columns else 0
            
            downsampled = df.iloc[::60].copy()
            cols_to_keep = [c for c in ['timestamp', 'distance', speed_col, 'heart_rate', 'cadence', 'enhanced_altitude'] if c and c in downsampled.columns]
            csv_snippet = downsampled[cols_to_keep].to_csv(index=False)
            
            return f"""
### Allenamento: {path}
**Statistiche Riassuntive:**
- Distanza: {dist:.2f} km
- Durata: {duration // 60} minuti
- Velocità Media: {avg_speed:.1f} km/h (Max: {max_speed:.1f} km/h)
- Battito Medio: {avg_hr:.0f} bpm
- Cadenza Media: {avg_cad:.0f} rpm

**Dati Campionati (1 misurazione al minuto per vedere l'andamento nel tempo):**
{csv_snippet}
"""

        summaries = [get_summary(r) for r in rides]
        all_summaries = "\n\n".join(summaries)
            
        prompt = f"""
Sei un preparatore atletico professionista esperto di ciclismo (cycling coach). 
Analizza i dati riassuntivi e campionati di questi {len(rides)} allenamenti e fornisci un confronto dettagliato.

**Profilo dell'Atleta:**
- Altezza: 1.78 m
- Peso: 70 kg
- Frequenza Cardiaca: Max 195 bpm, Riposo 40 bpm
- Setup Bici: Corone 50-34, Pignone 11-30

"""
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

Mantieni un tono analitico. Usa elenchi puntati per rendere facile la lettura.
Rispondi in Markdown puro
INSTRUZIONE IMPORTANTE:
Alla fine della tua risposta, devi aggiungere una sezione separata che inizia esattamente con "### APPUNTI AGGIORNATI" (su una nuova riga).
Sotto questa intestazione, scrivi un riassunto concentrato (massimo 150 parole) che diventerà il tuo NUOVO taccuino ufficiale su questo atleta (sostituendo il precedente). Includi: 1) Le sue debolezze attuali. 2) I progressi fatti. 3) I compiti/esercizi specifici assegnati per i prossimi allenamenti. Parla in terza persona (es. 'L'atleta deve...'). Formatta in modo pulito e conciso. Questa sezione non sarà visibile all'atleta ma verrà salvata nel sistema.

{all_summaries}
"""
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        text = response.text
        
        analysis = text
        if "### APPUNTI AGGIORNATI" in text:
            parts = text.split("### APPUNTI AGGIORNATI")
            analysis = parts[0].strip()
            new_notes = parts[1].strip()
            with open(app.config['NOTES_FILE'], 'w', encoding='utf-8') as f:
                f.write(new_notes)
        
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
    
    if not api_key:
        return jsonify({'error': 'API Key mancante. Configurala nelle impostazioni.'}), 401
        
    if not history:
        return jsonify({'error': 'History required'}), 400
        
    genai.configure(api_key=api_key)
        
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        gemini_history = []
        for msg in history[:-1]:
            gemini_history.append({
                "role": "model" if msg['role'] == "assistant" else "user",
                "parts": [msg['content']]
            })
            
        chat_session = model.start_chat(history=gemini_history)
        
        last_msg = history[-1]['content']
        last_msg += "\n\n(Istruzione di sistema: rispondi all'atleta. Se durante questa risposta dai un consiglio o fai un'analisi importante, alla fine della tua risposta aggiungi esattamente '### APPUNTI AGGIORNATI' e di seguito un riassunto concentrato aggiornato per il tuo taccuino sull'atleta. Includi debolezze, progressi e compiti in terza persona. Se non è necessario aggiornare gli appunti, non inserire questa sezione.)"
        
        response = chat_session.send_message(last_msg)
        text = response.text
        
        reply = text
        if "### APPUNTI AGGIORNATI" in text:
            parts = text.split("### APPUNTI AGGIORNATI")
            reply = parts[0].strip()
            new_notes = parts[1].strip()
            with open(app.config['NOTES_FILE'], 'w', encoding='utf-8') as f:
                f.write(new_notes)
        
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
    
    if not api_key:
        return jsonify({'error': 'API Key mancante.'}), 401
        
    if not history:
        return jsonify({'error': 'Nessuna cronologia trovata per fare il riassunto.'}), 400
        
    genai.configure(api_key=api_key)
    
    existing_notes = ""
    if os.path.exists(app.config['NOTES_FILE']):
        with open(app.config['NOTES_FILE'], 'r', encoding='utf-8') as f:
            existing_notes = f.read().strip()
            
    prompt = "Sei un Coach di ciclismo. Di seguito c'è la cronologia della tua ultima conversazione con l'atleta.\n"
    if existing_notes:
        prompt += f"\nQUESTI ERANO I TUOI APPUNTI PRECEDENTI:\n{existing_notes}\n"
        
    prompt += "\nCRONOLOGIA DELLA CHAT RECENTE:\n"
    for msg in history:
        role = "Atleta" if msg['role'] == "user" else "Coach"
        prompt += f"{role}: {msg['content']}\n"
        
    prompt += "\nCOMPITO:\nScrivi un riassunto concentrato (massimo 150 parole) che diventerà il tuo NUOVO taccuino ufficiale su questo atleta. Devi includere: 1) Le sue debolezze attuali. 2) I progressi fatti. 3) I compiti/esercizi specifici che gli hai assegnato per i prossimi allenamenti. Parla in terza persona (es. 'L'atleta deve...'). Formatta in modo pulito e coinciso."
    
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(prompt)
        new_notes = response.text.strip()
        
        with open(app.config['NOTES_FILE'], 'w', encoding='utf-8') as f:
            f.write(new_notes)
            
        return jsonify({'success': True, 'notes': new_notes})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
