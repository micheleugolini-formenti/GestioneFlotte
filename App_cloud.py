import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
from sqlalchemy import text
import io
import base64
from PIL import Image
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Configurazione della pagina web
st.set_page_config(page_title="Formenti Fleet Cloud System", layout="wide", page_icon="Vans")

# --- 1. DATABASE COMPLETO (TUTTE LE MAIL DEI REFERENTI IMPOSTATE SU MICHELE PER TEST) ---
MAIL_TEST_REFERENTI = "michele.ugolini@formentisrl.com"
MAIL_RESPONSABILE = "matteo.zanotti@formentisrl.com"

fleet_db = {
    "FORN. IND.LI FORMENTI SRL": [
        {"mezzo": "BMW 650 - EP700LY", "assegnato": "SIG. FORMENTI", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "FIORINO - FF362CP", "assegnato": "FIORINO MAGAZZINO", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "CLIO - GG880SN", "assegnato": "CUNEGO", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "CLIO - GW074FB", "assegnato": "SIG. FORMENTI (EX JOLLY)", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "DAILY - FZ861EH", "assegnato": "SIMONE MORENO MICHELE", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "CLIO - GL229DJ", "assegnato": "CLIO HYBRID - PENNER", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "CLIO - FL906PG", "assegnato": "TROLESE", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "DOBLO' - EL086GW", "assegnato": "PIETROPOLLI", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "BMW X1 - GT575Y6K", "assegnato": "SIG. FORMENTI", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "MAN - FZ860EH", "assegnato": "MONTRUCOLI MATTEO", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "DOBLO' - EZ988AX", "assegnato": "BERTELLI", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "CLIO - GR038AH", "assegnato": "CLIO HYBRID - SARTORI", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "PEUGEOT 208 - FF599PR", "assegnato": "JOLLY", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "AUDI A1 - FR531KB", "assegnato": "SIG. FORMENTI", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "CLIO - GG881SN", "assegnato": "MIOLO", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "PEUGEOT 308SW - FL293PL", "assegnato": "CAIAZZO", "email": MAIL_TEST_REFERENTI},
    ],
    "FORMENTI GASTONE SRL": [
        {"mezzo": "DAILY - EK255XE", "assegnato": "OFFICINA", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "DAILY - EV900GE", "assegnato": "OFFICINA", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "DOBLO' - GD292RH", "assegnato": "OFFICINA FERRARI MASSIMO", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "PEUGEOT EXPERT - GH781BP", "assegnato": "OFFICINA MATTIA", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "FIORINO - FF076PN", "assegnato": "PATTY FIORINO OFFICINA", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "PEUGEOT 3008 - GR859AH", "assegnato": "BELLINI", "email": MAIL_TEST_REFERENTI},
    ],
    "VENETA FUNI SRL": [
        {"mezzo": "IVECO DAILY - DS641ST", "assegnato": "FURGONE VENETA FUNI", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "NISSAN Piattaforma - EN752WD", "assegnato": "PIATTAFORMA 1à 'Vecchia'", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "NISSAN Piattaforma - FX747GW", "assegnato": "PIATTAFORMA 2à", "email": MAIL_TEST_REFERENTI},
        {"mezzo": "IVECO Piattaforma - HA245ED", "assegnato": "PIATTAFORMA NUOVA IVECO CTE 4,0", "email": MAIL_TEST_REFERENTI},
    ]
}

mezzi_prenotabili = ["FIORINO - FF362CP", "PEUGEOT 208 - FF599PR", "CLIO - GW074FB"]

def get_lista_totale_mezzi():
    lista = []
    for ditta in fleet_db:
        for item in fleet_db[ditta]: lista.append(item["mezzo"])
    return lista
tutti_i_mezzi = get_lista_totale_mezzi()

# --- 2. CONNESSIONE AL DATABASE CLOUD ---
try:
    conn = st.connection("sql")
except Exception as e:
    st.error("⚠️ Errore di configurazione del Database Cloud!")
    st.stop()

