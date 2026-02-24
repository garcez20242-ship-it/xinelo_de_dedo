import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Xinelo de Dedo v4.1", layout="wide", page_icon="🩴")

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
        return f"Erro PDF: {e}".encode('latin-1')

# --- CARREGAMENTO DE DADOS ---
@st.cache_data(ttl=2)
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
        st.success(f"Atualizado em {aba}!")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL (AVISOS E ALERTAS) ---
with st.sidebar:
    st.header("💳 Gestão Financeira")
    hoje = datetime.now().date()
    
    # 1. Contas a Pagar (Lembretes)
    if not df_lembretes.empty:
        df_l = df_lembretes.copy()
        df_l['DT'] = pd.to_datetime(df_l['Data'], dayfirst=True, errors='coerce').dt.date
        pends = df_l[df_l['DT'] <= hoje]
        if not pends.empty:
            st.subheader("🚩 Contas a Pagar")
            for _, r in pends.iterrows(): st.error(f"**{r['Nome']}**: R$ {limpar_valor(r['Valor']):.2f}")
    
    st.divider()
    # 2. Contas a Receber (Vendas Pendentes/Fiado)
    st.subheader("💰 Contas a Receber")
    if not df_pedidos.empty:
        df_vp = df_pedidos[df_pedidos['Status Pagto'] == "Pendente"]
        if not df_vp.empty:
            df_vp['V_N'] = df_vp['Valor Total'].apply(limpar_valor)
            res = df_vp.groupby('Cliente')['V_N'].sum()
            for cli, v in res.items(): st.warning(f"**{cli}**: R$ {v:.2f}")
        else: st.info("Nada pendente.")

    st.divider()
    # 3. Alertas de Estoque Baixo
    st.header("⚠️ Alertas de Estoque")
    if not df_estoque.empty:
        alerta = False
        for _, r in df_estoque.iterrows():
            criticos = [f"{t}({int(float(r[t]))}un)" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t] != "" else 0) <= 3]
            if criticos:
                st.warning(f"**{r['Modelo']}**:\n{', '.join(criticos)}")
                alerta = True
        if not alerta: st.success("Estoque OK!")

# --- INTERFACE PRINCIPAL ---
st.title("🩴 Gestão Xinelo de Dedo v4.1")
tab1, tab_cad, tab2, tab_ins, tab3, tab4, tab5, tab6 = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# --- TAB 1: ESTOQUE E ENTRADA ---
with tab1:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada Múltipla")
        mods = sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else []
        if not mods: st.warning("Cadastre um modelo na aba ao lado!")
        else:
            m_ent = st.selectbox("Modelo", mods, key="ent_mod")
            t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
            q_ent = st.number_input("Quantidade", min_value=1, key="ent_qtd")
            v_ent = st.number_input("Custo Unitário R$", min_value=0.0, key="ent_val")
            if st.button("➕ Adicionar à Entrada"):
                if 'carrinho_e' not in st.session_state: st.session_state.carrinho_e = []
                st.session_state.carrinho_e.append({"Modelo": m_ent, "Tam": t_ent, "Qtd": q_ent, "Unit": v_ent, "Sub": q_ent*v_ent})
                st.rerun()
        
        if 'carrinho_e' in st.session_state:
            for i, it in enumerate(st.session_state.carrinho_e):
                st.write(f"• {it['Modelo']} {it['Tam']} (x{it['Qtd']})")
                if st.button("🗑️", key=f"del_e_{i}"): st.session_state.carrinho_e.pop(i); st.rerun()
            if st.session_state.carrinho_e and st.button("✅ Confirmar Entrada"):
                df_atu = df_estoque.copy()
                hist_n, res_t, total_g = [], [], 0
                for it in st.session_state.carrinho_e:
                    idx = df_atu.index[df_atu['Modelo'] == it['Modelo']][0]
                    df_atu.at[idx, it['Tam']] = int(float(df_atu.at[idx, it['Tam']])) + it['Qtd']
                    hist_n.append({"Data": get_data_hora(), "Modelo": it['Modelo'], "Preco_Unit": it['Unit']})
                    res_t.append(f"{it['Modelo']}({it['Tam']}x{it['Qtd']})")
                    total_g += it['Sub']
                atualizar_planilha("Estoque", df_atu)
                atualizar_planilha("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_t), "Valor Total": total_g}])], ignore_index=True))
                atualizar_planilha("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame(hist_n)], ignore_index=True))
                st.session_state.carrinho_e = []; st.rerun()
    with c2:
        st.subheader("📋 Inventário (Ordem Alfabética)")
        if not df_estoque.empty:
            df_v = df_estoque.sort_values('Modelo')
            for idx, r in df_v.iterrows():
                cd, ct = st.columns([0.1, 0.9])
                if cd.button("🗑️", key=f"d_inv_{idx}"): 
                    atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
                ct.write(f"**{r['Modelo']}**")
            st.dataframe(df_v, hide_index=True)

# --- TAB NOVO MODELO ---
with tab_cad:
    with st.form("f_n_m"):
        st.subheader("✨ Cadastrar Novo Modelo")
        n_m = st.text_input("Nome")
        cs = st.columns(5)
        vs = {t: cs[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            if n_m:
                d_n = {"Modelo": n_m}; d_n.update(vs)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([d_n])], ignore_index=True)); st.rerun()

# --- TAB 2: VENDAS ---
with tab2:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Nova Venda")
        if not df_estoque.empty:
            v_cli = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Cliente Avulso"])
            v_mod = st.selectbox("Modelo", sorted(df_estoque['Modelo'].unique()))
            v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            est_d = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
            st.write(f"Disponível: {est_d}")
            v_pre = st.number_input("Preço Venda R$", min_value=0.0)
            v_qtd = st.number_input("Qtd", min_value=1, max_value=max(1, est_d))
            if st.button("➕ Adicionar Item"):
                if 'carrinho_v' not in st.session_state: st.session_state.carrinho_v = []
                st.session_state.carrinho_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        st.subheader("📄 Resumo da Venda")
        if 'carrinho_v' in st.session_state:
            for i, it in enumerate(st.session_state.carrinho_v):
                st.write(f"{it['Mod']} {it['Tam']} x{it['Qtd']} - R$ {it['Sub']:.2f}")
            if st.session_state.carrinho_v:
                tot_v = sum(x['Sub'] for x in st.session_state.carrinho_v)
                st.write(f"### Total: R$ {tot_v:.2f}")
                v_st = st.radio("Pagamento", ["Pago", "Pendente"], horizontal=True)
                v_fo = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "N/A"])
                if st.button("Finalizar Venda", type="primary"):
                    df_e_v = df_estoque.copy()
                    for x in st.session_state.carrinho_v:
                        ix = df_e_v.index[df_e_v['Modelo'] == x['Mod']][0]
                        df_e_v.at[ix, x['Tam']] = int(float(df_e_v.at[ix, x['Tam']])) - x['Qtd']
                    res = " | ".join([f"{x['Mod']}({x['Tam']}x{x['Qtd']})" for x in st.session_state.carrinho_v])
                    atualizar_planilha("Estoque", df_e_v)
                    atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": res, "Valor Total": tot_v, "Status Pagto": v_st, "Forma": v_fo}])], ignore_index=True))
                    st.session_state.carrinho_v = []; st.rerun()

