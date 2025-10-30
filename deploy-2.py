import streamlit as st
import pandas as pd
import numpy as np
import io
import random

# ----------------------------------------------------
# 0. Streamlit 页面配置
# ----------------------------------------------------
st.set_page_config(page_title="广告收入看板", layout="wide")

# ----------------------------------------------------
# 1. 全局定义
# ----------------------------------------------------

# 定义数据结构和范围
DEPARTMENTS_COUNTRY = ['AU', 'NZ', 'US', 'CA', 'UK', 'EU', 'JP', 'KP'] # 仅用于循环计算的国家/地区
TARGET_PERIOD = 202509
TARGET_BUSINESS_ATTR = '外卖BD'
ALL_DEPARTMENTS = DEPARTMENTS_COUNTRY + ['AD', 'OTHER']
AD_TYPES = ['同业广告', '异业广告']
BUSINESS_TYPES = [TARGET_BUSINESS_ATTR, '其他业务']
NUM_ROWS = 1000 # 伪数据行数

# 15 个指标的顺序
ALL_METRIC_ORDER = [
    '广告收入', '广告收入——同业收入', '广告收入——异业收入',
    '广告部：广告收入', '广告部—同业收入', '广告部—异业收入',
    '国家：广告收入', '国家-同业收入', '国家-异业收入',
    '国家BD人数（实际为有售卖的BD）', 
    '广告部BD人数', 
    '全球BD人数', 
    '全球BD：人均广告收入', 
    '广告部BD：人均广告收入', 
    '国家BD：人均广告收入' 
]

@st.cache_data
def create_simulated_data(target_period):
    """创建模拟数据，并确保包含 '国家' 列"""
    dept_choices = np.random.choice(ALL_DEPARTMENTS, NUM_ROWS)
    country_choices = []
    for dept in dept_choices:
        if dept == 'AD':
            # AD部门, 归属于一个随机的国家
            country_choices.append(np.random.choice(DEPARTMENTS_COUNTRY))
        elif dept in DEPARTMENTS_COUNTRY:
            # 国家部门, 国家=部门
            country_choices.append(dept)
        else:
            # 'OTHER' 部门
            country_choices.append('OTHER')

    data = {
        '所属账期': np.random.choice([target_period, 202508], NUM_ROWS, p=[0.9, 0.1]),
        '3级部门': dept_choices,
        '国家': country_choices, 
        '广告类型': np.random.choice(AD_TYPES, NUM_ROWS),
        '到账金额_gbp': np.random.randint(100, 100000, NUM_ROWS) / 100,
        '业务属性': np.random.choice(BUSINESS_TYPES, NUM_ROWS),
        '销售人工号': np.random.randint(10000, 10500, NUM_ROWS),
    }
    df = pd.DataFrame(data)
    
    # 添加干扰数据
    df_off_period = pd.DataFrame({
        '所属账期': 202508,
        '3级部门': np.random.choice(ALL_DEPARTMENTS, 50),
        '国家': np.random.choice(DEPARTMENTS_COUNTRY + ['OTHER'], 50),
        '广告类型': np.random.choice(AD_TYPES, 50),
        '到账金额_gbp': np.random.randint(100, 50000, 50) / 100,
        '业务属性': np.random.choice(BUSINESS_TYPES, 50),
        '销售人工号': np.random.randint(10000, 10500, 50),
    })
    df = pd.concat([df, df_off_period], ignore_index=True)
    
    return df

@st.cache_data
def create_and_process_data(target_period, target_biz_attr):
    """
    创建模拟数据，清理并执行所有指标计算。
    返回：
    1. summary_df: 汇总后的指标
    2. df_raw: 模拟的原始数据
    """
    
    df = create_simulated_data(target_period)

    # 清理数据 (保留核心逻辑)
    df['到账金额_gbp'] = pd.to_numeric(df['到账金额_gbp'], errors='coerce').fillna(0).round(2)
    
    # 执行计算
    summary_df = calculate_all_metrics(df, target_period, target_biz_attr, DEPARTMENTS_COUNTRY, ALL_METRIC_ORDER)
    
    return summary_df, df

# ----------------------------------------------------
# 2. 核心计算函数 (逻辑保持不变)
# ----------------------------------------------------

