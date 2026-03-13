import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v9.3", layout="wide", page_icon="🩴")

# --- 2. CONSTANTES ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- 3. FUNÇÕES TÉCNICAS INTEGRAIS ---

def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def converter_para_numero(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "" or str(valor).lower() == "nan":
            return 0.0
        limpo = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(limpo)
    except:
        return 0.0

def salvar_dados_no_google(aba, dataframe):
    try:
        df_para_salvar = dataframe.astype(str).replace(['nan', 'None', '<NA>'], '')
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_para_salvar)
        st.cache_data.clear()
        with st.spinner(f"Sincronizando {aba}..."):
            time.sleep(2.5) 
        return True
    except Exception as e:
        st.error(f"Erro na conexão: {e}")
        return False

# --- 4. CARREGAMENTO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_banco_completo():
    config_abas = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone", "Endereco"],
        "Insumos": ["Data", "Descricao", "Valor"],
        "Lembretes": ["Data", "Nome", "Vencimento", "Valor", "Categoria"]
    }
    resultado = {}
    for aba, colunas in config_abas.items():
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None:
                df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = [str(c).strip() for c in df.columns]
                for c in colunas:
                    if c not in df.columns: df[c] = ""
                if aba == "Estoque" and not df.empty:
                    df["Modelo"] = df["Modelo"].astype(str)
                    df = df.sort_values(by="Modelo", key=lambda x: x.str.lower())
                resultado[aba] = df
            else:
                resultado[aba] = pd.DataFrame(columns=colunas)
        except:
            resultado[aba] = pd.DataFrame(columns=colunas)
    return resultado

db = carregar_banco_completo()
df_est, df_ped, df_cli, df_ins, df_lem = db["Estoque"], db["Pedidos"], db["Clientes"], db["Insumos"], db["Lembretes"]

# --- 5. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    if st.button("🔄 Sincronizar Agora", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.divider()
    
    st.subheader("📌 Contas a Pagar")
    contas = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'conta']
    if not contas.empty:
        for _, r in contas.iterrows():
            if str(r['Nome']).strip(): st.info(f"**{r['Nome']}**\n📅 {r['Vencimento']} | 💰 R$ {r['Valor']}")
    
    st.subheader("👤 Pendências Clientes")
    pends = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'cliente']
    if not pends.empty:
        for _, r in pends.iterrows():
            if str(r['Nome']).strip(): st.error(f"**{r['Nome']}**\n💰 R$ {r['Valor']}")

    with st.expander("🚨 Ver Alerta de Estoque"):
        alertas = [f"{row['Modelo']} ({t})" for _, row in df_est.iterrows() for t in TAMANHOS_PADRAO if converter_para_numero(row[t]) < 5]
        if alertas:
            for a in alertas: st.write(f"• {a}")
        else: st.success("Tudo OK!")

# --- 6. ABAS ---
tabs = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "🧾 Histórico", "📅 Lembretes", "📦 Aquisição Chinelas", "🛠️ Insumos"])

with tabs[0]: # ESTOQUE
    st.subheader("📋 Inventário")
    st.dataframe(df_est, hide_index=True, use_container_width=True)
    with st.expander("✨ Cadastrar Novo Modelo"):
        with st.form("f_new_mod"):
            nm = st.text_input("Nome do Modelo")
            if st.form_submit_button("Criar"):
                if nm:
                    new = pd.DataFrame([{"Modelo": nm, **{t: 0 for t in TAMANHOS_PADRAO}}])
                    if salvar_dados_no_google("Estoque", pd.concat([df_est, new], ignore_index=True)): st.rerun()

with tabs[1]: # VENDAS
    st.subheader("🛒 Carrinho de Vendas")
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", sorted(df_cli['Nome'].astype(str).unique()) + ["Avulso"], key="sel_v_cli")
        v_mod = st.selectbox("Modelo", sorted(df_est['Modelo'].astype(str).unique()), key="sel_v_mod")
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="sel_v_tam")
        v_pre = st.number_input("Preço Unitário", min_value=0.0, key="num_v_pre")
        v_qtd = st.number_input("Qtd", min_value=1, key="num_v_qtd")
        if st.button("Adicionar Item"):
            if 'cv' not in st.session_state: st.session_state.cv = []
            st.session_state.cv.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
    with c2:
        if 'cv' in st.session_state and st.session_state.cv:
            tot, res = 0.0, []
            for i in st.session_state.cv:
                sub = i['Pre'] * i['Qtd']
                st.write(f"• {i['Mod']} ({i['Tam']}) x{i['Qtd']} = R${sub:.2f}")
                tot += sub
                res.append(f"{i['Mod']}({i['Tam']}x{i['Qtd']})")
            st.write(f"**Total: R$ {tot:.2f}**")
            if st.button("Finalizar Venda", type="primary"):
                df_e = df_est.copy()
                for i in st.session_state.cv:
                    idx = df_e.index[df_e['Modelo'] == i['Mod']][0]
                    df_e.at[idx, i['Tam']] = int(converter_para_numero(df_e.at[idx, i['Tam']]) - i['Qtd'])
                if salvar_dados_no_google("Estoque", df_e):
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": "VENDA: "+" | ".join(res), "Valor Total": tot, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.session_state.cv = []; st.rerun()

