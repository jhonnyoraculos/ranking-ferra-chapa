from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).parent
LOGO_FILE = BASE_DIR / "logo-jr.png"
REQUIRED_COLUMNS = {
    "Pedido origem",
    "Endereço",
    "Setor",
    "Produto",
    "Qtde. separado",
    "Nome separador",
    "Func. conferência",
}
PALETTE = ["#22346f", "#c5152f", "#d87900", "#1f4d8f", "#263238", "#00856f", "#8b3ffc"]


st.set_page_config(
    page_title="Dashboard Chaparia",
    page_icon=str(LOGO_FILE) if LOGO_FILE.exists() else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

TABLE_COLUMN_CONFIG = {
    "Qtd. separada": st.column_config.NumberColumn("Qtd. separada", format="%d"),
    "Qtd. conferida": st.column_config.NumberColumn("Qtd. conferida", format="%d"),
    "Qtde. separado": st.column_config.NumberColumn("Qtde. separado", format="%d"),
    "Peso": st.column_config.TextColumn("Peso"),
    "Peso medio": st.column_config.TextColumn("Peso medio"),
    "Linhas": st.column_config.NumberColumn("Linhas", format="%d"),
    "Pedidos": st.column_config.NumberColumn("Pedidos", format="%d"),
    "Setores": st.column_config.NumberColumn("Setores", format="%d"),
}


def find_excel_file() -> Path:
    files = sorted(
        [*BASE_DIR.glob("*.xls"), *BASE_DIR.glob("*.xlsx")],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise FileNotFoundError("Nenhuma planilha .xls ou .xlsx encontrada na pasta.")
    return files[0]


@st.cache_data(show_spinner="Carregando planilha...")
def load_data(excel_path: Path, file_version: int) -> pd.DataFrame:
    raw = pd.read_excel(excel_path, sheet_name=0, header=None)

    header_row = None
    for index, row in raw.iterrows():
        values = {str(value).strip() for value in row.dropna().tolist()}
        if {"Pedido origem", "Endereço", "Setor", "Produto"}.issubset(values):
            header_row = index
            break

    if header_row is None:
        raise ValueError("Nao encontrei o cabecalho esperado na planilha.")

    df = pd.read_excel(excel_path, sheet_name=0, header=header_row)
    df = df.dropna(how="all")
    df.columns = [str(column).strip() for column in df.columns]

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Colunas obrigatorias ausentes: {missing_list}")

    text_columns = [
        "Pedido origem",
        "Endereço",
        "Setor",
        "Produto",
        "Nome separador",
        "Func. conferência",
        "Placa",
    ]
    for column in text_columns:
        if column in df.columns:
            df[column] = df[column].astype("string").str.strip()

    df["Qtde. separado"] = (
        df["Qtde. separado"]
        .astype("string")
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    df["Qtde. separado"] = pd.to_numeric(df["Qtde. separado"], errors="coerce").fillna(0)

    if "Peso" in df.columns:
        df["Peso"] = (
            df["Peso"]
            .astype("string")
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        df["Peso"] = pd.to_numeric(df["Peso"], errors="coerce").fillna(0)
    else:
        df["Peso"] = 0

    for column in ["Data separação", "Data conferência"]:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], dayfirst=True, errors="coerce")

    return df[df["Setor"].notna() & df["Produto"].notna()].copy()


def format_number(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def format_weight(value: float) -> str:
    return format_number(round(value))


def format_weight_unit(value: float) -> str:
    if pd.isna(value):
        return ""
    if abs(value) >= 1000:
        return f"{format_weight(value / 1000)} t"
    return f"{format_weight(value)} kg"


def format_weight_columns(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    for column in ["Peso", "Peso medio"]:
        if column in data.columns:
            data[column] = data[column].map(format_weight_unit)
    return data


def aggregate_people(df: pd.DataFrame, person_column: str, sort_column: str) -> pd.DataFrame:
    return (
        df.dropna(subset=[person_column])
        .groupby(["Setor", person_column], as_index=False)
        .agg(
            quantidade=("Qtde. separado", "sum"),
            peso=("Peso", "sum"),
            linhas=("Pedido origem", "size"),
            pedidos=("Pedido origem", "nunique"),
        )
        .sort_values(["Setor", sort_column], ascending=[True, False])
    )


def aggregate_top(df: pd.DataFrame, group_column: str, sort_column: str) -> pd.DataFrame:
    return (
        df.dropna(subset=[group_column])
        .groupby(group_column, as_index=False)
        .agg(
            quantidade=("Qtde. separado", "sum"),
            peso=("Peso", "sum"),
            linhas=("Pedido origem", "size"),
            pedidos=("Pedido origem", "nunique"),
        )
        .sort_values(sort_column, ascending=False)
    )


def aggregate_weight_by_worker(df: pd.DataFrame) -> pd.DataFrame:
    result = (
        df.dropna(subset=["Nome separador"])
        .groupby("Nome separador", as_index=False)
        .agg(
            quantidade=("Qtde. separado", "sum"),
            peso=("Peso", "sum"),
            linhas=("Pedido origem", "size"),
            pedidos=("Pedido origem", "nunique"),
            setores=("Setor", "nunique"),
        )
        .sort_values("peso", ascending=False)
    )
    result["peso_medio"] = result["peso"] / result["linhas"].replace(0, pd.NA)
    return result


def shorten_labels(data: pd.DataFrame, source: str, target: str, max_chars: int = 44) -> pd.DataFrame:
    data = data.copy()
    data[target] = data[source].astype(str).str.slice(0, max_chars)
    data.loc[data[source].astype(str).str.len() > max_chars, target] += "..."
    return data


def horizontal_bar(data: pd.DataFrame, x: str, y: str, color: str | None = None, height: int = 430):
    data = data.copy()
    value_name = "Peso" if x == "peso" else "Quantidade"
    if x == "peso":
        use_tons = data[x].max() >= 1000
        data["_plot_valor"] = data[x] / 1000 if use_tons else data[x]
        data["_label_valor"] = data[x].map(format_weight_unit)
        axis_title = "Peso (t)" if use_tons else "Peso (kg)"
    else:
        data["_plot_valor"] = data[x]
        data["_label_valor"] = data[x].map(format_number)
        axis_title = "Quantidade"

    fig = px.bar(
        data,
        x="_plot_valor",
        y=y,
        color=color,
        orientation="h",
        text="_label_valor",
        color_discrete_sequence=PALETTE,
        custom_data=[column for column in ["Setor", "peso", "linhas", "pedidos"] if column in data.columns],
    )
    fig.update_traces(
        texttemplate="%{text}",
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        hovertemplate=f"<b>%{{y}}</b><br>{value_name}: %{{text}}<extra></extra>",
    )
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=42, t=12, b=8),
        xaxis_title=axis_title,
        yaxis_title=None,
        legend_title_text="Setor",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#263238", size=12),
        bargap=0.28,
    )
    fig.update_xaxes(showgrid=True, gridcolor="#edf0f4", zeroline=False)
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=12))
    return fig


