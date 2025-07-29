import streamlit as st
import pandas as pd
import urllib.parse
import re
import io

st.set_page_config(page_title="FAQ 分析アプリ", layout="wide")
st.title("📊 よくあるご質問 分析アプリ")

uploaded_file = st.file_uploader("📎 CSVファイルをアップロードしてください（Google Analyticsエクスポート形式）", type=["csv"])
run_button = st.button("✅ 分析を実行")

if run_button:
    if not uploaded_file:
        st.warning("CSVファイルをアップロードしてください。")
        st.stop()

    try:
        # --------------------------------------
        # 1. ヘッダー位置を探す
        # --------------------------------------
        raw_text = uploaded_file.getvalue().decode("utf-8")
        raw_lines = raw_text.splitlines()

        header_row = None
        for i, line in enumerate(raw_lines):
            if line.startswith("ページパス + クエリ文字列"):
                header_row = i
                break

        if header_row is None:
            st.error("CSV内にヘッダー行（ページパス + クエリ文字列）が見つかりませんでした。")
            st.stop()

        # データ読み込み
        df = pd.read_csv(io.StringIO(raw_text), skiprows=header_row)
        df.columns = [col.strip() for col in df.columns]

        # --------------------------------------
        # 2. 数値列を変換
        # --------------------------------------
        numeric_cols = [
            "表示回数", "セッション", "総ユーザー数", "新規ユーザー数",
            "セッションあたりのページビュー数", "直帰率", "離脱数", "平均セッション継続時間"
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # --------------------------------------
        # 3. 表示
        # --------------------------------------
        st.subheader("🔍 上位10ページ（表示回数順）")
        top10 = df.sort_values("表示回数", ascending=False).head(10)
        st.dataframe(top10.reset_index(drop=True))

        st.subheader("📉 ページ別 離脱率（離脱数 / 表示回数）")
        df["離脱率"] = df["離脱数"] / df["表示回数"]
        df_sorted = df.sort_values("離脱率", ascending=False)
        st.dataframe(df_sorted[["ページパス + クエリ文字列", "離脱率", "表示回数", "離脱数"]].head(10))

        st.subheader("📈 平均セッション継続時間（秒）が長いページ")
        df_time = df.sort_values("平均セッション継続時間", ascending=False)
        st.dataframe(df_time[["ページパス + クエリ文字列", "平均セッション継続時間", "セッション"]].head(10))

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
