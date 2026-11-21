import streamlit as st
import json
import os
import csv
from datetime import datetime

BASIS_MAP = os.path.dirname(os.path.abspath(__file__))
SPELERS_JSON = os.path.join(BASIS_MAP, "btlb_spelers.json")
EVENTS_CSV = os.path.join(BASIS_MAP, "seizoen_events_btlb.csv")
TRAINING_CSV = os.path.join(BASIS_MAP, "training_historiek.csv")
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
    alle_tegenstanders = sorted({(e.get("Speler") or "").strip() for e in alle_events if (e.get("Speler") or "").strip()})
    if not alle_tegenstanders:
        st.info("Zodra de eerste wedstrijden onder de 200fps camera zijn gespeeld, kun je hier elke tegenstander opzoeken.")
    else:
        gekozen_tegen = st.selectbox("Kies een tegenstander:", alle_tegenstanders)
        t_info = analyseer_speler_data(gekozen_tegen, alle_events)
        st.write(f"**Geanalyseerde acties:** {t_info['acties']}")
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

# --- TAB 4: CLUBWISSEL & PINCODE BEHEER ---
with tab4:
    st.subheader("⚙️ Club-instellingen (Volgend seizoen eenvoudig wisselen van club)")
    if not st.session_state["is_admin"]:
        st.info("Log in als **⚙️ Clubbeheer / Kapitein** (standaard pincode: `9999`) om van club te wisselen of pincodes van spelers te beheren.")
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
