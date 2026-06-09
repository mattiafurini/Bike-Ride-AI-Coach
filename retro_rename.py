import os
import pandas as pd
import shutil

csv_dir = './csv'

def process():
    for root, dirs, files in os.walk(csv_dir, topdown=False):
        for file in files:
            if file.endswith('.csv'):
                old_path = os.path.join(root, file)
                try:
                    df = pd.read_csv(old_path, nrows=1)
                    if 'timestamp' in df.columns and not df.empty:
                        first_timestamp = df['timestamp'].iloc[0]
                        dt = pd.to_datetime(first_timestamp)
                        month_folder = dt.strftime('%Y-%m')
                        
                        base_filename = dt.strftime('%Y-%m-%d')
                        target_dir = os.path.join(csv_dir, month_folder)
                        os.makedirs(target_dir, exist_ok=True)
                        
                        # Handle duplicates
                        counter = 0
                        new_filename = f"{base_filename}.csv"
                        new_path = os.path.join(target_dir, new_filename)
                        
                        # Only increment if the existing file is NOT the file we are currently renaming
                        while os.path.exists(new_path) and old_path != new_path:
                            counter += 1
                            new_filename = f"{base_filename} ({counter}).csv"
                            new_path = os.path.join(target_dir, new_filename)
                        
                        if old_path != new_path:
                            print(f"Renaming {old_path} -> {new_path}")
                            shutil.move(old_path, new_path)
                except Exception as e:
                    print(f"Error processing {old_path}: {e}")
        
        # Clean up empty directories
        if not os.listdir(root):
            os.rmdir(root)

if __name__ == "__main__":
    process()