with conn.session as session:
    session.execute(text("CREATE TABLE IF NOT EXISTS prenotazioni (chiave_mese VARCHAR(50), riga_giorno VARCHAR(50), mezzo VARCHAR(100), tecnico VARCHAR(100), PRIMARY KEY (chiave_mese, riga_giorno, mezzo));"))
    session.execute(text("CREATE TABLE IF NOT EXISTS scadenze_flotta (mezzo VARCHAR(100) PRIMARY KEY, km_attuali INT DEFAULT 0, km_prossimo_tagliando INT DEFAULT 0, scadenza_assicurazione DATE DEFAULT '2026-12-31', data_ultimo_agg_km DATE);"))
    session.execute(text("CREATE TABLE IF NOT EXISTS storico_foto_cruscotto (mezzo VARCHAR(100), chiave_mese_anno VARCHAR(50), km_registrati INT, foto_base64 TEXT, PRIMARY KEY (mezzo, chiave_mese_anno));"))
    for m in tutti_i_mezzi:
        session.execute(text("INSERT INTO scadenze_flotta (mezzo) VALUES (:mezzo) ON CONFLICT (mezzo) DO NOTHING"), {"mezzo": m})
    session.commit()

# --- 📧 FUNZIONE MOTORE INVIO EMAIL ---
def spedisci_email(a_chi, oggetto, testo_corpo):
    try:
        # Pesca le credenziali del mittente dai Secrets
        cfg = st.secrets["email_smtp"]
        msg = MIMEMultipart()
        msg['From'] = cfg["user"]
        msg['To'] = a_chi
        msg['Subject'] = oggetto
        msg.attach(MIMEText(testo_corpo, 'plain'))
        
        server = smtplib.SMTP(cfg["server"], int(cfg["port"]))
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["user"], a_chi, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"❌ Fallito invio mail a {a_chi}: assicurati di aver inserito correttamente i dati [email_smtp] nei Secrets di Streamlit!")
        return False

def query_mese_cloud(chiave_mese, giorni_lista):
    df = pd.DataFrame("", index=giorni_lista, columns=mezzi_prenotabili)
    try:
        res = conn.query("SELECT riga_giorno, mezzo, tecnico FROM prenotazioni WHERE chiave_mese = :mese", params={"mese": chiave_mese}, ttl=0)
        if not res.empty:
            for _, row in res.iterrows():
                riga, mezzo, tecnico = row['riga_giorno'], row['mezzo'], row['tecnico']
                if riga in df.index and mezzo in df.columns: df.at[riga, mezzo] = tecnico
    except Exception: pass
    return df

def applica_colore_cells(df_input):
    df_style = pd.DataFrame('', index=df_input.index, columns=df_input.columns)
    for index_row in df_input.index:
        if "DOM" in index_row: df_style.loc[index_row] = 'background-color: #ffcccc; color: #000000; font-weight: bold;'
        elif "(S)" in index_row: df_style.loc[index_row] = 'background-color: #ffe6cc; color: #000000;'
    return df_style

# --- 🛰️ PARSER URL ---
default_index_pren = 0
if "mezzo" in st.query_params:
    param_m = st.query_params["mezzo"].upper()
    if "page_redirected" not in st.session_state:
        st.session_state.page = "prenota"
        st.session_state.st_redir = True
    if "FF362CP" in param_m: default_index_pren = 0
    elif "FF599PR" in param_m: default_index_pren = 1
    elif "GW074FB" in param_m: default_index_pren = 2

if "km" in st.query_params:
    st.session_state.page = "inserimento_km_conducente"
    st.session_state.targa_km_target = st.query_params["km"].upper()

# --- 3. NAVIGAZIONE ---
if "page" not in st.session_state: st.session_state.page = "home"
def nav_to(page_name): st.session_state.page = page_name

if st.session_state.page == "home":
    st.title("Hub Formenti Fleet Cloud System v7.1 (Modalità Test)")
    st.subheader("Seleziona la sezione di lavoro:")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📱 INTERFACCIA SMARTPHONE\n(Prenotazione Rapida)", use_container_width=True): nav_to("prenota"); st.rerun()
    with col2:
        if st.button("📊 DASHBOARD PC UFFICIO\n(Tabellone Mensile)", use_container_width=True): nav_to("dashboard"); st.rerun()
    with col3:
        if st.button("🔧 GESTIONE SCADENZE & KM\n(Alert, Foto e Email)", use_container_width=True): nav_to("scadenze"); st.rerun()

