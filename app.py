import streamlit as st
import pandas as pd
import plotly.express as px
import os
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import platform
import re

# === 1. 基础配置 ===
st.set_page_config(page_title="招聘数据看板", layout="wide")
st.title("📊 招聘数据看板")

# 自动定位文件路径 (同级目录下的 xlsx)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILE = os.path.join(BASE_DIR, "nowcoder_ALL_jobs_analysis.xlsx")

# 字体设置 (为了词云不乱码)
# 尝试在代码同级目录下找 msyh.ttc，如果没有则尝试系统字体
FONT_PATH = os.path.join(BASE_DIR, "msyh.ttc")
if not os.path.exists(FONT_PATH):
    system = platform.system()
    if system == "Windows":
        FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
    elif system == "Darwin":  # Mac
        FONT_PATH = "/System/Library/Fonts/PingFang.ttc"
    else:
        FONT_PATH = None  # Linux/Cloud 需要自行上传字体文件


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

        # 自动改名兼容旧数据
        rename_dict = {
            "salarymin": "salary_min",
            "salaryMin": "salary_min",
            "avg_annual_K": "salary_min",  # 强力兼容
            "demand": "demand",
            "job_detail": "demand",
            "description": "demand",  # 兼容JD列
        }
        df.rename(columns=rename_dict, inplace=True)

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
st.sidebar.header("仪表盘")
uploaded_file = st.sidebar.file_uploader("上传Excel", type=["xlsx"])

df = pd.DataFrame()
if uploaded_file:
    df = load_data(uploaded_file)
elif os.path.exists(DEFAULT_FILE):
    df = load_data(DEFAULT_FILE)

if df.empty:
    st.warning("⚠️ 暂无有效数据。")
    st.stop()

# 侧边栏筛选
all_kw = df["keyword"].unique().tolist() if "keyword" in df.columns else []
selected_jobs = st.sidebar.multiselect(
    "选择岗位", all_kw, default=all_kw if all_kw else None
)

if not selected_jobs:
    st.info("请在左侧选择至少一个岗位进行分析")
    st.stop()

# 过滤数据
plot_df = df[df["keyword"].isin(selected_jobs)].copy()
plot_df.index = range(1, len(plot_df) + 1)  # 序号从1开始

st.success(f"✅ 分析样本：{len(plot_df)} 条")

# === 5. 多维度展示 (使用 Tabs 选项卡) ===
tab1, tab2, tab3 = st.tabs(["💰 薪资分析", "🔥 技能热度图", "📋 详细数据"])