def calculate_single_dept_metrics(dept_code, df, target_所属账期, target_业务属性):
    """计算单个部门的15个指标，并返回字典"""
    
    dept_condition = (df['所属账期'] == target_所属账期) & \
                     (df['3级部门'] == dept_code)
    
    # --- 收入指标 ---
    dept_revenue_total = df[dept_condition]['到账金额_gbp'].sum().round(2)
    dept_core_revenue = df[dept_condition & (df['广告类型'] == '同业广告')]['到账金额_gbp'].sum().round(2)
    dept_noncore_revenue = df[dept_condition & (df['广告类型'] == '异业广告')]['到账金额_gbp'].sum().round(2)
    dept_aggregated_revenue = (dept_revenue_total * 2).round(2) # '广告收入'
    
    # --- 人数指标 ---
    # 1. 国家BD人数 (dept_count)
    dept_count_condition = dept_condition & (df['业务属性'] == target_业务属性)
    dept_count = df[dept_count_condition]['销售人工号'].nunique()

    # 2. 广告部BD人数 (dept_ad_bd_count) 
    ad_bd_condition = (df['所属账期'] == target_所属账期) & \
                      (df['3级部门'] == 'AD') & \
                      (df['国家'] == dept_code)
    dept_ad_bd_count = df[ad_bd_condition]['销售人工号'].nunique()
    
    # 3. 全球BD人数 (部门总BD人数)
    dept_total_bd_count = dept_count + dept_ad_bd_count

    # --- 人效指标 ---
    # 1. 全球BD：人均广告收入 (使用 '广告收入' / 总BD)
    dept_global_bd_avg_revenue = (dept_aggregated_revenue / dept_total_bd_count) if dept_total_bd_count > 0 else 0
    
    # 2. 广告部BD：人均广告收入 (使用 '广告部：广告收入' / 广告部BD人数)
    dept_ad_bd_avg_revenue = (dept_revenue_total / dept_ad_bd_count) if dept_ad_bd_count > 0 else 0
    
    # 3. 国家BD：人均广告收入 (使用 '国家：广告收入' / 国家BD人数)
    dept_country_bd_avg_revenue = (dept_revenue_total / dept_count) if dept_count > 0 else 0

    # --- 15 Derived Metrics (名称已增加部门前缀) ---
    metrics = {
        # 业绩
        f'{dept_code}_广告部：广告收入': dept_revenue_total,
        f'{dept_code}_广告部—同业收入': dept_core_revenue,
        f'{dept_code}_广告部—异业收入': dept_noncore_revenue,
        f'{dept_code}_国家：广告收入': dept_revenue_total, 
        f'{dept_code}_国家-同业收入': dept_core_revenue,  
        f'{dept_code}_国家-异业收入': dept_noncore_revenue, 
        f'{dept_code}_广告收入': dept_aggregated_revenue,
        f'{dept_code}_广告收入——同业收入': (dept_core_revenue * 2).round(2),
        f'{dept_code}_广告收入——异业收入': (dept_noncore_revenue * 2).round(2),
        
        # 人数
        f'{dept_code}_国家BD人数（实际为有售卖的BD）': dept_count,
        f'{dept_code}_广告部BD人数': dept_ad_bd_count,
        f'{dept_code}_全球BD人数': dept_total_bd_count,

        # 人效
        f'{dept_code}_全球BD：人均广告收入': dept_global_bd_avg_revenue.round(2) if dept_global_bd_avg_revenue else 0,
        f'{dept_code}_广告部BD：人均广告收入': dept_ad_bd_avg_revenue.round(2) if dept_ad_bd_avg_revenue else 0,
        f'{dept_code}_国家BD：人均广告收入': dept_country_bd_avg_revenue.round(2) if dept_country_bd_avg_revenue else 0,
    }
    return metrics

