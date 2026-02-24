import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Xinelo de Dedo v4.2", layout="wide", page_icon="🩴")

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

# --- CONEXÃO E CARREGAMENTO (CORREÇÃO DO RECURSION ERROR) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def ler_aba(nome, colunas):
    try:
        df = conn.read(spreadsheet=URL_PLANILHA, worksheet=nome, ttl="0s")
        if df is None or df.empty: return pd.DataFrame(columns=colunas)
        df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
        df.columns = df.columns.str.strip()
        for col in colunas:
            if col not in df.columns: df[col] = 0 if col in TAMANHOS_PADRAO else ""
        return df
    except: 
        return pd.DataFrame(columns=colunas)

# Carregamento Direto (Sem cache aninhado para evitar o loop)
df_estoque = ler_aba("Estoque", ["Modelo"] + TAMANHOS_PADRAO)
df_pedidos = ler_aba("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"])
df_clientes = ler_aba("Clientes", ["Nome", "Loja", "Cidade", "Telefone"])
df_aquisicoes = ler_aba("Aquisicoes", ["Data", "Resumo", "Valor Total"])
df_insumos = ler_aba("Insumos", ["Data", "Descricao", "Valor"])
df_lembretes = ler_aba("Lembretes", ["Nome", "Data", "Valor"])
df_hist_precos = ler_aba("Historico_Precos", ["Data", "Modelo", "Preco_Unit"])

def atualizar_planilha(aba, dataframe):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=dataframe.astype(str).replace('nan', ''))
        st.cache_data.clear()
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL (AVISOS) ---
with st.sidebar:
    st.header("💳 Gestão Financeira")
    hoje = datetime.now().date()
    
    if not df_lembretes.empty:
        df_l = df_lembretes.copy()
        df_l['DT'] = pd.to_datetime(df_l['Data'], dayfirst=True, errors='coerce').dt.date
        pends = df_l[df_l['DT'] <= hoje]
        if not pends.empty:
            st.subheader("🚩 Contas a Pagar")
            for _, r in pends.iterrows(): st.error(f"**{r['Nome']}**: R$ {limpar_valor(r['Valor']):.2f}")
    
    st.divider()
    st.subheader("💰 Contas a Receber")
    if not df_pedidos.empty:
        df_vp = df_pedidos[df_pedidos['Status Pagto'] == "Pendente"]
        if not df_vp.empty:
            df_vp['V_N'] = df_vp['Valor Total'].apply(limpar_valor)
            res = df_vp.groupby('Cliente')['V_N'].sum()
            for cli, v in res.items(): st.warning(f"**{cli}**: R$ {v:.2f}")

    st.divider()
    st.header("⚠️ Alertas de Estoque")
    if not df_estoque.empty:
        for _, r in df_estoque.iterrows():
            criticos = [f"{t}({int(float(r[t]))}un)" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t] != "" else 0) <= 3]
            if criticos: st.warning(f"**{r['Modelo']}**:\n{', '.join(criticos)}")

# --- INTERFACE ---
st.title("🩴 Gestão Xinelo de Dedo v4.2")
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# 1. ESTOQUE
with tabs[0]:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada Múltipla")
        mods = sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else []
        if mods:
            m_ent = st.selectbox("Modelo", mods, key="ent_mod")
            t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="ent_tam")
            q_ent = st.number_input("Quantidade", min_value=1, key="ent_qtd")
            v_ent = st.number_input("Custo Unit R$", min_value=0.0, key="ent_val")
            if st.button("➕ Adicionar"):
                if 'c_ent' not in st.session_state: st.session_state.c_ent = []
                st.session_state.c_ent.append({"Modelo": m_ent, "Tam": t_ent, "Qtd": q_ent, "Unit": v_ent})
                st.rerun()
        if 'c_ent' in st.session_state:
            for i, it in enumerate(st.session_state.c_ent):
                st.write(f"• {it['Modelo']} {it['Tam']} (x{it['Qtd']})")
                if st.button("🗑️", key=f"del_e_{i}"): st.session_state.c_ent.pop(i); st.rerun()
            if st.session_state.c_ent and st.button("✅ Confirmar Entrada"):
                df_atu = df_estoque.copy()
                hist_n, res_t, total_g = [], [], 0
                for it in st.session_state.c_ent:
                    idx = df_atu.index[df_atu['Modelo'] == it['Modelo']][0]
                    df_atu.at[idx, it['Tam']] = int(float(df_atu.at[idx, it['Tam']])) + it['Qtd']
                    hist_n.append({"Data": get_data_hora(), "Modelo": it['Modelo'], "Preco_Unit": it['Unit']})
                    res_t.append(f"{it['Modelo']}({it['Tam']}x{it['Qtd']})")
                    total_g += (it['Qtd'] * it['Unit'])
                atualizar_planilha("Estoque", df_atu)
                atualizar_planilha("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_t), "Valor Total": total_g}])], ignore_index=True))
                atualizar_planilha("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame(hist_n)], ignore_index=True))
                st.session_state.c_ent = []; st.rerun()
    with c2:
        st.subheader("📋 Inventário (A-Z)")
        if not df_estoque.empty:
            df_v = df_estoque.sort_values('Modelo')
            for idx, r in df_v.iterrows():
                col_d, col_t = st.columns([0.1, 0.9])
                if col_d.button("🗑️", key=f"d_inv_{idx}"):
                    atualizar_planilha("Estoque", df_estoque.drop(idx)); st.rerun()
                col_t.write(f"**{r['Modelo']}**")
            st.dataframe(df_v, hide_index=True)

# 2. NOVO MODELO
with tabs[1]:
    with st.form("f_n_m"):
        st.subheader("✨ Cadastrar Novo")
        n_m = st.text_input("Nome")
        cs = st.columns(5)
        vs = {t: cs[i%5].number_input(f"T {t}", min_value=0) for i, t in enumerate(TAMANHOS_PADRAO)}
        if st.form_submit_button("Cadastrar"):
            if n_m:
                d_n = {"Modelo": n_m}; d_n.update(vs)
                atualizar_planilha("Estoque", pd.concat([df_estoque, pd.DataFrame([d_n])], ignore_index=True))

# 3. VENDAS
with tabs[2]:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("🛒 Venda")
        if not df_estoque.empty:
            v_cli = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Cliente Avulso"])
            v_mod = st.selectbox("Modelo", sorted(df_estoque['Modelo'].unique()))
            v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
            est_d = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
            st.write(f"Estoque: {est_d}")
            v_pre = st.number_input("Preço R$", min_value=0.0)
            v_qtd = st.number_input("Qtd", min_value=1, max_value=max(1, est_d))
            if st.button("➕ Adicionar Item"):
                if 'c_v' not in st.session_state: st.session_state.c_v = []
                st.session_state.c_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        if 'c_v' in st.session_state:
            for i, it in enumerate(st.session_state.c_v):
                st.write(f"{it['Mod']} {it['Tam']} x{it['Qtd']} - R$ {it['Sub']:.2f}")
            if st.session_state.c_v:
                tot_v = sum(x['Sub'] for x in st.session_state.c_v)
                st.write(f"### Total: R$ {tot_v:.2f}")
                v_st = st.radio("Pagto", ["Pago", "Pendente"], horizontal=True)
                v_fo = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "N/A"])
                if st.button("Finalizar Venda", type="primary"):
                    df_e_v = df_estoque.copy()
                    for x in st.session_state.c_v:
                        ix = df_e_v.index[df_e_v['Modelo'] == x['Mod']][0]
                        df_e_v.at[ix, x['Tam']] = int(float(df_e_v.at[ix, x['Tam']])) - x['Qtd']
                    res = " | ".join([f"{x['Mod']}({x['Tam']}x{x['Qtd']})" for x in st.session_state.c_v])
                    atualizar_planilha("Estoque", df_e_v)
                    atualizar_planilha("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": res, "Valor Total": tot_v, "Status Pagto": v_st, "Forma": v_fo}])], ignore_index=True))
                    st.session_state.c_v = []; st.rerun()

