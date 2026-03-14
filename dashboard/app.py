# Streamlit/Dash 可视化界面
 # 主入口，控制页面布局
import streamlit as st
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder

st.set_page_config(page_title="EmotionSense 情感分析仪表板", layout="wide", page_icon=":bar_chart:")

# 主题色与样式
st.markdown("""
    <style>
    .main {background-color: #f7f9fa;}
    .stButton>button {background-color: #4F8BF9; color: white;}
    .stMetric {background: #eaf1fb;}
    </style>
""", unsafe_allow_html=True)

# 侧边栏参数
with st.sidebar:
    st.title("仪表板参数")
    uploaded_file = st.file_uploader("上传情感分析数据", type=["csv"])
    # 主题切换
    theme = st.radio("主题", ["浅色", "深色"])
    # 时间区间选择
    date_range = st.slider("选择时间区间", min_value=2024, max_value=2025, value=(2024, 2025))
    # 关键词筛选
    keyword = st.text_input("关键词筛选（可选）")

# 数据加载
if uploaded_file:
    df = pd.read_csv(uploaded_file)
else:
    st.stop()

# 数据筛选
if "timestamp" in df.columns:
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    df = df[(df["date"].apply(lambda x: date_range[0] <= x.year <= date_range[1]))]
if keyword:
    df = df[df["content"].str.contains(keyword, na=False)]

# 统计卡片
col1, col2, col3, col4 = st.columns(4)
col1.metric("评论数", len(df))
col2.metric("唯一用户数", df["user_id"].nunique() if "user_id" in df else "-")
col3.metric("时间范围", f"{df['date'].min()} ~ {df['date'].max()}" if "date" in df else "-")
col4.metric("关键词数", df["keyword"].nunique() if "keyword" in df else "-")

# 情感分布可视化
st.subheader("情感分布")
if "sentiment" in df.columns:
    fig = px.histogram(df, x="sentiment", color="sentiment", barmode="group", title="情感类别分布")
    st.plotly_chart(fig, use_container_width=True)

# 趋势图（可联动）
st.subheader("每日情感趋势")
if "date" in df.columns and "sentiment" in df.columns:
    trend = df.groupby(["date", "sentiment"]).size().reset_index(name="count")
    fig = px.area(trend, x="date", y="count", color="sentiment", line_group="sentiment", title="情感趋势堆叠图")
    st.plotly_chart(fig, use_container_width=True)

# 交互式表格
st.subheader("数据明细（可筛选/排序/导出）")
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_pagination()
gb.configure_default_column(editable=False, groupable=True)
gridOptions = gb.build()
AgGrid(df, gridOptions=gridOptions, enable_enterprise_modules=True)

# 事件对齐与窗口分析（可选）
# ...（可集成事件窗口选择、显著性检验、事件高亮等）

# 导出当前筛选结果
st.download_button("导出当前数据", df.to_csv(index=False).encode("utf-8"), "filtered_data.csv")

st.markdown("---")
st.markdown("EmotionSense | 交互式情感分析仪表板 | 2025") 