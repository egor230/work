gnome-terminal -- bash -c "\
cd /mnt/807EB5FA7EB5E954/софт/виртуальная\ машина/linux\ must\ have/python_linux/Project; \
pdf_path='/mnt/807EB5FA7EB5E954/развития/книги/Трамп никогда не сдается.pdf'; \
output_name='outputname'; \
total_pages=\$(pdftoppm -list-pages \"\$pdf_path\" | wc -l); \
for page in \$(seq 1 \$total_pages); do \
    pdftoppm -f \$page -l \$page -png \"\$pdf_path\" \"\$output_name-\$page\"; \
    tesseract \"\$output_name-\$page.png\" \"\$output_name-\$page\" -l eng; \
    echo \$((page * 100 / total_pages)); \
done | zenity --progress --title='Конвертирование PDF' --text='Преобразование страниц...' --percentage=0 --auto-close; \
cat \"\$output_name\"-*.txt > Trump_never_give_up.txt; \
exec bash"
