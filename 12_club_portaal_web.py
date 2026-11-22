import streamlit as st
import json
import os
import csv
from datetime import datetime

BASIS_MAP = os.path.dirname(os.path.abspath(__file__))
SPELERS_JSON = os.path.join(BASIS_MAP, "btlb_spelers.json")
EVENTS_CSV = os.path.join(BASIS_MAP, "seizoen_events_btlb.csv")
TRAINING_CSV = os.path.join(BASIS_MAP, "training_historiek.csv")
LOGIN_LOG_CSV = os.path.join(BASIS_MAP, "login_log.csv")
import urllib.request, base64
import streamlit.components.v1 as components

CONFIG_JSON = os.path.join(BASIS_MAP, "portaal_config.json")

st.set_page_config(page_title="BTLB Club- & Spelersportaal", page_icon="⚽", layout="wide")


def veilig_getal(waarde, standaard=0.0):
    try:
        return float(waarde)
    except (ValueError, TypeError):
        return standaard


def bepaal_seizoen_uit_datum(datum_str):
    delen = (datum_str or "").strip().split("-")
    if len(delen) == 3:
        _, maand_str, jaar_str = delen
        if maand_str.isdigit() and jaar_str.isdigit():
            maand, jaar = int(maand_str), int(jaar_str)
            start_jaar = jaar if maand >= 8 else (jaar - 1)
            return f"{start_jaar}-{start_jaar + 1}"
    return "2026-2027"


def laad_btlb_spelers():
    if os.path.exists(SPELERS_JSON):
        try:
            with open(SPELERS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"3de afdeling": {"InCluesive 3A": ["Speler 1 (3P | ELO 1450)", "Speler 2 (3P | ELO 1440)"]}}


def laad_of_maak_config(btlb_data):
    standaard_ploeg = "InCluesive 3A"
    gevonden_reeks = next(iter(btlb_data.keys()), "3de afdeling")
    for r_nm, ploegen in btlb_data.items():
        for p_nm in ploegen.keys():
            if "incluesive" in p_nm.lower() and "3a" in p_nm.lower():
                gevonden_reeks = r_nm
                standaard_ploeg = p_nm
                break

    cfg = {
        "actieve_reeks": gevonden_reeks,
        "actieve_ploeg": standaard_ploeg,
        "admin_pin": "9999",
        "onedrive_video_url": "",
        "pincodes": {}
    }
    if os.path.exists(CONFIG_JSON):
        try:
            with open(CONFIG_JSON, "r", encoding="utf-8") as f:
                opgeslagen = json.load(f)
            cfg.update(opgeslagen)
        except Exception:
            pass

    ploeg_spelers = btlb_data.get(cfg["actieve_reeks"], {}).get(cfg["actieve_ploeg"], [])
    for sp in ploeg_spelers:
        if sp not in cfg["pincodes"]:
            cfg["pincodes"][sp] = "1234"
    sla_config_op(cfg)
    return cfg


