# app.py
# Kantingo SplitBill — Aplikasi Bayar Bareng & Hutang Bersama (Streamlit)
# Cara pakai:
# 1) pip install -r requirements.txt
# 2) streamlit run app.py

import streamlit as st
import pandas as pd
import io
from datetime import datetime
from typing import List, Dict, Tuple

st.set_page_config(page_title="Kantingo SplitBill", page_icon="💸", layout="wide")

# -----------------------
# Helper: initialize state
# -----------------------
if "events" not in st.session_state:
    st.session_state.events = {}  # event_id -> {'name','created','participants':[], 'expenses':[]}
if "current_event" not in st.session_state:
    st.session_state.current_event = None

def new_event_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")

# -----------------------
# Business logic
# -----------------------
def add_event(name: str):
    eid = new_event_id()
    st.session_state.events[eid] = {
        "id": eid,
        "name": name,
        "created": datetime.now().isoformat(),
        "participants": [],  # list of {'name','email'(opt)}
        "expenses": []       # list of {'id','desc','amount','payer','participants':[names], 'shares':{name:share}, 'created'}
    }
    st.session_state.current_event = eid

def add_participant(event_id: str, name: str, email: str = ""):
    p = {"name": name.strip(), "email": email.strip()}
    # avoid duplicates by name
    names = [x["name"] for x in st.session_state.events[event_id]["participants"]]
    if p["name"] and p["name"] not in names:
        st.session_state.events[event_id]["participants"].append(p)
        return True
    return False

def add_expense(event_id: str, desc: str, amount: float, payer: str, participant_names: List[str], shares: Dict[str, float]):
    exp = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "desc": desc,
        "amount": float(amount),
        "payer": payer,
        "participants": participant_names.copy(),
        "shares": shares.copy(),
        "created": datetime.now().isoformat()
    }
    st.session_state.events[event_id]["expenses"].append(exp)

def compute_net_balances(event_id: str) -> Dict[str, float]:
    """
    Returns net balance per participant.
    Positive => other people owe this person (they paid more than their share)
    Negative => this person owes others.
    """
    participants = [p["name"] for p in st.session_state.events[event_id]["participants"]]
    balances = {name: 0.0 for name in participants}
    expenses = st.session_state.events[event_id]["expenses"]
    for e in expenses:
        total = float(e["amount"])
        payer = e["payer"]
        # ensure shares sum to total (if shares given)
        if e["shares"]:
            # shares are absolute amounts per participant
            for name, share in e["shares"].items():
                balances[name] -= float(share)  # they owe this share
            balances[payer] += total  # payer paid full amount
        else:
            # equal split among participants
            n = len(e["participants"])
            if n == 0:
                continue
            share = total / n
            for name in e["participants"]:
                balances[name] -= share
            balances[payer] += total
    # balances currently: payer has positive full amount, non-payers negative of their share.
    # Net should reflect what each person should receive (positive) or pay (negative).
    # Round small floating noise
    balances = {k: round(v, 2) for k,v in balances.items()}
    return balances

def compute_settlements(balances: Dict[str, float]) -> List[Tuple[str, str, float]]:
    """
    Greedy algorithm:
    - creditors: positive balances (to receive)
    - debtors: negative balances (owe)
    - match biggest creditor with biggest debtor until settled
    Returns list of (debtor, creditor, amount)
    """
    # prepare lists
    creditors = [(name, amt) for name, amt in balances.items() if amt > 0.005]
    debtors = [(name, -amt) for name, amt in balances.items() if amt < -0.005]  # store positive owed amounts

    # sort descending
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    settlements = []
    i = 0
    j = 0
    # convert to mutable lists
    creditors = [[name, amt] for name, amt in creditors]
    debtors = [[name, amt] for name, amt in debtors]

    while i < len(debtors) and j < len(creditors):
        debtor_name, debt_amt = debtors[i]
        creditor_name, cred_amt = creditors[j]
        pay = min(debt_amt, cred_amt)
        # record: debtor pays creditor
        settlements.append((debtor_name, creditor_name, round(pay, 2)))
        # reduce amounts
        debtors[i][1] = round(debt_amt - pay, 2)
        creditors[j][1] = round(cred_amt - pay, 2)
        # advance pointers if zero (tolerance)
        if abs(debtors[i][1]) < 0.01:
            i += 1
        if abs(creditors[j][1]) < 0.01:
            j += 1
    return settlements

