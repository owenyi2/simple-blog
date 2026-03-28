#!/usr/bin/env bash
set -e

# 1️⃣ Preprocess Markdown
echo "Preprocessing Markdown..."
python3 build/preprocess.py

# 2️⃣ Create output folder
mkdir -p site

# 3️⃣ Convert all preprocessed Markdown files to HTML
echo "Converting Markdown to HTML..."
find build/md_ready -name "*.md" -print0 | while IFS= read -r -d '' f; do
    out_file="site/${f#build/md_ready/}"
    out_file="${out_file%.md}.html"
    mkdir -p "$(dirname "$out_file")"
    pandoc "$f" -o "$out_file" \
        -f markdown-blank_before_header+autolink_bare_uris \
        --standalone \
        --highlight-style=breezeDark \
        --include-in-header=styles \
        --mathjax
done

# 4️⃣ Copy Attachments/Assets
echo "Copying attachments..."
if [ -d "simple_blog/Attachments" ]; then
    mkdir -p site/Attachments
    cp -r simple_blog/Attachments/* site/Attachments/
fi

echo "✅ Build complete! HTML site is in ./site"

