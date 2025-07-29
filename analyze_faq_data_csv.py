import streamlit as st
import pandas as pd
import urllib.parse
import re
import io

st.title("FAQ 分析アプリ")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type=["csv"])

def decode_url_component(url_component):
    try:
        return urllib.parse.unquote(url_component)
    except:
        return url_component

def remove_columns(df):
    columns = df.columns.tolist()
    columns_to_remove = [0, 1, 12] if len(columns) > 12 else [0, 1]
    columns_to_drop = [columns[i] for i in columns_to_remove if i < len(columns)]
    return df.drop(columns=columns_to_drop, errors='ignore')

def convert_to_percentage(df):
    if '直帰率' in df.columns:
        df['直帰率'] = df['直帰率'] * 100
    return df

def format_columns(df):
    columns_to_round = ['セッションあたりのページビュー数', '直帰率', '平均セッション継続時間']
    for col in columns_to_round:
        if col in df.columns:
            df[col] = df[col].round(2)
    if '直帰率' in df.columns:
        df['直帰率'] = df['直帰率'].astype(str) + '%'
    return df

if uploaded_file:
    try:
        # 生テキスト読み込み
        raw_text = uploaded_file.getvalue().decode("utf-8")
        lines = raw_text.splitlines()

        # 1～6行目削除、7行目(インデックス6)をヘッダーに、8行目(インデックス7)削除
        processed_lines = [lines[6]] + lines[8:]

        # DataFrame化
        df = pd.read_csv(io.StringIO("\n".join(processed_lines)))
        
        # A列をURLデコード
        col_0 = df.columns[0]
        df[col_0] = df[col_0].astype(str).apply(decode_url_component)

        # 1. 「よくあるご質問」で始まらないレコードのセッション数ランキング
        not_faq = df[~df['ページ タイトルとスクリーン クラス'].astype(str).str.startswith('よくあるご質問', na=False)]
        faq_pattern = r'^/lowv/faq/\d+-\d+$'
        not_faq_filtered = not_faq[not_faq['ページパス + クエリ文字列'].astype(str).str.match(faq_pattern, na=False)]
        not_faq_sorted = not_faq_filtered.sort_values('セッション', ascending=False)
        not_faq_sorted['ページ タイトルとスクリーン クラス'] = not_faq_sorted['ページ タイトルとスクリーン クラス'].str.replace('｜Q.ENEST（キューエネス）でんき', '', regex=False)

        # 2. カテゴリ別ランキング
        cat_prefix = "/lowv/faq/result?category="
        cat_df = df[df['ページパス + クエリ文字列'].astype(str).str.startswith(cat_prefix, na=False)].copy()
        cat_df['カテゴリ名'] = cat_df['ページパス + クエリ文字列'].astype(str).str[len(cat_prefix):].apply(decode_url_component)
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

        # 3. キーワード別ランキング
        kw_prefix = "/lowv/faq/result?keyword="
        kw_df = df[df['ページパス + クエリ文字列'].astype(str).str.startswith(kw_prefix, na=False)].copy()
        kw_df['検索キーワード'] = kw_df['ページパス + クエリ文字列'].astype(str).str[len(kw_prefix):].apply(decode_url_component)
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

        # 指定列削除（not_faqのみ）
        not_faq_sorted = remove_columns(not_faq_sorted)

        # 詳細ページシートのA列：ページパス + クエリ文字列、B列：ページ タイトルとスクリーン クラスを確実に表示
        cols = list(not_faq_sorted.columns)
        if 'ページパス + クエリ文字列' in cols and 'ページ タイトルとスクリーン クラス' in cols:
            others = [c for c in cols if c not in ['ページパス + クエリ文字列', 'ページ タイトルとスクリーン クラス']]
            not_faq_sorted = not_faq_sorted[['ページパス + クエリ文字列', 'ページ タイトルとスクリーン クラス'] + others]
        else:
            st.warning("詳細ページに必要な列がありません。")

        # カテゴリ・キーワードはページタイトル列を削除
        cat_df_sorted = cat_df_sorted.drop(columns=['ページ タイトルとスクリーン クラス'], errors='ignore')
        kw_df_sorted = kw_df_sorted.drop(columns=['ページ タイトルとスクリーン クラス'], errors='ignore')

        # 直帰率を%変換、小数点整形
        not_faq_sorted = convert_to_percentage(not_faq_sorted)
        cat_df_sorted = convert_to_percentage(cat_df_sorted)
        kw_df_sorted = convert_to_percentage(kw_df_sorted)

        not_faq_sorted = format_columns(not_faq_sorted)
        cat_df_sorted = format_columns(cat_df_sorted)
        kw_df_sorted = format_columns(kw_df_sorted)

        # Excelファイル出力（メモリ上）
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            not_faq_sorted.to_excel(writer, sheet_name="詳細ページ", index=False)
            cat_df_sorted.to_excel(writer, sheet_name="カテゴリ", index=False)
            kw_df_sorted.to_excel(writer, sheet_name="キーワード", index=False)
        output.seek(0)

        st.success("✅ 分析が完了しました！")
        st.download_button(
            label="📥 FAQ_output.xlsx をダウンロード",
            data=output,
            file_name="FAQ_output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