# -----------------------
# UI: Sidebar - event / load / save
# -----------------------
st.sidebar.title("Kantingo SplitBill")
st.sidebar.markdown("Buat event baru atau pilih event yang sudah ada.")

with st.sidebar.form("create_event", clear_on_submit=True):
    new_name = st.text_input("Nama event (mis. 'Makan bareng 2025-12-09')", '')
    submitted = st.form_submit_button("➕ Buat Event")
    if submitted and new_name.strip():
        add_event(new_name.strip())
        st.experimental_rerun()

# event select
events = st.session_state.events
if events:
    ev_list = [(v["id"], v["name"]) for v in events.values()]
    # sort by created desc
    ev_list.sort(reverse=True)
    sel = st.sidebar.selectbox("Pilih Event", options=[(eid, name) for eid, name in ev_list], format_func=lambda x: events[x[0]]["name"] if isinstance(x, tuple) else events[x][ "name" ] )
    # to be safe handle format
    if isinstance(sel, tuple):
        selected_id = sel[0]
    else:
        selected_id = sel
    if st.sidebar.button("Pilih Event"):
        st.session_state.current_event = selected_id
        st.experimental_rerun()
else:
    st.sidebar.info("Belum ada event. Buat event baru di atas.")

# quick export all events (session)
if st.sidebar.button("Export semua event (CSV)"):
    # produce CSV of all expenses across events
    rows = []
    for eid, ev in st.session_state.events.items():
        for ex in ev["expenses"]:
            rows.append({
                "event_id": eid,
                "event_name": ev["name"],
                "expense_id": ex["id"],
                "desc": ex["desc"],
                "amount": ex["amount"],
                "payer": ex["payer"],
                "participants": ";".join(ex["participants"])
            })
    df_all = pd.DataFrame(rows)
    if df_all.empty:
        st.sidebar.warning("Tidak ada data untuk diexport.")
    else:
        buf = io.StringIO()
        df_all.to_csv(buf, index=False)
        st.sidebar.download_button("Download semua expenses (CSV)", data=buf.getvalue(), file_name="kantingo_all_expenses.csv", mime="text/csv")

# -----------------------
# Main area
# -----------------------
st.title("💸 Kantingo — SplitBill (Bayar Bareng & Hutang Bersama)")
st.write("Buat event, tambahkan peserta dan pengeluaran — aplikasi akan menghitung siapa berutang siapa.")

if st.session_state.current_event is None:
    st.info("Pilih event di sidebar atau buat event baru.")
    st.stop()

event = st.session_state.events[st.session_state.current_event]
st.header(f"Event: {event['name']}")

col1, col2 = st.columns([2,1])

