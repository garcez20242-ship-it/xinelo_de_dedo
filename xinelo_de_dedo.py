import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v8.9", layout="wide", page_icon="🩴")

# --- 2. CONSTANTES ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- 3. FUNÇÕES TÉCNICAS INTEGRAIS (NÃO SIMPLIFICADAS) ---

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
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone"],
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

# --- 5. CABEÇALHO ---
st.title("🩴 Sistema de Gestão Master")
st.divider()

# --- 6. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Sistema de Gestão - Xinelo de Dedo")
    if st.button("🔄 Sincronizar Agora", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    
    st.divider()
    
    # Lembretes (Contas)
    st.subheader("📌 Contas a Pagar")
    contas = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'conta']
    if not contas.empty:
        for _, r in contas.iterrows():
            if str(r['Nome']).strip(): st.warning(f"**{r['Nome']}**\n📅 {r['Vencimento']}\n💰 R$ {r['Valor']}")
    
    # Pendências (Clientes)
    st.subheader("👤 Pendências de Clientes")
    pends_cli = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'cliente']
    if not pends_cli.empty:
        for _, r in pends_cli.iterrows():
            if str(r['Nome']).strip(): st.error(f"**{r['Nome']}**\n💰 R$ {r['Valor']}")

    with st.expander("🚨 Estoque Baixo"):
        for _, row in df_est.iterrows():
            for t in TAMANHOS_PADRAO:
                if converter_para_numero(row[t]) < 5: st.write(f"• {row['Modelo']} ({t})")

# --- 7. ABAS ---
tabs = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "🧾 Histórico", "📅 Lembretes", "📦 Aquisições"])

with tabs[0]: # ESTOQUE
    st.subheader("📋 Inventário")
    st.dataframe(df_est, hide_index=True, use_container_width=True)

with tabs[1]: # VENDAS
    st.subheader("🛒 Registro de Vendas")
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", sorted(df_cli['Nome'].astype(str).unique()) + ["Avulso"])
        v_mod = st.selectbox("Modelo", sorted(df_est['Modelo'].astype(str).unique()))
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        v_pre = st.number_input("Preço", min_value=0.0)
        v_qtd = st.number_input("Qtd", min_value=1)
        if st.button("Adicionar"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            total, res = 0.0, []
            for it in st.session_state.cart:
                st.write(f"• {it['Mod']} x{it['Qtd']}")
                total += (it['Pre'] * it['Qtd'])
                res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            if st.button("Finalizar Venda"):
                df_e = df_est.copy()
                for i in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == i['Mod']][0]
                    df_e.at[idx, i['Tam']] = int(converter_para_numero(df_e.at[idx, i['Tam']]) - i['Qtd'])
                if salvar_dados_no_google("Estoque", df_e):
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(res), "Valor Total": total, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.session_state.cart = []; st.rerun()

with tabs[2]: # CLIENTES
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cli"):
        cn, cc, ct = st.text_input("Nome"), st.text_input("Cidade"), st.text_input("Telefone")
        if st.form_submit_button("Salvar"):
            nc = pd.DataFrame([{"Nome": cn, "Loja": cn, "Cidade": cc, "Telefone": ct}])
            if salvar_dados_no_google("Clientes", pd.concat([df_cli, nc], ignore_index=True)): st.rerun()
    st.dataframe(df_cli, use_container_width=True, hide_index=True)

with tabs[3]: # HISTÓRICO
    st.subheader("🧾 Histórico")
    if not df_ped.empty:
        df_h = df_ped[df_ped['Cliente'].astype(str).str.strip() != ""]
        for idx, r in df_h.iloc[::-1].iterrows():
            with st.container(border=True):
                c_h1, c_h2 = st.columns([0.8, 0.2])
                c_h1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']} | 💰 **R$ {converter_para_numero(r['Valor Total']):.2f}**")
                c_h1.caption(f"{r['Resumo']}")
                if c_h2.button("Excluir", key=f"del_{idx}"):
                    if salvar_dados_no_google("Pedidos", df_ped.drop(idx)): st.rerun()

with tabs[4]: # LEMBRETES
    st.subheader("📅 Lembretes")
    with st.form("f_lem"):
        lc, ln, lv, lval = st.selectbox("Tipo", ["Conta", "Cliente"]), st.text_input("Descrição"), st.text_input("Vencimento"), st.number_input("Valor")
        if st.form_submit_button("Agendar"):
            nl = pd.DataFrame([{"Data": get_data_hora(), "Nome": ln, "Vencimento": lv, "Valor": lval, "Categoria": lc}])
            if salvar_dados_no_google("Lembretes", pd.concat([df_lem, nl], ignore_index=True)): st.rerun()
    st.dataframe(df_lem, use_container_width=True, hide_index=True)

with tabs[5]: # AQUISIÇÕES (RESTRIÇÃO DE SIMPLIFICAÇÃO: FUNÇÃO COMPLETA)
    st.subheader("📦 Registro de Aquisições / Insumos")
    with st.form("f_ins"):
        i_desc = st.text_input("Descrição da Aquisição (Ex: Frete, Borracha, Tiras)")
        i_val = st.number_input("Valor Gasto (R$)", min_value=0.0)
        if st.form_submit_button("Registrar Aquisição"):
            if i_desc:
                nova_aq = pd.DataFrame([{"Data": get_data_hora(), "Descricao": i_desc, "Valor": i_val}])
                if salvar_dados_no_google("Insumos", pd.concat([df_ins, nova_aq], ignore_index=True)):
                    # Também registra no histórico para bater o caixa
                    log_aq = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "SAÍDA/INSUMO", "Resumo": i_desc, "Valor Total": -i_val, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log_aq], ignore_index=True))
                    st.success("Aquisição registrada e lançada no histórico!")
                    st.rerun()
    st.divider()
    st.write("📊 **Lista de Aquisições**")
    st.dataframe(df_ins, use_container_width=True, hide_index=True)
