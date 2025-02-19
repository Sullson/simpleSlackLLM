import re

def markdown_to_slack(md_text: str) -> str:
    """
    Convert a subset of Markdown to Slack-specific formatting, with these enhancements:
      1) Code blocks: remove any language spec (e.g. ```SQL => ```).
      2) Headings (# to ######) => bold lines. If heading text contains **bold**, remove those double-asterisks so
         we don't end up with nested bold. (e.g. "### **Key Features**" => "*Key Features*").
      3) **bold** => *bold*
      4) *italic* => _italic_
      5) ~~strikethrough~~ => ~strikethrough~
      6) [title](url) => <url|title>
      7) Bulleted lists: lines starting with "-" become Slack bullets ("* item"). 
         Leading spaces are turned into tabs (every 2 spaces => 1 tab).
    """

    # 1) Remove language spec after triple backticks (```SQL, ```plaintext, etc.)
    #    We keep the triple backticks, but discard the language name.
    #    E.g. ```SQL\n => ```\n
    #    or ```plaintext => ```
    md_text = re.sub(
        r'```+([^\n`]*)\n',
        '```\n',
        md_text
    )
    # (If a code block ends on the same line with a language, it’s uncommon in markdown; 
    #  but you can expand this if needed.)

    # 2) Convert headings (# ... up to ######) => Slack bold line. 
    #    Remove any internal **...** to avoid double bold.
    def heading_sub(match):
        text = match.group(2).strip()  # the heading text
        # Remove any ** markers inside the heading
        text = re.sub(r'\*\*', '', text)
        return f"*{text}*"

    # Regex for heading lines: up to 6 '#' plus a space, then text
    md_text = re.sub(
        r'^(#{1,6})\s+(.*)$',
        heading_sub,
        md_text,
        flags=re.MULTILINE
    )

    # 3) Convert bold: **text** => *text*
    md_text = re.sub(
        r'\*\*(.+?)\*\*',
        r'*\1*',
        md_text,
        flags=re.DOTALL
    )

    # 4) Convert italic: *text* => _text_
    #    (Naive approach; can conflict with nested bold if e.g. ***...***)
    md_text = re.sub(
        r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',
        r'_\1_',
        md_text,
        flags=re.DOTALL
    )

    # 5) Convert strikethrough: ~~text~~ => ~text~
    md_text = re.sub(
        r'~~(.+?)~~',
        r'~\1~',
        md_text,
        flags=re.DOTALL
    )

    # 6) Convert links: [title](url) => <url|title>
    md_text = re.sub(
        r'\[(.*?)\]\((.*?)\)',
        r'<\2|\1>',
        md_text
    )

    # 7) Convert bulleted lists: lines that start with "-" => Slack bullet
    #    Also handle indentation by mapping every 2 leading spaces => 1 tab.
    def bullet_sub(match):
        leading_spaces = match.group(1) or ""
        text_after_dash = match.group(2)
        # each 2 spaces => 1 tab
        tab_count = len(leading_spaces) // 2
        return f"{'\t' * tab_count}* {text_after_dash}"

    # Matches lines that look like (some spaces) - (then text)
    md_text = re.sub(
        r'^([ ]*)- (.*)',
        bullet_sub,
        md_text,
        flags=re.MULTILINE
    )

    return md_text
