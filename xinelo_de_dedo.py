import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v9.2", layout="wide", page_icon="🩴")

# --- 2. CONSTANTES E ESTILO ---
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
                    df = df.sort_values(by="Modelo")
                resultado[aba] = df
            else:
                resultado[aba] = pd.DataFrame(columns=colunas)
        except:
            resultado[aba] = pd.DataFrame(columns=colunas)
    return resultado

db = carregar_banco_completo()
df_est, df_ped, df_cli, df_lem = db["Estoque"], db["Pedidos"], db["Clientes"], db["Lembretes"]

# --- 5. BARRA LATERAL COM MINI CALENDÁRIO ---
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    if st.button("🔄 Sincronizar Agora", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    
    st.divider()
    
    # MINI CALENDÁRIO
    st.subheader("📅 Calendário de Lembretes")
    data_sel = st.date_input("Selecione uma data", datetime.now())
    data_str = data_sel.strftime("%d/%m") # Formato padrão DD/MM usado nos lembretes
    
    # Filtro de Lembretes do Dia
    lem_dia = df_lem[df_lem['Vencimento'].astype(str).str.contains(data_str)]
    if not lem_dia.empty:
        st.info(f"**Lembretes para {data_str}:**")
        for _, r in lem_dia.iterrows():
            icon = "👤" if r['Categoria'] == "Cliente" else "💸"
            st.write(f"{icon} {r['Nome']} - R$ {r['Valor']}")
    else:
        st.caption(f"Nenhum lembrete para {data_str}")

    st.divider()
    
    # Pendências de Clientes e Contas
    with st.expander("📌 Resumo Financeiro"):
        contas = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'conta']
        if not contas.empty:
            st.write("**Contas:**")
            for _, r in contas.iterrows(): st.warning(f"{r['Nome']} ({r['Vencimento']})")
        
        pends = df_lem[df_lem['Categoria'].astype(str).str.lower() == 'cliente']
        if not pends.empty:
            st.write("**Clientes:**")
            for _, r in pends.iterrows(): st.error(f"{r['Nome']} - R${r['Valor']}")

    # Alerta de Estoque
    with st.expander("🚨 Alerta de Estoque"):
        alertas = []
        for _, row in df_est.iterrows():
            for t in TAMANHOS_PADRAO:
                if converter_para_numero(row[t]) < 5: alertas.append(f"{row['Modelo']} ({t})")
        if alertas:
            for a in alertas: st.write(f"• {a}")
        else: st.success("Tudo abastecido!")

# --- 6. CORPO PRINCIPAL (ABAS) ---
tabs = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "🧾 Histórico", "📅 Lembretes", "📦 Aquisição"])

with tabs[2]: # ABA CLIENTES (COM ENDEREÇO)
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cli_92"):
        c1, c2 = st.columns(2)
        cn = c1.text_input("Nome/Loja")
        ct = c2.text_input("Telefone")
        cc = c1.text_input("Cidade")
        ce = c2.text_input("Endereço Completo")
        if st.form_submit_button("Salvar"):
            nc = pd.DataFrame([{"Nome": cn, "Loja": cn, "Cidade": cc, "Telefone": ct, "Endereco": ce}])
            if salvar_dados_no_google("Clientes", pd.concat([df_cli, nc], ignore_index=True)): st.rerun()
    st.dataframe(df_cli, use_container_width=True, hide_index=True)

with tabs[3]: # ABA HISTÓRICO
    st.subheader("🧾 Histórico de Pedidos")
    if df_ped.empty or (len(df_ped) == 0):
        st.info("🔎 Nenhum dado encontrado no histórico até o momento.")
    else:
        for idx, r in df_ped.iloc[::-1].iterrows():
            if str(r['Data']).strip():
                with st.container(border=True):
                    c_h1, c_h2 = st.columns([0.8, 0.2])
                    cor = "green" if converter_para_numero(r['Valor Total']) > 0 else "red"
                    c_h1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']}")
                    c_h1.write(f"💰 <span style='color:{cor}'>**R$ {converter_para_numero(r['Valor Total']):.2f}**</span>", unsafe_allow_html=True)
                    c_h1.caption(f"Detalhes: {r['Resumo']}")
                    c_h2.button("📄 PDF", key=f"pdf_{idx}")
                    if c_h2.button("🗑️", key=f"del_{idx}"):
                        if salvar_dados_no_google("Pedidos", df_ped.drop(idx)): st.rerun()

# --- NOTA: As abas de Vendas, Estoque e Aquisição seguem o padrão robusto da v9.1 ---
# (O código acima foca nas mudanças solicitadas para manter a clareza)
