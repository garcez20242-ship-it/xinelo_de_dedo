import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Xinelo de Dedo", layout="wide", page_icon="🩴")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- FUNÇÕES DE APOIO ---
def get_data_hora():
    return (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")

def limpar_valor(valor):
    try:
        if pd.isna(valor) or str(valor).strip() == "": return 0.0
        v = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(v)
    except: return 0.0

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'XINELO DE DEDO - RELATORIO DETALHADO', 0, 1, 'C')
        self.ln(10)

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=0)
def carregar_dados():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        def ler_aba(nome, colunas):
            try:
                df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl=0)
                if df is None or df.empty: return pd.DataFrame(columns=colunas)
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                for col in colunas:
                    if col not in df.columns: df[col] = 0 if col in TAMANHOS_PADRAO else ""
                return df
            except: return pd.DataFrame(columns=colunas)
        
        return conn, \
               ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO), \
               ler_aba("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]), \
               ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]), \
               ler_aba("Aquisicoes", ["Data", "Resumo", "Valor Total"]), \
               ler_aba("Insumos", ["Data", "Descricao", "Valor"]), \
               ler_aba("Lembretes", ["Nome", "Data", "Valor"])
    except: return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes, df_insumos, df_lembretes = carregar_dados()

def atualizar_planilha(aba, dataframe):
    conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=dataframe.astype(str).replace('nan', ''))
    st.cache_data.clear()

# --- ESTILIZAÇÃO DE TABELA ---
def colorir_estoque(val):
    try:
        v = int(float(val))
        if v == 0: return 'background-color: #ff4b4b; color: white'
        if v <= 3: return 'background-color: #ffeb3b; color: black'
        return ''
    except: return ''

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("💳 Alertas Financeiros")
    hoje = datetime.now().date()
    tem_pag = False
    
    # Pagamentos
    if not df_lembretes.empty:
        df_l_temp = df_lembretes.copy()
        df_l_temp['Data_DT'] = pd.to_datetime(df_l_temp['Data'], dayfirst=True, errors='coerce').dt.date
        pends = df_l_temp[df_l_temp['Data_DT'] <= hoje]
        for _, r in pends.iterrows():
            st.error(f"**CONTA:** {r['Nome']} ({r['Data']})")
            tem_pag = True
            
    # Cobrança
    if not df_pedidos.empty:
        inad = df_pedidos[df_pedidos['Status Pagto'] == 'Pendente']
        if not inad.empty:
            st.warning("🔴 **CLIENTES PENDENTES:**")
            for cli in inad['Cliente'].unique():
                st.write(f"- {cli}")
            tem_pag = True
    if not tem_pag: st.success("✅ Financeiro em dia")

    st.divider()
    st.header("⚠️ Estoque Crítico")
    alerta_vazio = True
    if not df_estoque.empty:
        for _, row in df_estoque.iterrows():
            criticos = []
            for tam in TAMANHOS_PADRAO:
                qtd = int(float(row[tam])) if str(row[tam]) != "" else 0
                if qtd <= 3:
                    status = "ESGOTADO" if qtd == 0 else f"{qtd} un"
                    criticos.append(f"{tam} ({status})")
            if criticos:
                st.warning(f"**{row['Modelo']}**\n{', '.join(criticos)}")
                alerta_vazio = False
    if alerta_vazio: st.success("✅ Estoque abastecido")

# --- INTERFACE ---
st.title("🩴 Xinelo de Dedo - Gestão Pro")
tab1, tab_cad, tab2, tab_ins, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "✨ Cadastro", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

with tab1:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("📦 Entrada")
        m_aq = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"], key="ent_mod")
        t_aq = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
        q_aq = st.number_input("Qtd", min_value=1, step=1)
        v_uni = st.number_input("R$ Unit. Compra", min_value=0.0)
        if st.button("Confirmar Entrada"):
            idx = df_estoque.index[df_estoque['Modelo'] == m_aq][0]
            df_estoque.at[idx, t_aq] = int(float(df_estoque.at[idx, t_aq])) + q_aq
            atualizar_planilha("Estoque", df_estoque)
            atualizar_planilha("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": f"{m_aq}({t_aq})x{q_aq}", "Valor Total": q_aq*v_uni}])], ignore_index=True))
            st.rerun()
    with c2:
        st.subheader("📋 Inventário")
        if not df_estoque.empty:
            for idx, row in df_estoque.iterrows():
                c_del, c_txt = st.columns([0.1, 0.9])
                if c_del.button("🗑️", key=f"del_inv_{idx}"):
                    atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
                c_txt.write(f"**{row['Modelo']}**")
            st.dataframe(df_estoque.style.applymap(colorir_estoque, subset=TAMANHOS_PADRAO), hide_index=True)

