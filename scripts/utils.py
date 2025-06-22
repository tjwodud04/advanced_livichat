import re

def remove_empty_parentheses(text):
    return re.sub(r'\(\s*\)', '', text)

def prettify_message(text):
    text = remove_empty_parentheses(text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'링크:\s*', '\n링크: ', text)
    return text.strip()

def markdown_to_html_links(text):
    return re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'<a href="\2" target="_blank">\1</a>', text)

def extract_first_markdown_url(text):
    match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', text)
    if match:
        return match.group(2)
    return None

def remove_emojis(text):
    # 일반적인 이모지 범위, 특수문자, 딩뱃 기호 등을 포함하는 정규식
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r'', text) 