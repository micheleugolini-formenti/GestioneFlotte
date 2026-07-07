import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
from sqlalchemy import text

# Configurazione della pagina web
st.set_page_config(page_title="Formenti Fleet Cloud System", layout="wide", page_icon="Vans")

# --- 1. DATABASE COMPLETO "A MAGAZZINO" ---
fleet_db = {
    "FORN. IND.LI FORMENTI SRL": [
        {"mezzo": "BMW 650 - EP700LY", "assegnato": "SIG. FORMENTI"},
        {"mezzo": "FIORINO - FF362CP", "assegnato": "FIORINO MAGAZZINO"},
        {"mezzo": "CLIO - GG880SN", "assegnato": "CUNEGO"},
        {"mezzo": "CLIO - GW074FB", "assegnato": "SIG. FORMENTI (EX JOLLY)"},
        {"mezzo": "DAILY - FZ861EH", "assegnato": "SIMONE MORENO MICHELE"},
        {"mezzo": "CLIO - GL229DJ", "assegnato": "CLIO HYBRID - PENNER"},
        {"mezzo": "CLIO - FL906PG", "assegnato": "TROLESE"},
        {"mezzo": "DOBLO' - EL086GW", "assegnato": "PIETROPOLLI"},
        {"mezzo": "BMW X1 - GT575Y6K", "assegnato": "SIG. FORMENTI"},
        {"mezzo": "MAN - FZ860EH", "assegnato": "MONTRUCOLI MATTEO"},
        {"mezzo": "DOBLO' - EZ988AX", "assegnato": "BERTELLI"},
        {"mezzo": "CLIO - GR038AH", "assegnato": "CLIO HYBRID - SARTORI"},
        {"mezzo": "PEUGEOT 208 - FF599PR", "assegnato": "JOLLY"},
        {"mezzo": "AUDI A1 - FR531KB", "assegnato": "SIG. FORMENTI"},
        {"mezzo": "CLIO - GG881SN", "assegnato": "MIOLO"},
        {"mezzo": "PEUGEOT 308SW - FL293PL", "assegnato": "CAIAZZO"},
    ],
    "FORMENTI GASTONE SRL": [
        {"mezzo": "DAILY - EK255XE", "assegnato": "OFFICINA"},
        {"mezzo": "DAILY - EV900GE", "assegnato": "OFFICINA"},
        {"mezzo": "DOBLO' - GD292RH", "assegnato": "OFFICINA FERRARI MASSIMO"},
        {"mezzo": "PEUGEOT EXPERT - GH781BP", "assegnato": "OFFICINA MATTIA"},
        {"mezzo": "FIORINO - FF076PN", "assegnato": "PATTY FIORINO OFFICINA"},
        {"mezzo": "PEUGEOT 3008 - GR859AH", "assegnato": "BELLINI"},
    ],
    "VENETA FUNI SRL": [
        {"mezzo": "IVECO DAILY - DS641ST", "assegnato": "FURGONE VENETA FUNI"},
        {"mezzo": "NISSAN Piattaforma - EN752WD", "assegnato": "PIATTAFORMA 1à 'Vecchia'"},
        {"mezzo": "NISSAN Piattaforma - FX747GW", "assegnato": "PIATTAFORMA 2à"},
        {"mezzo": "IVECO Piattaforma - HA245ED", "assegnato": "PIATTAFORMA NUOVA IVECO CTE 4,0"},
    ]
}

# --- 🎯 FILTRO ATTIVO ---
mezzi_prenotabili = [
    "FIORINO - FF362CP",
    "PEUGEOT 208 - FF599PR",
    "CLIO - GW074FB"
]

# --- 2. CONNESSIONE AL DATABASE CLOUD ---
try:
    conn = st.connection("sql")
except Exception as e:
    st.error("⚠️ Errore di configurazione del Database Cloud!")
    st.stop()

with conn.session as session:
    session.execute(text("""
    CREATE TABLE IF NOT EXISTS prenotazioni (
        chiave_mese VARCHAR(50),
        riga_giorno VARCHAR(50),
        mezzo VARCHAR(100),
        tecnico VARCHAR(100),
        PRIMARY KEY (chiave_mese, riga_giorno, mezzo)
    );
    """))
    session.commit()

