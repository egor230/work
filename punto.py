import json, os, re, subprocess, threading, time, sys, pyautogui, tkinter as tk
import bisect
from tkinter import Tk, Toplevel, Label, Frame
from pynput import mouse, keyboard
import pyatspi
from gi.repository import GLib

ENTRY_NAMES = ("file_search_entry", "content_search_entry")
SEARCH_LABEL_KEYWORDS = ("поиск файлов", "содержит", "search files", "contains", "поиск", "search", "find")
DEBOUNCE_MS = 500  # Уменьшили с 1500 мс для более отзывчивого поиска в Nemo
COOLDOWN_SEC = 0.3  # Уменьшили с 1.0 сек для быстрой реакции

class ToolTip: # Класс для отображения подсказок
    def __init__(self, widget, text):
        self.widget = widget
        self.tipwindow = None
        self.text = text
        self._showtip() # Показываем подсказку при инициализации

    def _showtip(self): # Создает окно подсказки
        if self.tipwindow or not self.text:
            return
        self.tipwindow = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(True) # Убираем рамку окна
        tw.wm_geometry("+0+0")
        label = Label(tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))
        label.pack(ipadx=1)

    def updatetext(self, text): # Обновляет текст подсказки
        self.text = text
        if self.tipwindow:
            for child in self.tipwindow.winfo_children():
                child.destroy()
            label = Label(self.tipwindow, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("tahoma", "12", "normal"))
            label.pack(ipadx=1)

    def hidetip(self): # Скрывает подсказку
        if self.tipwindow:
            try:
                self.tipwindow.destroy()
            except tk.TclError:
                pass
            self.tipwindow = None

