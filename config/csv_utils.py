"""共用小工具：防止 CSV 匯出被拿來做公式注入（CSV / Formula Injection）。

Excel、Google Sheets 等試算表軟體，如果 CSV 儲存格內容是以
`=`、`+`、`-`、`@` 開頭，會被當成公式解析，開啟檔案的人可能因此
被埋一個外部連結（HYPERLINK）甚至跑到非預期的公式。使用者可控的
欄位（帳號、姓名⋯）如果原封不動寫進匯出的 CSV，任何能設定自己
帳號名稱的使用者，都能讓之後開啟這份 CSV 的老師/管理員中招。

標準防禦方式（OWASP 建議）：這類開頭字元前面補一個單引號，讓
試算表軟體把它當成純文字而不是公式——Excel、Google Sheets 都吃這招。
"""

_FORMULA_TRIGGER_CHARS = ('=', '+', '-', '@')


def csv_safe(value):
    """把值轉成字串，並中和開頭可能觸發公式執行的字元。

    寫入 csv.writer 的每一列前，把使用者可控的欄位都經過這個函式。
    """
    text = '' if value is None else str(value)
    if text and text[0] in _FORMULA_TRIGGER_CHARS:
        return "'" + text
    return text
