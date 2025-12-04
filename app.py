import streamlit as st
import pandas as pd
import numpy as np
import math
import requests
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import copy  # Adicionado para deep copy

# Configuração de login usando st.secrets (para deployment seguro)
credentials = copy.deepcopy(dict(st.secrets['credentials']))  # Deep copy para mutável completo
cookie = dict(st.secrets['cookie'])
preauthorized = dict(st.secrets['preauthorized']) if 'preauthorized' in st.secrets else {}

authenticator = stauth.Authenticate(
    credentials,
    cookie['name'],
    cookie['key'],
    cookie['expiry_days'],
    preauthorized
)

login_result = authenticator.login(key='Login')
if login_result is not None:
    name, authentication_status, username = login_result
else:
    st.error("Login failed to render. Check library version or config.")

if st.session_state["authentication_status"]:
    authenticator.logout('Logout', 'main')
    st.write(f'Bem-vindo *{st.session_state["name"]}*')

    # Carregar cidades da folha "Locais" do Excel
    locais_df = pd.read_excel('Climatologia_8.xlsx', sheet_name='Locais', header=None)
    cidades_permitidas = sorted(locais_df[0].dropna().unique().tolist())  # Remove duplicatas e ordena

    # Dicionário hardcoded de mappings (baseado em matches reais da API IPMA)
    # Expandi com exemplos da sua lista "Locais" – adicione mais manualmente se necessário
    city_to_id = {
        'Portimão': '1210878',  # Correto: Portimão (Aeródromo)
        'Lisboa': '1200535',    # Correto: Lisboa (Geofísico)
        'Porto': '1200545',     # Correto: Porto, Pedras Rubras (Aeródromo)
        'Angra do Heroísmo': '1200511',  # Correto
        'Braga': '1210622',     # Correto: Braga, Merelim
        'Faro': '1200554',      # Correto: Faro (Aeródromo)
        'Beja': '1200571',      # Atualizado para Beja (Aeródromo) com dados recentes
        'Évora': '1200843',     # Correto: Évora (Aeródromo)
        'Coimbra': '1200559',   # Correto: Coimbra / Cernache
        'Viseu': '1240675',     # Correto: Viseu (Cidade)
        'Bragança': '1200575',  # Atualizado
        'Castelo Branco': '1200570',  # Atualizado
        'Guarda': '1200562',
        'Leiria': '1210718',    # Atualizado para Leiria (Aeródromo) - o ID anterior não tem dados
        'Santarém': '1200568',
        'Setúbal': '1210770',   # Atualizado
        'Aveiro': '1210702',
        'Viana do Castelo': '1240610',
        'Funchal': '1200548',
        'Ponta Delgada': '1210513',
        'Amadora': '1210881',   # Atualizado para Sintra/Granja do Marquês (close to Amadora with data)
        'Abrantes': '1210812',  # Alvega
        'Chaves': '1210616',    # Chaves (Aeródromo)
        'Espinho': '1210704',   # Espinho
        'Estremoz': '1210837',  # Estremoz
        'Lamego': '1210655',    # Lamego
        'Mafra': '1210747',     # Mafra
        'Santa Margarida da Coutada': '1210800',  # Santa Margarida da Coutada
        'São Jacinto': '1210704',  # São Jacinto (same as Espinho)
        'Tavira': '1210883',    # Tavira
        'Tomar': '1210724',     # Tomar, Valdonas
        'Vila Nova de Gaia': '1240903',
        'Vila Real': '1240566', # Vila Real (Cidade)
        'Vendas Novas': '1210840',  # Vendas Novas
        'Alcochete': '5210758', # Alcochete / Campo Tiro
        'Sesimbra': '1210770',  # Adicionado: Marco do Grilo, Sesimbra (usando ID de Setúbal, estação próxima)
        # Adicione mais da "Locais" com IDs correspondentes (consulte https://api.ipma.pt/open-data/observation/meteorology/stations/stations.json para matches)
        # Ex.: Se "Albufeira" não match exato, ignore ou mapeie para próximo como "Faro"
    }

    # Filtrar dropdown apenas para cidades da "Locais" com mapping válido
    cidades_disponiveis = sorted(city_to_id.keys())  # Use todas as chaves do dictionary, em ordem alfabética

    # Carregar tabelas de CSV com correções (separador ajustado para ',', encoding para BOM, conversão numérica)
    tabela_iii = pd.read_csv('tabela_iii.csv', skiprows=1, index_col=0, encoding='utf-8-sig')
    tabela_iii.index = pd.to_numeric(tabela_iii.index, errors='coerce')
    tabela_iii.columns = pd.to_numeric(tabela_iii.columns)
    tabela_iii = tabela_iii.apply(pd.to_numeric, errors='coerce')  # Converte valores como '_' para NaN

    tabela_iiibis = pd.read_csv('tabela_iiibis.csv', encoding='utf-8-sig')

    tabela_iv = pd.read_csv('tabela_iv.csv', encoding='utf-8-sig')  # Default sep=','
    tabela_iv['ts'] = pd.to_numeric(tabela_iv['ts'], errors='coerce')
    tabela_iv['tm'] = pd.to_numeric(tabela_iv['tm'], errors='coerce')
    tabela_iv['tv'] = pd.to_numeric(tabela_iv['tv'], errors='coerce')  # Converte valores como '-' para NaN

    # Função de Stull para tm (°C)
    def stull_wet_bulb(T, RH):
        import math
        tw = T * math.atan(0.151977 * (RH + 8.313659)**0.5) + math.atan(T + RH) - math.atan(RH - 1.676331) + 0.00391838 * RH**1.5 * math.atan(0.023101 * RH) - 4.686035
        return tw

    # Fetch dados IPMA (versão corrigida)
    def get_ipma_data(station_id):
        url = "https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json"
        response = requests.get(url)
        if response.status_code != 200:
            st.error(f"Erro na API IPMA: Código {response.status_code}. Verifique a conexão ou API.")
            return None, None, None
        data = response.json()
        # Obter timestamps ordenadas (mais recente primeiro)
        timestamps = sorted(data.keys(), reverse=True)
        # Iterar até encontrar dados válidos
        for ts in timestamps:
            if station_id in data[ts] and data[ts][station_id] is not None:
                obs = data[ts][station_id]
                try:
                    T = float(obs['temperatura'])
                    RH = float(obs['humidade'])
                    pressure = float(obs['pressao'])
                    if pressure == -99.0:
                        st.warning("Pressão ausente na API (-99.0 hPa). Usando valor padrão de 1013 hPa para cálculos.")
                        pressure = 1013.0
                    return T, RH, pressure
                except KeyError as e:
                    st.error(f"Dados incompletos para '{station_id}' em '{ts}': Campo '{e}' ausente.")
                    return None, None, None
        st.warning(f"Nenhuma observação recente encontrada para a estação '{station_id}'. Tente outra cidade ou verifique a API IPMA.")
        return None, None, None

    # Lookups com closest match
    def get_P(ts, delta, tabela_iii):
        ts_rounded = round(ts)
        delta_rounded = round(delta)
        if ts_rounded not in tabela_iii.index:
            closest_ts = tabela_iii.index[np.abs(tabela_iii.index - ts_rounded).argmin()]
        else:
            closest_ts = ts_rounded
        row = tabela_iii.loc[closest_ts]
        if delta_rounded not in row.index:
            closest_delta = row.index[np.abs(row.index - delta_rounded).argmin()]
        else:
            closest_delta = delta_rounded
        return row[closest_delta]

    def get_tv_tl(P, tabela_iiibis):
        closest = tabela_iiibis.iloc[(tabela_iiibis['P'] - P).abs().argsort()[:1]]
        return closest['tv'].values[0], closest['tl'].values[0]

    def get_tv_classB(ts_F, tm_F, tabela_iv):
        tabela_iv_clean = tabela_iv.dropna(subset=['ts', 'tm', 'tv'])
        closest = tabela_iv_clean.iloc[((tabela_iv_clean['ts'] - ts_F).abs() + (tabela_iv_clean['tm'] - tm_F).abs()).argsort()[:1]]
        if not closest.empty:
            return closest['tv'].values[0]
        return None

    # Formulário
    st.title("Climatologia Aplicada a Paióis")
    cidade = st.selectbox("Cidade", cidades_disponiveis)
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
                # Depuração atualizada para classe A
                st.write(f"ts arredondado={ts_rounded}ºC")
                st.write(f"ts-tm= {round(delta)}ºC")
                P = get_P(ts_rounded, round(delta), tabela_iii)
                st.write(f"Peso em gramas (g/m³) ={P}")
                if P:
                    tv, tl = get_tv_tl(P, tabela_iiibis)
                    if ti >= tv:
                        resultado = "ti ≥ tv – O paiol deve ser ventilado durante todo o tempo em que as condições atmosféricas o permitam."
                    elif tv > ti >= tl:
                        resultado = "tv > ti ≥ tl – O paiol deve ser ventilado rapidamente, apenas durante o tempo estritamente necessário para lançar uma corrente de ar que renove o ar interior."
                    else:
                        resultado = "tl > ti – O paiol deve manter-se fechado."
                else:
                    resultado = "Fora da tabela - Condições fora do range."
            else:  # Classe B
                ts_F = (ts_rounded * 9/5) + 32
                tm_F = (tm_rounded * 9/5) + 32
                tv_F = get_tv_classB(round(ts_F), round(tm_F), tabela_iv)
                # Depuração atualizada para classe B
                st.write(f"ts arredondado={round(ts_F)}ºF")
                st.write(f"tm={round(tm_F)}ºF")
                st.write(f"tv={tv_F}ºF")
                if tv_F:
                    tv = (tv_F - 32) * 5/9
                    if ti > tv:
                        resultado = "ti > tv – ventilar"
                    else:
                        resultado = "ti < tv - manter fechado"
                else:
                    resultado = "Fora da tabela - Condições fora do range."

            st.success(f"Resultado: {resultado}")
            st.write(f"Dados: T={T}°C, RH={RH}%, Pressão={pressure}hPa, tm={tm:.2f}°C")

elif st.session_state["authentication_status"] is False:
    st.error('Username/password incorreto')
elif st.session_state["authentication_status"] is None:
    st.warning('Por favor insira username e password')