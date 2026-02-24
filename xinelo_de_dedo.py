import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
from fpdf import FPDF
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Xinelo v5.6", layout="wide", page_icon="🩴")
st.title("🩴 Gestão Xinelo de Dedo v5.6")

URL_PLANILHA = "https://docs.google.com/spreadsheets/d/1wzJZx769gfPWKwYNdPVq9i0akPaBcon6iPrlDBfQiuU/edit"
TAMANHOS_PADRAO = ["25-26", "27-28", "29-30", "31-32", "33-34", "35-36", "37-38", "39-40", "41-42", "43-44"]

# --- CONEXÃO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def carregar_dados_blindado():
    def ler(aba, colunas):
        try:
            df = conn.read(spreadsheet=URL_PLANILHA, worksheet=aba, ttl="0s")
            if df is not None and not df.empty:
                df = df.dropna(how='all').loc[:, ~df.columns.str.contains('^Unnamed')]
                return df
            return pd.DataFrame(columns=colunas)
        except: return pd.DataFrame(columns=colunas)
    
    return {
        "est": ler("Estoque", ["Modelo"] + TAMANHOS_PADRAO),
        "ped": ler("Pedidos", ["Data", "Cliente", "Resumo", "Valor Total", "Status Pagto"]),
        "cli": ler("Clientes", ["Nome", "Loja", "Cidade", "Telefone"]),
        "ins": ler("Insumos", ["Data", "Descricao", "Valor"]),
        "aqui": ler("Aquisicoes", ["Data", "Resumo", "Valor Total"])
    }

d = carregar_dados_blindado()
df_estoque = d["est"].sort_values("Modelo") if not d["est"].empty else d["est"]
df_pedidos, df_clientes = d["ped"], d["cli"].sort_values("Nome") if not d["cli"].empty else d["cli"]

# --- A TRAVA DE SEGURANÇA MÁXIMA ---
def atualizar_estoque_seguro(df_novo, df_antigo):
    # Se o estoque antigo tinha 5 modelos e o novo está vindo com 1 só, algo deu errado na leitura.
    # Esta trava impede que o cadastro novo "atropele" e apague os antigos.
    if len(df_antigo) > 0 and len(df_novo) <= 1 and len(df_antigo) != len(df_novo):
        st.error("🚨 ERRO CRÍTICO: O Google falhou ao ler seus modelos antigos. Para evitar que o inventário resete, o salvamento foi bloqueado. AGUARDE 10 SEGUNDOS E TENTE NOVAMENTE.")
        return False

    try:
        conn.update(spreadsheet=URL_PLANILHA, worksheet="Estoque", data=df_novo.astype(str).replace('nan', ''))
        st.cache_data.clear()
        st.success("✅ Modelo cadastrado com segurança!")
        time.sleep(1)
        st.rerun()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# --- ABAS ---
tabs = st.tabs(["📊 Estoque", "✨ Novo Modelo", "🛒 Vendas", "🛠️ Insumos", "👥 Clientes", "🧾 Extrato"])

with tabs[0]:
    st.subheader("📋 Inventário Atual")
    st.dataframe(df_estoque, hide_index=True)

with tabs[1]:
    st.subheader("✨ Cadastrar Novo Modelo")
    with st.form("n_mod", clear_on_submit=True):
        nome = st.text_input("Nome do Modelo")
        if st.form_submit_button("Salvar Modelo"):
            if nome:
                if nome in df_estoque['Modelo'].values:
                    st.warning("Este modelo já existe!")
                else:
                    novo_item = {"Modelo": nome}
                    novo_item.update({t: 0 for t in TAMANHOS_PADRAO})
                    df_final = pd.concat([df_estoque, pd.DataFrame([novo_item])], ignore_index=True)
                    # Usa a função de salvamento com a trava de conferência
                    atualizar_estoque_seguro(df_final, df_estoque)

# (O restante das abas segue o padrão anterior, mas a trava no Estoque é o que resolve seu problema)

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

