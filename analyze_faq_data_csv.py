import streamlit as st
import pandas as pd
import urllib.parse
import re
from io import BytesIO

st.set_page_config(page_title="FAQレポート解析アプリ")
st.title("FAQレポート解析アプリ")

def safe_replace_title(df):
    col = "ページ タイトルとスクリーン クラス"
    if col in df.columns:
        df[col] = df[col].astype(str).str.replace(r"\|\s*Q\.ENEST（キューエネス）でんき", "", regex=True)
    return df

def decode_column(df, col_name):
    if col_name in df.columns:
        df[col_name] = df[col_name].astype(str).apply(lambda x: urllib.parse.unquote(x))
    return df

def extract_query_param(value, param):
    if pd.isna(value):
        return ""
    try:
        parsed = urllib.parse.urlparse(value)
        qs = urllib.parse.parse_qs(parsed.query)
        return qs.get(param, [""])[0]
    except:
        return ""

def extract_category_and_keyword_from_url(url):
    category = extract_query_param(url, "category")
    keyword = extract_query_param(url, "keyword")
    return category, keyword

def load_csv_with_header_adjustment(uploaded_file):
    # 1〜6行目削除、7行目をヘッダー、8行目以降をデータ
    raw = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    lines = raw.splitlines()
    if len(lines) < 7:
        st.error(f"{uploaded_file.name} は行数が少なく読み込めません。")
        return pd.DataFrame()
    header_line = lines[6]
    rest = lines[8:] if len(lines) > 8 else []
    combined = "\n".join([header_line] + rest)
    try:
        df = pd.read_csv(BytesIO(combined.encode("utf-8")), dtype=str)
    except Exception:
        # fallback: try normal skiprows
        df = pd.read_csv(uploaded_file, skiprows=6, dtype=str)
    return df

def process_report(file, report_type):
    df = load_csv_with_header_adjustment(file)
    if df.empty:
        return {}

    # 共通：タイトル内の不要文字除去（存在すれば）
    df = safe_replace_title(df)

    sheets = {}

    if report_type == "report1":
        # report1：ページパス+クエリをデコード、カテゴリ/キーワードを追加（C,D）
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")
            # 抽出
            category = df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            keyword = df["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            # 挿入：C列, D列 のイメージでタイトルとページパスの後ろに入れる
            # 元の列順を保持しつつ、カテゴリ・キーワードを後ろに追加
            df["カテゴリ"] = category
            df["キーワード"] = keyword
        sheets["詳細ページ"] = df

    elif report_type == "report2":
        # report2：詳細ページはカテゴリ/キーワード追加しない。ただしB列（ページパス+クエリ）をデコード
        if "ページパス + クエリ文字列" in df.columns:
            df = decode_column(df, "ページパス + クエリ文字列")
        sheets["詳細ページ"] = df

        # カテゴリシート（?category= がある行）
        if "ページパス + クエリ文字列" in df.columns:
            tmp = df.copy()
            tmp["カテゴリ"] = tmp["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "category"))
            # キーワードも抽出（ただしカテゴリシートはカテゴリ主体）
            tmp["キーワード"] = tmp["ページパス + クエリ文字列"].apply(lambda u: extract_query_param(u, "keyword"))
            # フィルタはカテゴリ非空
            cat_sheet = tmp[tmp["カテゴリ"].astype(str) != ""].copy()
            sheets["カテゴリ"] = cat_sheet

            # キーワードシート
            kw_sheet = tmp[tmp["キーワード"].astype(str) != ""].copy()
            sheets["キーワード"] = kw_sheet

    elif report_type == "report4":
        # report4：ページの参照元 URL が特定接頭辞で始まる行だけ
        url_col = "ページの参照元 URL"
        if url_col not in df.columns:
            st.warning(f"{file.name}: '{url_col}' 列がないため report4 の抽出ができません。")
            return {}

        # フィルタ
        filtered = df[df[url_col].astype(str).str.startswith("https://www.qenest-denki.com/lowv/faq/", na=False)].copy()
        if filtered.empty:
            st.warning(f"{file.name} に該当する faq URL 行がありません。")
            return {}

        # デコード
        filtered = decode_column(filtered, url_col)
        # カテゴリ/キーワード抽出（元のC列=参照元URL から）
        filtered["カテゴリ"] = filtered[url_col].apply(lambda u: extract_query_param(u, "category"))
        filtered["キーワード"] = filtered[url_col].apply(lambda u: extract_query_param(u, "keyword"))
        sheets["faqページ"] = filtered

    return sheets

uploaded_files = st.file_uploader("CSVファイルをアップロード（複数可）", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    # まとめて1つのExcelにする（ファイルごとシート名にプレフィックス）
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for file in uploaded_files:
            fname = file.name
            lower = fname.lower()
            if lower.startswith("report1"):
                report_type = "report1"
            elif lower.startswith("report2"):
                report_type = "report2"
            elif lower.startswith("report4"):
                report_type = "report4"
            else:
                st.warning(f"{fname} は report1 / report2 / report4 のいずれでもないためスキップします。")
                continue

            sheets = process_report(file, report_type)
            for sheet_name, df in sheets.items():
                # シート名衝突回避のためファイル名断片を付与
                safe_name = f"{sheet_name}_{fname}".replace(".", "_")
                writer.sheets  # ensure internal dict exists
                df.to_excel(writer, sheet_name=safe_name[:31], index=False)

    output.seek(0)
    st.download_button(
        label="変換済み Excel をダウンロード",
        data=output.getvalue(),
        file_name="faq解析結果.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
