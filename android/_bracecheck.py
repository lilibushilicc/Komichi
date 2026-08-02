import re, glob

kt_files = [
    "app/src/main/java/com/komichi/ui/theme/Palette.kt",
    "app/src/main/java/com/komichi/ui/theme/Theme.kt",
    "app/src/main/java/com/komichi/ui/theme/Color.kt",
    "app/src/main/java/com/komichi/viewmodel/ThemeViewModel.kt",
    "app/src/main/java/com/komichi/MainActivity.kt",
    "app/src/main/java/com/komichi/ui/screens/settings/SettingsScreen.kt",
    "app/src/main/java/com/komichi/data/StoreManager.kt",
]

def strip(s):
    s = re.sub(r'//[^\n]*', '', s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    out = []
    i, n, in_str = 0, len(s), None
    while i < n:
        c = s[i]
        if in_str:
            out.append(' ')
            if c == '\\':
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c == '"' or c == "'":
            in_str = c
            out.append(' ')
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)

print("== Kotlin 大括号配平 ==")
for f in kt_files:
    s = strip(open(f, encoding='utf-8').read())
    o = s.count('{')
    c = s.count('}')
    print(("OK  " if o == c else "WARN"), f, "open=%d close=%d" % (o, c))
