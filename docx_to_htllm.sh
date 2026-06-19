#!/bin/bash
SOURCE_DIR=$(pwd)
OUTPUT_BASE="${OUTPUT_BASE:-$SOURCE_DIR}"
OUTPUT_DIR="$OUTPUT_BASE/html_output"

mkdir -p "$OUTPUT_DIR"
chmod 755 "$OUTPUT_DIR"

FINAL_HTML="$OUTPUT_DIR/combined_all.html"
echo "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Combined Documents</title><style>body { font-family: sans-serif; margin: 20px; } .document-section { margin-bottom: 50px; border-bottom: 2px dashed #ccc; padding-bottom: 20px; }</style></head><body>" > "$FINAL_HTML"

count=0
shopt -s nullglob nocaseglob

for DOC_FILE in "$SOURCE_DIR"/*.doc; do
  if [ -f "$DOC_FILE" ]; then
    filename=$(basename "$DOC_FILE")
    name_no_ext="${filename%.*}"
    echo "Обрабатываю: $filename ..."
    
    libreoffice --headless --convert-to html:HTML --outdir "$OUTPUT_DIR" "$DOC_FILE"
    
    if [ $? -eq 0 ]; then
      html_file="$OUTPUT_DIR/${name_no_ext}.html"
      img_dir=""
      for d in "$OUTPUT_DIR/${name_no_ext}"_html_*; do
        if [ -d "$d" ]; then
          img_dir="$d"
          break
        fi
      done
      
      if [ -f "$html_file" ]; then
        python3 << EOF
import re, os, base64

html_file = "$html_file"
img_dir = "$img_dir"
final_html = "$FINAL_HTML"
doc_name = "$name_no_ext"

with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
  content = f.read()

pattern = r'(<img\s+[^>]*src=["\'])([^"\']+)(["\'])'
def repl(m):
  src = m.group(2)
  if img_dir and (img_dir in src or os.path.basename(img_dir) in src):
    img_path = os.path.join(img_dir, os.path.basename(src))
    if os.path.exists(img_path):
      with open(img_path, 'rb') as imf:
        b64 = base64.b64encode(imf.read()).decode()
        ext = os.path.splitext(img_path)[1].lower()
        mime = 'image/png' if ext=='.png' else 'image/jpeg' if ext in ('.jpg','.jpeg') else 'image/gif'
        return f'{m.group(1)}data:{mime};base64,{b64}{m.group(3)}'
  return m.group(0)

processed_content = re.sub(pattern, repl, content)

body_match = re.search(r'<body[^>]*>(.*?)</body>', processed_content, re.DOTALL | re.IGNORECASE)
if body_match:
  body_inside = body_match.group(1)
else:
  body_inside = processed_content

with open(final_html, 'a', encoding='utf-8') as f:
  f.write(f'<div class="document-section"><h2>{doc_name}</h2>\n')
  f.write(body_inside)
  f.write('\n</div>\n')

if img_dir and os.path.exists(img_dir):
  import shutil
  shutil.rmtree(img_dir)

if os.path.exists(html_file):
  os.remove(html_file)
EOF
        if [ $? -eq 0 ]; then
          echo "✅ Добавлено: $filename (картинки встроены)"
          ((count++))
        else
          echo "⚠️ Ошибка обработки скриптом Python для файла $filename"
        fi
      else
        echo "⚠️ Не найден HTML файл после конвертации: $filename"
      fi
    else
      echo "❌ Ошибка конвертации: $filename"
    fi
  fi
done

echo "</body></html>" >> "$FINAL_HTML"
chmod 755 "$FINAL_HTML"

shopt -u nullglob nocaseglob
echo "Готово! Все документы объединены в: $FINAL_HTML"
echo "Обработано файлов: $count"