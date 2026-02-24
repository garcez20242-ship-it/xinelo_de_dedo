import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

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

def gerar_recibo(dados_venda):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "RECIBO DE VENDA - XINELO DE DEDO", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 8, f"Data/Hora: {dados_venda['Data']}", ln=True)
        pdf.cell(190, 8, f"Cliente: {dados_venda['Cliente']}", ln=True)
        pdf.cell(190, 8, f"Status: {dados_venda['Status Pagto']}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 8, "Itens do Pedido:", ln=True)
        pdf.set_font("Arial", "", 11)
        resumo_limpo = str(dados_venda['Resumo']).replace(" | ", "\n")
        pdf.multi_cell(190, 8, resumo_limpo)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda['Valor Total']):.2f}", ln=True, align="R")
        pdf.set_font("Arial", "I", 8)
        pdf.ln(10)
        pdf.cell(190, 5, "Obrigado pela preferência!", ln=True, align="C")
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        return str(e).encode('latin-1')

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
               ler_aba("Lembretes", ["Nome", "Data", "Valor"]), \
               ler_aba("Historico_Precos", ["Data", "Modelo", "Preco_Unit"])
    except: return None, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

conn, df_estoque, df_pedidos, df_clientes, df_aquisicoes, df_insumos, df_lembretes, df_hist_precos = carregar_dados()

def atualizar_planilha(aba, dataframe):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=dataframe.astype(str).replace('nan', ''))
        st.cache_data.clear()
        time.sleep(1)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("💳 Financeiro")
    hoje = datetime.now().date()
    if not df_lembretes.empty:
        df_l_t = df_lembretes.copy()
        df_l_t['Data_DT'] = pd.to_datetime(df_l_t['Data'], dayfirst=True, errors='coerce').dt.date
        pends = df_l_t[df_l_t['Data_DT'] <= hoje]
        if not pends.empty:
            st.subheader("🚩 Pagar")
            for _, r in pends.iterrows(): st.error(f"**{r['Nome']}**: R$ {limpar_valor(r['Valor']):.2f}")
    
    st.divider()
    st.subheader("💰 Receber")
    if not df_pedidos.empty:
        df_vp = df_pedidos[df_pedidos['Status Pagto'] == "Pendente"]
        if not df_vp.empty:
            df_vp['V_N'] = df_vp['Valor Total'].apply(limpar_valor)
            res = df_vp.groupby('Cliente')['V_N'].sum()
            for cli, valor in res.items(): st.warning(f"**{cli}**: R$ {valor:.2f}")

# --- INTERFACE ---
st.title("🩴 Gestão Xinelo de Dedo v3.9")
tab1, tab_cad, tab2, tab_ins, tab3, tab4, tab5, tab6 = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços Compra"])