# --- Tab 1: 薪资图表 (柱状图 + 箱线图) ---
with tab1:
    col1, col2 = st.columns(2)
    col1.metric("平均月薪", f"{plot_df['salary_k'].mean():.1f} k")
    col2.metric("中位数月薪", f"{plot_df['salary_k'].median():.1f} k")

    # 图表 1: 箱线图 (最专业的分布图)
    st.subheader("1. 薪资分布 (箱线图)")
    fig_box = px.box(
        plot_df,
        x="keyword",
        y="salary_k",
        color="keyword",
        title="各岗位薪资分布区间",
        labels={"salary_k": "月薪(K)", "keyword": "岗位"},
    )
    st.plotly_chart(fig_box, use_container_width=True)

    # 图表 2: 柱状图 (平均值排行)
    st.subheader("2. 平均薪资排行 (柱状图)")
    # 算出每个岗位的平均值
    avg_df = (
        plot_df.groupby("keyword")["salary_k"]
        .mean()
        .reset_index()
        .sort_values("salary_k")
    )
    fig_bar = px.bar(
        avg_df,
        x="keyword",
        y="salary_k",
        color="keyword",
        text_auto=".1f",
        title="各岗位平均薪资对比",
        labels={"salary_k": "平均月薪(K)", "keyword": "岗位"},
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# --- Tab 2: 硬/软技能分离热度图 ---
with tab2:
    st.subheader("🔥 技能需求热度分析")

    # 1. 检查数据
    if "demand" not in plot_df.columns:
        st.error("数据缺少 'demand' 列，无法生成热度图")
        st.stop()

    # 2. 定义严格分离的词库
    # === A. 纯硬核技术栈 (English / Code Only) ===
    # 剔除了中文词（如'算法'），只留代码相关的英文，保证视觉纯净
    TECH_STACK_LIST = [
        "Java",
        "Python",
        "C++",
        "C#",
        "Go",
        "Golang",
        "PHP",
        "Ruby",
        "Rust",
        "Swift",
        "Kotlin",
        "JavaScript",
        "TypeScript",
        "HTML",
        "CSS",
        "Vue",
        "React",
        "Angular",
        "Node",
        "Node.js",
        "Spring",
        "SpringBoot",
        "SpringCloud",
        "MyBatis",
        "Hibernate",
        "JVM",
        "Netty",
        "MySQL",
        "Redis",
        "Oracle",
        "MongoDB",
        "PostgreSQL",
        "SQL",
        "NoSQL",
        "Linux",
        "Shell",
        "Bash",
        "Docker",
        "K8s",
        "Kubernetes",
        "Nginx",
        "Git",
        "Jenkins",
        "CI/CD",
        "Kafka",
        "RabbitMQ",
        "RocketMQ",
        "Elasticsearch",
        "Hadoop",
        "Spark",
        "Flink",
        "Hive",
        "TensorFlow",
        "PyTorch",
        "LLM",
        "NLP",
        "CV",
        "Transformer",
        "BERT",
        "GPT",
    ]

    # === B. 综合素质与软技能 (Chinese Only) ===
    # 只留中文描述，分析性格与能力
    SOFT_SKILLS_LIST = [
        "沟通",
        "团队",
        "协作",
        "责任心",
        "抗压",
        "学习能力",
        "逻辑思维",
        "自驱力",
        "热情",
        "细心",
        "解决问题",
        "执行力",
        "英语",
        "文档能力",
        "积极",
        "主动",
        "乐观",
        "创新",
        "严谨",
        "诚信",
        "刻苦",
        "适应能力",
        "数据结构",
        "算法",
        "多线程",
        "消息循环",
        "计算机网络",
        "操作系统",
        "数据库",
        "计算机组成",
        "本科",
        "硕士",
        "博士",
        "计算机",
        "软件工程",
    ]

    # 3. 增加切换开关 (Radio Button)
    view_mode = st.radio(
        "请选择分析维度：",
        ("💻 编程语言与技术栈", "🤝 综合素质与软技能"),
        horizontal=True,
    )

    # 4. 统计逻辑
    full_text = " ".join(plot_df["demand"].dropna().astype(str).tolist())

    def count_keywords(text, keyword_list):
        counts = {}
        for word in keyword_list:
            # 转义特殊字符(如C++) + 忽略大小写
            pattern = re.escape(word)
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            if matches > 0:
                # 统一 Key 的显示格式 (比如把 JAVA 统一显示为 Java)
                display_name = word
                if word.upper() in ["HTML", "CSS", "SQL"]:
                    display_name = word.upper()
                elif word.capitalize() in ["Java", "Python"]:
                    display_name = word.capitalize()

                counts[display_name] = matches
        return counts

    # 5. 根据选择渲染不同图表
    if "编程语言" in view_mode:
        # --- 渲染硬技能 ---
        counts = count_keywords(full_text, TECH_STACK_LIST)
        color_map = "ocean"  # 科技蓝
        title_text = "硬核技术栈热度"
    else:
        # --- 渲染软技能 ---
        counts = count_keywords(full_text, SOFT_SKILLS_LIST)
        color_map = "magma"  # 活力暖色
        title_text = "职场软实力热度"

    # 6. 画图 (单张大图)
    if counts:
        st.markdown(f"### {title_text}")
        try:
            wc = WordCloud(
                font_path=FONT_PATH,  # 确保有中文字体
                width=1000,
                height=500,  # 画布变大
                background_color="white",
                colormap=color_map,
                max_words=100,
                prefer_horizontal=0.9,
            ).generate_from_frequencies(counts)

            # 使用 Matplotlib 显示
            fig, ax = plt.subplots(figsize=(12, 6))  # 图表尺寸变大
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig, use_container_width=True)

            # 底部显示 Top 10 数据条
            with st.expander("查看详细排名数据"):
                df_rank = pd.DataFrame(
                    list(counts.items()), columns=["关键词", "出现频次"]
                )
                df_rank = df_rank.sort_values("出现频次", ascending=False).reset_index(
                    drop=True
                )
                df_rank.index += 1
                st.dataframe(df_rank.head(20), use_container_width=True)

        except Exception as e:
            st.error(f"词云生成失败，请检查字体设置。错误信息: {e}")
    else:
        st.warning(
            f"在当前选中的岗位中，未提取到相关的{view_mode.split(' ')[1]}关键词。"
        )

# --- Tab 3: 原始数据 ---
with tab3:
    st.dataframe(
        plot_df[["keyword", "title", "company", "salary_k", "url"]],
        # 核心修改：在这里定义每一列的中文名和格式
        column_config={
            "keyword": st.column_config.TextColumn("岗位方向"),
            "title": st.column_config.TextColumn("职位名称"),
            "company": st.column_config.TextColumn("公司名称"),
            # 薪资列：不仅改名，还保留1位小数，并加上 'k' 单位
            "salary_k": st.column_config.NumberColumn("月薪 (K)", format="%.1f k"),
            # 链接列：改名，并把长长的 URL 缩短显示为“点击查看”
            "url": st.column_config.LinkColumn("职位链接", display_text="点击查看"),
        },
        use_container_width=True,
        hide_index=True,  # 隐藏最左边的 0,1,2... 索引，看起来更像 Excel
    )

