import streamlit as st
import pandas as pd
import numpy as np
import math
import requests
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth

# Configuração de login (crie um config.yaml com credenciais)
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
)

login_result = authenticator.login(key='Login')
if login_result is not None:
    name, authentication_status, username = login_result
else:
    st.error("Login failed to render. Check library version or config.")

if st.session_state["authentication_status"]:
    authenticator.logout('Logout', 'main')
    st.write(f'Bem-vindo *{st.session_state["name"]}*')

    # Mapa de cidades para IDs IPMA (adicione mais da lista anterior)
    city_to_id = {
        'Portimão (Aeródromo)': '1210878',
        'Lisboa (Geofísico)': '1200535',
        'Porto, Pedras Rubras (Aeródromo)': '1200545',
        # Adicione outros, ex.: 'Braga, Merelim': '1210622'
    }

    # Carregar tabelas de CSV
    tabela_iii = pd.read_csv('tabela_iii.csv', index_col=0)  # ts como index, diferenças como colunas
    tabela_iiibis = pd.read_csv('tabela_iiibis.csv')  # P, tv, tl
    tabela_iv = pd.read_csv('tabela_iv.csv')  # ts_F, tm_F, tv_F

    # Função de Stull para tm (°C)
    def stull_wet_bulb(T, RH):
        import math
        tw = T * math.atan(0.151977 * (RH + 8.313659)**0.5) + math.atan(T + RH) - math.atan(RH - 1.676331) + 0.00391838 * RH**1.5 * math.atan(0.023101 * RH) - 4.686035
        return tw

    # Fetch dados IPMA (endpoint corrigido)
def get_ipma_data(station_id):
    url = "https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if station_id in data:
            last_obs = data[station_id][-1]  # Última observação
            try:
                return float(last_obs['temperatura']), float(last_obs['humidade']), float(last_obs['pressao'])
            except KeyError:
                st.error(f"Dados incompletos para a estação '{station_id}'.")
                return None, None, None
        else:
            st.error(f"ID da estação '{station_id}' não encontrado na API.")
            return None, None, None
    else:
        st.error(f"Erro na API IPMA: Código {response.status_code}. Verifique a conexão ou API.")
        return None, None, None

    # Lookups
    def get_P(ts, delta, tabela_iii):
        ts_rounded = round(ts)  # Arredonda como no Excel
        if ts_rounded in tabela_iii.index:
            row = tabela_iii.loc[ts_rounded]
            if delta in row.index:
                return row[delta]
        return None  # Fora da tabela

    def get_tv_tl(P, tabela_iiibis):
        # Match aproximado (interpolar ou closest)
        closest = tabela_iiibis.iloc[(tabela_iiibis['P'] - P).abs().argsort()[:1]]
        return closest['tv'].values[0], closest['tl'].values[0]

    def get_tv_classB(ts_F, tm_F, tabela_iv):
        match = tabela_iv[(tabela_iv['ts'] == ts_F) & (tabela_iv['tm'] == tm_F)]
        if not match.empty:
            return match['tv'].values[0]
        return None

    # Formulário
    st.title("Climatologia Aplicada a Paióis")
    cidade = st.selectbox("Cidade", list(city_to_id.keys()))
    ti = st.number_input("Temperatura Interior do Paiol (°C)", value=20.0)
    classe = st.selectbox("Classe do Paiol", ["A", "B"])

    if st.button("Calcular"):
        station_id = city_to_id[cidade]
        T, RH, pressure = get_ipma_data(station_id)
        if T is not None:
            tm = stull_wet_bulb(T, RH)
            delta = T - tm
            ts_rounded = round(T)
            tm_rounded = round(tm)

            if classe == "A":
                P = get_P(ts_rounded, round(delta), tabela_iii)
                if P:
                    tv, tl = get_tv_tl(P, tabela_iiibis)
                    if ti >= tv:
                        resultado = "ti ≥ tv – O paiol deve ser ventilado durante todo o tempo em que as condições atmosféricas o permitam."
                    elif tv > ti >= tl:
                        resultado = "tv > ti ≥ tl – O paiol deve ser ventilado rapidamente, apenas durante o tempo estritamente necessário para lançar uma corrente de ar que renove o ar interior."
                    else:
                        resultado = "tl > ti – O paiol deve manter-se fechado."
                else:
                    resultado = "Fora da tabela"
            else:  # Classe B
                ts_F = (ts_rounded * 9/5) + 32
                tm_F = (tm_rounded * 9/5) + 32
                tv_F = get_tv_classB(round(ts_F), round(tm_F), tabela_iv)
                if tv_F:
                    tv = (tv_F - 32) * 5/9
                    ti_F = (ti * 9/5) + 32  # Converter ti para °F se necessário, mas comparar em °C
                    if ti > tv:
                        resultado = "ti > tv – ventilar"
                    else:
                        resultado = "ti < tv - manter fechado"
                else:
                    resultado = "Fora da tabela"

            st.success(f"Resultado: {resultado}")
            st.write(f"Dados: T={T}°C, RH={RH}%, Pressão={pressure}hPa, tm={tm:.2f}°C")

elif st.session_state["authentication_status"] is False:
    st.error('Username/password incorreto')

elif st.session_state["authentication_status"] is None:
    st.warning('Por favor insira username e password')