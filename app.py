import streamlit as st
import pandas as pd
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import re

# === 1. 页面配置 ===
st.set_page_config(page_title="招聘数据可视化看板", layout="wide")
st.title("📊 招聘数据深度分析看板")

# === 2. 定义关键词库 (恢复多模式) ===
# 模式 A: 硬核技术
TECHNICAL_KEYWORDS = [
    # 语言
    r"Java",
    r"Python",
    r"C\+\+",
    r"Go",
    r"JavaScript",
    r"TypeScript",
    r"HTML",
    r"CSS",
    # 框架
    r"Vue",
    r"React",
    r"Spring Boot",
    r"Spring Cloud",
    r"MyBatis",
    r"Django",
    r"Flask",
    r"Node\.js",
    # 数据库 & 工具
    r"MySQL",
    r"Redis",
    r"MongoDB",
    r"Oracle",
    r"Linux",
    r"Docker",
    r"Kubernetes",
    r"Git",
]

# 模式 B: 软技能/通用能力
SOFT_SKILLS = [
    r"沟通",
    r"团队",
    r"协作",
    r"抗压",
    r"责任心",
    r"学习能力",
    r"逻辑",
    r"英语",
    r"本科",
    r"硕士",
    r"985",
    r"211",
]


# === 3. 数据加载 ===
@st.cache_data
def load_data():
    file_name = "nowcoder_ALL_jobs_analysis.xlsx"
    try:
        df = pd.read_excel(file_name, engine="openpyxl")
    except Exception as e:
        st.error(f"读取文件失败: {e}")
        return pd.DataFrame()

    def parse_salary(salary_str):
        if pd.isna(salary_str):
            return 0
        match = re.search(r"(\d+)-(\d+)", str(salary_str))
        if match:
            return (float(match.group(1)) + float(match.group(2))) / 2
        return 0

    if "avg_salary_k" not in df.columns:
        col = "salary_display" if "salary_display" in df.columns else df.columns[3]
        df["avg_salary_k"] = df[col].apply(parse_salary)

    return df


df = load_data()
if df.empty:
    st.stop()

# === 4. 侧边栏交互 ===
st.sidebar.header("🔍 筛选与控制")

# 4.1 岗位筛选
all_jobs = df["keyword"].unique().tolist()
selected_jobs = st.sidebar.multiselect("选择岗位类型", all_jobs, default=all_jobs[:2])

# 4.2 词云模式选择 (恢复此功能)
st.sidebar.markdown("---")
st.sidebar.subheader("☁️ 词云分析模式")
analysis_mode = st.sidebar.radio(
    "选择关键词类型：", ("硬核技术栈 (Java/Vue...)", "通用要求 (学历/软技能...)")
)

# 数据过滤
filtered_df = df[df["keyword"].isin(selected_jobs)]

# === 5. 核心指标 (左对齐) ===
# 之前是居中，现在直接用 columns 排列，视觉上就是左对齐
col1, col2, col3 = st.columns(3)
col1.metric("职位数量", f"{len(filtered_df)} 个")
col2.metric("平均月薪 (估算)", f"{filtered_df['avg_salary_k'].mean():.1f} K")
col3.write("")  # 占位，保持布局

st.markdown("---")

# === 6. 图表区域 ===
c_chart1, c_chart2 = st.columns([3, 2])

with c_chart1:
    st.subheader("💰 各岗位平均薪资排行")
    if not filtered_df.empty:
        # 计算每个岗位的平均薪资并排序
        salary_rank = (
            filtered_df.groupby("keyword")["avg_salary_k"]
            .mean()
            .sort_values(ascending=True)
            .reset_index()
        )

        # 改用【横向柱状图】，非常容易看懂
        fig = px.bar(
            salary_rank,
            x="avg_salary_k",
            y="keyword",
            orientation="h",  # 水平方向
            text_auto=".1f",  # 直接在柱子上显示数字
            color="keyword",
            labels={"avg_salary_k": "平均月薪 (K)", "keyword": "岗位类型"},
            title="岗位薪资排行榜 (由高到低)",
        )
        # 强制标题左对齐
        fig.update_layout(title_x=0)
        st.plotly_chart(fig, use_container_width=True)

with c_chart2:
    st.subheader(f"☁️ {analysis_mode} 热度图")
    if not filtered_df.empty and "demand" in filtered_df.columns:
        text = " ".join(filtered_df["demand"].dropna().astype(str).tolist())
        counts = {}

        # 根据侧边栏选择，切换词库
        target_list = TECHNICAL_KEYWORDS if "技术" in analysis_mode else SOFT_SKILLS

        for pattern in target_list:
            # 格式化显示名称 (去正则符号 + 首字母大写)
            display_name = (
                pattern.replace(r"\b", "")
                .replace("\\", "")
                .replace("+", "p")
                .capitalize()
                .replace("p", "+")
            )
            if display_name.upper() in ["HTML", "CSS", "SQL", "PHP", "KV", "KPI"]:
                display_name = display_name.upper()

            found_count = len(re.findall(pattern, text, re.IGNORECASE))
            if found_count > 0:
                counts[display_name] = found_count

        if counts:
            wc = WordCloud(
                font_path="msyh.ttc",
                width=500,
                height=400,
                background_color="white",
                colormap="viridis",
            ).generate_from_frequencies(counts)

            fig, ax = plt.subplots()
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig)
        else:
            st.warning("当前岗位描述中未找到相关关键词")

# === 7. 详细表格 (优化版) ===
st.markdown("---")
st.subheader("📋 职位详情列表")

if not filtered_df.empty:
    # 1. 筛选并重命名列 (去掉了公司名，保留了 URL)
    # 假设 Excel 里 URL 的列名是 'url'，如果不是请修改这里
    cols_to_show = ["keyword", "title", "avg_salary_k", "demand", "url"]

    # 防止列名不存在报错
    valid_cols = [c for c in cols_to_show if c in filtered_df.columns]
    display_df = filtered_df[valid_cols].copy()

    # 2. 格式化薪资
    if "avg_salary_k" in display_df.columns:
        display_df["avg_salary_k"] = display_df["avg_salary_k"].apply(
            lambda x: f"{x:.1f} K"
        )

    # 3. 重命名中文表头
    column_mapping = {
        "keyword": "岗位类型",
        "title": "职位名称",
        "avg_salary_k": "薪资(估)",
        "demand": "职位描述",
        "url": "链接",
    }
    display_df = display_df.rename(columns=column_mapping)

    # 4. 使用 Streamlit 的 LinkColumn 配置，让链接可点击
    st.dataframe(
        display_df,
        column_config={
            "链接": st.column_config.LinkColumn(
                "职位链接",
                help="点击跳转到招聘页面",
                display_text="点击查看详情",  # 这里设置显示的文字，不显示长长的URL
            ),
            "职位描述": st.column_config.TextColumn(
                "职位描述", width="large"  # 让描述列宽一点
            ),
        },
        hide_index=True,  # 隐藏索引列 0,1,2...
        use_container_width=True,
    )