# 4. INSUMOS
with tabs[3]:
    with st.form("f_ins"):
        st.subheader("🛠️ Insumos"); d_i = st.text_input("Desc"); v_i = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": d_i, "Valor": v_i}])], ignore_index=True))
    for idx, r in df_insumos.iterrows():
        c_l, c_r = st.columns([0.1, 0.9])
        if c_l.button("🗑️", key=f"d_ins_{idx}"): atualizar_planilha("Insumos", df_insumos.drop(idx))
        c_r.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

# 5. CLIENTES
with tabs[4]:
    with st.form("f_cli"):
        st.subheader("👥 Clientes"); c1, c2 = st.columns(2); n = c1.text_input("Nome"); l = c2.text_input("Loja")
        cid = c1.text_input("Cidade"); tel = c2.text_input("WhatsApp")
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": cid, "Telefone": tel}])], ignore_index=True))
    st.dataframe(df_clientes.sort_values('Nome'), hide_index=True)
    for idx, r in df_clientes.iterrows():
        if st.button(f"Remover {r['Nome']}", key=f"d_cli_{idx}"): atualizar_planilha("Clientes", df_clientes.drop(idx))

# 6. EXTRATO
with tabs[5]:
    st.subheader("🧾 Extrato")
    p = df_pedidos.assign(Tipo="Venda", Ori="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Ori="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    if not u.empty:
        u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        u = u.sort_values('DT', ascending=False)
        for idx, r in u.iterrows():
            c_d, c_b, c_p, c_t = st.columns([0.05, 0.12, 0.1, 0.73])
            if c_d.button("🗑️", key=f"d_ext_{idx}"):
                df_origem = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                atualizar_planilha(r['Ori'], df_origem[df_origem['Data'] != r['Data']])
            if r['Ori'] == "Pedidos" and r['Status Pagto'] == "Pendente":
                if c_b.button("✅ Receber", key=f"bx_{idx}"):
                    df_p_a = df_pedidos.copy()
                    df_p_a.loc[df_p_a['Data']==r['Data'], 'Status Pagto'] = "Pago"
                    atualizar_planilha("Pedidos", df_p_a)
            if r['Ori'] == "Pedidos":
                c_p.download_button("📄 PDF", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
            st.write(f"**{r['Data']}** | {r['Tipo']} | {r['Cliente'] if r['Tipo']=='Venda' else ''} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

# 7. LEMBRETES
with tabs[6]:
    with st.form("f_lem"):
        st.subheader("📅 Pagar"); ln = st.text_input("O que?"); ld = st.date_input("Venc"); lv = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar_planilha("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True))
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"d_lem_{idx}"): atualizar_planilha("Lembretes", df_lembretes.drop(idx))
        st.write(f"📅 {r['Data']} - {r['Nome']} - R$ {limpar_valor(r['Valor']):.2f}")

# 8. PREÇOS
with tabs[7]:
    if not df_hist_precos.empty:
        df_hist_precos['DT'] = pd.to_datetime(df_hist_precos['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        sel = st.selectbox("Modelo:", sorted(df_hist_precos['Modelo'].unique()))
        st.line_chart(df_hist_precos[df_hist_precos['Modelo'] == sel].sort_values('DT'), x='DT', y='Preco_Unit')
