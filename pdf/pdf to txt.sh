gnome-terminal -- bash -c "\
cd /mnt/807EB5FA7EB5E954/софт/виртуальная\ машина/linux\ must\ have/python_linux/Project/pdf;
pdf_path='Трамп никогда не сдается.pdf'; \
pdf_path='Трамп никогда не сдается.pdf'; \
pdf_name=\$(basename \"\$pdf_path\" .pdf); \
output_name=\"\$pdf_name\"-page; \

# Конвертируйте PDF в серию изображений (одно изображение на страницу)
pdftoppm \"\$pdf_path\" \"\$output_name\" -png

# Примените Tesseract OCR к каждому изображению, чтобы получить текст
for file in \$output_name-*.png; do
    tesseract \"\$file\" \"\${file%.*}\"
done

# Объедините все текстовые файлы в один файл txt
cat \$output_name-*.txt > \"\$pdf_name\".txt

# Удалите все временные PNG-файлы
rm \$output_name-*.png

# Удалите все временные текстовые файлы
rm \$output_name-*.txt
exec bash"