# --- TAB 1: ESTOQUE ---
with tab1:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada Múltipla")
        # Ordem alfabética no seletor de entrada
        modelos_dis = sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else []
        if not modelos_dis: st.warning("Cadastre um modelo!")
        else:
            m_ent = st.selectbox("Modelo", modelos_dis, key="ent_mod")
            t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
            q_ent = st.number_input("Qtd", min_value=1, key="ent_qtd")
            v_ent = st.number_input("Custo Unit R$", min_value=0.0, key="ent_val")
            if st.button("➕ Adicionar"):
                if 'carrinho_ent' not in st.session_state: st.session_state.carrinho_ent = []
                st.session_state.carrinho_ent.append({"Modelo": m_ent, "Tam": t_ent, "Qtd": q_ent, "Unit": v_ent, "Sub": q_ent*v_ent})
                st.rerun()
        
        if 'carrinho_ent' in st.session_state:
            for i, it in enumerate(st.session_state.carrinho_ent):
                cl, cr = st.columns([0.8, 0.2])
                cl.write(f"• {it['Modelo']} {it['Tam']} (x{it['Qtd']})")
                if cr.button("🗑️", key=f"del_e_{i}"): st.session_state.carrinho_ent.pop(i); st.rerun()
            if st.session_state.carrinho_ent and st.button("✅ Confirmar Entrada", type="primary"):
                df_e_atu = df_estoque.copy()
                hist_novos, res_txt, total_geral = [], [], 0
                for it in st.session_state.carrinho_ent:
                    idx = df_e_atu.index[df_e_atu['Modelo'] == it['Modelo']][0]
                    df_e_atu.at[idx, it['Tam']] = int(float(df_e_atu.at[idx, it['Tam']])) + it['Qtd']
                    hist_novos.append({"Data": get_data_hora(), "Modelo": it['Modelo'], "Preco_Unit": it['Unit']})
                    res_txt.append(f"{it['Modelo']}({it['Tam']}x{it['Qtd']})")
                    total_geral += it['Sub']
                atualizar_planilha("Estoque", df_e_atu)
                atualizar_planilha("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_txt), "Valor Total": total_geral}])], ignore_index=True))
                atualizar_planilha("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame(hist_novos)], ignore_index=True))
                st.session_state.carrinho_ent = []; st.rerun()
    with c2:
        st.subheader("📋 Inventário (Ordem Alfabética)")
        if not df_estoque.empty:
            # Organiza o inventário em ordem alfabética
            df_exibir = df_estoque.sort_values('Modelo')
            for idx, r in df_exibir.iterrows():
                cd, ct = st.columns([0.1, 0.9])
                if cd.button("🗑️", key=f"d_inv_{idx}"): atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
                ct.write(f"**{r['Modelo']}**")
            st.dataframe(df_exibir, hide_index=True)

# --- TAB NOVO MODELO ---
with tab_cad:
    with st.form("novo_mod"):
        st.subheader("✨ Novo Modelo")
        nm = st.text_input("Nome")
        cols = st.columns(5)
        vals = {t: cols[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            if nm:
                d_novo = {"Modelo": nm}; d_novo.update(vals)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([d_novo])], ignore_index=True)); st.rerun()

# --- TAB 2: VENDAS ---
with tab2:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        if not df_estoque.empty:
            v_cli = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Cliente Avulso"], key="v_cli")
            # Ordem alfabética no seletor de modelos para venda
            v_mod = st.selectbox("Modelo", sorted(df_estoque['Modelo'].unique()), key="v_mod")
            v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="v_tam")
            linha_est = df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam]
            est_disp = int(float(linha_est.values[0])) if not linha_est.empty else 0
            st.write(f"Disponível: {est_disp}")
            v_pre = st.number_input("Preço Venda R$", min_value=0.0, key="v_pre")
            v_qtd = st.number_input("Qtd", min_value=1, max_value=max(1, est_disp), key="v_qtd")
            if st.button("➕ Adicionar Item"):
                if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
                st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        st.subheader("📄 Resumo")
        if 'carrinho_v' in st.session_state:
            for i, it in enumerate(st.session_state.carrinho_v):
                st.write(f"{it['Mod']} {it['Tam']} x{it['Qtd']} - R$ {it['Sub']:.2f}")
            if st.session_state.carrinho_v:
                total_v = sum(x['Sub'] for x in st.session_state.carrinho_v)
                st.write(f"### Total: R$ {total_v:.2f}")
                status_v = st.radio("Status Pagto", ["Pago", "Pendente"], horizontal=True)
                forma_v = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "N/A"])
                if st.button("Finalizar Venda", type="primary"):
                    df_e_v = df_estoque.copy()
                    for x in st.session_state.carrinho_v:
                        ix = df_e_v.index[df_e_v['Modelo'] == x['Mod']][0]
                        df_e_v.at[ix, x['Tam']] = int(float(df_e_v.at[ix, x['Tam']])) - x['Qtd']
                    resumo = " | ".join([f"{x['Mod']}({x['Tam']}x{x['Qtd']})" for x in st.session_state.carrinho_v])
                    atualizar_planilha("Estoque", df_e_v)
                    atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": resumo, "Valor Total": total_v, "Status Pagto": status_v, "Forma": forma_v}])], ignore_index=True))
                    st.session_state.carrinho_v = []; st.rerun()