def calculate_all_metrics(df, target_所属账期, target_业务属性, DEPARTMENTS, original_order):
    """主计算函数，计算全球和所有部门的指标"""
    
    target_period_condition = (df['所属账期'] == target_所属账期)

    # 1. 计算 15 个原有（全球）指标
    # 1a. 非AD部门 (国家收入)
    non_ad_condition_total = target_period_condition & (df['3级部门'] != 'AD')
    国家_广告收入_总计 = df[non_ad_condition_total]['到账金额_gbp'].sum().round(2)
    同业收入_总计 = df[non_ad_condition_total & (df['广告类型'] == '同业广告')]['到账金额_gbp'].sum().round(2)
    异业收入_总计 = df[non_ad_condition_total & (df['广告类型'] == '异业广告')]['到账金额_gbp'].sum().round(2)

    # 国家BD人数（带业务属性过滤）
    country_bd_count_condition = target_period_condition & \
                                 (df['3级部门'].isin(DEPARTMENTS)) & \
                                 (df['业务属性'] == target_业务属性)
    国家BD人数_总计 = df[country_bd_count_condition]['销售人工号'].nunique()

    # 1b. AD部门
    ad_condition = target_period_condition & (df['3级部门'] == 'AD')
    广告部_广告收入_总计 = df[ad_condition]['到账金额_gbp'].sum().round(2)
    广告部_同业收入_总计 = df[ad_condition & (df['广告类型'] == '同业广告')]['到账金额_gbp'].sum().round(2)
    广告部_异业收入_总计 = df[ad_condition & (df['广告类型'] == '异业广告')]['到账金额_gbp'].sum().round(2)
    
    # 广告部BD人数
    广告部BD人数_总计 = df[ad_condition]['销售人工号'].nunique()

    # 1c. 聚合指标
    广告收入_总计 = (广告部_广告收入_总计 + 国家_广告收入_总计).round(2)
    广告收入_同业收入_总计 = (广告部_同业收入_总计 + 同业收入_总计).round(2)
    广告收入_异业收入_总计 = (广告部_异业收入_总计 + 异业收入_总计).round(2)

    # 1d. 人数与人效指标
    全球BD人数_总计 = 国家BD人数_总计 + 广告部BD人数_总计
    
    # 2. 全球BD：人均广告收入 (使用 '广告收入' / 全球BD)
    全球BD_人均广告收入_总计 = (广告收入_总计 / 全球BD人数_总计) if 全球BD人数_总计 > 0 else 0
    
    # 3. 广告部BD：人均广告收入 (使用 '广告部：广告收入' / 广告部BD人数)
    广告部BD_人均广告收入_总计 = (广告部_广告收入_总计 / 广告部BD人数_总计) if 广告部BD人数_总计 > 0 else 0

    # 4. 国家BD：人均广告收入 (使用 '国家：广告收入' / 国家BD人数)
    国家BD_人均广告收入_总计 = (国家_广告收入_总计 / 国家BD人数_总计) if 国家BD人数_总计 > 0 else 0


    # 2. 循环计算所有部门指标
    all_dept_values = {}
    for dept in DEPARTMENTS:
        dept_metrics = calculate_single_dept_metrics(dept, df, target_所属账期, target_业务属性)
        all_dept_values.update(dept_metrics)

    # 3. 整理成最终的 DataFrame
    data_values = {
        # 全球指标 (15个)
        '广告收入': 广告收入_总计, '广告收入——同业收入': 广告收入_同业收入_总计, '广告收入——异业收入': 广告收入_异业收入_总计,
        '广告部：广告收入': 广告部_广告收入_总计, '广告部—同业收入': 广告部_同业收入_总计, '广告部—异业收入': 广告部_异业收入_总计,
        '国家：广告收入': 国家_广告收入_总计, '国家-同业收入': 同业收入_总计, '国家-异业收入':异业收入_总计,
        '国家BD人数（实际为有售卖的BD）': 国家BD人数_总计,
        '广告部BD人数': 广告部BD人数_总计,
        '全球BD人数': 全球BD人数_总计,
        '全球BD：人均广告收入': 全球BD_人均广告收入_总计.round(2) if 全球BD_人均广告收入_总计 else 0,
        '广告部BD：人均广告收入': 广告部BD_人均广告收入_总计.round(2) if 广告部BD_人均广告收入_总计 else 0,
        '国家BD：人均广告收入': 国家BD_人均广告收入_总计.round(2) if 国家BD_人均广告收入_总计 else 0,
    }
    data_values.update(all_dept_values)

    # 4. 构造 final_order (包含 15 个指标)
    final_order = original_order.copy()
    
    # 全球新增的 5 个指标
    global_new_metrics = ['广告部BD人数', '全球BD人数', '全球BD：人均广告收入', '广告部BD：人均广告收入', '国家BD：人均广告收入']
    final_order.extend(global_new_metrics)
    
    for dept in DEPARTMENTS:
        dept_order = [f'{dept}_{name}' for name in original_order]
        dept_order.extend([f'{dept}_{name}' for name in global_new_metrics])
        final_order.extend(dept_order)

    temp_df = pd.DataFrame({
        '收入类型': final_order,
        '总计金额_gbp': [data_values.get(metric, 0) for metric in final_order]
    })

    # 5. 新增 '地区' 列
    def map_region(row):
        for dept_code in DEPARTMENTS:
            if row['收入类型'].startswith(f'{dept_code}_'):
                return dept_code
        return '全球'
    temp_df.insert(0, '地区', temp_df.apply(map_region, axis=1))

    # 6. 清理指标名称用于显示
    def clean_metric_name(row):
        if row['地区'] != '全球':
            # 移除地区前缀
            return row['收入类型'].replace(f"{row['地区']}_", "")
        return row['收入类型']
    temp_df['指标名称'] = temp_df.apply(clean_metric_name, axis=1)
    
    summary_df_final = temp_df[['地区', '指标名称', '总计金额_gbp']]
    return summary_df_final

