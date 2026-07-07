import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
from sqlalchemy import text
import io
import base64
from PIL import Image  # Per la compressione di sicurezza dell'immagine

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

mezzi_prenotabili = [
    "FIORINO - FF362CP",
    "PEUGEOT 208 - FF599PR",
    "CLIO - GW074FB"
]

def get_lista_totale_mezzi():
    lista = []
    for ditta in fleet_db:
        for item in fleet_db[ditta]:
            lista.append(item["mezzo"])
    return lista
tutti_i_mezzi = get_lista_totale_mezzi()

# --- 2. CONNESSIONE AL DATABASE CLOUD ---
try:
    conn = st.connection("sql")
except Exception as e:
    st.error("⚠️ Errore di configurazione del Database Cloud!")
    st.stop()

# Inizializzazione Tabelle Cloud (Inclusa tabella storico per le foto)
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
    session.execute(text("""
    CREATE TABLE IF NOT EXISTS scadenze_flotta (
        mezzo VARCHAR(100) PRIMARY KEY,
        km_attuali INT DEFAULT 0,
        km_prossimo_tagliando INT DEFAULT 0,
        scadenza_assicurazione DATE DEFAULT '2026-12-31',
        data_ultimo_agg_km DATE
    );
    """))
    session.execute(text("""
    CREATE TABLE IF NOT EXISTS storico_foto_cruscotto (
        mezzo VARCHAR(100),
        chiave_mese_anno VARCHAR(50),
        km_registrati INT,
        foto_base64 TEXT,
        PRIMARY KEY (mezzo, chiave_mese_anno)
    );
    """))
    for m in tutti_i_mezzi:
        session.execute(text("INSERT INTO scadenze_flotta (mezzo) VALUES (:mezzo) ON CONFLICT (mezzo) DO NOTHING"), {"mezzo": m})
    session.commit()

def query_mese_cloud(chiave_mese, giorni_lista):
    df = pd.DataFrame("", index=giorni_lista, columns=mezzi_prenotabili)
    try:
        res = conn.query("SELECT riga_giorno, mezzo, tecnico FROM prenotazioni WHERE chiave_mese = :mese", params={"mese": chiave_mese}, ttl=0)
        if not res.empty:
            for _, row in res.iterrows():
                riga = row['riga_giorno']
                mezzo = row['mezzo']
                tecnico = row['tecnico']
                if riga in df.index and mezzo in df.columns:
                    df.at[riga, mezzo] = tecnico
    except Exception: pass
    return df

def applica_colore_cells(df_input):
    df_style = pd.DataFrame('', index=df_input.index, columns=df_input.columns)
    for index_row in df_input.index:
        if "DOM" in index_row: df_style.loc[index_row] = 'background-color: #ffcccc; color: #000000; font-weight: bold;'
        elif "(S)" in index_row: df_style.loc[index_row] = 'background-color: #ffe6cc; color: #000000;'
    return df_style

# --- 🛰️ PARSER URL AVANZATO: RILEVA SE È UN CONDUCENTE CHE AGGIORNA I KM ---
default_index_pren = 0
if "mezzo" in st.query_params:
    param_m = st.query_params["mezzo"].upper()
    if "page_redirected" not in st.session_state:
        st.session_state.page = "prenota"
        st.session_state.st_redir = True
    if "FF362CP" in param_m: default_index_pren = 0
    elif "FF599PR" in param_m: default_index_pren = 1
    elif "GW074FB" in param_m: default_index_pren = 2

# Rilevamento link dedicato inserimento KM (es. ?km=FF362CP)
if "km" in st.query_params:
    st.session_state.page = "inserimento_km_conducente"
    st.session_state.targa_km_target = st.query_params["km"].upper()

# --- 3. NAVIGAZIONE PAGINE ---
if "page" not in st.session_state: st.session_state.page = "home"
def nav_to(page_name): st.session_state.page = page_name