# --- TAB INSUMOS ---
with tab_ins:
    with st.form("f_ins"):
        st.subheader("🛠️ Gastos Diversos"); d_i = st.text_input("Desc"); v_i = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar Insumo"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": d_i, "Valor": v_i}])], ignore_index=True)); st.rerun()
    for idx, r in df_insumos.iterrows():
        c_l, c_r = st.columns([0.1, 0.9])
        if c_l.button("🗑️", key=f"d_ins_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx)); st.rerun()
        c_r.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB CLIENTES ---
with tab3:
    with st.form("f_cli"):
        st.subheader("👥 Cadastro de Clientes"); c1, c2 = st.columns(2); n = c1.text_input("Nome"); l = c2.text_input("Loja")
        cid = c1.text_input("Cidade"); tel = c2.text_input("WhatsApp")
        if st.form_submit_button("Salvar Cliente"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": cid, "Telefone": tel}])], ignore_index=True)); st.rerun()
    st.dataframe(df_clientes.sort_values('Nome'), use_container_width=True, hide_index=True)
    for idx, r in df_clientes.iterrows():
        if st.button(f"Remover {r['Nome']}", key=f"d_cli_{idx}"): atualizar_planilha("Clientes", df_clientes.drop(idx)); st.rerun()

# --- TAB EXTRATO ---
with tab4:
    st.subheader("🧾 Extrato Financeiro Completo")
    f30 = st.checkbox("Filtrar últimos 30 dias", value=True)
    p = df_pedidos.assign(Tipo="Venda", Ori="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Ori="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    if not u.empty:
        u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        if f30: u = u[u['DT'] >= (datetime.now() - timedelta(days=30))]
        u = u.sort_values('DT', ascending=False)
        for idx, r in u.iterrows():
            c_d, c_b, c_pdf, c_t = st.columns([0.05, 0.12, 0.1, 0.73])
            if c_d.button("🗑️", key=f"d_ext_{idx}"):
                origem_df = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                atualizar_planilha(r['Ori'], origem_df[origem_df['Data'] != r['Data']]); st.rerun()
            if r['Ori'] == "Pedidos" and r['Status Pagto'] == "Pendente":
                if c_b.button("✅ Receber", key=f"bx_{idx}"):
                    df_p_a = df_pedidos.copy()
                    df_p_a.loc[df_p_a['Data']==r['Data'], 'Status Pagto'] = "Pago"
                    atualizar_planilha("Pedidos", df_p_a); st.rerun()
            if r['Ori'] == "Pedidos":
                c_pdf.download_button(label="📄 PDF", data=gerar_recibo(r), file_name=f"recibo_{idx}.pdf", key=f"pdf_{idx}")
            txt = f"{'🔴' if (r['Ori']=='Pedidos' and r['Status Pagto']=='Pendente') else '🟢' if r['Tipo']=='Venda' else '⚪'} **{r['Data']}** | {r['Tipo']} | {r['Cliente'] if r['Tipo']=='Venda' else ''} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**"
            c_t.write(txt)

# --- TAB LEMBRETES ---
with tab5:
    with st.form("f_lem"):
        st.subheader("📅 Agendar Pagamento"); ln = st.text_input("O que pagar?"); ld = st.date_input("Vencimento"); lv = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar Lembrete"):
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True)); st.rerun()
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"d_lem_{idx}"): atualizar_planilha("Lembretes", df_lembretes.drop(idx)); st.rerun()
        st.write(f"📅 {r['Data']} - {r['Nome']} - R$ {limpar_valor(r['Valor']):.2f}")

# --- TAB HISTÓRICO DE PREÇOS ---
with tab6:
    if not df_hist_precos.empty:
        df_hist_precos['DT'] = pd.to_datetime(df_hist_precos['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        sel = st.selectbox("Modelo para análise:", sorted(df_hist_precos['Modelo'].unique()))
        st.line_chart(df_hist_precos[df_hist_precos['Modelo'] == sel].sort_values('DT'), x='DT', y='Preco_Unit')