def sla_config_op(cfg):
    try:
        with open(CONFIG_JSON, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
def registreer_login(speler_naam, ploeg_naam):
    nu_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    bestaat = os.path.exists(LOGIN_LOG_CSV)
    try:
        with open(LOGIN_LOG_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Tijdstip", "Speler", "Ploeg"])
            if not bestaat:
                w.writeheader()
            w.writerow({"Tijdstip": nu_str, "Speler": speler_naam, "Ploeg": ploeg_naam})
    except Exception:
        pass

    # Bewaar login_log.csv ook direct op GitHub indien ingesteld in Streamlit Secrets
    try:
        gh_tok = st.secrets.get("GITHUB_TOKEN", "")
        gh_repo = st.secrets.get("GITHUB_REPO", "wullaert-tafelvoetbal/tafelvoetbal-clubportaal")
        if gh_tok and os.path.exists(LOGIN_LOG_CSV):
            domein = "api." + "github" + ".com"
            api_url = f"https://{domein}/repos/{gh_repo}/contents/login_log.csv"
            hdrs = {"Authorization": f"Bearer {gh_tok}", "Accept": "application/vnd.github+json", "User-Agent": "BTLB-Portaal"}
            sha = None
            try:
                with urllib.request.urlopen(urllib.request.Request(api_url, headers=hdrs), timeout=8) as r:
                    sha = json.loads(r.read().decode("utf-8")).get("sha")
            except Exception:
                pass
            with open(LOGIN_LOG_CSV, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            body = {"message": f"Login log: {speler_naam}", "content": b64}
            if sha:
                body["sha"] = sha
            req = urllib.request.Request(api_url, data=json.dumps(body).encode("utf-8"), headers=hdrs, method="PUT")
            urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass


def laad_events():
    rijen = []
    if os.path.exists(EVENTS_CSV):
        try:
            with open(EVENTS_CSV, "r", encoding="utf-8") as f:
                rijen = list(csv.DictReader(f))
        except Exception:
            pass
    return rijen


def analyseer_speler_data(speler_naam, events_lijst):
    basis_sp = (speler_naam or "").split("(").pop(0).strip().lower()
    sp_evs = [e for e in events_lijst if basis_sp and basis_sp in (e.get("Speler") or "").lower()]

    schoten_3 = [e for e in sp_evs if "3" in (e.get("Stang") or "") and e.get("Actie") in ("SCHOT_GOAL", "SCHOT_REDDING")]
    goals_3 = sum(1 for e in schoten_3 if e.get("Actie") == "SCHOT_GOAL")
    pct_3 = round((goals_3 / len(schoten_3)) * 100, 1) if schoten_3 else 0.0

    var_tot, var_gl = {}, {}
    hoek_telling = {"Links": 0, "Midden": 0, "Rechts": 0}
    for e in schoten_3:
        v = e.get("Variant") or "Onbekend"
        var_tot[v] = var_tot.get(v, 0) + 1
        if e.get("Actie") == "SCHOT_GOAL":
            var_gl[v] = var_gl.get(v, 0) + 1
        ey = veilig_getal(e.get("Eind_Y"), 220.0)
        if ey < 198:
            hoek_telling["Links"] += 1
        elif ey > 242:
            hoek_telling["Rechts"] += 1
        else:
            hoek_telling["Midden"] += 1

    fav_var = max(var_tot, key=var_tot.get) if var_tot else "Nog onbekend"
    kand_killer = [nm for nm, t in var_tot.items() if t >= 2] or list(var_tot.keys())
    if kand_killer:
        k_nm = max(kand_killer, key=lambda nm: (var_gl.get(nm, 0) / max(var_tot.get(nm, 1), 1), var_tot.get(nm, 0)))
        killer_txt = f"{k_nm} ({var_gl.get(k_nm, 0)}/{var_tot.get(k_nm, 0)})"
    else:
        killer_txt = "Nog onbekend"

    passes_5 = [e for e in sp_evs if e.get("Actie") in ("PASS_5_3", "PASS_5_3_GEBLOKT")]
    p5_ok = sum(1 for e in passes_5 if e.get("Actie") == "PASS_5_3")
    baan_tot, baan_ok = {}, {}
    for e in passes_5:
        b = e.get("Baan") or "Onbekend"
        baan_tot[b] = baan_tot.get(b, 0) + 1
        if e.get("Actie") == "PASS_5_3":
            baan_ok[b] = baan_ok.get(b, 0) + 1
    zwakste_baan = min(baan_tot, key=lambda b: baan_ok.get(b, 0) / max(baan_tot.get(b, 1), 1)) if baan_tot else "Nog onbekend"

    tegengoal_zones = {}
    for e in sp_evs:
        if e.get("Actie") == "TEGENGOAL_OP_12":
            dz = (e.get("Doelzone") or "Centraal").strip()
            tegengoal_zones[dz] = tegengoal_zones.get(dz, 0) + 1
    zwakste_zone = max(tegengoal_zones, key=tegengoal_zones.get) if tegengoal_zones else "Nog onbekend"

    return {
        "acties": len(sp_evs), "events": sp_evs, "schoten_3": len(schoten_3), "goals_3": goals_3,
        "pct_3": pct_3, "fav_var": fav_var, "killer": killer_txt,
        "fav_hoek": max(hoek_telling, key=hoek_telling.get) if schoten_3 else "Nog onbekend",
        "p5_ok": p5_ok, "p5_tot": len(passes_5), "zwakste_baan": zwakste_baan, "zwakste_zone": zwakste_zone
    }
btlb_data = laad_btlb_spelers()
config = laad_of_maak_config(btlb_data)
alle_events = laad_events()

if "ingelogde_speler" not in st.session_state:
    st.session_state["ingelogde_speler"] = None
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

st.title(f"⚽ BTLB Spelers- & Clubportaal — {config['actieve_ploeg']}")

# --- LOGIN SCHERM ---
if not st.session_state["ingelogde_speler"]:
    st.subheader("🔐 Inloggen voor Spelers & Kapitein")
    ploeg_leden = btlb_data.get(config["actieve_reeks"], {}).get(config["actieve_ploeg"], [])
    keuzes = ploeg_leden + ["⚙️ Clubbeheer / Kapitein"]

    col1, col2 = st.columns([2, 1])
    with col1:
        gekozen_user = st.selectbox("Kies jouw naam:", keuzes)
    with col2:
        pin_input = st.text_input("4-cijferige Pincode:", type="password", max_chars=8)

    if st.button("Inloggen", type="primary"):
        if gekozen_user == "⚙️ Clubbeheer / Kapitein":
            if pin_input == config.get("admin_pin", "9999"):
                st.session_state["ingelogde_speler"] = "Clubbeheerder"
                st.session_state["is_admin"] = True
                st.rerun()
            else:
                st.error("Onjuiste beheerderspincode.")
        else:
            juiste_pin = config.get("pincodes", {}).get(gekozen_user, "1234")
            if pin_input == juiste_pin:
                st.session_state["ingelogde_speler"] = gekozen_user
                st.session_state["is_admin"] = False
                registreer_login(gekozen_user, config["actieve_ploeg"])
                st.rerun()
            else:
                st.error("Onjuiste pincode. Vraag je pincode aan je kapitein (standaard: 1234).")
    st.stop()

# --- INLOGBALK BOVENAAN ---
c_top1, c_top2 = st.columns([4, 1])
with c_top1:
    st.success(f"Ingelogd als: **{st.session_state['ingelogde_speler']}**  |  Ploeg: **{config['actieve_ploeg']}**")
with c_top2:
    if st.button("Uitloggen"):
        st.session_state["ingelogde_speler"] = None
        st.session_state["is_admin"] = False
        st.rerun()

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Mijn Analyse & Video's",
    "⚔️ Tegenstander Scouten",
    "🏋️ Mijn Trainingsschema & Progressie",
    "⚙️ Club & Pincode Instellingen"
])

# --- TAB 1: EIGEN ANALYSE & GESORTEERDE VIDEO'S ---
with tab1:
    doel_speler = st.session_state["ingelogde_speler"]
    if st.session_state["is_admin"]:
        ploeg_leden = btlb_data.get(config["actieve_reeks"], {}).get(config["actieve_ploeg"], [])
        if ploeg_leden:
            doel_speler = st.selectbox("Bekijk analyse van ploegmaat:", ploeg_leden)

    info = analyseer_speler_data(doel_speler, alle_events)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("3-Stang Rendement", f"{info['pct_3']}%", f"{info['goals_3']}/{info['schoten_3']} goals")
    m2.metric("Dodelijkste Killer-schot", info["killer"])
    m3.metric("Pass 5 -> 3", f"{info['p5_ok']}/{info['p5_tot']}", f"Meest geblokt: {info['zwakste_baan']}")
    m4.metric("Voorkeur Doelhoek", info["fav_hoek"], f"Keeper kwetsbaar: {info['zwakste_zone']}")

    if config.get("onedrive_video_url"):
        st.info(f"🎬 **Slow-motion Video-herhalingen:** [Open gedeelde OneDrive-map]({config['onedrive_video_url']})  →  Kies daar eerst de map van de **Speelavond** en daarna jouw **Spelersmap**.")

    if info["events"]:
        st.subheader("🎞️ Jouw Acties & Video-overzicht per Speelavond")
        f_col1, f_col2 = st.columns(2)
        avonden = sorted({f"{e.get('Datum', '')} (vs {e.get('Tegenstander', 'Onbekend')})" for e in info["events"]}, reverse=True)
        gekozen_avond = f_col1.selectbox("Filter op Speelavond:", ["Alle speelavonden"] + avonden)
        gekozen_actie = f_col2.selectbox("Filter op Actie:", ["Alle acties", "Alleen Goals", "Reddingen", "Passes 5 -> 3"])

        gefilterde_clips = []
        for ev in reversed(info["events"]):
            avond_lbl = f"{ev.get('Datum', '')} (vs {ev.get('Tegenstander', 'Onbekend')})"
            if gekozen_avond != "Alle speelavonden" and avond_lbl != gekozen_avond:
                continue
            act = ev.get("Actie") or ""
            if gekozen_actie == "Alleen Goals" and "GOAL" not in act:
                continue
            if gekozen_actie == "Reddingen" and "REDDING" not in act:
                continue
            if gekozen_actie == "Passes 5 -> 3" and "PASS_5_3" not in act:
                continue

            ruw_pad = (ev.get("Video_Pad") or "").replace("\\", "/")
            korte_map = "/".join(ruw_pad.split("/")[-3:]) if "/" in ruw_pad else ruw_pad
            gefilterde_clips.append({
                "Datum": ev.get("Datum", ""),
                "Match": f"M{ev.get('Match', '')}",
                "Tegenstander": ev.get("Tegenstander", ""),
                "Actie": act,
                "Variant": ev.get("Variant", ""),
                "Snelheid (km/u)": ev.get("Snelheid_kmh", ""),
                "Map in OneDrive": korte_map or "Nog geen clip"
            })

        st.dataframe(gefilterde_clips, use_container_width=True)
    else:
        st.warning("Nog geen 200fps camera-acties opgeslagen voor deze speler.")

# --- TAB 2: TEGENSTANDER SCOUTEN ---
with tab2:
    st.subheader("⚔️ Tegenstander Scouting & Strijdplan")
    c_t1, c_t2 = st.columns(2)
    alle_reeksen = list(btlb_data.keys())
    idx_tr = alle_reeksen.index(config["actieve_reeks"]) if config["actieve_reeks"] in alle_reeksen else 0
    t_reeks = c_t1.selectbox("Kies Reeks van tegenstander:", alle_reeksen, index=idx_tr)

    ploegen_in_reeks = sorted(list(btlb_data.get(t_reeks, {}).keys()))
    t_ploeg = c_t2.selectbox("Kies Ploeg:", ploegen_in_reeks)

    spelers_in_ploeg = btlb_data.get(t_reeks, {}).get(t_ploeg, [])
    if not spelers_in_ploeg:
        st.info("Geen spelers gevonden in deze ploeg.")
    else:
        gekozen_tegen = st.selectbox("Kies Speler om te scouten:", spelers_in_ploeg)
        t_info = analyseer_speler_data(gekozen_tegen, alle_events)

        st.markdown(f"**BTLB Profiel:** `{gekozen_tegen}`  |  **200fps Camera-acties:** `{t_info['acties']}`")
        if t_info["acties"] == 0:
            st.info("ℹ️ Nog geen eigen 200fps camera-beelden van deze speler. Zodra jullie tegen deze ploeg spelen onder de camera, verschijnen hier automatisch zijn dodelijkste schot en open doelzone!")
        else:
            st.error(f"🚨 **Verdediging:** Dek vooral **{t_info['fav_var']}** richting **{t_info['fav_hoek']}** af (Killer-schot: {t_info['killer']}).")
            st.success(f"🎯 **Aanval:** Mik tegen zijn verdediging op zone **{t_info['zwakste_zone']}**.")

# --- TAB 3: PERSOONLIJK TRAININGSSCHEMA & JAARPROGRESSIE ---
with tab3:
    train_sp = st.session_state["ingelogde_speler"]
    if st.session_state["is_admin"]:
        ploeg_leden = btlb_data.get(config["actieve_reeks"], {}).get(config["actieve_ploeg"], [])
        if ploeg_leden:
            train_sp = st.selectbox("Training voor speler:", ploeg_leden, key="tr_sp_sel")

    t_data = analyseer_speler_data(train_sp, alle_events)
    modus = st.radio("Kies je trainingsvorm:", ["1P (Solo)", "1v1 (Duel)", "2v2 (Koppel)"], horizontal=True)

    st.markdown(f"""
    ### 📋 Jouw 4 Oefenblokken op maat ({modus})
    1. **Blok 1 — Balcontrole (5 min):** 20x strak doodleggen op 3-stang & tik-tak zonder balverlies.
    2. **Blok 2 — Pass 5 → 3 (8 min):** 25x passen via **{t_data['zwakste_baan']}** (je meest geblokte lijn).
    3. **Blok 3 — Afwerking (10 min):** 15x **{t_data['killer']}** + 10x variatie naar de andere hoek.
    4. **Blok 4 — Verdediging & Tijdsdruk (7 min):** 15x plankcontrole op harde ballen + 10x schot onder 12s-klokdruk.
    """)

    c_b1, c_b2, c_b3, c_b4 = st.columns(4)
    b1_ok = c_b1.number_input("Blok 1 geslaagd (/20)", 0, 50, 15)
    b2_ok = c_b2.number_input("Blok 2 geslaagd (/25)", 0, 50, 18)
    b3_ok = c_b3.number_input("Blok 3 geslaagd (/25)", 0, 50, 17)
    b4_ok = c_b4.number_input("Blok 4 geslaagd (/20)", 0, 50, 14)

    if st.button("🏁 Training Opslaan & Voortgang Bekijken", type="primary"):
        tot_ok = b1_ok + b2_ok + b3_ok + b4_ok
        tot_pct = round((tot_ok / 90.0) * 100, 1)
        vandaag = datetime.now().strftime("%d-%m-%Y")
        veldnamen = ["Datum", "Seizoen", "Modus", "Speler", "Duur_Min", "Blok1", "Blok2", "Blok3", "Blok4", "Totaal_Pct", "Focus"]
        bestaat = os.path.exists(TRAINING_CSV)
        with open(TRAINING_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=veldnamen)
            if not bestaat:
                w.writeheader()
            w.writerow({
                "Datum": vandaag, "Seizoen": bepaal_seizoen_uit_datum(vandaag), "Modus": modus.split(" ").pop(0),
                "Speler": train_sp, "Duur_Min": 30, "Blok1": f"{b1_ok}/20", "Blok2": f"{b2_ok}/25",
                "Blok3": f"{b3_ok}/25", "Blok4": f"{b4_ok}/20", "Totaal_Pct": tot_pct, "Focus": t_data["zwakste_baan"]
            })
        st.success(f"Training opgeslagen! Totaalscore vandaag: **{tot_pct}%** ({tot_ok}/90).")

    if os.path.exists(TRAINING_CSV):
        with open(TRAINING_CSV, "r", encoding="utf-8") as f:
            hist = [r for r in csv.DictReader(f) if train_sp.split("(").pop(0).strip().lower() in (r.get("Speler") or "").lower()]
        if hist:
            st.subheader("📈 Jouw Jaar- & Seizoensprogressie")
            st.dataframe(list(reversed(hist)), use_container_width=True)
        st.markdown("---")
    st.subheader("⚡ Thuis Reactie- & Geluidstrainer (3-Stang & Pass 5 → 3)")
    st.info("ℹ️ **Thuis-modus (alleen geluidssignaal):** Oefen je reactie op het onvoorspelbare piepje (3–15 sec). Voor automatische analyse van reactietijd (ms), juistheid en balsnelheid (km/u) train je op de clubtafel onder de 200fps camera.")

    alle_drills = [
        "3-stang: Frontpin Schot",
        "3-stang: Backpin Schot",
        "3-stang: Pull Shot (Trek Kort / Midden / Lang)",
        "3-stang: Push Shot (Duw Kort / Midden / Lang)",
        "3-stang: Schijn Trek -> Duw",
        "3-stang: Schijn Duw -> Trek",
        "3-stang: Snake / Jet (Rond de bal draaien)",
        "3-stang: Tic-Tac Schot op doel",
        "Pass 5 -> 3: Langs de band (Muur)",
        "Pass 5 -> 3: Rechtdoor",
        "Pass 5 -> 3: Schuin / Diagonaal",
        "Pass 5 -> 3: Tic-Tac Opbouw"
    ]
    gekozen_drills = st.multiselect(
        "Kies welke 3-stang schoten & Pass 5 → 3 je wilt oefenen:",
        alle_drills,
        default=["3-stang: Pull Shot (Trek Kort / Midden / Lang)", "3-stang: Push Shot (Duw Kort / Midden / Lang)", "Pass 5 -> 3: Langs de band (Muur)"]
    )
    c_r1, c_r2 = st.columns(2)
    aantal_pogingen = c_r1.number_input("Aantal herhalingen:", min_value=5, max_value=50, value=15, step=5)
    terugleg_sec = c_r2.number_input("Bal terugleggen (seconden):", min_value=2, max_value=10, value=4, step=1)

    if gekozen_drills:
        drills_json = json.dumps(gekozen_drills)
        html_trainer = f"""
        <div style="background:#0f172a;border:2px solid #334155;border-radius:12px;padding:18px;color:white;font-family:sans-serif;text-align:center;">
          <div id="teller" style="color:#94a3b8;font-weight:bold;font-size:14px;">Klaar voor {aantal_pogingen} pogingen</div>
          <div id="doel" style="color:#fde047;font-weight:bold;font-size:22px;margin:10px 0;">Druk op START om te beginnen</div>
          <div id="status" style="color:#38bdf8;font-weight:bold;font-size:18px;margin-bottom:14px;">🔔 Lage tik = timer loopt (3-15s) | Hoge piep = NU UITVOEREN!</div>
          <button onclick="startTrainer()" style="background:#16a34a;color:white;border:none;padding:12px 24px;font-size:16px;font-weight:bold;border-radius:8px;cursor:pointer;margin-right:8px;">▶️ START GELUIDSTRAINER</button>
          <button onclick="stopTrainer()" style="background:#dc2626;color:white;border:none;padding:12px 20px;font-size:16px;font-weight:bold;border-radius:8px;cursor:pointer;">⏹️ STOP</button>
        </div>
        <script>
          const drills = {drills_json};
          const maxPog = {int(aantal_pogingen)};
          const terugMs = {int(terugleg_sec) * 1000};
          let actief = false, pog = 0, t1 = null, t2 = null, audioCtx = null;

          function piep(freq, duur) {{
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            if (audioCtx.state === 'suspended') audioCtx.resume();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = 'sine';
            osc.frequency.value = freq;
            gain.gain.value = 0.25;
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            setTimeout(() => osc.stop(), duur);
          }}

          function volgende() {{
            if (!actief) return;
            if (pog >= maxPog) {{
              actief = false;
              document.getElementById('doel').innerText = "✅ SESSIE VOLTOOID!";
              document.getElementById('status').innerText = "Alle " + maxPog + " pogingen afgewerkt.";
              document.getElementById('status').style.color = "#4ade80";
              return;
            }}
            pog++;
            const gekozen = drills[Math.floor(Math.random() * drills.length)];
            document.getElementById('teller').innerText = "Poging " + pog + " van " + maxPog;
            document.getElementById('doel').innerText = "DOEL: " + gekozen;
            document.getElementById('status').innerText = "🔄 Leg de bal klaar onder de 3- of 5-stang (" + (terugMs/1000) + "s)...";
            document.getElementById('status').style.color = "#38bdf8";

            t1 = setTimeout(() => {{
              if (!actief) return;
              piep(600, 100);
              document.getElementById('status').innerText = "🔇 Timer loopt (3-15s)... focus op het piepje!";
              document.getElementById('status').style.color = "#cbd5e1";
              const wacht = 3000 + Math.floor(Math.random() * 12000);
              t2 = setTimeout(() => {{
                if (!actief) return;
                piep(1400, 240);
                document.getElementById('status').innerText = "🔊 BEEP! NU UITVOEREN!";
                document.getElementById('status').style.color = "#4ade80";
                setTimeout(volgende, 1800);
              }}, wacht);
            }}, terugMs);
          }}

          function startTrainer() {{
            stopTrainer();
            actief = true;
            pog = 0;
            piep(600, 60);
            volgende();
          }}

          function stopTrainer() {{
            actief = false;
            clearTimeout(t1);
            clearTimeout(t2);
            document.getElementById('status').innerText = "Gestopt.";
          }}
        </script>
        """
        components.html(html_trainer, height=230)


# --- TAB 4: CLUBWISSEL & PINCODE BEHEER ---
with tab4:
    st.subheader("🔐 Mijn Persoonlijke Pincode")
    if not st.session_state["is_admin"]:
        st.info("Hier kun je jouw eigen persoonlijke pincode aanpassen. (Clubinstellingen zijn alleen zichtbaar voor de kapitein/beheerder.)")
        if not st.session_state["is_admin"] and st.session_state["ingelogde_speler"]:
            nieuwe_pin = st.text_input("Eigen nieuwe 4-cijferige pincode instellen:", max_chars=6)
            if st.button("Mijn pincode wijzigen") and len(nieuwe_pin) >= 4:
                config["pincodes"][st.session_state["ingelogde_speler"]] = nieuwe_pin
                sla_config_op(config)
                st.success("Jouw persoonlijke pincode is bijgewerkt!")
    else:
        reeksen = list(btlb_data.keys())
        idx_r = reeksen.index(config["actieve_reeks"]) if config["actieve_reeks"] in reeksen else 0
        nieuwe_reeks = st.selectbox("Actieve BTLB Reeks:", reeksen, index=idx_r)
        ploegen = sorted(list(btlb_data.get(nieuwe_reeks, {}).keys()))
        idx_p = ploegen.index(config["actieve_ploeg"]) if config["actieve_ploeg"] in ploegen else 0
        nieuwe_ploeg = st.selectbox("Actieve Club / Ploeg:", ploegen, index=idx_p)
        nieuwe_admin_pin = st.text_input("Beheerderspincode:", value=config.get("admin_pin", "9999"))
        nieuwe_od_url = st.text_input("Gedeelde OneDrive-link voor video-herhalingen:", value=config.get("onedrive_video_url", ""))

        st.markdown("#### Pincodes per ploegmaat")
        leden_nu = btlb_data.get(nieuwe_reeks, {}).get(nieuwe_ploeg, [])
        nieuwe_pins = dict(config.get("pincodes", {}))
        for lid in leden_nu:
            nieuwe_pins[lid] = st.text_input(f"Pincode voor {lid}:", value=nieuwe_pins.get(lid, "1234"), key=f"pin_{lid}")

        if st.button("💾 Club- & Pincode-instellingen Opslaan", type="primary"):
            config["actieve_reeks"] = nieuwe_reeks
            config["actieve_ploeg"] = nieuwe_ploeg
            config["admin_pin"] = nieuwe_admin_pin
            config["onedrive_video_url"] = nieuwe_od_url
            config["pincodes"] = nieuwe_pins
            sla_config_op(config)
            st.success(f"Instellingen opgeslagen! Het portaal staat nu ingesteld op **{nieuwe_ploeg}**.")
            st.markdown("---")
        st.subheader("👀 Inlogstatistieken & Activiteit van Spelers")
        if os.path.exists(LOGIN_LOG_CSV):
            with open(LOGIN_LOG_CSV, "r", encoding="utf-8") as f:
                log_rijen = list(csv.DictReader(f))
            if log_rijen:
                tellingen = {}
                laatste_keer = {}
                for r in log_rijen:
                    sp = r.get("Speler", "Onbekend")
                    tellingen[sp] = tellingen.get(sp, 0) + 1
                    laatste_keer[sp] = r.get("Tijdstip", "")

                overzicht = [
                    {"Speler": sp, "Aantal Logins": cnt, "Laatst Ingelogd": laatste_keer.get(sp, "")}
                    for sp, cnt in sorted(tellingen.items(), key=lambda x: x[1], reverse=True)
                ]
                st.dataframe(overzicht, use_container_width=True)
                with st.expander("Bekijk laatste 25 losse logins chronologisch"):
                    st.dataframe(list(reversed(log_rijen[-25:])), use_container_width=True)
            else:
                st.info("Er heeft nog niemand ingelogd sinds de start van het logboek.")
        else:
            st.info("Zodra de eerste speler inlogt, verschijnt hier automatisch het overzicht per speler.")
