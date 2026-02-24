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

# --- ESTILIZAÇÃO ---
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
    if not df_lembretes.empty:
        df_l_temp = df_lembretes.copy()
        df_l_temp['Data_DT'] = pd.to_datetime(df_l_temp['Data'], dayfirst=True, errors='coerce').dt.date
        pends = df_l_temp[df_l_temp['Data_DT'] <= hoje]
        for _, r in pends.iterrows():
            st.error(f"**CONTA:** {r['Nome']} ({r['Data']})")
            tem_pag = True
    if not df_pedidos.empty:
        inad = df_pedidos[df_pedidos['Status Pagto'] == 'Pendente']
        if not inad.empty:
            st.warning("🔴 **PENDENTES:** " + ", ".join(inad['Cliente'].unique()))
            tem_pag = True
    if not tem_pag: st.success("✅ Financeiro em dia")

    st.divider()
    st.header("⚠️ Estoque Crítico")
    alerta_vazio = True
    if not df_estoque.empty:
        for _, row in df_estoque.iterrows():
            criticos = [f"{t}({int(float(row[t])) if row[t] != '' else 0}un)" for t in TAMANHOS_PADRAO if (int(float(row[t])) if row[t] != '' else 0) <= 3]
            if criticos:
                st.warning(f"**{row['Modelo']}**\n{', '.join(criticos)}")
                alerta_vazio = False
    if alerta_vazio: st.success("✅ Estoque abastecido")

# --- INTERFACE ---
st.title("🩴 Xinelo de Dedo - Gestão Pro")
tab1, tab_cad, tab2, tab_ins, tab3, tab4, tab5 = st.tabs(["📊 Estoque", "✨ Cadastro", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes"])

# --- TAB 1: ESTOQUE (COM ENTRADA MÚLTIPLA) ---
with tab1:
    if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada de Mercadoria")
        m_ent = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"], key="m_ent")
        t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="t_ent")
        q_ent = st.number_input("Qtd", min_value=1, step=1, key="q_ent")
        v_ent = st.number_input("R$ Unit. Compra", min_value=0.0, key="v_ent")
        if st.button("➕ Adicionar à Entrada"):
            st.session_state.carrinho_ent.append({"Modelo": m_ent, "Tam": t_ent, "Qtd": q_ent, "Sub": q_ent*v_ent})
            st.rerun()
        
        for i, it in enumerate(st.session_state.carrinho_ent):
            col_d, col_t = st.columns([0.2, 0.8])
            if col_d.button("🗑️", key=f"dent_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()
            col_t.write(f"{it['Modelo']} {it['Tam']} x{it['Qtd']} - R${it['Sub']:.2f}")
        
        if st.session_state.carrinho_ent:
            total_e = sum(x['Sub'] for x in st.session_state.carrinho_ent)
            if st.button(f"✅ Finalizar Entrada (R$ {total_e:.2f})", type="primary"):
                df_novo = df_estoque.copy()
                res_e = []
                for it in st.session_state.carrinho_ent:
                    idx = df_novo.index[df_novo['Modelo'] == it['Modelo']][0]
                    df_novo.at[idx, it['Tam']] = int(float(df_novo.at[idx, it['Tam']])) + it['Qtd']
                    res_e.append(f"{it['Modelo']}({it['Tam']}x{it['Qtd']})")
                atualizar_planilha("Estoque", df_novo)
                atualizar_planilha("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_e), "Valor Total": total_e}])], ignore_index=True))
                st.session_state.carrinho_ent = []; st.success("Entrada concluída!"); st.rerun()

    with c2:
        st.subheader("📋 Inventário")
        if not df_estoque.empty:
            for idx, r in df_estoque.iterrows():
                cd, ct = st.columns([0.1, 0.9])
                if cd.button("🗑️", key=f"dinv_{idx}"): atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
                ct.write(f"**{r['Modelo']}**")
            st.dataframe(df_estoque.style.applymap(colorir_estoque, subset=TAMANHOS_PADRAO), hide_index=True)

# --- TAB CADASTRO ---
with tab_cad:
    st.subheader("✨ Novo Modelo")
    with st.form("f_cad"):
        n_m = st.text_input("Nome")
        cols = st.columns(5)
        ipts = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            ni = {"Modelo": n_m}; ni.update(ipts)
            atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([ni])], ignore_index=True)); st.rerun()

