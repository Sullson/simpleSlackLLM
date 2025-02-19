import re

def markdown_to_slack(md_text: str) -> str:
    """
    Convert a subset of Markdown to Slack-specific formatting, with these enhancements:
      1) Code blocks: remove any language spec (e.g. ```SQL => ```).
      2) Headings (# ... up to ######) => Slack bold line. 
         If heading text contains **bold**, remove those so we don't nest bold.
      3) **bold** => *bold*
      4) *italic* => _italic_
      5) ~~strikethrough~~ => ~strikethrough~
      6) [title](url) => <url|title>
      7) Bulleted lists: lines starting with "-" => Slack bullet (* item).
         Leading spaces are converted to tab indentation (every 2 spaces => 1 tab).
    """

    # 1) Remove language spec from triple backticks (```SQL, ```plaintext, etc.)
    #    We'll keep ``` but strip out the optional language.
    md_text = re.sub(
        r'```+([^\n`]*)\n',
        '```\n',
        md_text
    )

    # 2) Convert headings to Slack bold lines, removing ** inside the heading text
    def heading_sub(match):
        heading_text = match.group(2).strip()
        # Remove any double-asterisks inside heading
        heading_text = re.sub(r'\*\*', '', heading_text)
        return f"*{heading_text}*"

    # Regex for 1-6 hashes at start of line, followed by space, then text
    md_text = re.sub(
        r'^(#{1,6})\s+(.*)$',
        heading_sub,
        md_text,
        flags=re.MULTILINE
    )

    # 3) Convert bold: **text** => *text*
    md_text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', md_text, flags=re.DOTALL)

    # 4) Convert italic: *text* => _text_
    md_text = re.sub(
        r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',
        r'_\1_',
        md_text,
        flags=re.DOTALL
    )

    # 5) Convert strikethrough: ~~text~~ => ~text~
    md_text = re.sub(r'~~(.+?)~~', r'~\1~', md_text, flags=re.DOTALL)

    # 6) Convert links: [title](url) => <url|title>
    md_text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<\2|\1>', md_text)

    # 7) Bulleted lists: lines that start with "-" => Slack bullet.
    #    Convert every 2 leading spaces => 1 tab for indentation.
    def bullet_sub(match):
        leading_spaces = match.group(1) or ""
        text_after_dash = match.group(2)
        # each 2 spaces => one actual tab character
        tab_count = len(leading_spaces) // 2
        tabs = "\t" * tab_count
        return f"{tabs}* {text_after_dash}"

    md_text = re.sub(
        r'^([ ]*)- (.*)',
        bullet_sub,
        md_text,
        flags=re.MULTILINE
    )

    return md_text