# --- TAB INSUMOS ---
with tab_ins:
    with st.form("ins_f"):
        st.subheader("🛠️ Gasto"); d_i = st.text_input("Desc"); v_i = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": d_i, "Valor": v_i}])], ignore_index=True)); st.rerun()
    for idx, r in df_insumos.iterrows():
        cl, cr = st.columns([0.1, 0.9])
        if cl.button("🗑️", key=f"d_ins_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        cr.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB CLIENTES ---
with tab3:
    with st.form("cli_f"):
        st.subheader("👥 Clientes"); c1, c2 = st.columns(2); n = c1.text_input("Nome"); l = c2.text_input("Loja")
        cid = c1.text_input("Cidade"); tel = c2.text_input("Tel")
        if st.form_submit_button("Cadastrar"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": cid, "Telefone": tel}])], ignore_index=True)); st.rerun()
    st.dataframe(df_clientes.sort_values('Nome'), hide_index=True)
    for idx, r in df_clientes.iterrows():
        if st.button(f"Remover {r['Nome']}", key=f"d_cli_{idx}"): atualizar_planilha("Clientes", df_clientes.drop(idx)); st.rerun()

# --- TAB EXTRATO ---
with tab4:
    st.subheader("🧾 Extrato")
    f_30 = st.checkbox("Últimos 30 dias", value=True)
    p = df_pedidos.assign(Tipo="Venda", Origem="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Origem="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Origem="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    if not u.empty:
        u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        if f_30: u = u[u['DT'] >= (datetime.now() - timedelta(days=30))]
        u = u.sort_values('DT', ascending=False)
        for idx, r in u.iterrows():
            c_d, c_b, c_pdf, c_t = st.columns([0.05, 0.12, 0.08, 0.75])
            if c_d.button("🗑️", key=f"d_ext_{idx}"):
                atualizar_planilha(r['Origem'], (df_pedidos if r['Origem']=="Pedidos" else df_aquisicoes if r['Origem']=="Aquisicoes" else df_insumos).drop(df_pedidos[df_pedidos['Data']==r['Data']].index if r['Origem']=="Pedidos" else df_aquisicoes[df_aquisicoes['Data']==r['Data']].index if r['Origem']=="Aquisicoes" else df_insumos[df_insumos['Data']==r['Data']].index)); st.rerun()
            if r['Origem'] == "Pedidos" and r['Status Pagto'] == "Pendente":
                if c_b.button("✅ Receber", key=f"bx_{idx}"):
                    df_p_atu = df_pedidos.copy()
                    df_p_atu.loc[(df_p_atu['Data']==r['Data']) & (df_p_atu['Cliente']==r['Cliente']), 'Status Pagto'] = "Pago"
                    atualizar_planilha("Pedidos", df_p_atu); st.rerun()
            if r['Origem'] == "Pedidos":
                c_pdf.download_button(label="📄 PDF", data=gerar_recibo(r), file_name=f"recibo_{idx}.pdf", mime="application/pdf", key=f"p_{idx}")
            c_t.write(f"{'🔴' if (r['Origem']=='Pedidos' and r['Status Pagto']=='Pendente') else '🟢' if r['Tipo']=='Venda' else '⚪'} **{r['Data']}** | {r['Tipo']} | {r['Cliente'] if r['Tipo']=='Venda' else ''} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

# --- TAB LEMBRETES ---
with tab5:
    with st.form("lem_f"):
        st.subheader("📅 Pagar"); ln = st.text_input("Título"); ld = st.date_input("Vencimento"); lv = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True)); st.rerun()
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"d_lem_{idx}"): atualizar_planilha("Lembretes", df_lembretes.drop(idx)); st.rerun()
        st.write(f"📅 {r['Data']} - {r['Nome']} - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB HISTÓRICO ---
with tab6:
    if not df_hist_precos.empty:
        df_hist_precos['DT'] = pd.to_datetime(df_hist_precos['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        sel = st.selectbox("Evolução:", sorted(df_hist_precos['Modelo'].unique()), key="h_mod")
        st.line_chart(df_hist_precos[df_hist_precos['Modelo'] == sel].sort_values('DT'), x='DT', y='Preco_Unit')
