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

def extract_category_from_url(url):
    match = re.search(r'[?&]category=([^&]+)', url)
    return urllib.parse.unquote(match.group(1)) if match else ""

def extract_keyword_from_url(url):
    match = re.search(r'[?&]keyword=([^&]+)', url)
    return urllib.parse.unquote(match.group(1)) if match else ""

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
        file_name = uploaded_file.name.lower()
        raw_text = uploaded_file.getvalue().decode("utf-8")
        lines = raw_text.splitlines()

        # 1～6行目削除、7行目をヘッダーに、8行目削除
        processed_lines = [lines[6]] + lines[8:]
        df = pd.read_csv(io.StringIO("\n".join(processed_lines)))

        if file_name.startswith("report2_"):
            # report2 特別処理
            col_a = 'ページ タイトルとスクリーン クラス'
            col_b = 'ページパス + クエリ文字列'

            # A列：タイトルから不要な文字削除
            if col_a in df.columns:
                df[col_a] = df[col_a].astype(str).str.replace('｜Q.ENEST（キューエネス）でんき', '', regex=False)

            # B列：URLデコード
            if col_b in df.columns:
                df[col_b] = df[col_b].astype(str).apply(decode_url_component)

                # カテゴリ・キーワード列の挿入
                df.insert(df.columns.get_loc(col_b) + 1, "カテゴリ", df[col_b].apply(extract_category_from_url))
                df.insert(df.columns.get_loc(col_b) + 2, "キーワード", df[col_b].apply(extract_keyword_from_url))

        else:
            # report1 通常処理
            col_0 = df.columns[0]
            df[col_0] = df[col_0].astype(str).apply(decode_url_component)

        # この先は共通処理（report1/2ともに）

        # 1. よくあるご質問を除く詳細ページ
        not_faq = df[~df['ページ タイトルとスクリーン クラス'].astype(str).str.startswith('よくあるご質問', na=False)]
        faq_pattern = r'^/lowv/faq/\d+-\d+$'
        not_faq_filtered = not_faq[not_faq['ページパス + クエリ文字列'].astype(str).str.match(faq_pattern, na=False)]
        not_faq_sorted = not_faq_filtered.sort_values('セッション', ascending=False)

        # A列・B列固定
        cols = list(not_faq_sorted.columns)
        if 'ページパス + クエリ文字列' in cols and 'ページ タイトルとスクリーン クラス' in cols:
            others = [c for c in cols if c not in ['ページパス + クエリ文字列', 'ページ タイトルとスクリーン クラス']]
            not_faq_sorted = not_faq_sorted[['ページパス + クエリ文字列', 'ページ タイトルとスクリーン クラス'] + others]
        else:
            st.warning("詳細ページに必要な列がありません。")

        # 2. カテゴリ別ランキング
        cat_prefix = "/lowv/faq/result?category="
        cat_df = df[df['ページパス + クエリ文字列'].astype(str).str.startswith(cat_prefix, na=False)].copy()
        cat_df['カテゴリ名'] = cat_df['ページパス + クエリ文字列'].astype(str).str[len(cat_prefix):].apply(decode_url_component)
        cat_df['カテゴリ名'] = cat_df['カテゴリ名'].str.replace(r'&page=\d+$', '', regex=True)

        cat_df['キーワード'] = cat_df['カテゴリ名'].apply(extract_keyword_from_url)
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

        kw_df['カテゴリ'] = kw_df['検索キーワード'].apply(extract_category_from_url)
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

        # フォーマット調整
        not_faq_sorted = convert_to_percentage(not_faq_sorted)
        cat_df_sorted = convert_to_percentage(cat_df_sorted)
        kw_df_sorted = convert_to_percentage(kw_df_sorted)

        not_faq_sorted = format_columns(not_faq_sorted)
        cat_df_sorted = format_columns(cat_df_sorted)
        kw_df_sorted = format_columns(kw_df_sorted)

        # 不要列削除（カテゴリ・キーワードのみ）
        cat_df_sorted = cat_df_sorted.drop(columns=['ページ タイトルとスクリーン クラス'], errors='ignore')
        kw_df_sorted = kw_df_sorted.drop(columns=['ページ タイトルとスクリーン クラス'], errors='ignore')

        # Excel出力
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
