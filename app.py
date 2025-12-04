import streamlit as st
import pandas as pd
import numpy as np
import math
import requests
import streamlit_authenticator as stauth

# ==============================================================
# AUTENTICAÇÃO – versão final que funciona no Streamlit Cloud
# ==============================================================
# Conversão simples e segura (sem copy/deepcopy)
credentials   = dict(st.secrets["credentials"])
cookie        = dict(st.secrets["cookie"])

# Criar autenticador (sem parâmetros depreciados)
authenticator = stauth.Authenticate(
    credentials,
    cookie["name"],
    cookie["key"],
    cookie["expiry_days"]
)

# Login no "main" (a versão atual da biblioteca aceita "main" novamente)
name, authentication_status, username = authenticator.login("Login", "sidebar")

# ==============================================================
# APP PRINCIPAL
# ==============================================================
if st.session_state["authentication_status"]:
    authenticator.logout("Logout", "sidebar")
    st.write(f"Bem-vindo *{name}*")

    # ---------------------- CIDADES ----------------------
    city_to_id = {
        'Portimão': '1210878',
        'Lisboa': '1200535',
        'Porto': '1200545',
        'Angra do Heroísmo': '1200511',
        'Braga': '1210622',
        'Faro': '1200554',
        'Beja': '1200571',
        'Évora': '1200843',
        'Coimbra': '1200559',
        'Viseu': '1240675',
        'Bragança': '1200575',
        'Castelo Branco': '1200570',
        'Guarda': '1200562',
        'Leiria': '1210718',
        'Santarém': '1200568',
        'Setúbal': '1210770',
        'Aveiro': '1210702',
        'Viana do Castelo': '1240610',
        'Funchal': '1200548',
        'Ponta Delgada': '1210513',
        'Amadora': '1210881',
        'Abrantes': '1210812',
        'Chaves': '1210616',
        'Espinho': '1210704',
        'Estremoz': '1210837',
        'Lamego': '1210655',
        'Mafra': '1210747',
        'Santa Margarida da Coutada': '1210800',
        'São Jacinto': '1210704',
        'Tavira': '1210883',
        'Tomar': '1210724',
        'Vila Nova de Gaia': '1240903',
        'Vila Real': '1240566',
        'Vendas Novas': '1210840',
        'Alcochete': '5210758',
        'Sesimbra': '1210770',  # Marco do Grilo
    }

    cidades_disponiveis = sorted(city_to_id.keys())

    # ---------------------- TABELAS ----------------------
    tabela_iii = pd.read_csv('tabela_iii.csv', skiprows=1, index_col=0, encoding='utf-8-sig')
    tabela_iii.index = pd.to_numeric(tabela_iii.index, errors='coerce')
    tabela_iii.columns = pd.to_numeric(tabela_iii.columns)
    tabela_iii = tabela_iii.apply(pd.to_numeric, errors='coerce')

    tabela_iiibis = pd.read_csv('tabela_iiibis.csv', encoding='utf-8-sig')
    tabela_iv = pd.read_csv('tabela_iv.csv', encoding='utf-8-sig')
    tabela_iv['ts'] = pd.to_numeric(tabela_iv['ts'], errors='coerce')
    tabela_iv['tm'] = pd.to_numeric(tabela_iv['tm'], errors='coerce')
    tabela_iv['tv'] = pd.to_numeric(tabela_iv['tv'], errors='coerce')

    # ---------------------- FUNÇÕES ----------------------
    def stull_wet_bulb(T, RH):
        import math
        tw = T * math.atan(0.151977 * (RH + 8.313659)**0.5) + math.atan(T + RH) - math.atan(RH - 1.676331) + 0.00391838 * RH**1.5 * math.atan(0.023101 * RH) - 4.686035
        return tw

    def get_ipma_data(station_id):
        url = "https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json"
        response = requests.get(url)
        if response.status_code != 200:
            st.error(f"Erro API IPMA: {response.status_code}")
            return None, None, None
        data = response.json()
        for ts in sorted(data.keys(), reverse=True):
            if station_id in data[ts] and data[ts][station_id]:
                obs = data[ts][station_id]
                try:
                    T = float(obs['temperatura'])
                    RH = float(obs['humidade'])
                    pressure = float(obs.get('pressao', 1013))
                    if pressure == -99.0:
                        st.warning("Pressão ausente → usando 1013 hPa")
                        pressure = 1013.0
                    return T, RH, pressure
                except (KeyError, ValueError):
                    continue
        st.warning("Sem dados recentes")
        return None, None, None

    def get_P(ts, delta, tabela):
        ts_r = round(ts)
        delta_r = round(delta)
        row = tabela.loc[ts_r] if ts_r in tabela.index else tabela.iloc[(tabela.index - ts_r).abs().argmin()]
        return row[delta_r] if delta_r in row.index else row.iloc[(row.index - delta_r).abs().argmin()]

    def get_tv_tl(P, tabela):
        row = tabela.iloc[(tabela['P'] - P).abs().argsort()[:1]]
        return row['tv'].values[0], row['tl'].values[0]

    def get_tv_classB(ts_F, tm_F, tabela):
        clean = tabela.dropna(subset=['ts', 'tm', 'tv'])
        row = clean.iloc[((clean['ts'] - ts_F).abs() + (clean['tm'] - tm_F).abs()).argsort()[:1]]
        return row['tv'].values[0] if not row.empty else None

    # ---------------------- INTERFACE ----------------------
    st.title("Climatologia Aplicada a Paióis")
    cidade = st.selectbox("Cidade", cidades_disponiveis)
    ti = st.number_input("Temperatura Interior (°C)", value=20.0)
    classe = st.selectbox("Classe do Paiol", ["A", "B"])

    if st.button("Calcular"):
        T, RH, pressure = get_ipma_data(city_to_id[cidade])
        if T is not None:
            tm = stull_wet_bulb(T, RH)
            delta = T - tm
            ts_rounded = round(T)

            if classe == "A":
                st.write(f"ts arredondado = {ts_rounded}ºC | delta = {round(delta)}ºC")
                P = get_P(ts_rounded, round(delta), tabela_iii)
                st.write(f"P = {P} g/m³")
                if P:
                    tv, tl = get_tv_tl(P, tabela_iiibis)
                    if ti >= tv:
                        res = "Ventilar sempre que possível"
                    elif tv > ti >= tl:
                        res = "Ventilar rapidamente"
                    else:
                        res = "Manter fechado"
                else:
                    res = "Fora da tabela"
            else:
                ts_F = ts_rounded * 9/5 + 32
                tm_F = round(tm) * 9/5 + 32
                tv_F = get_tv_classB(round(ts_F), round(tm_F), tabela_iv)
                st.write(f"ts = {round(ts_F)}ºF | tm = {round(tm_F)}ºF | tv = {tv_F if tv_F else 'N/D'}ºF")
                if tv_F:
                    tv_c = (tv_F - 32) * 5/9
                    res = "Ventilar" if ti > tv_c else "Manter fechado"
                else:
                    res = "Fora da tabela"

            st.success(f"Resultado: {res}")
            st.write(f"T={T}°C | RH={RH}% | P={pressure}hPa | tm={tm:.2f}°C")

elif st.session_state["authentication_status"] is False:
    st.error("Username ou password incorretos")
elif st.session_state["authentication_status"] is None:
    st.warning("Por favor faça login")