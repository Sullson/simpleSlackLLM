import re

def markdown_to_slack(md_text: str) -> str:
    """
    Convert a subset of Markdown to Slack-specific formatting.
    
    Conversions:
      - Protect fenced code blocks (```code```) and inline code (`code`) from further processing.
      - Headings:
           * Hash-style headings (e.g. "# Heading" or "## Heading ##") 
             are converted to bold text.
           * Underline-style headings (Setext headings, e.g. "Heading" followed by "===" or "---")
             are also converted to bold text.
      - **Bold** (using either ** or __) => *Bold*
      - *Italic* (using a single asterisk) => _Italic_
      - ~~Strikethrough~~ => ~Strikethrough~
      - [Link Text](url) => <url|Link Text>
      
    Fenced code blocks and inline code remain unchanged.
    """

    # --- Step 1. Protect Code Blocks and Inline Code ---
    # We replace code blocks and inline code with placeholders to ensure that
    # no further formatting is applied within them.
    code_placeholders = {}
    placeholder_prefix = "__CODE_PLACEHOLDER_"
    code_counter = 0

    # Protect fenced code blocks (``` ... ```)
    def replace_fenced(match):
        nonlocal code_counter
        code_block = match.group(0)
        placeholder = f"{placeholder_prefix}{code_counter}__"
        code_placeholders[placeholder] = code_block
        code_counter += 1
        return placeholder

    md_text = re.sub(r'```[\s\S]*?```', replace_fenced, md_text)

    # Protect inline code (`...`)
    def replace_inline(match):
        nonlocal code_counter
        code_span = match.group(0)
        placeholder = f"{placeholder_prefix}{code_counter}__"
        code_placeholders[placeholder] = code_span
        code_counter += 1
        return placeholder

    md_text = re.sub(r'`[^`]+?`', replace_inline, md_text)

    # --- Step 2. Convert Underline-Style Headings (Setext) ---
    # E.g., convert:
    #     Heading
    #     =======
    # into bold text.
    md_text = re.sub(r'(?m)^(?!\s*$)(.*?)\n(=+)\s*$', r'*\1*', md_text)
    md_text = re.sub(r'(?m)^(?!\s*$)(.*?)\n(-+)\s*$', r'*\1*', md_text)

    # --- Step 3. Convert Hash-Style Headings ---
    # This will convert headings like "# Heading" or "### Heading ###" to bold.
    md_text = re.sub(r'(?m)^(#{1,6})\s*(.*?)\s*(?:#+\s*)?$', r'*\2*', md_text)

    # --- Step 4. Convert Bold Text ---
    # Convert both **text** and __text__ to Slack bold (using asterisks).
    md_text = re.sub(r'(\*\*|__)(.+?)\1', r'*\2*', md_text, flags=re.DOTALL)

    # --- Step 5. Convert Italic Text ---
    # Convert single-asterisk italic to Slack italic (using underscores).
    md_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', md_text, flags=re.DOTALL)

    # --- Step 6. Convert Strikethrough ---
    # Convert ~~text~~ to Slack strikethrough (~text~).
    md_text = re.sub(r'~~(.+?)~~', r'~\1~', md_text, flags=re.DOTALL)

    # --- Step 7. Convert Links ---
    # Convert [Link Text](url) to Slack's link format: <url|Link Text>
    md_text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<\2|\1>', md_text)

    # --- Step 8. Restore Protected Code Blocks/Spans ---
    for placeholder, code in code_placeholders.items():
        md_text = md_text.replace(placeholder, code)

    return md_text