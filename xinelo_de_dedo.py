import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Xinelo de Dedo v5.5", layout="wide", page_icon="🩴")

# --- TÍTULO ---
st.title("🩴 Gestão Xinelo de Dedo v5.5")
st.markdown("---")

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

# --- CONEXÃO E CARREGAMENTO SEGURO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def carregar_dados():
    def ler(aba, colunas):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                df.columns = df.columns.str.strip()
                return df
            return pd.DataFrame(columns=colunas)
        except: return pd.DataFrame(columns=colunas)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto", "Forma"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "lem": ler("Lembretes", ["Nome", "Data", "Valor"]),
        "his": ler("Historico_Precos", ["Data", "Modelo", "Preco_Unit"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

d = carregar_dados()
df_estoque = d["est"].sort_values("Modelo") if not d["est"].empty else d["est"]
df_pedidos, df_clientes = d["ped"], d["cli"].sort_values("Nome") if not d["cli"].empty else d["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = d["ins"], d["lem"], d["his"], d["aqui"]

def atualizar(aba, df_novo, df_antigo):
    if not df_antigo.empty and df_novo.empty:
        st.error("🚨 TRAVA DE SEGURANÇA: O sistema detectou uma falha de leitura e impediu que a planilha fosse apagada. Tente novamente.")
        return
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Sincronizado!")
        time.sleep(0.5); st.rerun()
    except Exception as e: st.error(f"Erro: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔄 Sistema")
    if st.button("Forçar Atualização Geral"):
        st.cache_data.clear(); st.rerun()
    
    st.divider()
    st.header("💳 Painel Financeiro")
    if not df_pedidos.empty:
        pend = df_pedidos[df_pedidos['Status Pagto'].str.contains("Pendente", case=False, na=False)]
        if not pend.empty:
            st.warning(f"**Total a Receber: R$ {pend['Valor Total'].apply(limpar_valor).sum():.2f}**")
            for c, v in pend.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum()).items():
                st.caption(f"👤 {c}: R$ {v:.2f}")
    
    st.divider()
    st.header("⚠️ Alertas de Estoque")
    tem_alerta = False
    for _, r in df_estoque.iterrows():
        crit = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
        if crit:
            st.error(f"**{r['Modelo']}**\n{', '.join(crit)}")
            tem_alerta = True
    if not tem_alerta: st.success("Estoque OK.")

# --- ABAS ---
t = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# 1. ESTOQUE (ORDEM ALFABÉTICA + ENTRADA)
with t[0]:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada Múltipla")
        m_ent = st.selectbox("Modelo", df_estoque['Modelo'].unique()) if not df_estoque.empty else None
        t_ent = st.selectbox("Tamanho", TAMANHOS_PADRAO)
        q_ent = st.number_input("Quantidade", min_value=1)
        v_ent = st.number_input("Custo Unit R$", min_value=0.0)
        if st.button("Confirmar Entrada") and m_ent:
            df_atu = df_estoque.copy()
            idx = df_atu.index[df_atu['Modelo'] == m_ent][0]
            df_atu.at[idx, t_ent] = int(float(df_atu.at[idx, t_ent])) + q_ent
            atualizar("Estoque", df_atu, df_estoque)
            atualizar("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": f"{m_ent}({t_ent}x{q_ent})", "Valor Total": q_ent*v_ent}])]), df_aquisicoes)
            atualizar("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame([{"Data": get_data_hora(), "Modelo": m_ent, "Preco_Unit": v_ent}])]), df_hist_precos)
    with c2:
        st.subheader("📋 Inventário A-Z")
        st.dataframe(df_estoque, hide_index=True)

# 2. NOVO MODELO
with t[1]:
    with st.form("n_mod"):
        n_m = st.text_input("Nome do Modelo")
        if st.form_submit_button("Cadastrar"):
            if n_m:
                novo = {"Modelo": n_m}; novo.update({tam: 0 for tam in TAMANHOS_PADRAO})
                atualizar("Estoque", pd.concat([df_estoque, pd.DataFrame([novo])]), df_estoque)

# 3. VENDAS (CARRINHO COMPLETO)
with t[2]:
    c1, c2 = st.columns(2)
    with c1:
        v_cli = st.selectbox("Cliente", list(df_clientes['Nome'].unique()) + ["Avulso"])
        v_mod = st.selectbox("Modelo ", df_estoque['Modelo'].unique()) if not df_estoque.empty else None
        v_tam = st.selectbox("Tam ", TAMANHOS_PADRAO)
        v_pre = st.number_input("Preço R$", min_value=0.0)
        v_qtd = st.number_input("Qtd ", min_value=1)
        if st.button("➕ Add Carrinho"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": v_mod, "Tam": v_tam, "Qtd": v_qtd, "Pre": v_pre})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']} - R$ {it['Pre']*it['Qtd']:.2f}")
                if st.button("🗑️", key=f"c_{i}"): st.session_state.cart.pop(i); st.rerun()
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            v_st = st.radio("Pagto", ["Pago", "Pendente"], horizontal=True)
            v_fo = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão"])
            if st.button("🚀 Finalizar Venda", type="primary"):
                df_e = df_estoque.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                atualizar("Estoque", df_e, df_estoque)
                atualizar("Pedidos", pd.concat([df_pedidos, pd.DataFrame([{"Data": get_data_hora(), "Cliente": v_cli, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": v_st, "Forma": v_fo}])]), df_pedidos)
                st.session_state.cart = []; st.rerun()

# 4. INSUMOS
with t[3]:
    with st.form("f_ins"):
        desc_i = st.text_input("Gasto com quê?"); val_i = st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar Gasto"):
            atualizar("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": desc_i, "Valor": val_i}])]), df_insumos)
    st.dataframe(df_insumos, hide_index=True)

# 5. CLIENTES (COMPLETO: LOJA, CIDADE, TEL)
with t[4]:
    with st.form("f_cli"):
        co1, co2 = st.columns(2)
        n = co1.text_input("Nome")
        loj = co2.text_input("Loja")
        cid = co1.text_input("Cidade")
        tel = co2.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            atualizar("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": loj, "Cidade": cid, "Telefone": tel}])]), df_clientes)
    st.dataframe(df_clientes, hide_index=True)

