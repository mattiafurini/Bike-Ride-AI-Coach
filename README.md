# 🚴‍♂️ Bike Stats Dashboard & AI Coach

A powerful, interactive web application to visualize, analyze, and compare your cycling performance data. Upload your `.fit` files directly from your Garmin/Wahoo device, view beautiful charts of your metrics, and get professional advice from an integrated AI Cycling Coach.

## ✨ Features

- **.FIT to CSV Conversion**: Automatically parses complex binary `.fit` files into readable `.csv` formats.
- **Interactive Map**: Visualizes your GPS track using Leaflet.
- **Performance Charts**: Dynamic charts for Elevation, Speed, Heart Rate, and Cadence using Chart.js.
- **Monthly Ride Organizer**: Automatically groups and sorts your past rides by month.
- **🤖 AI Coach (BYOK)**: Compare an unlimited number of rides and chat with a virtual cycling coach powered by Google Gemini AI.

## 🚀 Getting Started

### Prerequisites

You need Python 3 installed on your machine.

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/bike-stats-dashboard.git
   cd bike-stats-dashboard
   ```

2. **Create a virtual environment (Recommended)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

1. Start the Flask local server:
   ```bash
   flask run
   ```
2. Open your browser and navigate to: `http://127.0.0.1:5000`

## 🤖 How to use the AI Coach

To keep the application free and secure, the AI Coach uses a **"Bring Your Own Key" (BYOK)** architecture. The app requires a Google Gemini API Key.

1. Go to [Google AI Studio](https://aistudio.google.com/) and create a free API Key.
2. Open the Bike Stats Dashboard web app.
3. Click the **⚙️ Settings icon** in the top right corner.
4. Paste your API Key and click **Save**.
   > *Note: Your key is stored safely in your browser's local storage and is never uploaded anywhere.*
5. Click **Compare Rides (VS)**, select multiple rides, and click the blue "Start Analysis" button to start chatting with your AI Coach!

## 📁 Project Structure

- `app.py`: The main Flask backend.
- `fit_to_csv.py`: Utility script that uses `fitparse` to decode Garmin files.
- `fit/`: Directory where uploaded `.fit` files are stored.
- `csv/`: Directory where converted `.csv` files are saved.
- `templates/`: HTML templates (contains `index.html`).
- `static/`: Frontend assets (`css/style.css`, `js/app.js`).

## 🛡️ Privacy & Security

This app is designed to run entirely locally. Your `.fit` files containing GPS and biometric data never leave your computer. The only data transmitted over the internet is the downsampled telemetry sent to Google's Gemini API during a Coach Analysis.

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
