import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão - Xinelo de Dedo", layout="wide", page_icon="🩴")

# --- 2. CONSTANTES ---
URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- 3. FUNÇÕES TÉCNICAS INTEGRAIS ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def converter_para_numero(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "" or str(valor).lower() == "nan": return 0.0
        return float(str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip())
    except: return 0.0

def salvar_dados_no_google(aba, dataframe):
    try:
        df_save = dataframe.astype(str).replace(['nan', 'None', '<NA>'], '')
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_save)
        st.cache_data.clear()
        with st.spinner(f"Sincronizando {aba}..."): time.sleep(2.5) 
        return True
    except Exception as e:
        st.error(f"Erro: {e}"); return False

# --- 4. CARREGAMENTO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_banco():
    config = {
        "Estoque": ["Modelo"] + TAMANHOS_PADRAO,
        "Pedidos": ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"],
        "Clientes": ["Nome", "Loja", "Cidade", "Telefone", "Endereco", "Forma Pagto"], # Coluna Restaurada
        "Insumos": ["Data", "Descricao", "Valor"],
        "Lembretes": ["Data", "Nome", "Vencimento", "Valor", "Categoria", "Status"]
    }
    res = {}
    for aba, cols in config.items():
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            for c in cols: 
                if c not in df.columns: df[c] = ""
            res[aba] = df
        except: res[aba] = pd.DataFrame(columns=cols)
    return res

db = carregar_banco()
df_est, df_ped, df_cli, df_ins, df_lem = db["Estoque"], db["Pedidos"], db["Clientes"], db["Insumos"], db["Lembretes"]

# --- 5. PAINEL FINANCEIRO ---
entradas = df_ped[df_ped['Valor Total'].apply(converter_para_numero) > 0]['Valor Total'].apply(converter_para_numero).sum()
saidas = abs(df_ped[df_ped['Valor Total'].apply(converter_para_numero) < 0]['Valor Total'].apply(converter_para_numero).sum())
saldo = entradas - saidas

st.title("Gestão - Xinelo de Dedo")
c_f1, c_f2, c_f3 = st.columns(3)
c_f1.metric("Faturação (Vendas)", f"R$ {entradas:,.2f}")
c_f2.metric("Custos (Stock/Insumos)", f"R$ {saidas:,.2f}")
c_f3.metric("Saldo Líquido", f"R$ {saldo:,.2f}")
st.divider()

# --- 6. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Painel")
    if st.button("🔄 Sincronizar", use_container_width=True): st.cache_data.clear(); st.rerun()
    st.divider()
    ativos = df_lem[df_lem['Status'].astype(str).str.lower() != 'concluido']
    
    st.subheader("📌 Contas")
    c_p = ativos[ativos['Categoria'] == 'Conta']
    if not c_p.empty:
        for idx, r in c_p.iterrows():
            st.info(f"**{r['Nome']}**\nVencto: {r['Vencimento']}\nR$ {r['Valor']}")
            if st.button("Pagar", key=f"pay_{idx}"):
                df_lem.at[idx, 'Status'] = 'Concluido'
                salvar_dados_no_google("Lembretes", df_lem); st.rerun()
    else: st.write("✅ Sem contas.")

    st.subheader("👤 Pendências Clientes")
    p_c = ativos[ativos['Categoria'] == 'Cliente']
    if not p_c.empty:
        for idx, r in p_c.iterrows():
            st.error(f"**{r['Nome']}**\nR$ {r['Valor']}")
            if st.button("Receber", key=f"rec_{idx}"):
                df_lem.at[idx, 'Status'] = 'Concluido'
                salvar_dados_no_google("Lembretes", df_lem); st.rerun()
    else: st.write("✅ Sem pendências.")

    with st.expander("🚨 Stock Crítico"):
        alertas = [f"{row['Modelo']} ({t})" for _, row in df_est.iterrows() for t in TAMANHOS_PADRAO if converter_para_numero(row[t]) < 5]
        for a in alertas: st.warning(a)

# --- 7. ABAS ---
tabs = st.tabs(["📊 Stock", "🛒 Vendas", "👥 Clientes", "🧾 Histórico", "📅 Lembretes", "🛠️ Insumos"])

with tabs[0]: # STOCK
    st.subheader("📋 Inventário")
    edit_est = st.data_editor(df_est, hide_index=True, use_container_width=True, key="ed_est")
    if st.button("Salvar Alterações de Stock"):
        salvar_dados_no_google("Estoque", edit_est); st.rerun()

