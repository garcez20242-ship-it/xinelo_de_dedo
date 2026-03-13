import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO (IDENTIDADE DO APP) ---
st.set_page_config(page_title="Gestão Master v8.8", layout="wide", page_icon="🩴")

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
    """Função mestre: mantém a barreira de 2.5s para evitar resets do Streamlit"""
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

# --- 4. CARREGAMENTO E ORDENAÇÃO A-Z ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_banco_completo():
    config_abas = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone"],
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
                
                # ORDENAÇÃO ALFABÉTICA PROTEGIDA
                if aba == "Estoque" and not df.empty:
                    df["Modelo"] = df["Modelo"].astype(str)
                    df = df.sort_values(by="Modelo", key=lambda x: x.str.lower())
                if aba == "Clientes" and not df.empty:
                    df["Nome"] = df["Nome"].astype(str)
                    df = df.sort_values(by="Nome", key=lambda x: x.str.lower())
                
                resultado[aba] = df
            else:
                resultado[aba] = pd.DataFrame(columns=colunas)
        except:
            resultado[aba] = pd.DataFrame(columns=colunas)
    return resultado

db = carregar_banco_completo()
df_est, df_ped, df_cli, df_lem = db["Estoque"], db["Pedidos"], db["Clientes"], db["Lembretes"]

# --- 5. CABEÇALHO ---
st.title("🩴 Sistema de Gestão Xinelo de Dedo")
st.caption(f"Status do Sistema: Online | Atualizado em: {get_data_hora()}")
st.divider()

# --- 6. BARRA LATERAL (FILTROS DE CATEGORIA) ---
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    if st.button("🔄 Forçar Sincronização", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    # Lembretes de Contas
    st.subheader("📌 Contas a Pagar")
    contas = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'conta']
    if not contas.empty:
        for _, r in contas.iterrows():
            if str(r['Nome']).strip():
                st.warning(f"**{r['Nome']}**\n📅 {r['Vencimento']}\n💰 R$ {r['Valor']}")
    
    st.divider()
    
    # Pendências de Clientes (Baseado nos Lembretes)
    st.subheader("👤 Pendências de Clientes")
    pends_cli = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'cliente']
    if not pends_cli.empty:
        for _, r in pends_cli.iterrows():
            if str(r['Nome']).strip():
                st.error(f"**{r['Nome']}**\n💰 R$ {r['Valor']}\nVencto: {r['Vencimento']}")

    st.divider()
    
    with st.expander("🚨 Estoque Baixo (< 5)"):
        alertas = []
        for _, row in df_est.iterrows():
            for t in TAMANHOS_PADRAO:
                qtd = converter_para_numero(row[t])
                if qtd < 5: alertas.append(f"{row['Modelo']} ({t}): {int(qtd)}")
        for a in alertas: st.write(f"• {a}")

# --- 7. ABAS PRINCIPAIS ---
tabs = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "🧾 Histórico", "📅 Lembretes"])

with tabs[0]: # ESTOQUE
    st.subheader("📋 Inventário Completo (A-Z)")
    st.dataframe(df_est, hide_index=True, use_container_width=True)
    with st.expander("✨ Cadastrar Novo Modelo"):
        with st.form("f_mod_v88"):
            n_m = st.text_input("Nome do Modelo")
            if st.form_submit_button("Salvar Modelo"):
                nova_l = pd.DataFrame([{"Modelo": n_m, **{t: 0 for t in TAMANHOS_PADRAO}}])
                if salvar_dados_no_google("Estoque", pd.concat([df_est, nova_l], ignore_index=True)): st.rerun()

with tabs[1]: # VENDAS
    st.subheader("🛒 Registro de Vendas")
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", sorted(df_cli['Nome'].astype(str).unique()) + ["Avulso"])
        v_mod = st.selectbox("Modelo", sorted(df_est['Modelo'].astype(str).unique()))
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        v_pre = st.number_input("Preço Unitário", min_value=0.0)
        v_qtd = st.number_input("Qtd", min_value=1)
        if st.button("Adicionar Item"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            total, resumo = 0.0, []
            for it in st.session_state.cart:
                st.write(f"• {it['Mod']} ({it['Tam']}) x{it['Qtd']}")
                total += (it['Pre'] * it['Qtd'])
                resumo.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            if st.button("Finalizar Pedido", type="primary"):
                df_est_atu = df_est.copy()
                for it in st.session_state.cart:
                    idx = df_est_atu.index[df_est_atu['Modelo'] == it['Mod']][0]
                    df_est_atu.at[idx, it['Tam']] = int(converter_para_numero(df_est_atu.at[idx, it['Tam']]) - it['Qtd'])
                if salvar_dados_no_google("Estoque", df_est_atu):
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(resumo), "Valor Total": total, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.session_state.cart = []
                    st.rerun()

with tabs[2]: # CLIENTES (RESTAURADA)
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cli_v88", clear_on_submit=True):
        c_n = st.text_input("Nome ou Loja")
        c_c = st.text_input("Cidade")
        c_t = st.text_input("Telefone")
        if st.form_submit_button("Cadastrar Cliente"):
            nova_c = pd.DataFrame([{"Nome": c_n, "Loja": c_n, "Cidade": c_c, "Telefone": c_t}])
            if salvar_dados_no_google("Clientes", pd.concat([df_cli, nova_c], ignore_index=True)):
                st.success("Cliente cadastrado!"); st.rerun()
    st.divider()
    st.dataframe(df_cli, use_container_width=True, hide_index=True)

with tabs[3]: # HISTÓRICO
    st.subheader("🧾 Histórico de Pedidos")
    if not df_ped.empty:
        # Exibe tudo que tenha Cliente ou Resumo preenchido
        df_h = df_ped[df_ped['Cliente'].astype(str).str.strip() != ""]
        if not df_h.empty:
            for idx, r in df_h.iloc[::-1].iterrows():
                with st.container(border=True):
                    c_h1, c_h2 = st.columns([0.8, 0.2])
                    c_h1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']} | 💰 **R$ {converter_para_numero(r['Valor Total']):.2f}**")
                    c_h1.caption(f"Resumo: {r['Resumo']} | Pagamento: {r['Status Pagto']}")
                    if c_h2.button("Excluir", key=f"del_v88_{idx}"):
                        if salvar_dados_no_google("Pedidos", df_ped.drop(idx)): st.rerun()
        else: st.info("Nenhum pedido registrado no histórico.")
    else: st.info("Aba de Pedidos está vazia.")

with tabs[4]: # LEMBRETES
    st.subheader("📅 Gestão de Lembretes e Pendências")
    with st.form("f_lem_v88", clear_on_submit=True):
        col_l1, col_l2 = st.columns(2)
        l_cat = col_l1.selectbox("O que é?", ["Conta", "Cliente"])
        l_nom = col_l2.text_input("Descrição/Nome")
        l_val = col_l1.number_input("Valor R$", min_value=0.0)
        l_ven = col_l2.text_input("Data de Vencimento")
        if st.form_submit_button("Adicionar Lembrete"):
            nova_lem = pd.DataFrame([{"Data": get_data_hora(), "Nome": l_nom, "Vencimento": l_ven, "Valor": l_val, "Categoria": l_cat}])
            if salvar_dados_no_google("Lembretes", pd.concat([df_lem, nova_lem], ignore_index=True)): st.rerun()
    st.divider()
    st.dataframe(df_lem, use_container_width=True, hide_index=True)
