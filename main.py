import streamlit as st
import requests
import pandas as pd
from io import StringIO
import datetime
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# --- 網頁設定 ---
st.set_page_config(page_title="ai-st filter", layout="wide")
st.title("📈AI Filter)")

# --- 側邊欄：使用者輸入 ---
st.sidebar.header("篩選設定")
# 預設為今天，但如果今天是週末或尚未收盤，使用者可以往前選
selected_date = st.sidebar.date_input("選擇日期", datetime.date.today())

# --- 核心邏輯 (加上快取功能，避免頻繁刷網頁被證交所封鎖) ---
@st.cache_data(ttl=600) # 資料快取 10 分鐘
def get_stock_data(date_obj):
    date_str = date_obj.strftime('%Y%m%d')
    url = 'https://www.twse.com.tw/exchangeReport/MI_INDEX'
    
    payloads = {
        'response': 'html',
        'date': date_str,
        'type': 'ALLBUT0999'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.80 Safari/537.36'
    }

    try:
        response = requests.get(url, params=payloads, headers=headers, verify=False)
        
        # 簡單檢查回傳是否有效
        if len(response.text) < 500:
            return None, "資料不足或當日未開盤"

        df = pd.read_html(StringIO(response.text))[-1]
        df.columns = df.columns.get_level_values(1)
        
        # 資料清洗
        df = df.astype(str).map(lambda x: x.replace(',', ''))
        df['漲跌價差'] = pd.to_numeric(df['漲跌價差'], errors='coerce')
        mask_negative = df['漲跌(+/-)'].str.contains('-', na=False)
        df.loc[mask_negative, '漲跌價差'] = -df.loc[mask_negative, '漲跌價差']
        df.drop(['證券名稱', '漲跌(+/-)'], inplace=True, axis=1)
        
        df = df.apply(pd.to_numeric, errors='coerce')
        df.dropna(subset=['收盤價'], inplace=True)
        
        # 計算指標
        df['昨日收盤價'] = df['收盤價'] - df['漲跌價差']
        df['股價振幅'] = (df['最高價'] - df['最低價']) / df['昨日收盤價'] * 100
        
        return df, None
    except Exception as e:
        return None, str(e)

# --- 執行按鈕 ---
if st.button("開始分析"):
    with st.spinner(f"正在抓取 {selected_date} 的資料..."):
        df, error = get_stock_data(selected_date)
        
        if error:
            st.error(f"發生錯誤：{error}")
        elif df is None or df.empty:
            st.warning("查無資料，可能是假日或資料尚未更新。")
        else:
            # --- 篩選邏輯區域 ---
            st.success("資料抓取成功！開始篩選...")
            
            # 這裡可以做成動態拉桿，讓使用者自己調整
            min_vol = 500
            max_vol = 2000
            min_amp = 6.318
            
            cond_vol = (df['成交股數'] >= min_vol * 1000) & (df['成交股數'] <= max_vol * 1000)
            cond_amp = df['股價振幅'] > min_amp
            
            result = df[cond_vol & cond_amp]
            
            # 排序與顯示
            final_view = result.sort_values(by=['股價振幅'], ascending=False).head(13)
            
            # 顯示結果
            st.subheader(f"🎯 篩選結果 ({len(final_view)} 檔)")
            # 為了美觀，只顯示重要欄位
            cols_to_show = ['證券代號','成交股數', '開盤價', '最高價', '最低價', '收盤價', '股價振幅']

            st.dataframe(final_view[cols_to_show], use_container_width=True)

