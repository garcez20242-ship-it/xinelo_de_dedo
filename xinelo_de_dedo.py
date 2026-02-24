import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Xinelo de Dedo v4.9", layout="wide", page_icon="🩴")

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
        pdf.cell(190, 8, f"Data/Hora: {dados_venda.get('Data', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Cliente: {dados_venda.get('Cliente', 'N/A')}", ln=True)
        pdf.cell(190, 8, f"Status: {dados_venda.get('Status Pagto', 'N/A')}", ln=True)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 8, "Itens do Pedido:", ln=True)
        resumo = str(dados_venda.get('Resumo', '')).replace(" | ", "\n")
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(190, 8, resumo)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda.get('Valor Total', 0)):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO E CACHE (PROTEÇÃO COTA 429) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=15)
def carregar_dados_completos():
    def ler(aba, cols):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is None or df.empty: return pd.DataFrame(columns=cols)
            df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
            df.columns = df.columns.str.strip()
            for c in cols:
                if c not in df.columns: df[c] = 0 if c in TAMANHOS_PADRAO else ""
            return df
        except: return pd.DataFrame(columns=cols)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler("Lembretes", ["Nome", "Data", "Valor"]),
        "his": ler("Historico_Precos", ["Data", "Modelo", "Preco_Unit"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

d = carregar_dados_completos()
df_estoque, df_pedidos, df_clientes = d["est"], d["ped"], d["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = d["ins"], d["lem"], d["his"], d["aqui"]

def atualizar(aba, df):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Salvo com sucesso!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL (ORDEM SOLICITADA) ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Forçar Atualização Geral", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.header("💳 Painel Financeiro")
    tem_pendencia = False
    if not df_pedidos.empty:
        pendentes = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not pendentes.empty:
            tem_pendencia = True
            total_pend = pendentes['Valor Total'].apply(limpar_valor).sum()
            st.warning(f"**Total a Receber: R$ {total_pend:.2f}**")
            res_cli = pendentes.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum())
            for cli, val in res_cli.items():
                st.caption(f"👤 {cli}: R$ {val:.2f}")
    
    if not tem_pendencia:
        st.info("Nenhum pagamento pendente no momento.")

    st.divider()
    st.header("⚠️ Alertas de Estoque")
    tem_alerta_estoque = False
    if not df_estoque.empty:
        for _, r in df_estoque.iterrows():
            criticos = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
            if criticos:
                tem_alerta_estoque = True
                st.error(f"**{r['Modelo']}**\n{', '.join(criticos)}")
    
    if not tem_alerta_estoque:
        st.success("Estoque em níveis normais.")

# --- TABS ---
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
            if st.button("➕ Adicionar à Lista"):
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
                atualizar("Estoque", df_atu)
                atualizar("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_t), "Valor Total": total_g}])], ignore_index=True))
                atualizar("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame(hist_n)], ignore_index=True))
                st.session_state.c_ent = []; st.rerun()
    with c2:
        st.subheader("📋 Inventário")
        st.dataframe(df_estoque.sort_values('Modelo'), hide_index=True)
        if not df_estoque.empty:
            m_del = st.selectbox("Remover Modelo:", ["-"] + sorted(list(df_estoque['Modelo'])))
            if m_del != "-" and st.button("🗑️ Apagar do Sistema"):
                atualizar("Estoque", df_estoque[df_estoque['Modelo'] != m_del])

# 2. NOVO MODELO
with tabs[1]:
    with st.form("f_n_m"):
        st.subheader("✨ Cadastrar Novo Modelo")
        n_m = st.text_input("Nome")
        if st.form_submit_button("Cadastrar"):
            if n_m:
                d_n = {"Modelo": n_m}; d_n.update({t: 0 for t in TAMANHOS_PADRAO})
                atualizar("Estoque", pd.concat([df_estoque, pd.DataFrame([d_n])], ignore_index=True))

# 3. VENDAS
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🛒 Carrinho de Vendas")
        v_cli = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Cliente Avulso"])
        v_mod = st.selectbox("Modelo", sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else [])
        v_tam = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        if v_mod:
            est_d = int(float(df_estoque.loc[df_estoque['Modelo'] == v_mod, v_tam].values[0]))
            st.info(f"Estoque disponível: {est_d}")
            v_pre = st.number_input("Preço R$", min_value=0.0)
            v_qtd = st.number_input("Qtd", min_value=1, max_value=max(1, est_d))
            if st.button("➕ Adicionar Item"):
                if 'c_v' not in st.session_state: st.session_state.c_v = []
                st.session_state.c_v.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Sub": v_qtd*v_pre})
                st.rerun()
    with c2:
        if 'c_v' in st.session_state and st.session_state.c_v:
            tot_v, res_v = 0, []
            for i, it in enumerate(st.session_state.c_v):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']} - R$ {it['Sub']:.2f}")
                if st.button("🗑️", key=f"del_c_{i}"): st.session_state.c_v.pop(i); st.rerun()
                tot_v += it['Sub']; res_v.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            st.write(f"### Total: R$ {tot_v:.2f}")
            v_st = st.radio("Pagamento", ["Pago", "Pendente"], horizontal=True)
            v_fo = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "N/A"])
            if st.button("🚀 Finalizar Venda", type="primary"):
                df_e_v = df_estoque.copy()
                for x in st.session_state.c_v:
                    ix = df_e_v.index[df_e_v['Modelo'] == x['Mod']][0]
                    df_e_v.at[ix, x['Tam']] = int(float(df_e_v.at[ix, x['Tam']])) - x['Qtd']
                atualizar("Estoque", df_e_v)
                atualizar("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(res_v), "Valor Total": tot_v, "Status Pagto": v_st, "Forma": v_fo}])], ignore_index=True))
                st.session_state.c_v = []; st.rerun()

# 4. INSUMOS
with tabs[3]:
    with st.form("f_ins"):
        st.subheader("🛠️ Insumos"); d_i = st.text_input("Descrição"); v_i = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar"):
            atualizar("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": d_i, "Valor": v_i}])], ignore_index=True))
    for idx, r in df_insumos.iterrows():
        cl, cr = st.columns([0.1, 0.9])
        if cl.button("🗑️", key=f"di_{idx}"): atualizar("Insumos", df_insumos.drop(idx))
        cr.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

