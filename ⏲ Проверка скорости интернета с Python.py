import speedtest
st = speedtest.Speedtest()

download_mbps = st.download() / 1_000_000  # Мбит/с
upload_mbps = st.upload() / 1_000_000      # Мбит/с
ping_ms = st.results.ping

print("Загрузка:", round(download_mbps, 2), "Мбит/с")
print("Выгрузка:", round(upload_mbps, 2), "Мбит/с")
print("Пинг:", ping_ms, "мс")

# Переводим мегабиты в гигабайты за час
# (скорость в Мбит/с) * 3600 секунд / 8 (бит в байте) / 1024 (МБ в ГБ)
download_gb_per_hour = (download_mbps * 3600) / 8 / 1024
upload_gb_per_hour = (upload_mbps * 3600) / 8 / 1024

print("За час можно загрузить примерно:", round(download_gb_per_hour, 2), "ГБ")
print("За час можно выгрузить примерно:", round(upload_gb_per_hour, 2), "ГБ")