if st.session_state.page == "home":
    st.title("Hub Formenti Fleet Cloud System v6.5")
    st.subheader("Seleziona la sezione di lavoro:")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📱 INTERFACCIA SMARTPHONE\n(Prenotazione Rapida)", use_container_width=True): nav_to("prenota"); st.rerun()
    with col2:
        if st.button("📊 DASHBOARD PC UFFICIO\n(Tabellone Mensile)", use_container_width=True): nav_to("dashboard"); st.rerun()
    with col3:
        if st.button("🔧 GESTIONE SCADENZE & KM\n(Alert e Monitoraggio Flotta)", use_container_width=True): nav_to("scadenze"); st.rerun()

elif st.session_state.page == "prenota":
    if st.button("⬅️ Torna al Menu Principale"): st.query_params.clear(); nav_to("home"); st.rerun()
    st.title("📱 Controllo Rapido e Prenotazione")
    veicolo_sel = st.selectbox("Scegli l'automezzo da prenotare:", mezzi_prenotabili, index=default_index_pren)
    
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
    
    res_singolo = conn.query("SELECT tecnico FROM prenotazioni WHERE chiave_mese = :mese AND riga_giorno = :riga AND mezzo = :mezzo", params={"mese": chiave_mese, "riga": label_riga, "mezzo": veicolo_sel}, ttl=0)
    stato_attuale = res_singolo.iloc[0]['tecnico'] if not res_singolo.empty else ""
    
    if stato_attuale == "" or pd.isna(stato_attuale):
        st.success("✅ IL MEZZO RISULTA DISPONIBILE")
        nome_pren = st.text_input("Scrivi il tuo nome per prenotarlo:")
        if st.button("Registra Prenotazione"):
            if nome_pren:
                with conn.session as session:
                    session.execute(text("INSERT INTO prenotazioni (chiave_mese, riga_giorno, mezzo, tecnico) VALUES (:mese, :riga, :mezzo, :tecnico) ON CONFLICT (chiave_mese, riga_giorno, mezzo) DO UPDATE SET tecnico = :tecnico"), {"mese": chiave_mese, "riga": label_riga, "mezzo": veicolo_sel, "tecnico": nome_pren})
                    session.commit()
                st.success("Salva! Prenotazione attiva.")
                st.balloons(); st.rerun()
    else: st.error(f"🔴 MEZZO OCCUPATO DA: {stato_attuale}")

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
    
    df_styled = df_filtrato.style.apply(applica_colore_cells, axis=None)
    df_edit = st.data_editor(df_styled, use_container_width=True, height=550, key=f"ed_{mese_nome}_{anno}_{ditta_sel}")
    
    if not df_edit.equals(df_filtrato):
        with conn.session as session:
            for riga in giorni_lista:
                for mezzo in veicoli_da_mostrare:
                    valore_nuovo = df_edit.at[riga, mezzo]
                    if valore_nuovo != df_filtrato.at[riga, mezzo]:
                        if valore_nuovo == "" or pd.isna(valore_nuovo):
                            session.execute(text("DELETE FROM prenotazioni WHERE chiave_mese=:mese AND riga_giorno=:riga AND mezzo=:mezzo"), {"mese": f"{mese_nome}_{anno}", "riga": riga, "mezzo": mezzo})
                        else:
                            session.execute(text("INSERT INTO prenotazioni (chiave_mese, riga_giorno, mezzo, tecnico) VALUES (:mese, :riga, :mezzo, :tecnico) ON CONFLICT (chiave_mese, riga_giorno, mezzo) DO UPDATE SET tecnico = :tecnico"), {"mese": f"{mese_nome}_{anno}", "riga": riga, "mezzo": mezzo, "tecnico": valore_nuovo})
            session.commit()
        st.success("💾 Cloud aggiornato con successo!"); st.rerun()

