from PIL import Image

def resize_image(input_path, output_path, size):
    image = Image.open(input_path)
    resized_image = image.resize((size, size), Image.LANCZOS)
    resized_image.save(output_path)

file = "WolfSP_x"
input_image_path = "1.png"


# Создаем изображение размером 256x256
output_256_path = file + "256.png"
resize_image(input_image_path, output_256_path, 256)

# Создаем изображение размером 64x64
output_64_path = file + "96.png"
resize_image(input_image_path, output_64_path, 64)