# 6. EXTRATO (LIXEIRA + PAGO + PDF)
with t[5]:
    st.subheader("🧾 Movimentações")
    vendas = df_pedidos.assign(Tipo="VENDA", Ori="Pedidos")
    compras = df_aquisicoes.assign(Tipo="COMPRA", Ori="Aquisicoes")
    ins = df_insumos.assign(Tipo="INSUMO", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    tudo = pd.concat([vendas, compras, ins], ignore_index=True)
    if not tudo.empty:
        tudo['DT_O'] = pd.to_datetime(tudo['Data'], dayfirst=True, errors='coerce')
        for idx, r in tudo.sort_values('DT_O', ascending=False).iterrows():
            with st.container(border=True):
                cl1, cl2, cl3, cl4 = st.columns([0.05, 0.05, 0.05, 0.85])
                if cl1.button("🗑️", key=f"del_{idx}"):
                    df_ori = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                    atualizar(r['Ori'], df_ori[df_ori['Data'] != r['Data']], df_ori)
                if r['Ori'] == "Pedidos" and "Pendente" in str(r['Status Pagto']) and cl2.button("✅", key=f"ok_{idx}"):
                    df_up = df_pedidos.copy(); df_up.loc[df_up['Data']==r['Data'], 'Status Pagto'] = "Pago"
                    atualizar("Pedidos", df_up, df_pedidos)
                if r['Ori'] == "Pedidos":
                    cl3.download_button("📄", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
                st.write(f"**{r['Data']}** | {r['Tipo']} | {r.get('Cliente','')} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}**")

# 7. LEMBRETES
with t[6]:
    with st.form("f_lem"):
        ln, lv = st.text_input("Lembrar de:"), st.number_input("Valor R$ ", min_value=0.0)
        if st.form_submit_button("Agendar"):
            atualizar("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Data": get_data_hora(), "Nome": ln, "Valor": lv}])]), df_lembretes)
    st.dataframe(df_lembretes, hide_index=True)

# 8. PREÇOS (HISTÓRICO)
with t[7]:
    if not df_hist_precos.empty:
        df_h = df_hist_precos.copy()
        df_h['DT'] = pd.to_datetime(df_h['Data'], dayfirst=True, errors='coerce')
        df_h['Preco_Unit'] = df_h['Preco_Unit'].apply(limpar_valor)
        sel = st.selectbox("Histórico do Modelo:", df_h['Modelo'].unique())
        st.line_chart(df_h[df_h['Modelo']==sel].sort_values('DT'), x='DT', y='Preco_Unit')