def query_mese_cloud(chiave_mese, giorni_lista):
    df = pd.DataFrame("", index=giorni_lista, columns=mezzi_prenotabili)
    try:
        res = conn.query("SELECT riga_giorno, mezzo, tecnico FROM prenotazioni WHERE chiave_mese = :mese", 
                         params={"mese": chiave_mese}, ttl=0)
        if not res.empty:
            for _, row in res.iterrows():
                riga = row['riga_giorno']
                mezzo = row['mezzo']
                tecnico = row['tecnico']
                if riga in df.index and mezzo in df.columns:
                    df.at[riga, mezzo] = tecnico
    except Exception:
        pass
    return df

# --- 🎨 FUNZIONE DI FORMATTAZIONE RIGHE PER IL FINE SETTIMANA ---
def applica_colore_celle(df_input):
    # Genera una tabella di stili della stessa dimensione del DF originale
    df_style = pd.DataFrame('', index=df_input.index, columns=df_input.columns)
    for index_row in df_input.index:
        if "DOM" in index_row:
            df_style.loc[index_row] = 'background-color: #ffcccc; color: #000000; font-weight: bold;'
        elif "(S)" in index_row:
            df_style.loc[index_row] = 'background-color: #ffe6cc; color: #000000;'
    return df_style

# --- 🛰️ PARSER URL PER QR CODE ---
default_index = 0
if "mezzo" in st.query_params:
    param_mezzo = st.query_params["mezzo"].upper()
    if "page_redirected" not in st.session_state:
        st.session_state.page = "prenota"
        st.session_state.page_redirected = True
    
    if "FF362CP" in param_mezzo: default_index = 0
    elif "FF599PR" in param_mezzo: default_index = 1
    elif "GW074FB" in param_mezzo: default_index = 2

# --- 3. NAVIGAZIONE ---
if "page" not in st.session_state: st.session_state.page = "home"
def nav_to(page_name): st.session_state.page = page_name

if st.session_state.page == "home":
    st.title("🚐 Formenti Fleet Cloud System v5.7")
    st.subheader("Seleziona la modalità d'accesso:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📱 INTERFACCIA SMARTPHONE\n(Controllo Rapido e Prenotazione)", use_container_width=True): nav_to("prenota"); st.rerun()
    with col2:
        if st.button("📊 DASHBOARD PC UFFICIO\n(Tabellone Mensile Completo)", use_container_width=True): nav_to("dashboard"); st.rerun()

elif st.session_state.page == "prenota":
    if st.button("⬅️ Torna al Menu Principale"): 
        if "page_redirected" in st.session_state: del st.session_state["page_redirected"]
        st.query_params.clear()
        nav_to("home")
        st.rerun()
        
    st.title("📱 Controllo Rapido e Prenotazione")
    
    veicolo_sel = st.selectbox("Scegli l'automezzo da prenotare:", mezzi_prenotabili, index=default_index)
    
    proprietario_azienda = "Non specificato"
    utilizzatore_abituale = "Non specificato"
    for ditta, lista_mezzi in fleet_db.items():
        for m in lista_mezzi:
            if m["mezzo"] == veicolo_sel:
                proprietario_azienda = ditta
                utilizzatore_abituale = m["assegnato"]
                
    st.warning(f"🏢 **Proprietario (Azienda):** {proprietario_azienda}")
    st.info(f"👤 **Utilizzatore Abituale:** {utilizzatore_abituale}")
    
    data_sel = st.date_input("Seleziona la data dell'attività:", datetime.now())
    giorni_settimana = ["L", "M", "M", "G", "V", "S", "D"]
    sigla_giorno = giorni_settimana[calendar.weekday(data_sel.year, data_sel.month, data_sel.day)]
    label_riga = f"{data_sel.day:02d}/{data_sel.month:02d} (🔴 DOM)" if sigla_giorno == "D" else f"{data_sel.day:02d}/{data_sel.month:02d} ({sigla_giorno})"
    
    mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    chiave_mese = f"{mesi_ita[data_sel.month - 1]}_{data_sel.year}"
    
    res_singolo = conn.query("SELECT tecnico FROM prenotazioni WHERE chiave_mese = :mese AND riga_giorno = :riga AND mezzo = :mezzo", 
                             params={"mese": chiave_mese, "riga": label_riga, "mezzo": veicolo_sel}, ttl=0)
    stato_attuale = res_singolo.iloc[0]['tecnico'] if not res_singolo.empty else ""
    
    if stato_attuale == "" or pd.isna(stato_attuale):
        st.success("✅ IL MEZZO RISULTA DISPONIBILE")
        nome_pren = st.text_input("Scrivi il tuo nome per prenotarlo (Testo Libero):")
        if st.button("Registra Prenotazione sul Cloud"):
            if nome_pren:
                with conn.session as session:
                    session.execute(text("INSERT INTO prenotazioni (chiave_mese, riga_giorno, mezzo, tecnico) VALUES (:mese, :riga, :mezzo, :tecnico) ON CONFLICT (chiave_mese, riga_giorno, mezzo) DO UPDATE SET tecnico = :tecnico"),
                                    {"mese": chiave_mese, "riga": label_riga, "mezzo": veicolo_sel, "tecnico": nome_pren})
                    session.commit()
                st.success("Salva! La prenotazione è attiva sul Cloud.")
                st.balloons()
                st.rerun()
    else:
        st.error(f"🔴 MEZZO OCCUPATO DA: {stato_attuale}")

