# Список путей
games_checkmark_paths = ['C:/Windows/explorer.exe', '/mnt/807EB5FA7EB5E954/games/Splinter Cell - Chaos Theory/System/SPLINTERCELL3.EXE', '/mnt/807EB5FA7EB5E954/games/Alien Isolation/AI.exe',
  '/mnt/807EB5FA7EB5E954/games/Medal of Honor Allied Assault Breakthrough/MOHAA.EXE', '/mnt/807EB5FA7EB5E954/games/Oblivion Gold/obse_loader.exe',
  '/mnt/807EB5FA7EB5E954/games/Cold Fear/ColdFear_retail.exe', '/mnt/807EB5FA7EB5E954/games/Serious Sam Classic/Bin/SeriousSam_Custom.exe',
  '/mnt/807EB5FA7EB5E954/games/Serious Sam Classics Revolution/Bin/SeriousSam.exe']
# Ключевая подстрока для поиска (убираем лишний пробел)
key_paths = "Oblivion.exe"
key_paths=key_paths[:-4]
key_paths=key_paths[:-4]
print(key_paths)
# Поиск пути, содержащего key_paths (игнорируем регистр)
file_path = next((p for p in games_checkmark_paths if key_paths.lower() in p.lower()), None)

if file_path:
    print(f"Найден путь: {file_path}")
    # Сделать что-нибудь с file_path
else:
    print(f"Путь, содержащий '{key_paths}', не найден")