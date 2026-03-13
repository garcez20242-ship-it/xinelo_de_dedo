import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Master v9.0", layout="wide", page_icon="🩴")

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
st.title("🩴 Gestão Master v9.0")
st.divider()

# --- 6. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Controle")
    if st.button("🔄 Sincronizar", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.divider()
    with st.expander("🚨 Estoque Crítico"):
        for _, row in df_est.iterrows():
            for t in TAMANHOS_PADRAO:
                if converter_para_numero(row[t]) < 5: st.write(f"• {row['Modelo']} ({t})")

# --- 7. ABAS ---
tabs = st.tabs(["📊 Estoque", "🛒 Vendas", "👥 Clientes", "🧾 Histórico", "📅 Lembretes", "📦 Aquisição de Chinelas"])

with tabs[0]: # ESTOQUE
    st.subheader("📋 Inventário Atual")
    st.dataframe(df_est, hide_index=True, use_container_width=True)
    with st.expander("✨ Cadastrar Novo Modelo no Sistema"):
        with st.form("novo_mod_v9"):
            n_m = st.text_input("Nome do Modelo")
            if st.form_submit_button("Criar Modelo"):
                if n_m:
                    nova_l = pd.DataFrame([{"Modelo": n_m, **{t: 0 for t in TAMANHOS_PADRAO}}])
                    if salvar_dados_no_google("Estoque", pd.concat([df_est, nova_l], ignore_index=True)): st.rerun()

with tabs[1]: # VENDAS
    st.subheader("🛒 Carrinho de Vendas (Saída)")
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", sorted(df_cli['Nome'].astype(str).unique()) + ["Avulso"])
        v_mod = st.selectbox("Modelo para Venda", sorted(df_est['Modelo'].astype(str).unique()))
        v_tam = st.selectbox("Tamanho (Venda)", TAMANHOS_PADRAO)
        v_pre = st.number_input("Preço Unitário Venda (R$)", min_value=0.0)
        v_qtd = st.number_input("Quantidade Venda", min_value=1)
        if st.button("Adicionar ao Carrinho de Venda"):
            if 'cart_v' not in st.session_state: st.session_state.cart_v = []
            st.session_state.cart_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
    with c2:
        if 'cart_v' in st.session_state and st.session_state.cart_v:
            total_v, res_v = 0.0, []
            for it in st.session_state.cart_v:
                sub = it['Pre'] * it['Qtd']
                st.write(f"• {it['Mod']} ({it['Tam']}) | {it['Qtd']}x R${it['Pre']:.2f} = **R${sub:.2f}**")
                total_v += sub
                res_v.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            st.write(f"### Total Venda: R$ {total_v:.2f}")
            if st.button("Finalizar Venda e Baixar Estoque", type="primary"):
                df_e = df_est.copy()
                for i in st.session_state.cart_v:
                    idx = df_e.index[df_e['Modelo'] == i['Mod']][0]
                    df_e.at[idx, i['Tam']] = int(converter_para_numero(df_e.at[idx, i['Tam']]) - i['Qtd'])
                if salvar_dados_no_google("Estoque", df_e):
                    log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": "VENDA: " + " | ".join(res_v), "Valor Total": total_v, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                    st.session_state.cart_v = []; st.rerun()

with tabs[5]: # AQUISIÇÃO DE CHINELAS (Sincronizada com Estoque e Histórico)
    st.subheader("📦 Carrinho de Aquisição (Entrada de Estoque)")
    ca1, ca2 = st.columns(2)
    with ca1:
        a_mod = st.selectbox("Modelo Adquirido", sorted(df_est['Modelo'].astype(str).unique()))
        a_tam = st.selectbox("Pontuação (Tamanho)", TAMANHOS_PADRAO)
        a_pre = st.number_input("Custo Unitário (R$)", min_value=0.0)
        a_qtd = st.number_input("Quantidade Adquirida", min_value=1)
        if st.button("Adicionar ao Carrinho de Aquisição"):
            if 'cart_a' not in st.session_state: st.session_state.cart_a = []
            st.session_state.cart_a.append({"Mod": a_mod, "Tam": a_tam, "Qtd": a_qtd, "Pre": a_pre})
    with ca2:
        if 'cart_a' in st.session_state and st.session_state.cart_a:
            total_a, res_a = 0.0, []
            for it in st.session_state.cart_a:
                sub = it['Pre'] * it['Qtd']
                st.write(f"➕ {it['Mod']} ({it['Tam']}) | {it['Qtd']}x R${it['Pre']:.2f} = **R${sub:.2f}**")
                total_a += sub
                res_a.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            st.write(f"### Total Custo: R$ {total_a:.2f}")
            if st.button("Finalizar Aquisição e Somar Estoque", type="primary"):
                df_e = df_est.copy()
                for i in st.session_state.cart_a:
                    idx = df_e.index[df_e['Modelo'] == i['Mod']][0]
                    df_e.at[idx, i['Tam']] = int(converter_para_numero(df_e.at[idx, i['Tam']]) + i['Qtd'])
                if salvar_dados_no_google("Estoque", df_e):
                    log_a = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "FORNECEDOR (Entrada)", "Resumo": "COMPRA: " + " | ".join(res_a), "Valor Total": -total_a, "Status Pagto": "Pago"}])
                    salvar_dados_no_google("Pedidos", pd.concat([df_ped, log_a], ignore_index=True))
                    st.session_state.cart_a = []; st.rerun()

