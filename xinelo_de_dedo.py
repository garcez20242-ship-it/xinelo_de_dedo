import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import io
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Xinelo de Dedo v4.5", layout="wide", page_icon="🩴")

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
        resumo_limpo = str(dados_venda['Resumo']).replace(" | ", "\n")
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(190, 8, resumo_limpo)
        pdf.ln(5)
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, f"VALOR TOTAL: R$ {limpar_valor(dados_venda['Valor Total']):.2f}", ln=True, align="R")
        return pdf.output(dest='S').encode('latin-1')
    except: return b""

# --- CONEXÃO COM CACHE PARA EVITAR ERRO 429 ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=15)
def carregar_tudo():
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

d = carregar_tudo()
df_estoque, df_pedidos, df_clientes = d["est"], d["ped"], d["cli"]
df_insumos, df_lembretes, df_hist_precos, df_aquisicoes = d["ins"], d["lem"], d["his"], d["aqui"]

def salvar(aba, df):
    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet=aba, data=df.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("Salvo!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Erro: {e}")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("💳 Financeiro")
    if not df_pedidos.empty:
        pend = df_pedidos[df_pedidos['Status Pagto'] == "Pendente"]
        if not pend.empty:
            st.warning(f"Fiado Total: R$ {pend['Valor Total'].apply(limpar_valor).sum():.2f}")
            res_cli = pend.groupby('Cliente')['Valor Total'].apply(lambda x: x.apply(limpar_valor).sum())
            for c, v in res_cli.items(): st.caption(f"{c}: R$ {v:.2f}")

    st.divider()
    st.header("⚠️ Estoque Crítico")
    if not df_estoque.empty:
        for _, r in df_estoque.iterrows():
            b = [f"{t}({int(float(r[t]))})" for t in TAMANHOS_PADRAO if (int(float(r[t])) if r[t]!="" else 0) <= 3]
            if b: st.error(f"**{r['Modelo']}**\n{', '.join(b)}")

# --- INTERFACE ---
st.title("🩴 Sistema Xinelo de Dedo v4.5")
t = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato", "📅 Lembretes", "📈 Preços"])

# 1. ESTOQUE INTEGRAL
with t[0]:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("📦 Entrada de Mercadoria")
        mods = sorted(df_estoque['Modelo'].unique()) if not df_estoque.empty else []
        if mods:
            m_e = st.selectbox("Modelo", mods, key="me")
            t_e = st.selectbox("Tamanho", TAMANHOS_PADRAO, key="te")
            q_e = st.number_input("Qtd", min_value=1, key="qe")
            v_e = st.number_input("Custo Unitário R$", min_value=0.0, key="ve")
            if st.button("➕ Adicionar à Lista"):
                if 'lista_e' not in st.session_state: st.session_state.lista_e = []
                st.session_state.lista_e.append({"Mod": m_e, "Tam": t_e, "Qtd": q_e, "Val": v_e})
                st.rerun()
        
        if 'lista_e' in st.session_state and st.session_state.lista_e:
            for i, it in enumerate(st.session_state.lista_e):
                st.write(f"• {it['Mod']} {it['Tam']} (x{it['Qtd']})")
                if st.button("🗑️", key=f"del_le_{i}"): st.session_state.lista_e.pop(i); st.rerun()
            if st.button("✅ Confirmar Tudo"):
                df_atu = df_estoque.copy()
                novos_h, res_compra, v_total = [], [], 0
                for it in st.session_state.lista_e:
                    idx = df_atu.index[df_atu['Modelo'] == it['Mod']][0]
                    df_atu.at[idx, it['Tam']] = int(float(df_atu.at[idx, it['Tam']])) + it['Qtd']
                    novos_h.append({"Data": get_data_hora(), "Modelo": it['Mod'], "Preco_Unit": it['Val']})
                    res_compra.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
                    v_total += (it['Qtd'] * it['Val'])
                salvar("Estoque", df_atu)
                salvar("Aquisicoes", pd.concat([df_aquisicoes, pd.DataFrame([{"Data": get_data_hora(), "Resumo": " | ".join(res_compra), "Valor Total": v_total}])], ignore_index=True))
                salvar("Historico_Precos", pd.concat([df_hist_precos, pd.DataFrame(novos_h)], ignore_index=True))
                st.session_state.lista_e = []; st.rerun()
    with c2:
        st.subheader("📋 Inventário")
        st.dataframe(df_estoque.sort_values("Modelo"), hide_index=True)
        if not df_estoque.empty:
            m_del = st.selectbox("Excluir Modelo:", ["-"] + list(df_estoque['Modelo']))
            if m_del != "-" and st.button("🗑️ Apagar Modelo"):
                salvar("Estoque", df_estoque[df_estoque['Modelo'] != m_del])