elif st.session_state.page == "prenota":
    if st.button("⬅️ Torna al Menu Principale"): st.query_params.clear(); nav_to("home"); st.rerun()
    st.title("📱 Controllo Rapido e Prenotazione")
    veicolo_sel = st.selectbox("Scegli l'automezzo da prenotare:", mezzi_prenotabili, index=default_index_pren)
    
    proprietario_azienda = "Non specificato"
    utilizzatore_abituale = "Non specificato"
    for ditta, lista_mezzi in fleet_db.items():
        for m in lista_mezzi:
            if m["mezzo"] == veicolo_sel:
                proprietario_azienda, utilizzatore_abituale = ditta, m["assegnato"]
                
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
    st.title("📊 Tabellone Mensile Flotta")
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

elif st.session_state.page == "inserimento_km_conducente":
    targa_target = st.session_state.get("targa_km_target", "")
    mezzo_completo_selezionato, referente_rilevato = None, "Non specificato"
    for ditta, mezzi in fleet_db.items():
        for m in mezzi:
            if targa_target in m["mezzo"]: mezzo_completo_selezionato, referente_rilevato = m["mezzo"], m["assegnato"]
                
    if not mezzo_completo_selezionato:
        st.error(f"⚠️ Errore: La targa '{targa_target}' non è registrata."); st.stop()
        
    st.title(f"🚐 Registrazione KM Mensile")
    st.subheader(f"Mezzo: {mezzo_completo_selezionato} | Referente: {referente_rilevato}")
    
    res_last = conn.query("SELECT km_attuali FROM scadenze_flotta WHERE mezzo = :m", params={"m": mezzo_completo_selezionato}, ttl=0)
    km_precedenti = int(res_last.iloc[0]['km_attuali']) if not res_last.empty else 0
    st.metric(label="Chilometri registrati l'ultimo mese:", value=f"{km_precedenti:,} KM")
    
    km_inseriti = st.number_input("Inserisci i Chilometri attuali segnati sul cruscotto:", min_value=km_precedenti, step=1, value=km_precedenti)
    file_foto = st.file_uploader("📸 Scatta una foto del contachilometri:", type=["jpg", "jpeg", "png"])
    
    if file_foto is not None:
        st.success("✅ Foto caricata.")
        img = Image.open(file_foto)
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.thumbnail((800, 800))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=65)
        foto_base64_string = base64.b64encode(buffer.getvalue()).decode()
        st.image(buffer.getvalue(), caption="Anteprima foto", width=250)
        
        if st.button("Invia dati e foto in Direzione", use_container_width=True):
            oggi = date.today()
            mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
            chiave_mese_anno = f"{mesi_ita[oggi.month - 1]}_{oggi.year}"
            with conn.session as session:
                session.execute(text("UPDATE scadenze_flotta SET km_attuali = :km, data_ultimo_agg_km = :oggi WHERE mezzo = :mezzo"), {"km": km_inseriti, "oggi": oggi, "mezzo": mezzo_completo_selezionato})
                session.execute(text("INSERT INTO storico_foto_cruscotto (mezzo, chiave_mese_anno, km_registrati, foto_base64) VALUES (:mezzo, :chiave, :km, :foto) ON CONFLICT (mezzo, chiave_mese_anno) DO UPDATE SET km_registrati = :km, foto_base64 = :foto"), {"mezzo": mezzo_completo_selezionato, "chiave": chiave_mese_anno, "km": km_inseriti, "foto": foto_base64_string})
                session.commit()
            st.success("🎉 Chilometri e foto registrati con successo!")
            st.balloons()
    else: st.warning("🔒 Per salvare devi caricare la foto del cruscotto.")

