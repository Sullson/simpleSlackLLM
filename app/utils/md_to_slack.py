import re

def markdown_to_slack(md_text: str) -> str:
    """
    Convert a subset of Markdown to Slack-specific formatting, ignoring text inside code blocks.

    Transformations:
      1) Code blocks: identify them with triple backticks (```).
         - Remove any language spec (e.g. ```SQL => ```).
         - Preserve block content exactly (no further formatting).
      2) Italic: *text* => _text_
      3) Headings (# ... up to ######) => Slack bold lines,
         remove **bold** inside heading text to avoid nested bold (## **Foo** => *Foo*).
      4) Bold: **text** => *text*
      5) Strikethrough: ~~text~~ => ~text~
      6) Links: [title](url) => <url|title>
      7) Bulleted lists: lines that start with '-' => bullet (•).
         - Each 2 leading spaces => one tab (\t), and we use bullet char "•" for level 0,
           "◦" for deeper levels as an example.
    """

    # -------------------------------------------------
    # 0) EXTRACT CODE BLOCKS FIRST
    # -------------------------------------------------
    # We'll capture:
    #   group(1) = opening triple backticks (at least 3)
    #   group(2) = optional language spec (any non-backtick chars)
    #   group(3) = the code block content (until matching triple backticks)
    #   group(4) = closing triple backticks
    code_block_regex = re.compile(
        r'(?s)(```+)([^\n`]*)(\n)(.*?)(```+)'
    )

    code_blocks = []

    def replace_code_block(m):
        """
        Store the code block content (minus language spec) in a placeholder
        so we can skip transformations on it.
        """
        opening = m.group(1)   # ``` or ```` etc.
        language = m.group(2)  # e.g. SQL, plaintext, etc.
        newline_after_lang = m.group(3)  # the \n after the language
        content = m.group(4)   # the code block content
        closing = m.group(5)   # the closing backticks

        # We'll remove the language spec from the opening fence, e.g. ```SQL => ```
        # But keep the triple backticks themselves:
        pure_opening = '```'   # always 3 backticks for Slack (ignore extra backticks)
        pure_closing = '```'

        # We'll store the entire block content as-is
        code_blocks.append((pure_opening, content, pure_closing))

        # The index of this block in code_blocks
        idx = len(code_blocks) - 1

        # Return a placeholder
        return f"@@CODEBLOCK{idx}@@"

    # Replace all code blocks with placeholders
    text_with_placeholders = code_block_regex.sub(replace_code_block, md_text)

    # -------------------------------------------------
    # 1) PERFORM NORMAL MARKDOWN -> SLACK TRANSFORMS
    #    (on text outside code blocks)
    # -------------------------------------------------

    # (a) Convert italic: *text* => _text_
    text_with_placeholders = re.sub(
        r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)',
        r'_\1_',
        text_with_placeholders,
        flags=re.DOTALL
    )

    # (b) Convert headings => Slack bold line; remove ** if present in heading text
    def heading_sub(match):
        heading_text = match.group(2).strip()
        heading_text = re.sub(r'\*\*', '', heading_text)
        return f"*{heading_text}*"

    text_with_placeholders = re.sub(
        r'^(#{1,6})\s+(.*)$',
        heading_sub,
        text_with_placeholders,
        flags=re.MULTILINE
    )

    # (c) Convert bold: **text** => *text*
    text_with_placeholders = re.sub(
        r'\*\*(.+?)\*\*',
        r'*\1*',
        text_with_placeholders,
        flags=re.DOTALL
    )

    # (d) Convert strikethrough: ~~text~~ => ~text~
    text_with_placeholders = re.sub(
        r'~~(.+?)~~',
        r'~\1~',
        text_with_placeholders,
        flags=re.DOTALL
    )

    # (e) Convert links: [title](url) => <url|title>
    text_with_placeholders = re.sub(
        r'\[(.*?)\]\((.*?)\)',
        r'<\2|\1>',
        text_with_placeholders
    )

    # (f) Bulleted lists: lines that start with '-' => bullet (• or ◦).
    def bullet_sub(match):
        leading_spaces = match.group(1) or ""
        text_after_dash = match.group(2)
        tab_count = len(leading_spaces) // 2
        tabs = "\t" * tab_count
        bullet_char = "•" if tab_count == 0 else "◦"
        return f"{tabs}{bullet_char} {text_after_dash}"

    text_with_placeholders = re.sub(
        r'^([ ]*)- (.*)',
        bullet_sub,
        text_with_placeholders,
        flags=re.MULTILINE
    )

    # -------------------------------------------------
    # 2) REINSERT CODE BLOCKS (unchanged except no language spec)
    # -------------------------------------------------
    def restore_code_block(match):
        # match.group(1) = index from @@CODEBLOCK(\d+)@@
        idx = int(match.group(1))
        opening, content, closing = code_blocks[idx]
        # Rebuild the code block in Slack style, e.g. ```\n content \n```
        return f"{opening}\n{content}{closing}"

    # Regex to find placeholders like @@CODEBLOCK42@@
    placeholder_regex = re.compile(r'@@CODEBLOCK(\d+)@@')
    final_text = placeholder_regex.sub(restore_code_block, text_with_placeholders)

    return final_text
