image_url=$(copyq read 0)    # Получаем URL изображения из буфера обмена
path_new="/home/egor/Downloads/new_image.png"
cp -f "$image_url" "$path_new"
while true; do
 sleep 1
 if [ -f "$path_new" ]; then  
  break 
 fi
done
echo "$image_url" 
echo "$path_new"
image_url="$path_new"
xclip -selection clipboard -t image/png -i "$image_url" 
read
exit;