def render_metric(label: str, value: float, detail: str, formatter=format_number, suffix: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <span>{label}</span>
            <strong>{formatter(value)}{suffix}</strong>
            <small>{detail}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="panel-title">
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


excel_file = find_excel_file()
df = load_data(excel_file, excel_file.stat().st_mtime_ns)

st.markdown(
    """
    <style>
    :root {
        --jr-red: #c5152f;
        --jr-blue: #1f4d8f;
        --jr-navy: #22346f;
        --jr-navy-dark: #1b2a60;
        --ink: #1d2939;
        --muted: #667085;
        --line: #cfdbef;
        --paper: #f4f7fc;
    }

    .stApp {
        background: var(--paper);
        background-image:
            radial-gradient(circle at 11% 34%, rgba(34,52,111,.16) 0 2px, transparent 3px),
            radial-gradient(circle at 50% 25%, rgba(197,21,47,.13) 0 2px, transparent 3px),
            radial-gradient(circle at 83% 64%, rgba(34,52,111,.14) 0 2px, transparent 3px);
        background-size: 360px 360px, 420px 420px, 520px 520px;
    }

    section[data-testid="stSidebar"] {
        display: none;
    }

    .block-container {
        max-width: 1540px;
        padding: 0 1.5rem 2.5rem;
    }

    .app-hero {
        background: var(--jr-navy);
        border-bottom: 1px solid rgba(255,255,255,.08);
        box-shadow: 0 14px 34px rgba(27, 42, 96, .22);
        color: #ffffff;
        padding: 26px 32px 22px;
        margin: 0 -1.5rem 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 22px;
        min-height: 104px;
    }

    .app-hero h1 {
        font-size: clamp(1.2rem, 1.6vw, 1.7rem);
        line-height: 1.15;
        margin: 0;
        letter-spacing: 0;
        font-weight: 800;
    }

    .app-hero p {
        color: rgba(255,255,255,.78);
        margin: 6px 0 0;
        font-size: .95rem;
    }

    .hero-brand {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .hero-logo {
        background: transparent;
        border-radius: 8px;
        padding: 0;
        width: 46px;
        height: 46px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 auto;
    }

    .hero-logo img {
        max-width: 46px;
        max-height: 46px;
        border-radius: 8px;
    }

    .filter-shell {
        background: var(--jr-navy);
        margin: 0 -1.5rem -50px;
        padding: 0 32px 78px;
    }

    .filter-title {
        color: rgba(255,255,255,.72);
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: 0;
        margin: 0 0 8px;
    }

    .dashboard-spacer {
        height: 64px;
    }

    .metric-card {
        background: #ffffff;
        border: 1px solid #c6d6ef;
        border-top: 4px solid var(--jr-navy);
        border-radius: 8px;
        padding: 24px 18px;
        min-height: 126px;
        text-align: center;
        box-shadow: 0 18px 38px rgba(27, 42, 96, .12);
    }

    .metric-card span {
        display: block;
        color: var(--muted);
        font-size: .76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0;
    }

    .metric-card strong {
        display: block;
        color: var(--jr-navy);
        font-size: 1.85rem;
        line-height: 1.1;
        margin-top: 12px;
        letter-spacing: 0;
    }

    .metric-card small {
        display: block;
        color: var(--muted);
        margin-top: 8px;
        font-size: .82rem;
    }

    .panel-title {
        margin: 30px 0 10px;
    }

    .panel-title h2 {
        color: var(--jr-navy);
        font-size: 1rem;
        margin: 0;
        letter-spacing: 0;
        font-weight: 800;
    }

    .panel-title h2::after {
        content: "";
        display: block;
        width: 34px;
        height: 3px;
        background: var(--jr-red);
        border-radius: 999px;
        margin-top: 10px;
    }

    .panel-title p {
        color: var(--muted);
        font-size: .9rem;
        margin: 6px 0 0;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px;
        border-color: #c8d3e4;
        box-shadow: 0 16px 34px rgba(27, 42, 96, .08);
        background: rgba(255,255,255,.92);
    }

    div[data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid var(--line);
    }

    .stTabs [data-baseweb="tab"] {
        height: 40px;
        padding: 0 14px;
        border-radius: 8px 8px 0 0;
        color: var(--muted);
    }

    .stTabs [aria-selected="true"] {
        color: var(--jr-red);
        font-weight: 700;
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {
        border-radius: 8px;
    }

    div[data-testid="stSelectbox"] label,
    div[data-testid="stMultiSelect"] label,
    div[data-testid="stDateInput"] label,
    div[data-testid="stSlider"] label,
    div[data-testid="stRadio"] label {
        color: rgba(255,255,255,.74);
        font-size: .76rem;
        font-weight: 800;
    }

    div[data-testid="stSelectbox"] > div > div,
    div[data-testid="stDateInput"] input,
    div[data-testid="stNumberInput"] input {
        min-height: 40px;
    }

    div[data-testid="stButton"] button {
        background: var(--jr-red);
        color: #ffffff;
        border: 0;
        border-radius: 8px;
        min-height: 40px;
        font-weight: 800;
        box-shadow: none;
    }

    div[data-testid="stButton"] button:hover {
        background: #a91227;
        color: #ffffff;
        border: 0;
    }

    .main .block-container > div:nth-child(5) {
        margin-top: -44px;
    }

    @media (max-width: 800px) {
        .block-container {
            padding: 0 1rem 1.5rem;
        }
        .app-hero {
            align-items: flex-start;
            flex-direction: column;
            margin: 0 -1rem 0;
            padding: 20px 18px;
        }
        .filter-shell {
            margin: 0 -1rem -28px;
            padding: 0 18px 54px;
        }
        .main .block-container > div:nth-child(5) {
            margin-top: -22px;
        }
        .dashboard-spacer {
            height: 34px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

logo_html = ""
if LOGO_FILE.exists():
    import base64

    encoded_logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("utf-8")
    logo_html = f'<div class="hero-logo"><img src="data:image/png;base64,{encoded_logo}" /></div>'

st.markdown(
    f"""
    <div class="app-hero">
        <div class="hero-brand">
            {logo_html}
            <div>
                <h1>JR DASHBOARD • Ranking ferragem e chaparia</h1>
                <p>Separação, conferência, peso por colaborador, produtos e endereços.</p>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

setores = sorted(df["Setor"].dropna().unique().tolist())
date_column = "Data separação" if "Data separação" in df.columns else None
if date_column and df[date_column].notna().any():
    min_date = df[date_column].min().date()
    max_date = df[date_column].max().date()
else:
    min_date = None
    max_date = None

if "setor_filter" not in st.session_state:
    st.session_state.setor_filter = "Todos"
if "metric_filter" not in st.session_state:
    st.session_state.metric_filter = "Quantidade"
if "top_n_filter" not in st.session_state:
    st.session_state.top_n_filter = 10
if "date_filter" not in st.session_state and min_date and max_date:
    st.session_state.date_filter = (min_date, max_date)


def reset_filters() -> None:
    st.session_state.setor_filter = "Todos"
    st.session_state.metric_filter = "Quantidade"
    st.session_state.top_n_filter = 10
    if min_date and max_date:
        st.session_state.date_filter = (min_date, max_date)

st.markdown('<div class="filter-shell"><div class="filter-title">FILTROS</div></div>', unsafe_allow_html=True)
filter_cols = st.columns([1.4, 2.2, 1.6, 1.3, 1.5, 1.2])
with filter_cols[0]:
    selected_setor = st.selectbox(
        "Setor",
        ["Todos", *setores],
        key="setor_filter",
        label_visibility="collapsed",
    )
with filter_cols[1]:
    if min_date and max_date:
        selected_dates = st.date_input(
            "Período",
            value=st.session_state.date_filter,
            min_value=min_date,
            max_value=max_date,
            format="DD/MM/YYYY",
            key="date_filter",
            label_visibility="collapsed",
        )
    else:
        selected_dates = None
with filter_cols[2]:
    selected_metric = st.selectbox(
        "Ordenar por",
        ["Quantidade", "Peso"],
        key="metric_filter",
        label_visibility="collapsed",
    )
with filter_cols[3]:
    top_n = st.selectbox(
        "Top N",
        [5, 10, 15, 20, 25],
        format_func=lambda value: f"Top {value}",
        key="top_n_filter",
        label_visibility="collapsed",
    )
with filter_cols[4]:
    st.button("Limpar filtros", width="stretch", on_click=reset_filters)
with filter_cols[5]:
    st.button("Atualizar", width="stretch")

selected_setores = setores if selected_setor == "Todos" else [selected_setor]

filtered = df[df["Setor"].isin(selected_setores)].copy()

if isinstance(selected_dates, tuple) and date_column and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    filtered = filtered[
        filtered[date_column].dt.date.between(start_date, end_date, inclusive="both")
    ]

if filtered.empty:
    st.warning("Nenhum registro encontrado para os filtros selecionados.")
    st.stop()

st.markdown('<div class="dashboard-spacer"></div>', unsafe_allow_html=True)

total_qtd = filtered["Qtde. separado"].sum()
total_peso = filtered["Peso"].sum()
total_linhas = len(filtered)
total_pedidos = filtered["Pedido origem"].nunique()
total_setores = filtered["Setor"].nunique()
metric_column = "peso" if selected_metric == "Peso" else "quantidade"
top_sector = (
    filtered.groupby("Setor")["Peso" if metric_column == "peso" else "Qtde. separado"]
    .sum()
    .sort_values(ascending=False)
    .index[0]
)

metric_cols = st.columns(5)
with metric_cols[0]:
    render_metric("Qtd. separada", total_qtd, "soma das unidades")
with metric_cols[1]:
    render_metric("Peso total", total_peso, "peso dos itens", formatter=format_weight_unit)
with metric_cols[2]:
    render_metric("Linhas", total_linhas, "registros filtrados")
with metric_cols[3]:
    render_metric("Pedidos", total_pedidos, "pedidos distintos")
with metric_cols[4]:
    render_metric("Setores", total_setores, f"Líder: {top_sector}")

separator_rank = aggregate_people(filtered, "Nome separador", metric_column)
checker_rank = aggregate_people(filtered, "Func. conferência", metric_column)
product_rank = aggregate_top(filtered, "Produto", metric_column)
address_rank = aggregate_top(filtered, "Endereço", metric_column)
sector_rank = aggregate_top(filtered, "Setor", metric_column)
worker_weight_rank = aggregate_weight_by_worker(filtered)

render_panel_title(
    "Visão por setor",
    f"Distribuição por {selected_metric.lower()} entre os setores filtrados.",
)
with st.container(border=True):
    st.plotly_chart(
        horizontal_bar(sector_rank, metric_column, "Setor", height=330),
        width="stretch",
    )

render_panel_title(
    "Colaboradores",
    "Quem mais separou e conferiu, mantendo a quebra por setor.",
)
separator_tab, checker_tab = st.tabs(["Separação", "Conferência"])

with separator_tab:
    chart_data = separator_rank.groupby("Setor", group_keys=False).head(top_n)
    chart_data = chart_data.assign(
        colaborador_setor=chart_data["Nome separador"] + " | " + chart_data["Setor"]
    )
    with st.container(border=True):
        st.plotly_chart(
            horizontal_bar(chart_data, metric_column, "colaborador_setor", "Setor", height=520),
            width="stretch",
        )
    st.dataframe(
        format_weight_columns(
            chart_data.rename(
                columns={
                    "Nome separador": "Colaborador",
                    "quantidade": "Qtd. separada",
                    "peso": "Peso",
                    "linhas": "Linhas",
                    "pedidos": "Pedidos",
                }
            )[["Setor", "Colaborador", "Qtd. separada", "Peso", "Linhas", "Pedidos"]]
        ),
        hide_index=True,
        width="stretch",
        column_config=TABLE_COLUMN_CONFIG,
    )

with checker_tab:
    chart_data = checker_rank.groupby("Setor", group_keys=False).head(top_n)
    chart_data = chart_data.assign(
        colaborador_setor=chart_data["Func. conferência"] + " | " + chart_data["Setor"]
    )
    with st.container(border=True):
        st.plotly_chart(
            horizontal_bar(chart_data, metric_column, "colaborador_setor", "Setor", height=520),
            width="stretch",
        )
    st.dataframe(
        format_weight_columns(
            chart_data.rename(
                columns={
                    "Func. conferência": "Colaborador",
                    "quantidade": "Qtd. conferida",
                    "peso": "Peso",
                    "linhas": "Linhas",
                    "pedidos": "Pedidos",
                }
            )[["Setor", "Colaborador", "Qtd. conferida", "Peso", "Linhas", "Pedidos"]]
        ),
        hide_index=True,
        width="stretch",
        column_config=TABLE_COLUMN_CONFIG,
    )

render_panel_title(
    "Peso por colaborador",
    "Separadores que mais carregaram peso no periodo e setores filtrados.",
)
with st.container(border=True):
    top_workers_weight = worker_weight_rank.head(top_n)
    st.plotly_chart(
        horizontal_bar(top_workers_weight, "peso", "Nome separador", height=470),
        width="stretch",
    )
    st.dataframe(
        format_weight_columns(
            top_workers_weight.rename(
                columns={
                    "Nome separador": "Colaborador",
                    "quantidade": "Qtd. separada",
                    "peso": "Peso",
                    "peso_medio": "Peso medio",
                    "linhas": "Linhas",
                    "pedidos": "Pedidos",
                    "setores": "Setores",
                }
            )[["Colaborador", "Peso", "Peso medio", "Qtd. separada", "Linhas", "Pedidos", "Setores"]]
        ),
        hide_index=True,
        width="stretch",
        column_config=TABLE_COLUMN_CONFIG,
    )

render_panel_title(
    "Itens que mais saíram",
    f"Produtos e endereços ordenados por {selected_metric.lower()}.",
)
product_col, address_col = st.columns(2)

with product_col:
    with st.container(border=True):
        top_products = shorten_labels(product_rank.head(top_n), "Produto", "produto_curto")
        st.markdown("#### Produtos")
        st.plotly_chart(
            horizontal_bar(top_products, metric_column, "produto_curto", height=470),
            width="stretch",
        )
        st.dataframe(
            format_weight_columns(
                top_products.rename(
                    columns={"quantidade": "Qtd. separada", "peso": "Peso", "linhas": "Linhas", "pedidos": "Pedidos"}
                )[["Produto", "Qtd. separada", "Peso", "Linhas", "Pedidos"]]
            ),
            hide_index=True,
            width="stretch",
            column_config=TABLE_COLUMN_CONFIG,
        )

with address_col:
    with st.container(border=True):
        top_addresses = address_rank.head(top_n)
        st.markdown("#### Endereços")
        st.plotly_chart(
            horizontal_bar(top_addresses, metric_column, "Endereço", height=470),
            width="stretch",
        )
        st.dataframe(
            format_weight_columns(
                top_addresses.rename(
                    columns={"quantidade": "Qtd. separada", "peso": "Peso", "linhas": "Linhas", "pedidos": "Pedidos"}
                )[["Endereço", "Qtd. separada", "Peso", "Linhas", "Pedidos"]]
            ),
            hide_index=True,
            width="stretch",
            column_config=TABLE_COLUMN_CONFIG,
        )

with st.expander("Ver base filtrada", expanded=False):
    visible_columns = [
        "Pedido origem",
        "Endereço",
        "Setor",
        "Produto",
        "Qtde. separado",
        "Peso",
        "Nome separador",
        "Data separação",
        "Func. conferência",
        "Data conferência",
        "Placa",
    ]
    st.dataframe(
        format_weight_columns(filtered[[column for column in visible_columns if column in filtered.columns]]),
        hide_index=True,
        width="stretch",
        column_config=TABLE_COLUMN_CONFIG,
    )
