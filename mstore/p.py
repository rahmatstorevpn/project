from flask import Flask, request
import json, os
from datetime import datetime

app = Flask(__name__)

SAVE_DIR = "/root/notifications"  # folder penyimpanan
os.makedirs(SAVE_DIR, exist_ok=True)  # pastikan folder ada


@app.route('/notify', methods=['POST'])
def notify():
    try:
        # 🔹 Deteksi semua tipe konten
        content_type = request.headers.get('Content-Type', '').lower()
        data = None

        # ---- JSON ----
        if 'application/json' in content_type:
            data = request.get_json(silent=True)
        
        # ---- Form Data (x-www-form-urlencoded / multipart/form-data) ----
        if not data and ('form' in dir(request)) and (request.form or request.files):
            data = request.form.to_dict()
        
        # ---- Text / Raw body ----
        if not data:
            raw = request.data.decode('utf-8', errors='ignore').strip()
            # coba parse ke JSON jika mungkin
            try:
                data = json.loads(raw)
            except:
                data = {'raw': raw}

        # ---- Fallback ----
        if not data:
            data = {'message': 'Tidak ada data diterima'}

        # tampilkan di terminal
        print("🔔 Notifikasi diterima:", data)

        # buat nama file berdasarkan waktu
        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.json")
        filepath = os.path.join(SAVE_DIR, filename)

        # simpan ke file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        return "ok", 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return str(e), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
  