class SmartTyper: # Основной класс для автозамены и подсказок
    def __init__(self, abbreviations_path, words_path):
        self.abbreviations_path = abbreviations_path
        self.words_path = words_path
        self.abbreviations = {}
        self.normalized_abbrevs = {}
        self.sorted_abbrevs = []
        self.longest_abbreviation_length = 0
        self.word_text_data = ""
        self.suggestion_cache = {}
        self.words_by_first = {}
        self.words_alpha_by_first = {}
        self.max_suggestions = 6

        self.ru_to_en_layout = { # Словарь для транслитерации с русской раскладки на английскую
            'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
            'х': '[', 'ъ': ']', 'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k',
            'д': 'l', 'ж': ';', 'э': "'", 'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
            'б': ',', 'ю': '.', '.': '/', 'ё': '`', 'Й': 'Q', 'Ц': 'W', 'У': 'E', 'К': 'R', 'Е': 'T', 'Н': 'Y', 'Г': 'U', 'Ш': 'I', 'Щ': 'O', 'З': 'P',
            'Х': '{', 'Ъ': '}', 'Ф': 'A', 'Ы': 'S', 'В': 'D', 'А': 'F', 'П': 'G', 'Р': 'H', 'О': 'J', 'Л': 'K', 'Д': 'L', 'Ж': ':', 'Э': '"', 'Я': 'Z', 'Ч': 'X', 'С': 'C', 'М': 'V', 'И': 'B', 'Т': 'N', 'Ь': 'M', 'Б': '<', 'Ю': '>', ',': '?', 'Ё': '~'
        }
        self.en_to_ru_layout = { # Словарь для транслитерации с английской раскладки на русскую
            'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з',
            'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д',
            'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', '[': 'х', ']': 'ъ', ';': 'ж', "'": 'э', ',': 'б', '.': 'ю', '`': 'ё',
            'Q': 'Й', 'W': 'Ц', 'E': 'У', 'R': 'К', 'T': 'Е', 'Y': 'Н', 'U': 'Г', 'I': 'Ш', 'O': 'Щ', 'P': 'З',
            'A': 'Ф', 'S': 'Ы', 'D': 'В', 'F': 'А', 'G': 'П', 'H': 'Р', 'J': 'О', 'K': 'Л', 'L': 'Д', 'Z': 'Я', 'X': 'Ч', 'C': 'С', 'V': 'М', 'B': 'И', 'N': 'Т', 'M': 'Ь'
        }

        # Состояние ATSPI для каждого окна Nemo: key = id(frame), value = [timer_id, last_text, cooldown_until]
        self.nemo_states = {}
        self._load_data() # Загружаем данные из файлов
        self.current_word = ""
        self.matched_abbrev_key = ""
        self.suggestions = []
        self.abbrev_res = ""
        self.tooltip = None
        self.tooltip_root = None
        self.last_key_press_time = time.time()
        self.user = self._get_current_user() # Получаем текущего пользователя
        self.disabled = False
        self.replacing = False
        self._setup_ui() # Настраиваем интерфейс
        # Блокировка для защиты общих переменных от race conditions при быстром вводе
        self.state_lock = threading.Lock()

    def _load_data(self): # Загружает данные из файлов аббревиатур и словаря
        if os.path.exists(self.abbreviations_path):
            with open(self.abbreviations_path, 'r', encoding='utf-8') as json_file:
                self.abbreviations = json.load(json_file)
            if self.abbreviations:
                for k, v in self.abbreviations.items():
                    self.normalized_abbrevs[k] = v
                self.longest_abbreviation_length = len(max(self.normalized_abbrevs.keys(), key=len))
                self.sorted_abbrevs = sorted(self.normalized_abbrevs.keys(), key=len, reverse=True)

        if os.path.exists(self.words_path):
            with open(self.words_path, 'r', encoding="cp1251", errors='ignore') as f:
                self.word_text_data = f.read()
        self._build_word_index()

    def _build_word_index(self): # Строит индекс слов для быстрого поиска подсказок
        self.words_by_first = {}
        self.words_alpha_by_first = {}
        self.suggestion_cache = {}
        if not self.word_text_data:
            return
        words = re.findall(r'[а-яёА-ЯЁ]+', self.word_text_data)
        unique_words = {}
        for w in words:
            lw = w.lower()
            if lw and lw not in unique_words:
                unique_words[lw] = w
        for lw, w in unique_words.items():
            first = lw[0]
            if first not in self.words_by_first:
                self.words_by_first[first] = []
                self.words_alpha_by_first[first] = []
            self.words_by_first[first].append((len(lw), lw, w))
            self.words_alpha_by_first[first].append((lw, w))
        for first in self.words_by_first:
            self.words_by_first[first].sort()
            self.words_alpha_by_first[first].sort()

    def _get_current_user(self): # Получает имя текущего пользователя
        script = '#!/bin/bash\necho $(whoami)\nexit;'
        return subprocess.run(['bash'], input=script, stdout=subprocess.PIPE, text=True).stdout.strip()

    def _setup_ui(self): # Настраивает интерфейс для подсказок
        self.root = Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.resizable(1, 1)
        self.root.withdraw()
        frame = Frame(self.root, borderwidth=0)
        frame.pack(fill=tk.X)
        self.suggestion_labels = [Label(frame, text="", font='Times 14') for _ in range(6)]
        for label in self.suggestion_labels:
            label.pack(side=tk.LEFT, padx=3, fill=tk.X, expand=False)

    def _get_current_keyboard_layout(self):
        try:
            result = subprocess.run("xset -q | grep 'LED mask' | awk '{print $10}'", shell=True, capture_output=True, text=True)
            led_mask = result.stdout.strip()
            if led_mask == "00001002":
                return "us"
            else:
                return "ru"
        except Exception:
            return "ru"

    def _get_translated_key(self, key_char): # Возвращает транслитерированный символ
        ch = key_char.lower()
        layout = self._get_current_keyboard_layout()
        if layout == "ru":
            return ch
        else:
            return self.ru_to_en_layout.get(ch, ch)

    def clean(self):
        # Сбрасываем состояние сразу (thread-safe)
        self.current_word = ""
        self.matched_abbrev_key = ""
        self.suggestions = []
        # UI-очистку делегируем в GLib главный поток (исправляет RuntimeError)
        GLib.idle_add(self._do_hide_all)

    def _type_text_and_finish(self, text): # Печатает текст и сбрасывает флаг replacing
        try:
            for char in text:
                time.sleep(0.18)
                if char == ' ':
                    pyautogui.press('space')
                else:
                    subprocess.call(['xdotool', 'type', '--delay', '9', char])
        finally:
            self.replacing = False

    def _replace_word_async(self, new_word, extra_backspace=1): # Асинхронно заменяет слово
        if self.replacing:
            return
        self.replacing = True
        backspace_count = len(self.current_word) + extra_backspace
        for _ in range(backspace_count):
            subprocess.run(['xdotool', 'key', 'BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.21)
        t = threading.Thread(target=self._type_text_and_finish, args=(new_word,))
        t.start()
        self.clean()
        t.join()
        self.replacing = False

    def _do_replace_abbrev_async(self): # Асинхронно заменяет аббревиатуру
        if self.replacing or not self.abbrev_res:
            return
        self.replacing = True
        t = threading.Thread(target=self._type_text_and_finish, args=(self.abbrev_res,))
        backspace_count = len(self.current_word)+1
        for _ in range(backspace_count):
            subprocess.run(['xdotool', 'key', 'BackSpace'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.31)
        self.clean()
        t.start()
        t.join()
        self.replacing = False

    # --- ATSPI Nemo Live Search ---
    def _panel_has_search_label(self, node): # Проверяет, есть ли среди прямых детей label'а подписи поиска
        try:
            for i in range(node.getChildCount()):
                try:
                    child = node.getChildAtIndex(i)
                    if child.getRole() == pyatspi.ROLE_LABEL:
                        text = (child.name or "")
                        try:
                            q = child.queryText()
                            if q:
                                text += " " + (q.getText(0, -1) or "")
                        except Exception:
                            pass
                        low = text.lower()
                        if any(k in low for k in SEARCH_LABEL_KEYWORDS):
                            return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def _is_nemo_search_entry(self, obj): # Надёжная идентификация поля поиска Nemo (имя может быть пустым)
        name = obj.name or ""
        if name in ENTRY_NAMES:
            return True
        cur = obj
        while cur:
            try:
                role = cur.getRole()
                if role in (pyatspi.ROLE_FRAME, pyatspi.ROLE_WINDOW, pyatspi.ROLE_DIALOG):
                    break
                if role in (pyatspi.ROLE_TABLE, pyatspi.ROLE_TREE_TABLE, pyatspi.ROLE_ICON):
                    # Поле внутри списка файлов — это переименование (F2), не поиск
                    return False
            except Exception:
                pass
            if self._panel_has_search_label(cur):
                return True
            try:
                cur = cur.parent
            except Exception:
                break
        return False

    def on_text_changed(self, event): # Обработчик ATSPI-события text-changed: ловит ввод в поисковое поле Nemo
        obj = event.source
        if not obj:
            return

        # Проверяем, что это поле ввода в Nemo
        try:
            app = obj.getApplication()
            if not app or (app.name or "").lower() != "nemo":
                return
            if obj.getRole() != pyatspi.ROLE_TEXT:
                return

            if not self._is_nemo_search_entry(obj):
                return

            # Находим окно (frame) для per-window состояния
            frame = None
            cur = obj
            while cur:
                try:
                    if cur.getRole() in (pyatspi.ROLE_FRAME, pyatspi.ROLE_DIALOG, pyatspi.ROLE_WINDOW):
                        frame = cur
                        break
                except:
                    pass
                cur = cur.parent

            if not frame:
                return

            key = id(frame)

            # Отменяем предыдущий таймер для этого окна
            if key in self.nemo_states and self.nemo_states[key][0]:
                GLib.source_remove(self.nemo_states[key][0])

            # Функция, которая выполнится после паузы (debounce)
            def fire():
                try:
                    if not obj:
                        return

                    # Проверяем, что объект всё ещё в фокусе и видим
                    state = obj.getState()
                    if not state.contains(pyatspi.STATE_FOCUSED):
                        return
                    if not state.contains(pyatspi.STATE_VISIBLE):
                        return

                    # Проверяем, что активное окно всё ещё принадлежит Nemo
                    try:
                        app_pid = app.get_process_id()
                    except Exception:
                        app_pid = None
                    if app_pid is not None:
                        active_win_id = subprocess.run(['xdotool', 'getactivewindow'], capture_output=True, text=True).stdout.strip()
                        if active_win_id:
                            pid = subprocess.run(['xdotool', 'getwindowpid', active_win_id], capture_output=True, text=True).stdout.strip()
                            if pid and pid != str(app_pid):
                                return

                    text = obj.queryText().getText(0, -1) or ""
                    if not text.strip():
                        return

                    # Проверяем cooldown и повтор текста
                    now = time.time()
                    if now < self.nemo_states.get(key, [None, "", 0.0])[2]:
                        return
                    last = self.nemo_states.get(key, [None, "", 0.0])[1]
                    if text == last:
                        return

                    self.replacing = True
                    # Обновляем состояние
                    self.nemo_states[key] = [None, text, now + COOLDOWN_SEC]

                    # Эмулируем Enter
                    subprocess.run('xte "keydown Return" "keyup Return"', shell=True, check=False)
                    time.sleep(0.1) # Ждём, чтобы эмулированный Enter успел дойти до _on_press
                    self.replacing = False
                except Exception as e:
                    print(f"Ошибка в fire: {e}")
                    self.replacing = False
                finally:
                    # Сбрасываем timer_id в состоянии
                    if key in self.nemo_states:
                        self.nemo_states[key][0] = None

            timer_id = GLib.timeout_add(DEBOUNCE_MS, fire)

            # Сохраняем состояние: [timer_id, last_text, cooldown_until]
            if key in self.nemo_states:
                self.nemo_states[key][0] = timer_id
            else:
                self.nemo_states[key] = [timer_id, "", 0.0]

        except Exception as e:
            print(f"Ошибка в on_text_changed: {e}")

    def _find_word_suggestions(self, prefix): # Ищет подсказки для введенного префикса
        if not prefix:
            return []
        prefix_lower = prefix.lower()
        if not prefix_lower:
            return []

        if prefix[:1].isupper():
            cache_key = prefix_lower + "|cap"
        else:
            cache_key = prefix_lower + "|low"

        if cache_key in self.suggestion_cache:
            return self.suggestion_cache[cache_key]
        if len(self.suggestion_cache) > 1000:
            self.suggestion_cache.clear()

        first = prefix_lower[0]
        alpha = self.words_alpha_by_first.get(first, [])
        if not alpha:
            self.suggestion_cache[cache_key] = []
            return []

        lo = bisect.bisect_left(alpha, (prefix_lower,))
        hi = bisect.bisect_left(alpha, (prefix_lower + chr(0x10ffff),))
        if lo >= hi:
            self.suggestion_cache[cache_key] = []
            return []

        res = []
        seen = set()
        need_cap = prefix[:1].isupper()
        count = hi - lo

        if count <= 5000:
            temp = []
            for lw, w in alpha[lo:hi]:
                if len(lw) > len(prefix_lower):
                    temp.append((len(lw), lw, w))
            temp.sort()
            for _len, lw, w in temp:
                out = w.capitalize() if need_cap else w.lower()
                if out not in seen:
                    seen.add(out)
                    res.append(out)
                    if len(res) >= self.max_suggestions:
                        break
        else:
            for _len, lw, w in self.words_by_first.get(first, []):
                if lw.startswith(prefix_lower) and len(lw) > len(prefix_lower):
                    out = w.capitalize() if need_cap else w.lower()
                    if out not in seen:
                        seen.add(out)
                        res.append(out)
                        if len(res) >= self.max_suggestions:
                            break

        self.suggestion_cache[cache_key] = res
        return res

    def _update_suggestions_ui(self): # Обновляет интерфейс подсказок
        if self.tooltip and self.abbrev_res:
            self.tooltip.updatetext(self.abbrev_res)
        if not self.suggestions:
         self.root.withdraw()
         return
        for label in self.suggestion_labels:
            label.config(text="")

        total_width = 60
        for i, word in enumerate(self.suggestions[:self.max_suggestions]):
            display_text = f"{word}"
            self.suggestion_labels[i].config(text=display_text)
            total_width += len(display_text) * 12

        self.root.geometry(f"{total_width}x25+700+1010")
        self.root.deiconify()

    def _hide_suggestions(self): # Скрывает подсказки
        self.suggestions = []
        self.matched_abbrev_key = ""
        try:
            self.root.withdraw()
        except tk.TclError:
            pass

    def _show_abbrev_tooltip(self): # Показывает подсказку для аббревиатуры
        if self.tooltip and self.tooltip_root and self.tooltip.tipwindow:
            self.tooltip.updatetext(self.abbrev_res)
            return
        try:
            if self.tooltip_root:
                try:
                    self.tooltip_root.destroy()
                except tk.TclError:
                    pass
        except tk.TclError:
            pass

        self.tooltip_root = Toplevel(self.root)
        self.tooltip_root.withdraw()
        self.tooltip = ToolTip(self.tooltip_root, self.abbrev_res)

    def hide_abbrev_tooltip(self): # Скрывает подсказку для аббревиатуры
        if self.tooltip:
            try:
                self.tooltip.hidetip()
            except tk.TclError:
                pass
            self.tooltip = None
        if self.tooltip_root:
            try:
                self.tooltip_root.destroy()
            except tk.TclError:
                pass
            self.tooltip_root = None

    def _do_update_state(self): # Обновляет состояние подсказок
        if self.replacing:
            return
        match = self.check_for_abbreviation()
        if match:
            self.abbrev_res = match
            self._show_abbrev_tooltip()
        else:
            self.abbrev_res = ""
            self.hide_abbrev_tooltip()

        self.suggestions = self._find_word_suggestions(self.current_word)
        if self.suggestions:
            self._update_suggestions_ui()
        else:
            for label in self.suggestion_labels:
                label.config(text="")
            try:
                self.root.withdraw()
            except tk.TclError:
                pass

    def _do_hide_all(self): # Скрывает все подсказки
        self._hide_suggestions()
        self.hide_abbrev_tooltip()
        self.abbrev_res = ""

    def check_for_abbreviation(self): # Проверяет, совпадает ли ввод с аббревиатурой
        self.matched_abbrev_key = None
        if not self.current_word:
            return None
        if self.longest_abbreviation_length and len(self.current_word) > self.longest_abbreviation_length:
            return None

        abbre = ""
        for key_char in self.current_word:
            trans_key = self._get_translated_key(key_char)
            abbre += trans_key

        for abbrev_key in self.sorted_abbrevs:
            if len(self.current_word) == len(abbrev_key) and abbrev_key == abbre:
                self.matched_abbrev_key = abbrev_key
                return self.normalized_abbrevs[abbrev_key]
        return None

    def _check_active_window_loop(self): # Проверяет активное окно в цикле
        get_main_id = '''#!/bin/bash
active_window_id=$(xdotool getactivewindow 2>/dev/null)
if [ -n "$active_window_id" ]; then
    process_id_active=$(xdotool getwindowpid "$active_window_id" 2>/dev/null)
    echo "$process_id_active"
else
    echo "0"
fi
exit'''
        while True:
            try:
                found = False
                time.sleep(1)
                process_id = int(subprocess.run(['bash'], input=get_main_id, stdout=subprocess.PIPE, text=True).stdout.strip())
                result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE, text=True).stdout
                lines = [line for line in result.splitlines() if self.user in line]
                pattern = r"(\.exe|\.EXE)"
                for line in lines:
                    dir_process_name = line.split(maxsplit=10)[10].replace('\\', '/')
                    if re.search(pattern, dir_process_name) and process_id == int(line.split()[1]):
                        file_path_lower = dir_process_name.lower()
                        if (".exe" in file_path_lower or '/portproton/data/scripts/start.sh' in file_path_lower) and "winword.exe" not in file_path_lower:
                            self.disabled = True
                            self.current_word = ""
                            self.suggestions = []
                            self.abbrev_res = ""
                            GLib.idle_add(self._do_hide_all)
                            found = True
                            break
                if not found:
                    self.disabled = False
            except Exception as e:
                print(e)
                self.disabled = False
                pass

    def _on_press(self, key): # Обрабатывает нажатия клавиш
        if self.replacing:
            return True
        if self.disabled:
            return True

        key_str = str(key).replace("'", "").replace(" ", "")

        if any(k in key_str for k in ["down", "right", "up", "left", "Key.tab", "Key.caps_lock", "Key.shift", "<65032>", "<65512>", "Key.ctrl_r"]):
            self.clean()
            return True

        if key_str == "<65437>":
            key_str = "5"

        if time.time() - self.last_key_press_time < 0.005:
            self.last_key_press_time = time.time()
            return True

        self.last_key_press_time = time.time()

        if key == keyboard.Key.backspace:
            if self.current_word:
                self.current_word = self.current_word[:-1]
                GLib.idle_add(self._do_update_state)
            else:
                GLib.idle_add(self._do_hide_all)
            return True

        if key == keyboard.Key.space:
            if self.abbrev_res:
                self._do_replace_abbrev_async()
            self.clean()
            return True

        if key == keyboard.Key.enter:
            if self.abbrev_res:
                self._do_replace_abbrev_async()
            else:
                self.clean()
            return True

        control_keys = {
            keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt_l, keyboard.Key.alt_r,
            keyboard.Key.shift, keyboard.Key.shift_r, keyboard.Key.tab, keyboard.Key.caps_lock,
            keyboard.Key.left, keyboard.Key.right, keyboard.Key.up, keyboard.Key.down,
            keyboard.Key.home, keyboard.Key.end, keyboard.Key.delete, keyboard.Key.esc,
            keyboard.Key.cmd, keyboard.Key.num_lock, keyboard.Key.page_up, keyboard.Key.page_down,
            keyboard.Key.insert, keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
            keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8, keyboard.Key.f9,
            keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12
        }

        if key in control_keys or key_str in {'.', ',', '\\', '/', "'", '"', '<', '>', '?', '~', ':', ';', '{', '}', '[', ']', '0'}:
            GLib.idle_add(self._do_hide_all)
            self._do_replace_abbrev_async()
            self.abbrev_res = ""
            return True

        if self.suggestions and key_str in "123456":
            index = int(key_str) - 1
            if index < len(self.suggestions):
                self._replace_word_async(self.suggestions[index], extra_backspace=1)
                return False # "Съедаем" нажатие цифры, чтобы она не напечаталась в текст
            return True

        if hasattr(key, 'char') and key.char and key.char.isprintable() and key_str not in {"+", "-", "*", "/"}:
            key_char = key.char
            self.current_word += key_char
            GLib.idle_add(self._do_update_state)
            return True

        return True

    def _on_click(self, x, y, button, pressed): # Обрабатывает клики мыши
        if pressed:
            self.clean()
        return True

    def start(self): # Запускает основной цикл приложения
        # --- Регистрируем ATSPI-слушатель для Nemo Live Search ---
        pyatspi.Registry.registerEventListener(self.on_text_changed, "object:text-changed")

        # --- Прокачка tkinter для обновления UI подсказок из GLib mainloop ---
        def _pump_tkinter():
            try:
                self.root.update_idletasks()
            except tk.TclError:
                return False
            return True

        GLib.timeout_add(50, _pump_tkinter)

        # --- Фоновые потоки ---
        window_checker_thread = threading.Thread(target=self._check_active_window_loop, daemon=True)
        window_checker_thread.start()

        keyboard_listener = keyboard.Listener(on_press=self._on_press)
        mouse_listener = mouse.Listener(on_click=self._on_click)
        keyboard_listener.start()
        mouse_listener.start()

        # --- GLib mainloop вместо tkinter mainloop ---
        pyatspi.Registry.start()

        keyboard_listener.stop()
        mouse_listener.stop()
        keyboard_listener.join()
        mouse_listener.join()

if __name__ == "__main__":
    abbreviations_file = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/dictionary of substitutions.json"
    words_file = "/mnt/807EB5FA7EB5E954/soft/Virtual_machine/linux must have/python_linux/work/words.txt"

    if not os.path.exists(abbreviations_file):
        print(f"Ошибка: Файл аббревиатур не найден по пути: {abbreviations_file}")
        sys.exit(1)
    if not os.path.exists(words_file):
        print(f"Ошибка: Файл со словарем не найден по пути: {words_file}")
        sys.exit(1)

    app = SmartTyper(abbreviations_path=abbreviations_file, words_path=words_file)
    app.start()