# --- 📱📱📱 NUOVA INTERFACCIA DEDICATA INSERIMENTO KM CONDUCENTE (SBLOCCATA DA QR) ---
elif st.session_state.page == "inserimento_km_conducente":
    targa_target = st.session_state.get("targa_km_target", "")
    
    # Cerca il mezzo corrispondente nei 26 totali
    mezzo_completo_selezionato = None
    referente_rilevato = "Non specificato"
    for ditta, mezzi in fleet_db.items():
        for m in mezzi:
            if targa_target in m["mezzo"]:
                mezzo_completo_selezionato = m["mezzo"]
                referente_rilevato = m["assegnato"]
                
    if not mezzo_completo_selezionato:
        st.error(f"⚠️ Errore: La targa '{targa_target}' non corrisponde a nessun veicolo in anagrafica Formenti.")
        if st.button("Vai alla Home"): st.query_params.clear(); nav_to("home"); st.rerun()
        st.stop()
        
    st.title(f"🚐 Registrazione KM Mensile")
    st.subheader(f"Mezzo: {mezzo_completo_selezionato}")
    st.info(f"👤 **Referente/Utilizzatore Abituale:** {referente_rilevato}")
    
    # Carica l'ultimo chilometraggio salvato
    res_last = conn.query("SELECT km_attuali FROM scadenze_flotta WHERE mezzo = :m", params={"m": mezzo_completo_selezionato}, ttl=0)
    km_precedenti = int(res_last.iloc[0]['km_attuali']) if not res_last.empty else 0
    st.metric(label="Chilometri registrati l'ultimo mese:", value=f"{km_precedenti:,} KM")
    
    st.markdown("---")
    
    # INPUT 1: I Chilometri (Obbligatoriamente superiori ai precedenti)
    km_inseriti = st.number_input("Inserisci i Chilometri attuali segnati sul cruscotto:", min_value=km_precedenti, step=1, value=km_precedenti)
    
    # INPUT 2: La Foto (Mandatoria per sbloccare il bottone)
    st.markdown("#### 📸 Foto del Cruscotto (Obbligatoria)")
    file_foto = st.file_uploader("Scatta una foto del contachilometri o caricala dalla galleria:", type=["jpg", "jpeg", "png"])
    
    if file_foto is not None:
        st.success("✅ Foto caricata correttamente. Elaborazione e compressione in corso...")
        
        # LOGICA DI COMPRESSIONE: Riduce l'immagine a 800px max per risparmiare spazio sul database Neon
        img = Image.open(file_foto)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.thumbnail((800, 800))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=65)  # Qualità 65% per file leggerissimo (~40KB) ma nitido
        foto_base64_string = base64.b64encode(buffer.getvalue()).decode()
        
        st.image(buffer.getvalue(), caption="Anteprima della foto che verrà salvata", width=300)
        
        # Abilita il salvataggio se i km sono aumentati (o uguali se fermo, ma veritieri)
        if st.button("Invia dati e foto in Direzione", use_container_width=True):
            oggi = date.today()
            mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
            chiave_mese_anno = f"{mesi_ita[oggi.month - 1]}_{oggi.year}"
            
            with conn.session as session:
                # 1. Aggiorna lo stato attuale
                session.execute(text("""
                    UPDATE scadenze_flotta 
                    SET km_attuali = :km, data_ultimo_agg_km = :oggi 
                    WHERE mezzo = :mezzo
                """), {"km": km_inseriti, "oggi": oggi, "mezzo": mezzo_completo_selezionato})
                
                # 2. Salva la foto nello storico mensile (sovrascrive se reinviata nello stesso mese)
                session.execute(text("""
                    INSERT INTO storico_foto_cruscotto (mezzo, chiave_mese_anno, km_registrati, foto_base64)
                    VALUES (:mezzo, :chiave, :km, :foto)
                    ON CONFLICT (mezzo, chiave_mese_anno) 
                    DO UPDATE SET km_registrati = :km, foto_base64 = :foto
                """), {"mezzo": mezzo_completo_selezionato, "chiave": chiave_mese_anno, "km": km_inseriti, "foto": foto_base64_string})
                
                session.commit()
                
            st.success("🎉 Perfetto! I chilometri e la foto sono stati registrati sul Cloud Formenti.")
            st.balloons()
            st.info("Puoi chiudere questa pagina internet del telefono.")
    else:
        st.warning("🔒 Per salvare i dati devi prima scattare e caricare la foto del cruscotto.")