elif st.session_state.page == "dashboard":
    if st.button("⬅️ Torna al Menu Principale"): nav_to("home"); st.rerun()
    st.title("📊 Tabellone Mensile Flotta (Sincronizzato Cloud)")
    
    col_m1, col_m2, col_m3 = st.columns([1, 1, 2])
    with col_m1: anno = st.selectbox("📆 Seleziona Anno", [2026, 2027], index=0)
    with col_m2:
        mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
        mese_nome = st.selectbox("📅 Seleziona Mese", mesi_ita, index=6)
    with col_m3: ditta_sel = st.selectbox("🏢 Filtra per Società", ["Tutte le ditte"] + list(fleet_db.keys()))
    
    m_idx = mesi_ita.index(mese_nome) + 1
    num_giorni = calendar.monthrange(anno, m_idx)[1]
    giorni_settimana = ["L", "M", "M", "G", "V", "S", "D"]
    giorni_lista = []
    for i in range(1, num_giorni + 1):
        sigla = giorni_settimana[calendar.weekday(anno, m_idx, i)]
        giorni_lista.append(f"{i:02d}/{m_idx:02d} (🔴 DOM)" if sigla == "D" else f"{i:02d}/{m_idx:02d} ({sigla})")
        
    df_db = query_mese_cloud(f"{mese_nome}_{anno}", giorni_lista)
    
    veicoli_da_mostrare = [v for v in mezzi_prenotabili if ditta_sel == "Tutte le ditte" or any(item["mezzo"] == v for item in fleet_db[ditta_sel])]
    df_filtrato = df_db[veicoli_da_mostrare]
    
    st.info("💡 Fai doppio click su una cella per scrivere. Quando clicchi fuori, il dato si sincronizza online per tutti.")
    
    # 🎨 NUOVA LOGICA DI STYLE: Applica il colore alle celle del data_editor in modo nativo e blindato
    df_styled = df_filtrato.style.apply(applica_colore_celle, axis=None)
    df_edit = st.data_editor(df_styled, use_container_width=True, height=550, key=f"editor_{mese_nome}_{anno}_{ditta_sel}")
    
    if not df_edit.equals(df_filtrato):
        with conn.session as session:
            for riga in giorni_lista:
                for mezzo in veicoli_da_mostrare:
                    valore_nuovo = df_edit.at[riga, mezzo]
                    if valore_nuovo != df_filtrato.at[riga, mezzo]:
                        if valore_nuovo == "" or pd.isna(valore_nuovo):
                            session.execute(text("DELETE FROM prenotazioni WHERE chiave_mese=:mese AND riga_giorno=:riga AND mezzo=:mezzo"),
                                            {"mese": f"{mese_nome}_{anno}", "riga": riga, "mezzo": mezzo})
                        else:
                            session.execute(text("INSERT INTO prenotazioni (chiave_mese, riga_giorno, mezzo, tecnico) VALUES (:mese, :riga, :mezzo, :tecnico) ON CONFLICT (chiave_mese, riga_giorno, mezzo) DO UPDATE SET tecnico = :tecnico"),
                                            {"mese": f"{mese_nome}_{anno}", "riga": riga, "mezzo": mezzo, "tecnico": valore_nuovo})
            session.commit()
        st.success("💾 Cloud aggiornato con successo!")
        st.rerun()