# ----------------------------------------------------
# 3. 明细数据筛选函数 (逻辑保持不变)
# ----------------------------------------------------

def get_metric_detail_data(df, metric_name, region, target_period, target_biz_attr):
    """
    根据所选指标和地区，从原始df中筛选出明细数据
    """
    
    base_condition = (df['所属账期'] == target_period)
    
    # 收入指标筛选逻辑 (前9个)
    def revenue_filter(condition, metric_name):
        if '同业收入' in metric_name:
            return condition & (df['广告类型'] == '同业广告')
        elif '异业收入' in metric_name:
            return condition & (df['广告类型'] == '异业广告')
        return condition # 广告收入/总收入

    if region == '全球':
        # --- 全球指标筛选 ---
        if metric_name in ALL_METRIC_ORDER[:9]: # 业绩指标
            if metric_name in ['广告收入', '广告收入——同业收入', '广告收入——异业收入']:
                # 广告收入 (Aggregate total) - 明细为所有数据
                return df[base_condition & revenue_filter(pd.Series(True, index=df.index), metric_name)]
            elif metric_name in ['广告部：广告收入', '广告部—同业收入', '广告部—异业收入']:
                ad_condition = base_condition & (df['3级部门'] == 'AD')
                return df[revenue_filter(ad_condition, metric_name)]
            elif metric_name in ['国家：广告收入', '国家-同业收入', '国家-异业收入']:
                # 修正后的国家收入逻辑: 3级部门 != AD
                non_ad_condition = base_condition & (df['3级部门'] != 'AD')
                return df[revenue_filter(non_ad_condition, metric_name)]

        elif metric_name in ['国家BD人数（实际为有售卖的BD）', '全球BD人数', '广告部BD人数']:
            # --- 人数指标筛选 ---
            if metric_name == '广告部BD人数':
                # 广告部BD人数: 3级部门 == AD
                return df[base_condition & (df['3级部门'] == 'AD')]
            
            elif metric_name == '国家BD人数（实际为有售卖的BD）':
                # 国家BD人数: 3级部门 in DEPARTMENTS_COUNTRY AND 业务属性 == TARGET_BUSINESS_ATTR
                return df[base_condition & (df['3级部门'].isin(DEPARTMENTS_COUNTRY)) & (df['业务属性'] == target_biz_attr)]
            
            elif metric_name == '全球BD人数':
                # 全球BD人数: 3级部门 == AD OR (3级部门 in DEPARTMENTS_COUNTRY AND 业务属性 == TARGET_BUSINESS_ATTR)
                ad_bd_condition = base_condition & (df['3级部门'] == 'AD')
                country_bd_condition = base_condition & (df['3级部门'].isin(DEPARTMENTS_COUNTRY)) & (df['业务属性'] == target_biz_attr)
                # 合并两个集合的销售人工号（注意：这里返回的是用于计算BD人数的原始行）
                return df[ad_bd_condition | country_bd_condition]
                
        elif metric_name in ['全球BD：人均广告收入', '广告部BD：人均广告收入', '国家BD：人均广告收入']:
            # 人效指标：明细数据意义不大，但为保持功能完整，默认返回总广告收入的明细
             return df[base_condition]

    else:
        # --- 地区指标筛选 (例如 'AU') ---
        dept_condition = base_condition & (df['3级部门'] == region)
        
        if metric_name in ALL_METRIC_ORDER[:9]: # 业绩指标
            return df[revenue_filter(dept_condition, metric_name)]
            
        elif metric_name == '国家BD人数（实际为有售卖的BD）':
            return df[dept_condition & (df['业务属性'] == target_biz_attr)]
            
        elif metric_name == '广告部BD人数':
            # 广告部BD人数: 3级部门 == AD AND 国家 == region
            return df[base_condition & (df['3级部门'] == 'AD') & (df['国家'] == region)]
            
        elif metric_name == '全球BD人数':
            # 全球BD人数: (3级部门 == region) OR (3级部门 == AD AND 国家 == region)
            ad_bd_condition = base_condition & (df['3级部门'] == 'AD') & (df['国家'] == region)
            country_bd_condition = base_condition & (df['3级部门'] == region)
            return df[ad_bd_condition | country_bd_condition]
            
        elif metric_name in ['全球BD：人均广告收入', '广告部BD：人均广告收入', '国家BD：人均广告收入']:
            # 人效指标：默认返回该地区总广告收入的明细
            return df[dept_condition]

    # 如果没有匹配的逻辑，返回空DataFrame
    return pd.DataFrame(columns=df.columns)