with tab_cad:
    st.subheader("✨ Novo Modelo")
    with st.form("cad"):
        n_m = st.text_input("Nome")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            ni = {"Modelo": n_m}; ni.update(ipts)
            atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)); st.rerun()

with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique() if not df_clientes.empty else ["-"])
        v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"])
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0])) if not df_estoque.empty else 0
        st.metric("Disponível", disp)
        v_qtd = st.number_input("Venda Qtd", min_value=0, max_value=disp)
        v_pre = st.number_input("R$ Unit.", min_value=0.0)
        if st.button("➕ Adicionar"):
            if v_qtd > 0:
                st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Preco": v_pre, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        for i, it in enumerate(st.session_state.carrinho_v):
            if st.button("🗑️", key=f"cv_{i}"): st.session_state.carrinho_v.pop(i); st.rerun()
            st.write(f"{it['Mod']} ({it['Tam']}) x{it['Qtd']} - R$ {it['Sub']:.2f}")
        if st.session_state.carrinho_v:
            tot = sum(i['Sub'] for i in st.session_state.carrinho_v)
            st.subheader(f"Total: R$ {tot:.2f}")
            st_pg = st.selectbox("Status", ["Pago", "Pendente"])
            fm_pg = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão"])
            if st.button("Finalizar Venda"):
                for it in st.session_state.carrinho_v:
                    ix = df_estoque.index[df_estoque['Modelo'] == it['Mod']][0]
                    df_estoque.at[ix, it['Tam']] = int(float(df_estoque.at[ix, it['Tam']])) - it['Qtd']
                atualizar_planilha("Estoque", df_estoque)
                atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": str(st.session_state.carrinho_v), "Valor Total": tot, "Status Pagto": st_pg, "Forma": fm_pg}])], ignore_index=True))
                st.session_state.carrinho_v = []; st.rerun()

with tab_ins:
    with st.form("ins"):
        desc = st.text_input("Gasto")
        val = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc, "Valor": val}])], ignore_index=True)); st.rerun()
    for idx, r in df_insumos.iterrows():
        if st.button("🗑️", key=f"di_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        st.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

with tab3:
    with st.form("cli"):
        n = st.text_input("Nome Cliente")
        l = st.text_input("Loja")
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l}])], ignore_index=True)); st.rerun()
    for idx, r in df_clientes.iterrows():
        if st.button("🗑️", key=f"dc_{idx}"): atualizar_planilha("Clientes", df_clientes.drop(idx)); st.rerun()
        st.write(f"**{r['Nome']}** - {r['Loja']}")

with tab4:
    col_x, col_d = st.columns([2, 1])
    with col_x:
        st.subheader("🧾 Histórico")
        p = df_pedidos.assign(Tipo="🔴 Venda", Origem="Pedidos")
        a = df_aquisicoes.assign(Tipo="🟢 Compra", Origem="Aquisicoes")
        i = df_insumos.assign(Tipo="🟠 Insumo", Origem="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
        u = pd.concat([p, a, i], ignore_index=True)
        if not u.empty:
            u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
            u = u.sort_values('DT', ascending=False)
            for idx, r in u.iterrows():
                c_del, c_txt = st.columns([0.1, 0.9])
                if c_del.button("🗑️", key=f"dx_{idx}"):
                    # Lógica de remoção correta por aba
                    if r['Origem'] == "Pedidos": atualizar_planilha("Pedidos", df_pedidos[df_pedidos['Data'] != r['Data']])
                    elif r['Origem'] == "Aquisicoes": atualizar_planilha("Aquisicoes", df_aquisicoes[df_aquisicoes['Data'] != r['Data']])
                    elif r['Origem'] == "Insumos": atualizar_planilha("Insumos", df_insumos[df_insumos['Data'] != r['Data']])
                    st.rerun()
                st.write(f"**{r['Data']}** | {r['Tipo']} | R$ {limpar_valor(r['Valor Total']):.2f}")
            if st.button("📄 Exportar PDF"):
                pdf = PDF(); pdf.add_page(); pdf.set_font('Arial', '', 12); pdf.cell(0, 10, "Extrato Detalhado", ln=True)
                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="extrato.pdf")
    with col_d:
        st.subheader("🏆 Mais Vendidos")
        if not df_pedidos.empty:
            # Simplificação técnica: contagem por cliente/pedido já que 'Resumo' é string de lista
            st.write(df_pedidos['Cliente'].value_counts().head(3))

with tab5:
    with st.form("lem"):
        ln = st.text_input("Lembrete")
        ld = st.date_input("Data", format="DD/MM/YYYY")
        lv = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True)); st.rerun()
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"dl_{idx}"): atualizar_planilha("Lembretes", df_lembretes.drop(idx)); st.rerun()
        st.write(f"**{r['Nome']}** - {r['Data']} - R$ {limpar_valor(r['Valor']):.2f}")