# --- 🔧 PAGINA CENTRALIZZATA SCADENZE & ALERT UFFICIO ---
elif st.session_state.page == "scadenze":
    if st.button("⬅️ Torna al Menu Principale"): nav_to("home"); st.rerun()
    st.title("🔧 Monitoraggio Scadenze, Chilometraggi e Foto")
    
    res_scadenze = conn.query("SELECT * FROM scadenze_flotta", ttl=0)
    mappa_referenti = {}
    for ditta, mezzi in fleet_db.items():
        for m in mezzi: mappa_referenti[m["mezzo"]] = m["assegnato"]
            
    st.subheader("🚨 Pannello Alert Meccanici / Assicurativi")
    oggi = date.today()
    alert_generati = 0
    
    # Alert standard (Tagliandi e Assicurazioni)
    if not res_scadenze.empty:
        for _, row in res_scadenze.iterrows():
            mezzo = row['mezzo']
            km_att = row['km_attuali']
            km_tagl = row['km_prossimo_tagliando']
            scad_ass = row['scadenza_assicurazione']
            referente = mappa_referenti.get(mezzo, "Non specificato")
            
            if km_tagl > 0 and (km_tagl - km_att) <= 1500:
                st.error(f"🔧 **TAGLIANDO RICHIESTO** su **{mezzo}** | KM Attuali: {km_att:,} / Soglia: {km_tagl:,} KM. \n👤 *Referente:* {referente}")
                alert_generati += 1
            if scad_ass:
                giorni_mancanti = (scad_ass - oggi).days
                if giorni_mancanti <= 30:
                    st.warning(f"📄 **ASSICURAZIONE IN SCADENZA** su **{mezzo}** | Scade il {scad_ass.strftime('%d/%m/%Y')} (Mancano {giorni_mancanti} giorni). \n👤 *Referente:* {referente}")
                    alert_generati += 1
                    
    # 🚨 NUOVO ALERT: CONTROLLO RITARDI INSERIMENTO KM FINE MESE
    st.subheader("⚠️ Registrazioni KM Mancanti Questo Mese")
    mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    nome_mese_corrente = mesi_ita[oggi.month - 1]
    
    mancanti_count = 0
    col_manc_1, col_manc_2 = st.columns(2)
    with col_manc_1:
        if not res_scadenze.empty:
            for _, row in res_scadenze.iterrows():
                mezzo = row['mezzo']
                dt_agg = row['data_ultimo_agg_km']
                referente = mappa_referenti.get(mezzo, "Non specificato")
                
                # Se non ha mai aggiornato o l'ultimo aggiornamento non è del mese/anno corrente
                if dt_agg is None or dt_agg.month != oggi.month or dt_agg.year != oggi.year:
                    st.write(f"❌ **{mezzo}** | Referente: `{referente}` (Nessun dato per {nome_mese_corrente})")
                    mancanti_count += 1
        if mancanti_count == 0: st.success(f"✅ Splendido! Tutti i referenti hanno inserito i KM di {nome_mese_corrente}.")

    st.markdown("---")
    
    # 📸 NUOVO STRUMENTO: VERIFICA VISIVA DELLE FOTO CARICATE DAI TECNICI
    st.subheader("📸 Archivio e Verifica Foto Contachilometri")
    mezzo_foto_sel = st.selectbox("Seleziona il veicolo di cui vuoi controllare la prova fotografica:", tutti_i_mezzi)
    chiave_mese_foto = st.selectbox("Seleziona il mese da verificare:", [f"{m}_{oggi.year}" for m in mesi_ita], index=oggi.month-1)
    
    res_foto = conn.query("SELECT km_registrati, foto_base64 FROM storico_foto_cruscotto WHERE mezzo = :m AND chiave_mese_anno = :c", 
                          params={"m": mezzo_foto_sel, "c": chiave_mese_foto}, ttl=0)
    
    if not res_foto.empty:
        km_f = res_foto.iloc[0]['km_registrati']
        blob_f = res_foto.iloc[0]['foto_base64']
        st.success(f"📸 Foto trovata! KM dichiarati dal tecnico in questa sessione: **{km_f:,} KM**")
        st.image(base64.b64decode(blob_f), caption=f"Cruscotto ufficiale {mezzo_foto_sel} - {chiave_mese_foto}", width=450)
    else:
        st.info(f"⚪ Nessuna foto caricata per {mezzo_foto_sel} nel mese di {chiave_mese_foto}.")
        
    st.markdown("---")
    
    # Tabellone generale editabile dall'ufficio
    st.subheader("📊 Registro Storico e Soglie (PC Ufficio)")
    righe_tabella = []
    for ditta, mezzi in fleet_db.items():
        for m in mezzi:
            m_nome = m["mezzo"]
            ref = m["assegnato"]
            db_row = res_scadenze[res_scadenze['mezzo'] == m_nome] if not res_scadenze.empty else pd.DataFrame()
            if not db_row.empty:
                km_a = int(db_row.iloc[0]['km_attuali'])
                km_t = int(db_row.iloc[0]['km_prossimo_tagliando'])
                scad = db_row.iloc[0]['scadenza_assicurazione']
                data_agg = db_row.iloc[0]['data_ultimo_agg_km']
            else: km_a, km_t, scad, data_agg = 0, 0, date(2026, 12, 31), None
                
            righe_tabella.append({
                "Società": ditta, "Automezzo": m_nome, "Referente / Utilizzo": ref,
                "KM Attuali": km_a, "Soglia Tagliando (KM)": km_t, "Scadenza Assicurazione": scad, "Ultimo Aggiornamento": data_agg
            })
            
    df_scadenze_visualizza = pd.DataFrame(righe_tabella)
    df_edit_scadenze = st.data_editor(
        df_scadenze_visualizza,
        disabled=["Società", "Automezzo", "Referente / Utilizzo", "Ultimo Aggiornamento"],
        column_config={
            "KM Attuali": st.column_config.NumberColumn(format="%d"),
            "Soglia Tagliando (KM)": st.column_config.NumberColumn(format="%d"),
            "Scadenza Assicurazione": st.column_config.DateColumn(format="DD/MM/YYYY")
        },
        use_container_width=True, height=400, key="editor_scadenze_globali"
    )
    
    if not df_edit_scadenze.equals(df_scadenze_visualizza):
        with conn.session as session:
            for i in range(len(df_edit_scadenze)):
                mezzo_nome = df_edit_scadenze.at[i, "Automezzo"]
                km_att_nuovo = int(df_edit_scadenze.at[i, "KM Attuali"])
                km_tag_nuovo = int(df_edit_scadenze.at[i, "Soglia Tagliando (KM)"])
                scad_nuova = df_edit_scadenze.at[i, "Scadenza Assicurazione"]
                km_vecchio = int(df_scadenze_visualizza.at[i, "KM Attuali"])
                data_agg_nuova = oggi if km_att_nuovo != km_vecchio else df_scadenze_visualizza.at[i, "Ultimo Aggiornamento"]
                
                session.execute(text("""
                    UPDATE scadenze_flotta 
                    SET km_attuali = :km_a, km_prossimo_tagliando = :km_t, scadenza_assicurazione = :scad, data_ultimo_agg_km = :dt_agg
                    WHERE mezzo = :mezzo
                """), {"km_a": km_att_nuovo, "km_t": km_tag_nuovo, "scad": scad_nuova, "dt_agg": data_agg_nuova, "mezzo": mezzo_nome})
            session.commit()
        st.success("💾 Database aggiornato con successo!"); st.rerun()
