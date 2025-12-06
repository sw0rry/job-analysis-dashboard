import streamlit as st
import pandas as pd
import plotly.express as px
import os

# === 1. 基础配置 ===
st.set_page_config(page_title="招聘数据看板", layout="wide")
st.title("📊 招聘数据看板")

# 自动定位文件路径 (同级目录下的 xlsx)
DEFAULT_FILE = "nowcoder_ALL_jobs_analysis.xlsx"


def clean_monthly_salary(row):
    # 优先取 salary_min，如果没有则取 salary_display 里的数字试试（防止爬虫没存min）
    val = row.get("salary_min", 0)

    # 如果没取到值，或者是空
    if pd.isna(val):
        return 0

    # 过滤掉 0 值
    if val <= 0:
        return 0

    # 【单位归一化】
    # 虽然都是月薪，但有的写 20000(元)，有的写 20(k)
    # 为了画图不错乱，统一转成 k
    if val > 1000:
        return val / 1000  # 比如 20000 -> 20k
    else:
        return val  # 比如 20 -> 20k


# === 3. 数据加载 ===
@st.cache_data
def load_data(file):
    try:
        df = pd.read_excel(file)

        # 容错：如果Excel里没有 salary_min，尝试找 salaryMin
        if "salary_min" not in df.columns:
            # 看看有没有全小写的
            if "salarymin" in df.columns:
                df.rename(columns={"salarymin": "salary_min"}, inplace=True)
            # 看看有没有驼峰的
            elif "salaryMin" in df.columns:
                df.rename(columns={"salaryMin": "salary_min"}, inplace=True)

        # 执行清洗
        if "salary_min" in df.columns:
            df["salary_k"] = df.apply(clean_monthly_salary, axis=1)
            # 只保留大于0的数据 (即剔除了0)
            valid_df = df[df["salary_k"] > 0].copy()
            return valid_df
        else:
            return pd.DataFrame()  # 没找到列

    except Exception as e:
        st.error(f"读取失败: {e}")
        return pd.DataFrame()


# === 4. 界面展示 ===
st.sidebar.header("数据控制")
uploaded_file = st.sidebar.file_uploader("上传数据", type=["xlsx"])

df = pd.DataFrame()
if uploaded_file:
    df = load_data(uploaded_file)
elif os.path.exists(DEFAULT_FILE):
    df = load_data(DEFAULT_FILE)

if df.empty:
    st.warning("⚠️ 暂无有效数据。")
    st.stop()

# === 5. 图表区域 ===
st.success(f"✅ 数据加载成功！有效样本：{len(df)} 条")

all_keywords = df["keyword"].unique().tolist() if "keyword" in df.columns else []
selected_jobs = st.sidebar.multiselect(
    "筛选岗位", all_keywords, default=all_keywords if all_keywords else None
)

if selected_jobs:
    plot_df = df[df["keyword"].isin(selected_jobs)]

    # 1. 核心指标
    avg_val = plot_df["salary_k"].mean()
    med_val = plot_df["salary_k"].median()

    col1, col2 = st.columns(2)
    col1.metric("平均月薪", f"{avg_val:.1f} k")
    col2.metric("中位数月薪", f"{med_val:.1f} k")

    # 2. 箱线图 (汉化坐标轴)
    st.subheader("📊 综合薪资分布图")

    fig = px.box(
        plot_df,
        x="keyword",
        y="salary_k",
        color="keyword",
        title="各岗位综合月薪分布 (K)",
        points="all",
        # 【核心修改】这里把英文列名映射成中文显示
        labels={"keyword": "岗位方向", "salary_k": "综合月薪 (K)", "count": "职位数量"},
    )

    # 进一步强制更新坐标轴标题 (双重保险)
    fig.update_layout(xaxis_title="岗位方向", yaxis_title="综合月薪 (K)")

    st.plotly_chart(fig, use_container_width=True)

    # 3. 数据明细
    with st.expander("点击查看原始数据"):
        st.dataframe(
            plot_df[["keyword", "title", "company", "salary_k", "url"]],
            column_config={
                "url": st.column_config.LinkColumn("链接"),
                "salary_k": st.column_config.NumberColumn("综合月薪(K)", format="%.1f"),
            },
        )
else:
    st.info("请在左侧勾选至少一个岗位")

