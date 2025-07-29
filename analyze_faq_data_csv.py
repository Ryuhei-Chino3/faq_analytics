import streamlit as st
import pandas as pd
import urllib.parse
import re
import io

st.set_page_config(page_title="FAQ 分析アプリ", layout="wide")
st.title("📊 よくあるご質問 分析アプリ")

uploaded_file = st.file_uploader("📎 CSVファイルをアップロードしてください（Google Analyticsエクスポート形式）", type=["csv"])

if uploaded_file:
    df_preview = pd.read_csv(uploaded_file, skiprows=8)  # または skiprows=6 など適宜変更
    st.write("読み込んだ列名一覧:", df_preview.columns.tolist())

run_button = st.button("✅ 分析を実行")

if run_button:
    if not uploaded_file:
        st.warning("CSVファイルをアップロードしてください。")
        st.stop()

    try:
        # -------------------------------
        # データ読み込み
        # -------------------------------
        df = pd.read_csv(uploaded_file, skiprows=8)  # 9行目から本データ開始
        df.columns = [col.strip() for col in df.columns]  # ヘッダー整形

        # 必要列チェック
        required_columns = ['ページパス + クエリ文字列', 'ページ タイトルとスクリーン クラス', 'セッション']
        if not all(col in df.columns for col in required_columns):
            st.error("必要な列がCSVに存在しません。Google Analyticsの形式を確認してください。")
            st.stop()

        df['ページパス + クエリ文字列'] = df['ページパス + クエリ文字列'].astype(str).apply(urllib.parse.unquote)
        df['ページ タイトルとスクリーン クラス'] = df['ページ タイトルとスクリーン クラス'].astype(str)

        # -------------------------------
        # 1. 詳細ページ（よくあるご質問以外）
        # -------------------------------
        not_faq = df[~df['ページ タイトルとスクリーン クラス'].str.startswith('よくあるご質問', na=False)]
        faq_pattern = r'^/lowv/faq/\d+-\d+$'
        not_faq_filtered = not_faq[not_faq['ページパス + クエリ文字列'].str.match(faq_pattern, na=False)]
        not_faq_sorted = not_faq_filtered.sort_values('セッション', ascending=False)
        not_faq_sorted['ページ タイトルとスクリーン クラス'] = not_faq_sorted['ページ タイトルとスクリーン クラス'].str.replace('｜Q.ENEST（キューエネス）でんき', '', regex=False)

        # -------------------------------
        # 2. カテゴリ別ランキング
        # -------------------------------
        cat_prefix = "/lowv/faq/result?category="
        cat_df = df[df['ページパス + クエリ文字列'].str.startswith(cat_prefix, na=False)].copy()
        cat_df['カテゴリ名'] = cat_df['ページパス + クエリ文字列'].str[len(cat_prefix):].apply(urllib.parse.unquote)
        cat_df['カテゴリ名'] = cat_df['カテゴリ名'].str.replace(r'&page=\d+$', '', regex=True)

        def extract_keyword(category_name):
            match = re.search(r'&keyword=([^&]+)', category_name)
            return urllib.parse.unquote(match.group(1)) if match else ""

        cat_df['キーワード'] = cat_df['カテゴリ名'].apply(extract_keyword)
        cat_df['カテゴリ名'] = cat_df['カテゴリ名'].str.replace(r'&keyword=[^&]+', '', regex=True)

        cat_df_grouped = cat_df.groupby(['カテゴリ名', 'キーワード']).agg({
            'ページパス + クエリ文字列': 'first',
            'ページ タイトルとスクリーン クラス': 'first',
            '表示回数': 'sum',
            'セッション': 'sum',
            '総ユーザー数': 'sum',
            '新規ユーザー数': 'sum',
            'セッションあたりのページビュー数': 'mean',
            '直帰率': 'mean',
            '離脱数': 'sum',
            '平均セッション継続時間': 'mean'
        }).reset_index()

        cat_df_sorted = cat_df_grouped.sort_values('セッション', ascending=False)

        # -------------------------------
        # 3. キーワード別ランキング
        # -------------------------------
        kw_prefix = "/lowv/faq/result?keyword="
        kw_df = df[df['ページパス + クエリ文字列'].str.startswith(kw_prefix, na=False)].copy()
        kw_df['検索キーワード'] = kw_df['ページパス + クエリ文字列'].str[len(kw_prefix):].apply(urllib.parse.unquote)
        kw_df['検索キーワード'] = kw_df['検索キーワード'].str.replace(r'&page=\d+', '', regex=True)

        def extract_category(keyword_value):
            match = re.search(r'&category=([^&]+)', keyword_value)
            return urllib.parse.unquote(match.group(1)) if match else ""

        kw_df['カテゴリ'] = kw_df['検索キーワード'].apply(extract_category)
        kw_df['検索キーワード'] = kw_df['検索キーワード'].str.replace(r'&category=[^&]+', '', regex=True)

        kw_df_grouped = kw_df.groupby(['検索キーワード', 'カテゴリ']).agg({
            'ページパス + クエリ文字列': 'first',
            'ページ タイトルとスクリーン クラス': 'first',
            '表示回数': 'sum',
            'セッション': 'sum',
            '総ユーザー数': 'sum',
            '新規ユーザー数': 'sum',
            'セッションあたりのページビュー数': 'mean',
            '直帰率': 'mean',
            '離脱数': 'sum',
            '平均セッション継続時間': 'mean'
        }).reset_index()

        kw_df_sorted = kw_df_grouped.sort_values('セッション', ascending=False)

        # -------------------------------
        # 整形処理
        # -------------------------------
        def format_df(df, drop_title=False):
            if drop_title and 'ページ タイトルとスクリーン クラス' in df.columns:
                df = df.drop(columns=['ページ タイトルとスクリーン クラス'])

            if '直帰率' in df.columns:
                df['直帰率'] = df['直帰率'] * 100
                df['直帰率'] = df['直帰率'].round(2).astype(str) + '%'

            for col in ['セッションあたりのページビュー数', '平均セッション継続時間']:
                if col in df.columns:
                    df[col] = df[col].round(2)
            return df

        not_faq_sorted = format_df(not_faq_sorted)
        cat_df_sorted = format_df(cat_df_sorted, drop_title=True)
        kw_df_sorted = format_df(kw_df_sorted, drop_title=True)

        # -------------------------------
        # Excel出力（メモリ内）
        # -------------------------------
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            not_faq_sorted.to_excel(writer, sheet_name="詳細ページ", index=False)
            cat_df_sorted.to_excel(writer, sheet_name="カテゴリ", index=False)
            kw_df_sorted.to_excel(writer, sheet_name="キーワード", index=False)
        output.seek(0)

        st.success("✅ 分析が完了しました！")
        st.download_button(
            label="📥 FAQ_output_v1.xlsx をダウンロード",
            data=output,
            file_name="FAQ_output_v1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