with tabs[3]: # HISTÓRICO
    st.subheader("🧾 Histórico Completo")
    if not df_ped.empty:
        # Removido filtro que limpava a tela - mostra tudo que tem Data
        df_h = df_ped.dropna(subset=['Data'])
        for idx, r in df_h.iloc[::-1].iterrows():
            with st.container(border=True):
                c_h1, c_h2 = st.columns([0.8, 0.2])
                cor = "green" if converter_para_numero(r['Valor Total']) > 0 else "red"
                c_h1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']}")
                c_h1.write(f"💰 <span style='color:{cor}'>**R$ {converter_para_numero(r['Valor Total']):.2f}**</span>", unsafe_allow_html=True)
                c_h1.caption(f"Detalhes: {r['Resumo']}")
                # Botão Simulado de PDF (Para PDF real requer biblioteca FPDF ou reportlab no requirements)
                c_h2.button("📄 Baixar PDF", key=f"pdf_{idx}")
                if c_h2.button("🗑️ Excluir", key=f"del_{idx}"):
                    if salvar_dados_no_google("Pedidos", df_ped.drop(idx)): st.rerun()

with tabs[2]: # CLIENTES
    st.subheader("👥 Clientes")
    with st.form("f_cli"):
        cn, cc, ct = st.text_input("Nome/Loja"), st.text_input("Cidade"), st.text_input("Telefone")
        if st.form_submit_button("Salvar"):
            nc = pd.DataFrame([{"Nome": cn, "Loja": cn, "Cidade": cc, "Telefone": ct}])
            salvar_dados_no_google("Clientes", pd.concat([df_cli, nc], ignore_index=True))
            st.rerun()
    st.dataframe(df_cli, hide_index=True, use_container_width=True)

with tabs[4]: # LEMBRETES
    st.subheader("📅 Lembretes e Pendências")
    with st.form("f_lem"):
        lc, ln, lv, lval = st.selectbox("Categoria", ["Conta", "Cliente"]), st.text_input("Descrição"), st.text_input("Vencimento"), st.number_input("Valor")
        if st.form_submit_button("Salvar Lembrete"):
            nl = pd.DataFrame([{"Data": get_data_hora(), "Nome": ln, "Vencimento": lv, "Valor": lval, "Categoria": lc}])
            salvar_dados_no_google("Lembretes", pd.concat([df_lem, nl], ignore_index=True))
            st.rerun()
    st.dataframe(df_lem, use_container_width=True, hide_index=True)