with tabs[1]: # VENDAS
    st.subheader("🛒 Carrinho")
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", sorted(df_cli['Nome'].astype(str).unique()) + ["Avulso"])
        v_mod = st.selectbox("Modelo", sorted(df_est['Modelo'].astype(str).unique()))
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        
        qtd_atual = converter_para_numero(df_est[df_est['Modelo'] == v_mod][v_tam].values[0])
        st.write(f"Stock disponível: **{int(qtd_atual)}**")
        
        v_pre = st.number_input("Preço", min_value=0.0)
        v_qtd = st.number_input("Quantidade", min_value=1, step=1)
        
        if st.button("Adicionar"):
            if v_qtd > qtd_atual: st.error("⚠️ Quantidade superior ao stock!")
            else:
                if 'cv' not in st.session_state: st.session_state.cv = []
                st.session_state.cv.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
    with c2:
        if 'cv' in st.session_state and st.session_state.cv:
            tot, res = 0.0, []
            for i in st.session_state.cv:
                sub = i['Pre'] * i['Qtd']; tot += sub
                st.write(f"• {i['Mod']} ({i['Tam']}) x{i['Qtd']} = R${sub:.2f}")
                res.append(f"{i['Mod']}({i['Tam']}x{i['Qtd']})")
            if st.button("Finalizar Venda", type="primary"):
                df_e = df_est.copy()
                for i in st.session_state.cv:
                    idx = df_e.index[df_e['Modelo'] == i['Mod']][0]
                    df_e.at[idx, i['Tam']] = int(converter_para_numero(df_e.at[idx, i['Tam']]) - i['Qtd'])
                salvar_dados_no_google("Estoque", df_e)
                log = pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": "VENDA: "+" | ".join(res), "Valor Total": tot, "Status Pagto": "Pago"}])
                salvar_dados_no_google("Pedidos", pd.concat([df_ped, log], ignore_index=True))
                st.session_state.cv = []; st.rerun()

with tabs[2]: # CLIENTES (RESTAURADO COM FORMA DE PAGAMENTO)
    st.subheader("👥 Cadastro e Gestão de Clientes")
    # Edição direta na tabela
    edit_cli = st.data_editor(df_cli, hide_index=True, use_container_width=True, key="ed_cli_v101")
    if st.button("Salvar Alterações de Clientes"):
        salvar_dados_no_google("Clientes", edit_cli); st.rerun()
    
    with st.expander("➕ Novo Cliente"):
        with st.form("f_cli_new"):
            c_n, c_c, c_e, c_t = st.text_input("Nome/Loja"), st.text_input("Cidade"), st.text_input("Endereço"), st.text_input("Telefone")
            c_p = st.selectbox("Forma de Pagto Padrão", ["Dinheiro", "Pix", "Cartão", "Boleto", "Outros"])
            if st.form_submit_button("Cadastrar Cliente"):
                new = pd.DataFrame([{"Nome": c_n, "Loja": c_n, "Cidade": c_c, "Telefone": c_t, "Endereco": c_e, "Forma Pagto": c_p}])
                salvar_dados_no_google("Clientes", pd.concat([df_cli, new], ignore_index=True)); st.rerun()

with tabs[3]: # HISTÓRICO
    st.subheader("🧾 Histórico")
    if df_ped.empty: st.info("Sem registos.")
    else:
        for idx, r in df_ped.iloc[::-1].iterrows():
            with st.container(border=True):
                c_h1, c_h2 = st.columns([0.8, 0.2])
                val = converter_para_numero(r['Valor Total'])
                cor = "green" if val > 0 else "red"
                c_h1.write(f"📅 **{r['Data']}** | 👤 {r['Cliente']} | <span style='color:{cor}'>**R$ {val:.2f}**</span>", unsafe_allow_html=True)
                c_h1.caption(f"Detalhes: {r['Resumo']}")
                if c_h2.button("🗑️", key=f"del_{idx}"):
                    salvar_dados_no_google("Pedidos", df_ped.drop(idx)); st.rerun()

with tabs[4]: # LEMBRETES
    st.subheader("📅 Lembretes")
    st.dataframe(df_lem, use_container_width=True, hide_index=True)
    with st.form("f_lem_new"):
        cat, nome, vencto, valor = st.selectbox("Tipo", ["Conta", "Cliente"]), st.text_input("Descrição"), st.text_input("Vencimento"), st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Agendar"):
            nl = pd.DataFrame([{"Data": get_data_hora(), "Nome": nome, "Vencimento": vencto, "Valor": valor, "Categoria": cat, "Status": "Pendente"}])
            salvar_dados_no_google("Lembretes", pd.concat([df_lem, nl], ignore_index=True)); st.rerun()

with tabs[5]: # INSUMOS
    st.subheader("🛠️ Gastos Diversos")
    with st.form("f_ins_new"):
        desc, val = st.text_input("Item/Serviço"), st.number_input("Custo R$", min_value=0.0)
        if st.form_submit_button("Lançar Gasto"):
            log_i = pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc, "Valor": val}])
            salvar_dados_no_google("Insumos", pd.concat([df_ins, log_i], ignore_index=True))
            log_p = pd.DataFrame([{"Data": get_data_hora(), "Cliente": "GASTO/INSUMO", "Resumo": desc, "Valor Total": -val, "Status Pagto": "Pago"}])
            salvar_dados_no_google("Pedidos", pd.concat([df_ped, log_p], ignore_index=True)); st.rerun()