# 2. NOVO MODELO INTEGRAL
with t[1]:
    with st.form("f_m"):
        st.subheader("Cadastrar Novo Chinelo")
        n_m = st.text_input("Nome")
        if st.form_submit_button("Salvar Modelo"):
            if n_m:
                d_n = {"Modelo": n_m}; d_n.update({tam: 0 for tam in TAMANHOS_PADRAO})
                salvar("Estoque", pd.concat([df_estoque, pd.DataFrame([d_n])], ignore_index=True))

# 3. VENDAS INTEGRAL
with t[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🛒 Carrinho")
        cl_v = st.selectbox("Cliente", sorted(df_clientes['Nome'].unique()) if not df_clientes.empty else ["Avulso"])
        mo_v = st.selectbox("Chinelo", sorted(df_estoque['Modelo'].unique()))
        ta_v = st.selectbox("Tam ", TAMANHOS_PADRAO)
        est_d = int(float(df_estoque.loc[df_estoque['Modelo'] == mo_v, ta_v].values[0]))
        st.caption(f"Em estoque: {est_d}")
        pr_v = st.number_input("Preço de Venda R$", min_value=0.0)
        qt_v = st.number_input("Qtd ", min_value=1, max_value=max(1, est_d))
        if st.button("🛒 Adicionar"):
            if 'cart' not in st.session_state: st.session_state.cart = []
            st.session_state.cart.append({"Mod": mo_v, "Tam": ta_v, "Qtd": qt_v, "Pre": pr_v})
            st.rerun()
    with c2:
        if 'cart' in st.session_state and st.session_state.cart:
            tot, res = 0, []
            for i, it in enumerate(st.session_state.cart):
                st.write(f"**{it['Mod']} {it['Tam']}** x{it['Qtd']} = R$ {it['Pre']*it['Qtd']:.2f}")
                if st.button("🗑️", key=f"del_c_{i}"): st.session_state.cart.pop(i); st.rerun()
                tot += it['Pre']*it['Qtd']; res.append(f"{it['Mod']}({it['Tam']}x{it['Qtd']})")
            st.write(f"### Total: R$ {tot:.2f}")
            st_v = st.radio("Status Pagto", ["Pago", "Pendente"], horizontal=True)
            fo_v = st.selectbox("Forma", ["Pix", "Dinheiro", "Cartão", "N/A"])
            if st.button("🚀 Finalizar Venda", type="primary"):
                df_e = df_estoque.copy()
                for it in st.session_state.cart:
                    idx = df_e.index[df_e['Modelo'] == it['Mod']][0]
                    df_e.at[idx, it['Tam']] = int(float(df_e.at[idx, it['Tam']])) - it['Qtd']
                salvar("Estoque", df_e)
                nova_v = {"Data": get_data_hora(), "Cliente": cl_v, "Resumo": " | ".join(res), "Valor Total": tot, "Status Pagto": st_v, "Forma": fo_v}
                salvar("Pedidos", pd.concat([df_pedidos, pd.DataFrame([nova_v])], ignore_index=True))
                st.session_state.cart = []; st.rerun()

# 4. INSUMOS INTEGRAL
with t[3]:
    with st.form("f_i"):
        st.subheader("🛠️ Gastos Diversos")
        d_i, v_i = st.text_input("Descrição"), st.number_input("Valor", min_value=0.0)
        if st.form_submit_button("Salvar Insumo"):
            salvar("Insumos", pd.concat([df_insumos, pd.DataFrame([{"Data": get_data_hora(), "Descricao": d_i, "Valor": v_i}])], ignore_index=True))
    for idx, r in df_insumos.iterrows():
        c_l, c_r = st.columns([0.1, 0.9])
        if c_l.button("🗑️", key=f"d_ins_{idx}"): salvar("Insumos", df_insumos.drop(idx))
        c_r.write(f"{r['Data']} - {r['Descricao']} - R$ {limpar_valor(r['Valor']):.2f}")

# 5. CLIENTES INTEGRAL (RESTAURADO)
with t[4]:
    with st.form("f_c"):
        st.subheader("👥 Cadastro de Clientes")
        c1, c2 = st.columns(2)
        n = c1.text_input("Nome")
        l = c2.text_input("Loja")
        cid = c1.text_input("Cidade")
        tel = c2.text_input("Telefone")
        if st.form_submit_button("Salvar Cliente"):
            salvar("Clientes", pd.concat([df_clientes, pd.DataFrame([{"Nome": n, "Loja": l, "Cidade": cid, "Telefone": tel}])], ignore_index=True))
    for idx, r in df_clientes.iterrows():
        c_del, c_txt = st.columns([0.1, 0.9])
        if c_del.button("🗑️", key=f"dc_{idx}"): salvar("Clientes", df_clientes.drop(idx))
        c_txt.write(f"**{r['Nome']}** - {r['Loja']} ({r['Cidade']}) - {r['Telefone']}")

# 6. EXTRATO INTEGRAL (LIXEIRA, PAGO, PDF)
with t[5]:
    st.subheader("🧾 Histórico Financeiro")
    p = df_pedidos.assign(Tipo="Venda", Ori="Pedidos")
    a = df_aquisicoes.assign(Tipo="Compra", Ori="Aquisicoes")
    i = df_insumos.assign(Tipo="Insumo", Ori="Insumos").rename(columns={"Descricao": "Resumo", "Valor": "Valor Total"})
    u = pd.concat([p, a, i], ignore_index=True)
    if not u.empty:
        u['DT'] = pd.to_datetime(u['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        for idx, r in u.sort_values('DT', ascending=False).iterrows():
            c_d, c_b, c_p, c_t = st.columns([0.05, 0.12, 0.1, 0.73])
            if c_d.button("🗑️", key=f"d_ex_{idx}"):
                origem = df_pedidos if r['Ori']=="Pedidos" else df_aquisicoes if r['Ori']=="Aquisicoes" else df_insumos
                salvar(r['Ori'], origem[origem['Data'] != r['Data']])
            if r['Ori'] == "Pedidos" and r['Status Pagto'] == "Pendente":
                if c_b.button("✅ Receber", key=f"bx_{idx}"):
                    df_atu_p = df_pedidos.copy()
                    df_atu_p.loc[df_atu_p['Data']==r['Data'], 'Status Pagto'] = "Pago"
                    salvar("Pedidos", df_atu_p)
            if r['Ori'] == "Pedidos":
                c_p.download_button("📄 PDF", gerar_recibo(r), f"recibo_{idx}.pdf", key=f"pdf_{idx}")
            c_t.write(f"**{r['Data']}** | {r['Tipo']} | {r['Cliente'] if r['Tipo']=='Venda' else ''} | {r['Resumo']} | **R$ {limpar_valor(r['Valor Total']):.2f}** ({r.get('Status Pagto', 'OK')})")

# 7. LEMBRETES INTEGRAL
with t[6]:
    with st.form("f_l"):
        st.subheader("📅 Contas a Pagar")
        ln, ld, lv = st.text_input("O que?"), st.date_input("Vencimento"), st.number_input("Valor R$", min_value=0.0)
        if st.form_submit_button("Agendar"):
            salvar("Lembretes", pd.concat([df_lembretes, pd.DataFrame([{"Nome": ln, "Data": ld.strftime("%d/%m/%Y"), "Valor": lv}])], ignore_index=True))
    for idx, r in df_lembretes.iterrows():
        if st.button("🗑️", key=f"dl_{idx}"): salvar("Lembretes", df_lembretes.drop(idx))
        st.write(f"📅 {r['Data']} - {r['Nome']} - R$ {limpar_valor(r['Valor']):.2f}")

# 8. PREÇOS INTEGRAL
with t[7]:
    if not df_hist_precos.empty:
        df_hist_precos['DT'] = pd.to_datetime(df_hist_precos['Data'], format='%d/%m/%Y %H:%M', errors='coerce')
        sel = st.selectbox("Ver Histórico de:", sorted(df_hist_precos['Modelo'].unique()))
        st.line_chart(df_hist_precos[df_hist_precos['Modelo'] == sel].sort_values('DT'), x='DT', y='Preco_Unit')
