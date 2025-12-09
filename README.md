# SplitBill-Bayar-Bareng-Hutang-Bersama-
# Kantingo SplitBill (Streamlit)

Aplikasi SplitBill sederhana untuk menghitung pembagian tagihan dan settlement.

## Cara jalankan
1. Buat virtualenv (opsional)
2. pip install -r requirements.txt
3. streamlit run app.py
4. Buka browser di alamat yang disediakan Streamlit.

## Fitur
- Buat event, tambah peserta, tambah pengeluaran (equal / custom shares)
- Hitung saldo per orang
- Generate settlement plan (siapa harus bayar siapa)
- Export CSV expenses & settlements

Catatan: data disimpan hanya selama sesi Streamlit (paket session_state). Untuk persistent storage, bisa ditambahkan SQLite atau Google Sheets.
