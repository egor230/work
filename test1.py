import subprocess
import re

import subprocess
import re

# Получаем текущую группу (0 = первая раскладка, 1 = вторая и т.д.)
result = subprocess.run(['xset', '-q'], capture_output=True, text=True)
print(result)

