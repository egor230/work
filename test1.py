import subprocess
import re

result = subprocess.run(['setxkbmap', '-query'], capture_output=True, text=True)
if result.returncode == 0:
  match = re.search(r'layout:\s*(\w+(?:,\w+)*)', result.stdout)
  if match:
    layouts = match.group(1).split(',')
    # Если только одна раскладка, она и текущая
    if len(layouts) == 1:
      current = layouts[0]
      print(current)
    else:
      # Здесь хак: если несколько, setxkbmap не говорит, какая активна.
      # Для простоты берём первую (us), но см. ниже, как улучшить
      current = layouts[0]

    if current == 'us':
      print("en")
    elif current == 'ru':
      print("ru")
    else:
      print(f"Unknown: {current}")
  else:
    print("No layout found")
else:
  print("Error running setxkbmap")