# --- 🔧 PAGINA SCADENZE & AUTOMAZIONE EMAIL (UFFICIO) ---
elif st.session_state.page == "scadenze":
    if st.button("⬅️ Torna al Menu Principale"): nav_to("home"); st.rerun()
    st.title("🔧 Gestione Avanzata Scadenze & Solleciti Email")
    
    res_scadenze = conn.query("SELECT * FROM scadenze_flotta", ttl=0)
    
    mappa_referenti, mappa_email = {}, {}
    for ditta, mezzi in fleet_db.items():
        for m in mezzi:
            mappa_referenti[m["mezzo"]] = m["assegnato"]
            mappa_email[m["mezzo"]] = m["email"]
            
    oggi = date.today()
    mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    nome_mese_corrente = mesi_ita[oggi.month - 1]
    
    # 🚨 BLOCCO 1: SISTEMA SOLLECITI AUTOMATICI
    st.subheader("🚀 Centro Invio Promemoria & Escalation (Modo TEST)")
    st.info(f"📅 Oggi è il giorno **{oggi.day}** di **{nome_mese_corrente}**. \n- Giorno 1-2: Mail all'autista (tutte inviate a Michele).\n- Giorno 3+: Mail all'autista + Rapporto a Matteo.")
    
    lista_ritardatari = []
    if not res_scadenze.empty:
        for _, row in res_scadenze.iterrows():
            m_nome = row['mezzo']
            dt_agg = row['data_ultimo_agg_km']
            if dt_agg is None or dt_agg.month != oggi.month or dt_agg.year != oggi.year:
                lista_ritardatari.append(m_nome)
                
    if st.button("📧 Esegui Controllo Flotta e Spedisci Email", use_container_width=True):
        if len(lista_ritardatari) == 0:
            st.success("🎉 Fantastico! Tutti i mezzi sono già stati aggiornati per questo mese.")
        else:
            successi_autisti = 0
            report_per_responsabile = f"RAPPORTO RITARDATARI FLOTTA FORMENTI - MESE DI {nome_mese_corrente.upper()}\n"
            report_per_responsabile += f"Generato automaticamente il {oggi.strftime('%d/%m/%Y')}\n\n"
            report_per_responsabile += "I seguenti mezzi non hanno inserito i KM entro il 3 del mese:\n"
            
            for r_mezzo in lista_ritardatari:
                dest_autista = mappa_email.get(r_mezzo, "")
                nome_autista = mappa_referenti.get(r_mezzo, "Autista")
                targa_isoli = r_mezzo.split(" - ")[1] if " - " in r_mezzo else r_mezzo
                
                testo_autista = f"Ciao {nome_autista},\nti ricordiamo che e' obbligatorio aggiornare i KM mensili per il mezzo {r_mezzo}.\n"
                testo_autista += f"Clicca qui dal telefono per caricare la foto del cruscotto:\n"
                testo_autista += f"https://appcloudpy-npj6kyu77i5r34nctylryp.streamlit.app/?km={targa_isoli}\n\n"
                testo_autista += "Grazie,\nDirezione Formenti Srl"
                
                if dest_autista:
                    if spedisci_email(dest_autista, f"📋 TEST PROMEMORIA KM - {nome_mese_corrente}", testo_autista):
                        successi_autisti += 1
                        
                report_per_responsabile += f"- 🚐 {r_mezzo} | Referente: {nome_autista}\n"
                
            st.success(f"📨 Inviate {successi_autisti} email di promemoria (recapitate a Michele).")
            
            # ESCALATION: Giorno 3 o superiore
            if oggi.day >= 3:
                st.warning(f"⚠️ Essendo oltre il giorno 3, spedizione del report a Matteo ({MAIL_RESPONSABILE})...")
                if spedisci_email(MAIL_RESPONSABILE, f"🚨 ALERT TEST: Ritardatari KM {nome_mese_corrente}", report_per_responsabile):
                    st.success("📧 Mail di Escalation recapitata a Matteo con successo!")
            else:
                st.info("ℹ️ Prima del 3 del mese: escalation a Matteo NON inviata (come previsto).")

    st.markdown("---")
    
    st.subheader("🚨 Pannello Allarmi Attivi")
    if not res_scadenze.empty:
        for _, row in res_scadenze.iterrows():
            mezzo, km_att, km_tagl, scad_ass = row['mezzo'], row['km_attuali'], row['km_prossimo_tagliando'], row['scadenza_assicurazione']
            ref = mappa_referenti.get(mezzo, "Non specificato")
            if km_tagl > 0 and (km_tagl - km_att) <= 1500: st.error(f"🔧 **TAGLIANDO MECCANICO** su {mezzo} | Referente: {ref}")
            if scad_ass and (scad_ass - oggi).days <= 30: st.warning(f"📄 **ASSICURAZIONE IN SCADENZA** su {mezzo} | Referente: {ref}")
                    
    st.subheader(f"❌ Mezzi non aggiornati a {nome_mese_corrente} ({len(lista_ritardatari)} totali)")
    for rit in lista_ritardatari: st.write(f"• `{rit}` - Referente: **{mappa_referenti.get(rit)}**")
        
    st.markdown("---")
    st.subheader("📸 Archivio Foto Contachilometri")
    mezzo_foto_sel = st.selectbox("Seleziona il veicolo da controllare:", tutti_i_mezzi)
    chiave_mese_foto = st.selectbox("Seleziona il mese:", [f"{m}_{oggi.year}" for m in mesi_ita], index=oggi.month-1)
    res_foto = conn.query("SELECT km_registrati, foto_base64 FROM storico_foto_cruscotto WHERE mezzo = :m AND chiave_mese_anno = :c", params={"m": mezzo_foto_sel, "c": chiave_mese_foto}, ttl=0)
    if not res_foto.empty:
        st.success(f"📸 Foto trovata! KM dichiarati: **{res_foto.iloc[0]['km_registrati']:,} KM**")
        st.image(base64.b64decode(res_foto.iloc[0]['foto_base64']), width=400)
    else: st.info("⚪ Nessuna foto caricata per questo mese.")
        
    st.markdown("---")
    st.subheader("📊 Registro Soglie (Ufficio)")
    righe_tabella = []
    for ditta, mezzi in fleet_db.items():
        for m in mezzi:
            m_nome, ref = m["mezzo"], m["assegnato"]
            db_row = res_scadenze[res_scadenze['mezzo'] == m_nome] if not res_scadenze.empty else pd.DataFrame()
            km_a, km_t, scad, data_agg = (int(db_row.iloc[0]['km_attuali']), int(db_row.iloc[0]['km_prossimo_tagliando']), db_row.iloc[0]['scadenza_assicurazione'], db_row.iloc[0]['data_ultimo_agg_km']) if not db_row.empty else (0, 0, date(2026, 12, 31), None)
            righe_tabella.append({"Società": ditta, "Automezzo": m_nome, "Referente / Utilizzo": ref, "KM Attuali": km_a, "Soglia Tagliando (KM)": km_t, "Scadenza Assicurazione": scad, "Ultimo Aggiornamento": data_agg})
    df_scadenze_visualizza = pd.DataFrame(righe_tabella)
    df_edit_scadenze = st.data_editor(df_scadenze_visualizza, disabled=["Società", "Automezzo", "Referente / Utilizzo", "Ultimo Aggiornamento"], column_config={"KM Attuali": st.column_config.NumberColumn(format="%d"), "Soglia Tagliando (KM)": st.column_config.NumberColumn(format="%d"), "Scadenza Assicurazione": st.column_config.DateColumn(format="DD/MM/YYYY")}, use_container_width=True, height=400, key="editor_scadenze_globali")
    
    if not df_edit_scadenze.equals(df_scadenze_visualizza):
        with conn.session as session:
            for i in range(len(df_edit_scadenze)):
                mezzo_nome, km_att_nuovo, km_tag_nuovo, scad_nuova = df_edit_scadenze.at[i, "Automezzo"], int(df_edit_scadenze.at[i, "KM Attuali"]), int(df_edit_scadenze.at[i, "Soglia Tagliando (KM)"]), df_edit_scadenze.at[i, "Scadenza Assicurazione"]
                data_agg_nuova = oggi if km_att_nuovo != int(df_scadenze_visualizza.at[i, "KM Attuali"]) else df_scadenze_visualizza.at[i, "Ultimo Aggiornamento"]
                session.execute(text("UPDATE scadenze_flotta SET km_attuali = :km_a, km_prossimo_tagliando = :km_t, scadenza_assicurazione = :scad, data_ultimo_agg_km = :dt_agg WHERE mezzo = :mezzo"), {"km_a": km_att_nuovo, "km_t": km_tag_nuovo, "scad": scad_nuova, "dt_agg": data_agg_nuova, "mezzo": mezzo_nome})
            session.commit()
        st.success("💾 Database aggiornato!"); st.rerun()