# ----------------------------------------------------
# 4. Streamlit 网页布局
# ----------------------------------------------------

# --- 加载数据 ---
st.info("🚀 正在创建伪数据并计算指标，以便部署到 Streamlit Community Cloud...")
summary_df, df_raw = create_and_process_data(TARGET_PERIOD, TARGET_BUSINESS_ATTR)
st.success("✅ 伪数据创建和指标计算成功!")


# --- 网页标题 ---
st.title("🌍 全球/地区 广告收入看板 (伪数据演示)")
st.markdown(f"**所属账期:** `{TARGET_PERIOD}` | **BD业务属性:** `{TARGET_BUSINESS_ATTR}`")
st.divider()

# --- 侧边栏选择器 ---
st.sidebar.header("地区选择")
ALL_REGIONS = ['全球'] + DEPARTMENTS_COUNTRY
selected_region = st.sidebar.selectbox(
    label="选择要查看的地区:",
    options=ALL_REGIONS,
    index=0 
)

# --- 主内容区 ---
st.header(f"📊 {selected_region} 地区核心指标")

# 1. 筛选并展示指标表格
if selected_region == '全球':
    filtered_df = summary_df[summary_df['地区'] == '全球'].copy()
else:
    filtered_df = summary_df[summary_df['地区'] == selected_region].copy()

display_df = filtered_df[['指标名称', '总计金额_gbp']].copy()
display_df = display_df.rename(columns={
    '指标名称': '指标名称',
    '总计金额_gbp': '总计金额 (GBP)'
})

# 2. 定义智能格式化函数
def intelligent_formatter(val):
    """根据值是整数还是浮点数来格式化"""
    if isinstance(val, (int, float)):
        # 针对 BD 人数，强制格式化为整数
        if val == int(val) and 'BD人数' in display_df['指标名称'].to_list():
             return f"{int(val):,}" 
        return f"{val:,.2f}"
    return val

# 3. 应用样式 (Styler)
# 解决渲染冲突的关键：使用 st.dataframe 接收 Styler 对象
styled_df = display_df.style.format({
    "总计金额 (GBP)": intelligent_formatter
}).set_properties(
    **{'text-align': 'center'}
).set_table_styles([
    {'selector': 'th', 'props': [('text-align', 'center')]}, 
    {'selector': 'td:first-child', 'props': [('text-align', 'left')]}, 
    {'selector': 'th:first-child', 'props': [('text-align', 'left')]}
])

# 4. 渲染表格 (使用原生的 st.dataframe，避免 HTML 冲突)
st.dataframe(styled_df, use_container_width=True, hide_index=True)


st.divider()

# ----------------------------------------------------
# 5. 下载明细功能
# ----------------------------------------------------
st.subheader(f"📥 下载指标明细数据")
st.markdown(f"请为 **{selected_region}** 地区选择要下载的指标明细：")

# 1. 创建指标选择器 (使用包含 15 个指标的列表)
selected_metric = st.selectbox(
    label="选择指标:",
    options=ALL_METRIC_ORDER 
)

# 2. 根据选择动态筛选数据
detail_df_to_download = get_metric_detail_data(
    df_raw, 
    selected_metric, 
    selected_region, 
    TARGET_PERIOD, 
    TARGET_BUSINESS_ATTR
)

# 3. 缓存CSV转换函数
@st.cache_data
def convert_df_to_csv(df):
    if '销售人工号' in df.columns:
        df['销售人工号'] = df['销售人工号'].astype(str)
    return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')

csv_data = convert_df_to_csv(detail_df_to_download)

# 4. 创建动态文件名
filename = f"{selected_region}_{selected_metric}_明细_{TARGET_PERIOD}.csv"

# 5. 显示下载按钮
st.download_button(
    label=f"点击下载: {filename}",
    data=csv_data,
    file_name=filename,
    mime='text/csv',
    use_container_width=True
)

# 6. 预览功能
show_preview = st.checkbox(
    label=f"预览 {selected_metric} 的明细数据 (前100行)",
    key="show_detail_preview" 
)

if show_preview:
    if detail_df_to_download.empty:
        st.warning(f"没有找到 '{selected_metric}' 的明细数据。")
    else:
        st.dataframe(detail_df_to_download.head(100), use_container_width=True)