# 5. CLIENTES
with tabs[4]:
    with st.form("f_cli"):
        st.subheader("👥 Cadastro de Clientes")
        c1, c2 = st.columns(2); n = c1.text_input("Nome"); l = c2.text_input("Loja")
        cid = c1.text_input("Cidade"); tel = c2.text_input("WhatsApp")
        if st.form_submit_button("Salvar Cliente"):
            atualizar("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": cid, "Telefone": tel}])], ignore_index=True))
    for idx, r in df_clientes.iterrows():
        cd, ct = st.columns([0.1, 0.9])
        if cd.button("🗑️", key=f"dc_{idx}"): atualizar("Clientes", df_clientes.drop(idx))
        ct.write(f"**{r['Nome']}** - {r['Loja']} ({r['Cidade']}) - {r['Telefone']}")

# 6. EXTRATO
with tabs[5]:
    st.subheader("🧾 Extrato Financeiro")
    p = df_pedidos.assign(Tipo="Venda", Ori="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Ori="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    if not u.empty:
        u['DT'] = pd.to_datetime(u['Data'], dayfirst=True, errors='coerce')
        for idx, r in u.sort_values('DT', ascending=False).iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.05, 0.05, 0.1, 0.8])
                if c1.button("🗑️", key=f"de_{idx}"):
                    orig = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                    atualizar(r['Ori'], orig[orig['Data'] != r['Data']])
                if r['Ori'] == "Pedidos" and "Pendente" in str(r.get('Status Pagto', '')):
                    if c2.button("✅", key=f"px_{idx}"):
                        df_at = df_pedidos.copy()
                        df_at.loc[df_at['Data']==r['Data'], 'Status Pagto'] = "Pago"
                        atualizar("Pedidos", df_at)
                if r['Ori'] == "Pedidos":
                    c3.download_button("📄 PDF", gerar_recibo(r), f"rec_{idx}.pdf", key=f"pd_{idx}")
                st.write(f"**{r['Data']}** | {r['Tipo']} | {r.get('Cliente','')} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

# 7. LEMBRETES
with tabs[6]:
    with st.form("f_lem"):
        st.subheader("📅 Contas a Pagar")
        ln, ld, lv = st.text_input("O que?"), st.date_input("Vencimento"), st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Agendar"):
            atualizar("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True))
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"dl_{idx}"): atualizar("Lembretes", df_lembretes.drop(idx))
        st.write(f"📅 {r['Data']} - {r['Nome']} - R$ {limpar_valor(r['Valor']):.2f}")

# 8. PREÇOS
with tabs[7]:
    if not df_hist_precos.empty:
        df_h = df_hist_precos.copy()
        df_h['DT'] = pd.to_datetime(df_h['Data'], dayfirst=True, errors='coerce')
        df_h['Preco_Unit'] = df_h['Preco_Unit'].apply(limpar_valor)
        sel = st.selectbox("Histórico do Modelo:", sorted(df_h['Modelo'].unique()))
        df_plot = df_h[df_h['Modelo'] == sel].sort_values('DT')
        if not df_plot.empty:
            st.line_chart(df_plot, x='DT', y='Preco_Unit')
            st.table(df_plot[['Data', 'Preco_Unit']].sort_values('DT', ascending=False))
