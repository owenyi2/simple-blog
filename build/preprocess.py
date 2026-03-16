import re
from pathlib import Path
import shutil

VAULT_DIR = Path("simple_blog")
OUTPUT_MD_DIR = Path("build/md_ready")

# PREPROCESSING FUNCTIONS

def replace_wiki_links(text: str) -> str:
    """
    Convert Obsidian-style wiki links [[note]] to Markdown links [note](note.html).
    """
    link_pattern = re.compile(r"\[\[([^\]]+)\]\]")
    return link_pattern.sub(r"[\1](\1.html)", text)

def replace_image_size_syntax(text: str) -> str:
    """
    Convert Obsidian image size syntax ![|291](image) to Pandoc attribute syntax ![](image){ width=291px }
    """
    image_size_pattern = re.compile(r"!\[\|(\d+)\]\(([^)]+)\)")
    def repl(match):
        size = match.group(1)
        url = match.group(2)
        return f"![]({url}){{ width={size}px }}"
    return image_size_pattern.sub(repl, text)

def ensure_images_on_newline(text: str) -> str:
    """
    Ensure images have a blank line before and after, so Pandoc treats them as block.
    """
    lines = text.splitlines()
    new_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("![]") or re.match(r"!\[\|\d+\]", stripped):
            # Add blank line before if previous line is not blank
            if new_lines and new_lines[-1].strip() != "":
                new_lines.append("")
            new_lines.append(line)
            # Add blank line after if next line exists and is not blank
            if i + 1 < len(lines) and lines[i+1].strip() != "":
                new_lines.append("")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)

def ensure_blank_line_before_list(text: str) -> str:
    """Ensure a blank line exists before a list (-, *, +) if not already present."""
    lines = text.splitlines()
    new_lines = []
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if re.match(r'^[-*+]\s+', stripped):
            # if previous line exists and is not blank, insert a blank line
            if new_lines and new_lines[-1].strip() != "":
                new_lines.append("")
        new_lines.append(line)
    return "\n".join(new_lines)

# ---

def preprocess_markdown_file(md_path: Path, out_path: Path):
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    text = replace_wiki_links(text)
    text = replace_image_size_syntax(text)
    text = ensure_images_on_newline(text)
    text = ensure_blank_line_before_list(text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)

def clean_output_dir():
    if OUTPUT_MD_DIR.exists():
        shutil.rmtree(OUTPUT_MD_DIR)
    OUTPUT_MD_DIR.mkdir(parents=True, exist_ok=True)

def main():
    clean_output_dir()
    for md_file in VAULT_DIR.glob("**/*.md"):
        relative_path = md_file.relative_to(VAULT_DIR)
        out_file = OUTPUT_MD_DIR / relative_path
        preprocess_markdown_file(md_file, out_file)

if __name__ == "__main__":
    main()
