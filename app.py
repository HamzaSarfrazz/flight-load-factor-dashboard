"""
Flight Load Factor Dashboard
-----------------------------
Run locally with:
    pip install streamlit pandas plotly
    streamlit run app.py

Expects "Flight_Load_Factor_Data.csv" in the same folder (included alongside
this script). To use your own refreshed data, just overwrite that CSV with
the same column layout:
    Year, Month, MonthDate, Route, Flights, Seat_Capacity, Seats_Occupied, Load_Factor
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Flight Load Factor Dashboard",
    page_icon="\u2708\ufe0f",
    layout="wide",
)

DATA_PATH = "Flight_Load_Factor_Data.csv"


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["MonthDate"])
    df["Route"] = df["Route"].astype(str)
    df["Is_Total_Row"] = df["Route"].str.startswith("TOTAL")

    # Split "110 KHI-DXB" -> route code "110", route name "KHI-DXB"
    split = df["Route"].str.split(" ", n=1, expand=True)
    df["Route_Code"] = split[0]
    df["Route_Name"] = split[1].fillna(df["Route"])
    df.loc[df["Is_Total_Row"], "Route_Name"] = "All Routes (Total)"

    return df


try:
    data = load_data(DATA_PATH)
except FileNotFoundError:
    st.error(
        f"Couldn't find **{DATA_PATH}**. Place it in the same folder as app.py, "
        "or update DATA_PATH at the top of the script."
    )
    st.stop()

totals = data[data["Is_Total_Row"]].copy()
routes_only = data[~data["Is_Total_Row"]].copy()

# ----------------------------------------------------------------------------
# Sidebar filters
# ----------------------------------------------------------------------------
st.sidebar.header("Filters")

years = sorted(data["Year"].unique())
selected_years = st.sidebar.multiselect("Year", years, default=years)

all_routes = sorted(routes_only["Route_Name"].unique())
selected_routes = st.sidebar.multiselect(
    "Route (leave empty for all routes)", all_routes, default=[]
)

st.sidebar.caption(
    "Overall trend charts always use the pre-computed monthly TOTAL rows. "
    "The route filter only affects the route-level table and chart below."
)

totals_f = totals[totals["Year"].isin(selected_years)].sort_values("MonthDate")
routes_f = routes_only[routes_only["Year"].isin(selected_years)]
if selected_routes:
    routes_f = routes_f[routes_f["Route_Name"].isin(selected_routes)]

# ----------------------------------------------------------------------------
# Header + headline metrics
# ----------------------------------------------------------------------------
st.title("\u2708\ufe0f Flight Load Factor Dashboard")
st.caption("Overall and route-level load factor trends over time")

if len(totals_f) >= 2:
    first_val = totals_f.iloc[0]["Load_Factor"] * 100
    last_val = totals_f.iloc[-1]["Load_Factor"] * 100
    delta = last_val - first_val
else:
    first_val = last_val = delta = None

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Latest monthly load factor",
    f"{last_val:.1f}%" if last_val is not None else "N/A",
    f"{delta:+.1f} pts vs first month shown" if delta is not None else None,
)
col2.metric(
    "Average load factor (selected years)",
    f"{totals_f['Load_Factor'].mean()*100:.1f}%" if len(totals_f) else "N/A",
)
col3.metric(
    "Total flights (selected years)",
    f"{int(totals_f['Flights'].sum()):,}" if len(totals_f) else "N/A",
)
col4.metric(
    "Weighted avg. load factor",
    f"{(totals_f['Seats_Occupied'].sum() / totals_f['Seat_Capacity'].sum() * 100):.1f}%"
    if len(totals_f) and totals_f["Seat_Capacity"].sum() > 0
    else "N/A",
)

st.divider()

# ----------------------------------------------------------------------------
# Monthly trend
# ----------------------------------------------------------------------------
st.subheader("Monthly load factor trend (system-wide)")

fig_monthly = px.line(
    totals_f,
    x="MonthDate",
    y="Load_Factor",
    markers=True,
    labels={"MonthDate": "Month", "Load_Factor": "Load Factor"},
)
fig_monthly.update_yaxes(tickformat=".0%", range=[0, 1])
fig_monthly.update_traces(hovertemplate="%{x|%b %Y}<br>Load Factor: %{y:.1%}")
st.plotly_chart(fig_monthly, use_container_width=True)

# ----------------------------------------------------------------------------
# Yearly comparison
# ----------------------------------------------------------------------------
st.subheader("Yearly load factor (weighted)")

yearly = (
    totals_f.groupby("Year")
    .agg(Seats_Occupied=("Seats_Occupied", "sum"), Seat_Capacity=("Seat_Capacity", "sum"))
    .reset_index()
)
yearly["Load_Factor"] = yearly["Seats_Occupied"] / yearly["Seat_Capacity"]

fig_yearly = px.bar(
    yearly,
    x="Year",
    y="Load_Factor",
    text=yearly["Load_Factor"].map(lambda v: f"{v:.1%}"),
    labels={"Load_Factor": "Load Factor"},
)
fig_yearly.update_yaxes(tickformat=".0%", range=[0, 1])
fig_yearly.update_traces(textposition="outside")
fig_yearly.update_layout(xaxis=dict(type="category"))
st.plotly_chart(fig_yearly, use_container_width=True)

if len(yearly) >= 2:
    trend = yearly["Load_Factor"].iloc[-1] - yearly["Load_Factor"].iloc[0]
    direction = "declined" if trend < 0 else "improved"
    st.info(
        f"Weighted load factor has **{direction}** by "
        f"**{abs(trend)*100:.1f} percentage points** from "
        f"{yearly['Year'].iloc[0]} to {yearly['Year'].iloc[-1]} across the years selected."
    )

st.divider()

# ----------------------------------------------------------------------------
# Flights Year-over-Year
# ----------------------------------------------------------------------------
st.subheader("Flights: Year-over-Year")

flights_yearly = (
    totals_f.groupby("Year")
    .agg(Flights=("Flights", "sum"))
    .reset_index()
    .sort_values("Year")
)
flights_yearly["Flights_YoY_Change"] = flights_yearly["Flights"].diff()
flights_yearly["Flights_YoY_Pct"] = flights_yearly["Flights"].pct_change() * 100

col_a, col_b = st.columns([3, 2])

with col_a:
    fig_flights_yoy = go.Figure()
    fig_flights_yoy.add_bar(
        x=flights_yearly["Year"].astype(str),
        y=flights_yearly["Flights"],
        name="Flights",
        text=flights_yearly["Flights"].map(lambda v: f"{int(v):,}"),
        textposition="outside",
    )
    fig_flights_yoy.update_layout(
        yaxis_title="Total Flights",
        xaxis=dict(type="category"),
        showlegend=False,
    )
    st.plotly_chart(fig_flights_yoy, use_container_width=True)

with col_b:
    display_flights = flights_yearly.copy()
    display_flights["Flights"] = display_flights["Flights"].map(lambda v: f"{int(v):,}")
    display_flights["Flights_YoY_Change"] = display_flights["Flights_YoY_Change"].map(
        lambda v: f"{v:+,.0f}" if pd.notna(v) else "\u2014"
    )
    display_flights["Flights_YoY_Pct"] = display_flights["Flights_YoY_Pct"].map(
        lambda v: f"{v:+.1f}%" if pd.notna(v) else "\u2014"
    )
    display_flights = display_flights.rename(
        columns={
            "Flights_YoY_Change": "YoY Change",
            "Flights_YoY_Pct": "YoY %",
        }
    )
    st.dataframe(display_flights, hide_index=True, use_container_width=True)

st.divider()

# ----------------------------------------------------------------------------
# Sector Trend Explorer (multi-year, pick specific sectors)
# ----------------------------------------------------------------------------
st.subheader("Sector Trend Explorer")
st.caption(
    "Pick one or more sectors to see their Flights and Load Factor across every "
    "year in the data (e.g. 'ISB-KHI' or route code '200')."
)

all_sector_labels = sorted(routes_only["Route"].unique())
picked_sectors = st.multiselect(
    "Search by route code or route name (e.g. 200, ISB-KHI)",
    all_sector_labels,
    default=[],
    key="sector_explorer",
)

if picked_sectors:
    sector_hist = (
        routes_only[routes_only["Route"].isin(picked_sectors)]
        .groupby(["Route", "Year"])
        .agg(
            Flights=("Flights", "sum"),
            Seat_Capacity=("Seat_Capacity", "sum"),
            Seats_Occupied=("Seats_Occupied", "sum"),
        )
        .reset_index()
    )
    sector_hist["Load_Factor"] = (
        sector_hist["Seats_Occupied"] / sector_hist["Seat_Capacity"]
    )
    sector_hist = sector_hist.sort_values(["Route", "Year"])

    hist_col1, hist_col2 = st.columns(2)

    with hist_col1:
        fig_hist_lf = px.line(
            sector_hist,
            x="Year",
            y="Load_Factor",
            color="Route",
            markers=True,
            labels={"Load_Factor": "Load Factor"},
            title="Load Factor by Year",
        )
        fig_hist_lf.update_yaxes(tickformat=".0%")
        fig_hist_lf.update_layout(xaxis=dict(type="category"))
        st.plotly_chart(fig_hist_lf, use_container_width=True)

    with hist_col2:
        fig_hist_flights = px.line(
            sector_hist,
            x="Year",
            y="Flights",
            color="Route",
            markers=True,
            title="Flights by Year",
        )
        fig_hist_flights.update_layout(xaxis=dict(type="category"))
        st.plotly_chart(fig_hist_flights, use_container_width=True)

    display_hist = sector_hist.copy()
    display_hist["Load_Factor"] = (display_hist["Load_Factor"] * 100).round(1).astype(str) + "%"
    display_hist["Flights"] = display_hist["Flights"].astype(int)
    display_hist["Seat_Capacity"] = display_hist["Seat_Capacity"].astype(int)
    display_hist["Seats_Occupied"] = display_hist["Seats_Occupied"].astype(int)
    st.dataframe(
        display_hist[["Route", "Year", "Flights", "Seat_Capacity", "Seats_Occupied", "Load_Factor"]],
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info("Choose at least one sector above to see its year-by-year history.")

st.divider()

# ----------------------------------------------------------------------------
# Sector (Route) Year-over-Year
# ----------------------------------------------------------------------------
st.subheader("Sector (Route): Year-over-Year (two-year comparison)")

sector_years = sorted(routes_f["Year"].unique())

if len(sector_years) < 2:
    st.warning("Select at least two years in the sidebar to compare sectors year-over-year.")
else:
    compare_col1, compare_col2 = st.columns(2)
    with compare_col1:
        year_a = st.selectbox("Compare from (base year)", sector_years, index=len(sector_years) - 2)
    with compare_col2:
        year_b = st.selectbox("Compare to (latest year)", sector_years, index=len(sector_years) - 1)

    sector_yearly = (
        routes_f[routes_f["Year"].isin([year_a, year_b])]
        .groupby(["Route_Name", "Year"])
        .agg(
            Flights=("Flights", "sum"),
            Seat_Capacity=("Seat_Capacity", "sum"),
            Seats_Occupied=("Seats_Occupied", "sum"),
        )
        .reset_index()
    )
    sector_yearly["Load_Factor"] = (
        sector_yearly["Seats_Occupied"] / sector_yearly["Seat_Capacity"]
    )

    pivot_flights = sector_yearly.pivot(index="Route_Name", columns="Year", values="Flights")
    pivot_lf = sector_yearly.pivot(index="Route_Name", columns="Year", values="Load_Factor")

    # Only compare sectors that flew in both years
    common_routes = pivot_flights.dropna(subset=[year_a, year_b]).index

    sector_compare = pd.DataFrame(index=common_routes)
    sector_compare[f"Flights {year_a}"] = pivot_flights.loc[common_routes, year_a]
    sector_compare[f"Flights {year_b}"] = pivot_flights.loc[common_routes, year_b]
    sector_compare["Flights YoY %"] = (
        (sector_compare[f"Flights {year_b}"] - sector_compare[f"Flights {year_a}"])
        / sector_compare[f"Flights {year_a}"]
        * 100
    )
    sector_compare[f"Load Factor {year_a}"] = pivot_lf.loc[common_routes, year_a]
    sector_compare[f"Load Factor {year_b}"] = pivot_lf.loc[common_routes, year_b]
    sector_compare["Load Factor YoY (pts)"] = (
        sector_compare[f"Load Factor {year_b}"] - sector_compare[f"Load Factor {year_a}"]
    ) * 100

    sector_compare = sector_compare.reset_index().rename(columns={"index": "Route_Name"})

    tab1, tab2, tab3 = st.tabs(
        ["Biggest load factor declines", "Biggest load factor gains", "Full sector comparison"]
    )

    with tab1:
        st.dataframe(
            sector_compare.sort_values("Load Factor YoY (pts)").head(15).style.format(
                {
                    f"Flights {year_a}": "{:.0f}",
                    f"Flights {year_b}": "{:.0f}",
                    "Flights YoY %": "{:+.1f}%",
                    f"Load Factor {year_a}": "{:.1%}",
                    f"Load Factor {year_b}": "{:.1%}",
                    "Load Factor YoY (pts)": "{:+.1f}",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    with tab2:
        st.dataframe(
            sector_compare.sort_values("Load Factor YoY (pts)", ascending=False).head(15).style.format(
                {
                    f"Flights {year_a}": "{:.0f}",
                    f"Flights {year_b}": "{:.0f}",
                    "Flights YoY %": "{:+.1f}%",
                    f"Load Factor {year_a}": "{:.1%}",
                    f"Load Factor {year_b}": "{:.1%}",
                    "Load Factor YoY (pts)": "{:+.1f}",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    with tab3:
        st.dataframe(
            sector_compare.sort_values("Route_Name").style.format(
                {
                    f"Flights {year_a}": "{:.0f}",
                    f"Flights {year_b}": "{:.0f}",
                    "Flights YoY %": "{:+.1f}%",
                    f"Load Factor {year_a}": "{:.1%}",
                    f"Load Factor {year_b}": "{:.1%}",
                    "Load Factor YoY (pts)": "{:+.1f}",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    dropped = pivot_flights.index[pivot_flights[year_a].notna() & pivot_flights[year_b].isna()]
    added = pivot_flights.index[pivot_flights[year_a].isna() & pivot_flights[year_b].notna()]
    if len(dropped) or len(added):
        st.caption(
            f"{len(dropped)} sector(s) flown in {year_a} were not flown in {year_b}, and "
            f"{len(added)} sector(s) are new in {year_b} \u2014 these are excluded from the "
            "comparison above since there's nothing to compare them against."
        )

st.divider()

# ----------------------------------------------------------------------------
# Route-level breakdown
# ----------------------------------------------------------------------------
st.subheader("Route-level load factor")

route_summary = (
    routes_f.groupby("Route_Name")
    .agg(
        Flights=("Flights", "sum"),
        Seat_Capacity=("Seat_Capacity", "sum"),
        Seats_Occupied=("Seats_Occupied", "sum"),
    )
    .reset_index()
)
route_summary["Load_Factor"] = (
    route_summary["Seats_Occupied"] / route_summary["Seat_Capacity"]
)
route_summary = route_summary.sort_values("Load_Factor", ascending=False)

left, right = st.columns([2, 3])

with left:
    st.markdown("**Lowest load factor routes** (selected years/routes)")
    st.dataframe(
        route_summary.sort_values("Load_Factor").head(10).assign(
            Load_Factor=lambda d: (d["Load_Factor"] * 100).round(1).astype(str) + "%"
        ),
        hide_index=True,
        use_container_width=True,
    )

with right:
    top_n = route_summary.head(20)
    fig_routes = px.bar(
        top_n.sort_values("Load_Factor"),
        x="Load_Factor",
        y="Route_Name",
        orientation="h",
        labels={"Load_Factor": "Load Factor", "Route_Name": "Route"},
    )
    fig_routes.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig_routes, use_container_width=True)

st.caption(
    "Note: Route codes were mostly stable across years but a handful of new "
    "codes/routes appear in later years (e.g. Umrah/charter routes) \u2014 "
    "this is expected and reflects real schedule changes, not a data error."
)

with st.expander("View raw monthly totals"):
    st.dataframe(
        totals_f[["Year", "Month", "Flights", "Seat_Capacity", "Seats_Occupied", "Load_Factor"]],
        hide_index=True,
        use_container_width=True,
    )