# -----------------------
# Left: Participants & Expenses
# -----------------------
with col1:
    st.subheader("👥 Peserta")
    with st.form("add_participant", clear_on_submit=True):
        pname = st.text_input("Nama peserta")
        pemail = st.text_input("Email (opsional)")
        btnp = st.form_submit_button("Tambah peserta")
        if btnp:
            if pname.strip()=="":
                st.warning("Masukkan nama peserta.")
            else:
                ok = add_participant(event["id"], pname, pemail)
                if ok:
                    st.success(f"Peserta '{pname}' ditambahkan.")
                else:
                    st.warning("Nama peserta sudah ada atau kosong.")
                st.experimental_rerun()

    # show participants
    if event["participants"]:
        dfp = pd.DataFrame(event["participants"])
        st.table(dfp)
    else:
        st.info("Belum ada peserta. Tambahkan peserta terlebih dahulu.")

    st.markdown("---")
    st.subheader("➕ Tambah Pengeluaran")
    with st.form("add_expense"):
        desc = st.text_input("Deskripsi (mis. 'Makan di Warteg')", '')
        amt = st.number_input("Jumlah (Rp)", min_value=0.0, format="%.2f")
        payer = st.selectbox("Pembayar", options=[p["name"] for p in event["participants"]] if event["participants"] else [])
        # select participants who participate in this expense (default all)
        if event["participants"]:
            default_checked = [p["name"] for p in event["participants"]]
            participants_selected = st.multiselect("Siapa yang ikut bayar (pilih peserta)", options=[p["name"] for p in event["participants"]], default=default_checked)
        else:
            participants_selected = []
        split_mode = st.radio("Metode pembagian", options=["Equal (bagikan sama rata)", "Custom shares (masukkan jumlah per orang)"], index=0)
        shares_input = {}
        if split_mode.startswith("Custom"):
            # dynamic inputs for shares
            st.markdown("Masukkan jumlah (Rp) untuk tiap peserta yang ikut")
            for name in participants_selected:
                val = st.number_input(f"Share - {name}", min_value=0.0, format="%.2f", key=f"share_{name}")
                shares_input[name] = float(val)
        submit_exp = st.form_submit_button("Simpan pengeluaran")
        if submit_exp:
            if desc.strip()=="":
                st.warning("Isi deskripsi pengeluaran.")
            elif amt <= 0:
                st.warning("Jumlah harus lebih besar dari 0.")
            elif payer == "":
                st.warning("Pilih pembayar.")
            elif not participants_selected:
                st.warning("Pilih setidaknya satu peserta yang ikut pengeluaran.")
            else:
                shares = {}
                if split_mode.startswith("Custom"):
                    # use shares_input; ensure sum <= amount (or equal expected)
                    total_shares = sum(shares_input.get(n,0.0) for n in participants_selected)
                    if abs(total_shares - amt) > 0.01:
                        st.warning(f"Jumlah total shares ({total_shares}) tidak cocok dengan total amount ({amt}). Pastikan jumlah shares sama dengan total pengeluaran.")
                    else:
                        for n in participants_selected:
                            shares[n] = float(shares_input.get(n, 0.0))
                        add_expense(event["id"], desc, amt, payer, participants_selected, shares)
                        st.success("Pengeluaran ditambahkan (custom shares).")
                        st.experimental_rerun()
                else:
                    # equal split: shares left empty meaning split equally
                    add_expense(event["id"], desc, amt, payer, participants_selected, {})
                    st.success("Pengeluaran ditambahkan (equal split).")
                    st.experimental_rerun()

    st.markdown("---")
    st.subheader("Daftar Pengeluaran")
    exps = event["expenses"]
    if exps:
        dfex = pd.DataFrame([{
            "Tanggal": e["created"][:19],
            "Deskripsi": e["desc"],
            "Jumlah": e["amount"],
            "Pembayar": e["payer"],
            "Peserta": ", ".join(e["participants"])
        } for e in exps])
        st.dataframe(dfex)
        # export CSV button
        buf = io.StringIO()
        dfex.to_csv(buf, index=False)
        st.download_button("Download pengeluaran (CSV)", data=buf.getvalue(), file_name=f"{event['id']}_expenses.csv")
    else:
        st.info("Belum ada pengeluaran untuk event ini.")

# -----------------------
# Right: Balances & Settlements
# -----------------------
with col2:
    st.subheader("🔢 Ringkasan & Penyelesaian")
    if not event["participants"]:
        st.info("Tambahkan peserta agar ringkasan muncul.")
    else:
        balances = compute_net_balances(event["id"])
        df_bal = pd.DataFrame([{"Nama": k, "Saldo (positif=harus diterima)": v} for k, v in balances.items()]).sort_values(by="Saldo (positif=harus diterima)", ascending=False)
        st.table(df_bal.style.format({"Saldo (positif=harus diterima)": "{:,.2f}"}))

        st.markdown("**Settlement plan (siapa bayar siapa)**")
        settlements = compute_settlements(balances)
        if settlements:
            df_set = pd.DataFrame([{"Dari (pembayar)": s[0], "Ke (penerima)": s[1], "Jumlah (Rp)": s[2]} for s in settlements])
            st.dataframe(df_set)
            # export settlements
            buf2 = io.StringIO()
            df_set.to_csv(buf2, index=False)
            st.download_button("Download settlement plan (CSV)", data=buf2.getvalue(), file_name=f"{event['id']}_settlements.csv")
        else:
            st.info("Semua sudah seimbang — tidak ada yang perlu dibayar.")

    st.markdown("---")
    st.subheader("Opsi Event")
    if st.button("Reset event (hapus peserta & pengeluaran)"):
        st.session_state.events[event["id"]]["participants"] = []
        st.session_state.events[event["id"]]["expenses"] = []
        st.success("Event di-reset.")
        st.experimental_rerun()

    if st.button("Hapus event ini (permanen)"):
        del st.session_state.events[event["id"]]
        st.session_state.current_event = None
        st.success("Event dihapus.")
        st.experimental_rerun()