with tabs[2]: # CLIENTES
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cli"):
        cn, cc, ce, ct = st.text_input("Nome/Loja"), st.text_input("Cidade"), st.text_input("Endereço"), st.text_input("Telefone")
        if st.form_submit_button("Salvar"):
            nc = pd.DataFrame([{"Nome": cn, "Loja": cn, "Cidade": cc, "Telefone": ct, "Endereco": ce}])
            if salvar_dados_no_google("Clientes", pd.concat([df_cli, nc], ignore_index=True)): st.rerun()
    st.dataframe(df_cli, hide_index=True, use_container_width=True)

with tabs[3]: # HISTÓRICO
    st.subheader("🧾 Histórico")
    df_h = df_ped[df_ped['Data'].astype(str).str.strip() != ""] if not df_ped.empty else pd.DataFrame()
    if df_h.empty:
        st.info("🔎 Nenhum dado encontrado.")
    else:
        for idx, r in df_h.iloc[::-1].iterrows():
            with st.container(border=True):
                c_h1, c_h2 = st.columns([0.8, 0.2])
                cor = "green" if converter_para_numero(r['Valor Total']) > 0 else "red"
                c_h1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']} | 💰 <span style='color:{cor}'>**R$ {converter_para_numero(r['Valor Total']):.2f}**</span>", unsafe_allow_html=True)
                c_h1.caption(f"Detalhes: {r['Resumo']}")
                c_h2.button("📄 PDF", key=f"p_{idx}")
                if c_h2.button("🗑️", key=f"d_{idx}"):
                    if salvar_dados_no_google("Pedidos", df_ped.drop(idx)): st.rerun()

with tabs[4]: # LEMBRETES
    st.subheader("📅 Lembretes")
    with st.form("f_lem"):
        lc, ln, lv, lval = st.selectbox("Categoria", ["Conta", "Cliente"]), st.text_input("Nome"), st.text_input("Vencimento"), st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Agendar"):
            nl = pd.DataFrame([{"Data": get_data_hora(), "Nome": ln, "Vencimento": lv, "Valor": lval, "Categoria": lc}])
            if salvar_dados_no_google("Lembretes", pd.concat([df_lem, nl], ignore_index=True)): st.rerun()
    st.dataframe(df_lem, use_container_width=True, hide_index=True)

with tabs[5]: # AQUISIÇÃO CHINELAS
    st.subheader("📦 Entrada de Estoque (Chinelas)")
    ca1, ca2 = st.columns(2)
    with ca1:
        am, at, ap, aq = st.selectbox("Modelo", sorted(df_est['Modelo'].astype(str).unique()), key="am"), st.selectbox("Tamanho", TAMANHOS_PADRAO, key="at"), st.number_input("Custo Unit.", min_value=0.0, key="ap"), st.number_input("Qtd", min_value=1, key="aq")
        if st.button("Adicionar à Compra"):
            if 'ca' not in st.session_state: st.session_state.ca = []
            st.session_state.ca.append({"Mod": am, "Tam": at, "Qtd": aq, "Pre": ap})
    with ca2:
        if 'ca' in st.session_state and st.session_state.ca:
            ta, ra = 0.0, []
            for i in st.session_state.ca:
                sub = i['Pre'] * i['Qtd']
                st.write(f"➕ {i['Mod']} ({i['Tam']}) x{i['Qtd']} = R${sub:.2f}"); ta += sub; ra.append(f"{i['Mod']}({i['Tam']}x{i['Qtd']})")
            st.write(f"**Total Custo: R$ {ta:.2f}**")
            if st.button("Finalizar Entrada", type="primary"):
                df_e = df_est.copy()
                for i in st.session_state.ca:
                    idx = df_e.index[df_e['Modelo'] == i['Mod']][0]
                    df_e.at[idx, i['Tam']] = int(converter_para_numero(df_e.at[idx, i['Tam']]) + i['Qtd'])
                if salvar_dados_no_google("Estoque", df_e):
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "FORNECEDOR", "Resumo": "COMPRA CHINELA: "+" | ".join(ra), "Valor Total": -ta, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.session_state.ca = []; st.rerun()

with tabs[6]: # INSUMOS
    st.subheader("🛠️ Aquisição de Insumos (Gastos Gerais)")
    with st.form("f_ins"):
        desc = st.text_input("Descrição (Ex: 10kg de Cola, Frete Correios)")
        val = st.number_input("Valor Pago (R$)", min_value=0.0)
        if st.form_submit_button("Registrar Gasto"):
            if desc:
                ni = pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc, "Valor": val}])
                if salvar_dados_no_google("Insumos", pd.concat([df_ins, ni], ignore_index=True)):
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "INSUMO/GASTO", "Resumo": desc, "Valor Total": -val, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.rerun()
    st.dataframe(df_ins, use_container_width=True, hide_index=True)