# --- TAB 2: VENDAS ---
with tab2:
    if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        v_cli = st.selectbox("Cliente", df_clientes['Nome'].unique() if not df_clientes.empty else ["-"])
        v_mod = st.selectbox("Modelo", df_estoque['Modelo'].unique() if not df_estoque.empty else ["-"])
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        disp = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0])) if not df_estoque.empty else 0
        st.metric("Disponível", disp)
        v_qtd = st.number_input("Venda Qtd", min_value=0, max_value=disp)
        v_pre = st.number_input("R$ Unit. Venda", min_value=0.0)
        if st.button("➕ Add Item"):
            if v_qtd > 0:
                st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        for i, it in enumerate(st.session_state.carrinho_v):
            if st.button("🗑️", key=f"dvv_{i}"): st.session_state.carrinho_v.pop(i); st.rerun()
            st.write(f"{it['Mod']} ({it['Tam']}) x{it['Qtd']} - R$ {it['Sub']:.2f}")
        if st.session_state.carrinho_v:
            tot_v = sum(i['Sub'] for i in st.session_state.carrinho_v)
            st.subheader(f"Total: R$ {tot_v:.2f}")
            st_pg = st.selectbox("Status", ["Pago", "Pendente"])
            fm_pg = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão"])
            if st.button("Finalizar Venda"):
                df_e_v = df_estoque.copy()
                res_v = " | ".join([f"{x['Mod']}({x['Tam']}x{x['Qtd']})" for x in st.session_state.carrinho_v])
                for x in st.session_state.carrinho_v:
                    ix = df_e_v.index[df_e_v['Modelo'] == x['Mod']][0]
                    df_e_v.at[ix, x['Tam']] = int(float(df_e_v.at[ix, x['Tam']])) - x['Qtd']
                atualizar_planilha("Estoque", df_e_v)
                atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": res_v, "Valor Total": tot_v, "Status Pagto": st_pg, "Forma": fm_pg}])], ignore_index=True))
                st.session_state.carrinho_v = []; st.rerun()

# --- TAB CLIENTES (CORRIGIDA) ---
with tab3:
    st.subheader("👥 Cadastro de Clientes")
    with st.form("f_cli"):
        c1, c2 = st.columns(2)
        nc = c1.text_input("Nome")
        lc = c2.text_input("Loja")
        cc = c1.text_input("Cidade")
        tc = c2.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": nc, "Loja": lc, "Cidade": cc, "Telefone": tc}])], ignore_index=True)); st.rerun()
    
    st.markdown("---")
    if not df_clientes.empty:
        for idx, r in df_clientes.iterrows():
            cd, ct = st.columns([0.1, 0.9])
            if cd.button("🗑️", key=f"dcli_{idx}"): atualizar_planilha("Clientes", df_clientes.drop(idx)); st.rerun()
            ct.write(f"**{r['Nome']}** | {r['Loja']} | {r['Cidade']} | {r['Telefone']}")
        st.dataframe(df_clientes, hide_index=True, use_container_width=True)

# --- TAB 4: EXTRATO (COM MENSAGEM VAZIA) ---
with tab4:
    st.subheader("🧾 Extrato e Dashboard")
    col_ext, col_dash = st.columns([2, 1])
    
    with col_ext:
        p = df_pedidos.assign(Tipo="🔴 Venda", Origem="Pedidos")
        a = df_aquisicoes.assign(Tipo="🟢 Compra", Origem="Aquisicoes")
        i = df_insumos.assign(Tipo="🟠 Insumo", Origem="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
        u = pd.concat([p, a, i], ignore_index=True)
        
        if u.empty:
            st.info("ℹ️ Nenhuma movimentação registrada no sistema.")
        else:
            u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
            u = u.sort_values('DT', ascending=False)
            for idx, r in u.iterrows():
                cd, ct = st.columns([0.1, 0.9])
                if cd.button("🗑️", key=f"dex_{idx}"):
                    if r['Origem'] == "Pedidos": atualizar_planilha("Pedidos", df_pedidos[df_pedidos['Data'] != r['Data']])
                    elif r['Origem'] == "Aquisicoes": atualizar_planilha("Aquisicoes", df_aquisicoes[df_aquisicoes['Data'] != r['Data']])
                    elif r['Origem'] == "Insumos": atualizar_planilha("Insumos", df_insumos[df_insumos['Data'] != r['Data']])
                    st.rerun()
                ct.write(f"**{r['Data']}** | {r['Tipo']} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")
            
            if st.button("📄 Gerar PDF"):
                pdf = PDF(); pdf.add_page(); pdf.set_font('Arial', '', 12); pdf.cell(0, 10, "Relatorio Detalhado", ln=True)
                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="extrato.pdf")

    with col_dash:
        st.subheader("🏆 Mais Vendidos")
        if not df_pedidos.empty:
            v_list = []
            for res in df_pedidos['Resumo']:
                for item in res.split(' | '): v_list.append(item.split('(')[0])
            st.write(pd.Series(v_list).value_counts().head(3))
        else: st.write("Sem vendas para analisar.")

# --- TAB INSUMOS ---
with tab_ins:
    with st.form("f_ins"):
        desc = st.text_input("Gasto")
        val = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar Insumo"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc, "Valor": val}])], ignore_index=True)); st.rerun()
    for idx, r in df_insumos.iterrows():
        if st.button("🗑️", key=f"dins_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        st.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB 5: LEMBRETES ---
with tab5:
    with st.form("f_lem"):
        ln = st.text_input("Lembrete")
        ld = st.date_input("Vencimento", format="DD/MM/YYYY")
        lv = st.number_input("R$ Valor", min_value=0.0)
        if st.form_submit_button("Agendar"):
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True)); st.rerun()
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"dlem_{idx}"): atualizar_planilha("Lembretes", df_lembretes.drop(idx)); st.rerun()
        st.write(f"**{r['Nome']}** - {r['Data']} - R$ {limpar_valor(r['Valor']):.2f}")
