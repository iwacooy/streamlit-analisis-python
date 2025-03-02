import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st
import geopandas as gpd
from shapely.geometry import Point
from babel.numbers import format_currency

sns.set(style='darkgrid')

def load_data(file_path):
    df = pd.read_csv(file_path)
    date_columns = ["order_approved_at", "order_delivered_customer_date", "order_purchase_timestamp"]
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    df.sort_values(by="order_approved_at", inplace=True)
    return df

def load_geolocation(file_path):
    df = pd.read_csv(file_path)
    df.drop_duplicates(subset=['geolocation_zip_code_prefix'], inplace=True)
    return df

def merge_customer_geolocation(customers_df, geolocation_df):
    return customers_df.merge(geolocation_df, how='left', left_on='customer_zip_code_prefix', right_on='geolocation_zip_code_prefix')

def plot_geolocation(customers_gdf):
    world = gpd.read_file("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson")
    brazil = world[world["ADMIN"] == "Brazil"]
    
    fig, ax = plt.subplots(figsize=(10, 10))
    brazil.plot(ax=ax, color="lightgrey", edgecolor="black")
    customers_gdf.plot(ax=ax, markersize=1, color="maroon", alpha=0.3)
    
    plt.title("Persebaran Pelanggan di Brazil")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    return fig

def prepare_daily_orders(df):
    daily_df = df.resample('D', on='order_approved_at').agg({
        "order_id": "nunique",
        "payment_value": "sum"
    }).reset_index()
    daily_df.rename(columns={
        "order_id": "total_orders",
        "payment_value": "total_revenue"
    }, inplace=True)
    return daily_df

def compute_total_spending(df):
    spending_df = df.resample('D', on='order_approved_at')["payment_value"].sum().reset_index()
    spending_df.rename(columns={"payment_value": "daily_spending"}, inplace=True)
    return spending_df

def aggregate_products(df):
    product_df = df.groupby("product_category_name_english")["product_id"].count().reset_index()
    product_df.rename(columns={"product_id": "total_sold"}, inplace=True)
    return product_df.sort_values(by='total_sold', ascending=False)

def customer_distribution_by_state(df):
    state_df = df.groupby("customer_state")["customer_id"].nunique().reset_index()
    state_df.rename(columns={"customer_id": "num_customers"}, inplace=True)
    return state_df.sort_values(by='num_customers', ascending=False)

def analyze_review_scores(df):
    score_counts = df['review_score'].value_counts().sort_values(ascending=False)
    return score_counts, score_counts.idxmax()

def analyze_top_low_products(df):
    sum_order_items_df = df.groupby("product_category_name_english").agg({"order_id": "count"}).reset_index()
    sum_order_items_df.columns = ["product_category_name_english", "products"]
    return sum_order_items_df

# Load data
all_df = load_data("/mount/src/streamlit-analisis-python/data/all_data_df.csv")
geolocation_df = load_geolocation("/mount/src/streamlit-analisis-python/data/all_data_df.csv")
customers_df = merge_customer_geolocation(all_df, geolocation_df)

# Convert to GeoDataFrame
customers_df['geometry'] = customers_df.apply(lambda x: Point(x['geolocation_lng'], x['geolocation_lat']) if pd.notnull(x['geolocation_lng']) else None, axis=1)
customers_gdf = gpd.GeoDataFrame(customers_df.dropna(subset=['geometry']), geometry='geometry', crs="EPSG:4326")

# Sidebar Filters
st.sidebar.title("E-Commerce Dashboard")
st.sidebar.image("https://github.com/dicodingacademy/assets/raw/main/logo.png")

date_range = st.sidebar.date_input(
    "Select Date Range", 
    [all_df["order_approved_at"].min(), all_df["order_approved_at"].max()]
)

filtered_df = all_df[(all_df["order_approved_at"] >= str(date_range[0])) & 
                      (all_df["order_approved_at"] <= str(date_range[1]))]

daily_orders = prepare_daily_orders(filtered_df)
daily_spending = compute_total_spending(filtered_df)
product_sales = aggregate_products(filtered_df)
customer_states = customer_distribution_by_state(filtered_df)
review_stats, top_review = analyze_review_scores(filtered_df)
sum_order_items_df = analyze_top_low_products(filtered_df)

# Dashboard UI
st.subheader("E-Commerce Revenue Insights")
st.metric("Total Revenue", format_currency(daily_spending["daily_spending"].sum(), "BRL", locale="pt_BR"))
st.metric("Average Daily Revenue", format_currency(daily_spending["daily_spending"].mean(), "BRL", locale="pt_BR"))

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(daily_spending["order_approved_at"], daily_spending["daily_spending"], color='blue', linewidth=2)
ax.set_xlabel("Date")
ax.set_ylabel("Revenue")
st.pyplot(fig)

st.subheader("Top Selling Products")
fig, ax = plt.subplots(figsize=(10, 5))
top_colors = ["#72BCD4"] + ["#D3D3D3"] * (len(product_sales.head(5)) - 1)
sns.barplot(x="total_sold", y="product_category_name_english", data=product_sales.head(5), palette=top_colors, ax=ax)
st.pyplot(fig)

st.subheader("Least Selling Products")
fig, ax = plt.subplots(figsize=(10, 5))
low_colors = ["#FF6F61"] + ["#D3D3D3"] * (len(sum_order_items_df.tail(5)) - 1)
sns.barplot(x="products", y="product_category_name_english", data=sum_order_items_df.sort_values(by="products", ascending=True).head(5), palette=low_colors, ax=ax)
st.pyplot(fig)

st.subheader("Customer Distribution by State")
fig, ax = plt.subplots(figsize=(10, 5))
sns.barplot(x="num_customers", y="customer_state", data=customer_states.head(10), ax=ax)
st.pyplot(fig)

st.subheader("Customer Distribution Map")
fig = plot_geolocation(customers_gdf)
st.pyplot(fig)

st.subheader("Customer Satisfaction Ratings")
review_scores_df = review_stats.reset_index()
review_scores_df.columns = ['rating', 'count']
sns.set(style="ticks")
plt.figure(figsize=(10, 5))
sns.barplot(data=review_scores_df, x="rating", y="count", order=review_scores_df["rating"], palette=["#068DA9" if score == top_review else "#D3D3D3" for score in review_scores_df["rating"]])
plt.title("Rating kepuasan customers", fontsize=18)
st.pyplot(plt)
