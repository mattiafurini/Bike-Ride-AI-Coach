import csv
import sys
from fitparse import FitFile

def converti_fit_in_csv(input_fit, output_csv):
    print(f"Lettura del file {input_fit} in corso...")
    try:
        fitfile = FitFile(input_fit)
    except Exception as e:
        print(f"Errore durante l'apertura del file FIT: {e}")
        return

    # Estraiamo solo i messaggi di tipo 'record' (i punti traccia del GPS/Sensori)
    records = []
    for record in fitfile.get_messages('record'):
        record_data = {}
        for data in record:
            # Salviamo il nome del campo e il suo valore
            record_data[data.name] = data.value
        records.append(record_data)

    if not records:
        print("Nessun dato di tracciamento trovato in questo file.")
        return

    # Raccogliamo tutti i nomi delle colonne possibili trovati nei record
    colonne = set()
    for record in records:
        colonne.update(record.keys())
    colonne = sorted(list(colonne))

    # Creiamo il file CSV
    print(f"Scrittura dei dati su {output_csv}...")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=colonne)
        writer.writeheader()
        for record in records:
            writer.writerow(record)
            
    print(f"Finito! File salvato come {output_csv}")

if __name__ == '__main__':
    # Controlla se l'utente ha inserito i nomi dei file da terminale
    if len(sys.argv) < 3:
        print("Uso corretto: python fit_to_csv.py <file_input.fit> <file_output.csv>")
        print("Esempio: python fit_to_csv.py Morning_Ride-6.fit allenamento_6.csv")
    else:
        converti_fit_in_csv(sys.argv[1], sys.argv[2])