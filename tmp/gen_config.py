import os
import re
import shutil

DOWNLOADS_DIR = "tmp/downloads"
WPI_INSTALL_PHYSICAL = os.path.join("tmp", "WPI", "Install")
WPI_INSTALL_PATH = "%wpipath%\\\\Install"

CAT_FOLDER = {
    "Системные": "Системные", "Защита": "Защита", "Медиа": "Медиа",
    "Интернет": "Интернет", "Для игр": "Для игр",
    "Applications": "Applications", "Iso": "Iso",
}

VCREDIST_BAT_CONTENT = """CD /d %~dp0

echo.
echo Microsoft Visual C++ All-In-One Runtimes
echo.
echo Installing runtime packages...

set IS_X64=0 && if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (set IS_X64=1) else (if "%PROCESSOR_ARCHITEW6432%"=="AMD64" (set IS_X64=1))

if "%IS_X64%" == "1" goto X64

echo 2005...
start /wait vcredist2005_x86.exe /q

echo 2008...
start /wait vcredist2008_x86.exe /qb

echo 2010...
start /wait vcredist2010_x86.exe /passive /norestart

echo 2012...
start /wait vcredist2012_x86.exe /passive /norestart

echo 2013...
start /wait vcredist2013_x86.exe /passive /norestart

echo 2015, 2017 ^& 2019...
start /wait VC_redist.x86.exe /passive /norestart

goto END

:X64

echo 2005...
start /wait vcredist2005_x86.exe /q
start /wait vcredist2005_x64.exe /q

echo 2008...
start /wait vcredist2008_x86.exe /qb
start /wait vcredist2008_x64.exe /qb

echo 2010...
start /wait vcredist2010_x86.exe /passive /norestart
start /wait vcredist2010_x64.exe /passive /norestart

echo 2012...
start /wait vcredist2012_x86.exe /passive /norestart
start /wait vcredist2012_x64.exe /passive /norestart

echo 2013...
start /wait vcredist2013_x86.exe /passive /norestart
start /wait vcredist2013_x64.exe /passive /norestart

echo 2015, 2017 ^& 2019 ^& 2022...
start /wait vc_redist.x86.exe /passive /norestart
start /wait vc_redist.x64.exe /passive /norestart

goto END

:END

echo.
echo Installation completed successfully

exit
"""

APP_RULES = {
    "7zip":        {"name": "7-Zip",           "cat": "Системные",    "uid": "7ZIP",      "default": False, "match": r"7z.*"},
    "hwinfo":      {"name": "HWiNFO64",        "cat": "Системные",    "uid": "HWINFO",    "default": True,  "match": r"hwi64.*"},
    "cpu_fix":     {"name": "WuaCpuFix",       "cat": "Системные",    "uid": "CPUFIX",    "default": True,  "match": r"WuaCpuFix.*"},
    "hash_tab":    {"name": "OpenHashTab",     "cat": "Системные",    "uid": "HASHTAB",   "default": True,  "match": r"OpenHashTab.*"},
    "unlocker":    {"name": "Unlocker",        "cat": "Системные",    "uid": "UNLOCKER",  "default": True,  "match": r"Unlocker.*"},
    "vcredist":    {"name": "Visual C++ AIO",  "cat": "Системные",    "uid": "VCREDIST",  "default": True,  "match": r"vc_redist.*|vcredist.*|vc_.*", "folder": "VCRedist"},
    "dotnet":      {"name": ".NET Framework",  "cat": "Системные",    "uid": "DOTNET",    "default": True,  "match": r"ndp.*|NetFramework.*"},
    "directx":     {"name": "DirectX Web",     "cat": "Системные",    "uid": "DIRECTX",   "default": True,  "match": r"dxweb.*|DirectX.*"},
    "unchecky":    {"name": "Unchecky",        "cat": "Защита",       "uid": "UNCHECKY",  "default": False, "match": r"unchecky.*"},
    "vlc":         {"name": "VLC Media Player","cat": "Медиа",        "uid": "VLC",       "default": True,  "match": r"vlc.*"},
    "qpview":      {"name": "QuickPicViewer",  "cat": "Медиа",        "uid": "QPVIEW",    "default": False, "match": r"QuickPictureViewer.*"},
    "qbittorrent": {"name": "qBittorrent",     "cat": "Интернет",     "uid": "QBIT",      "default": True,  "match": r"qbittorrent.*"},
    "motrix":      {"name": "Motrix",          "cat": "Интернет",     "uid": "MOTRIX",    "default": False, "match": r"Motrix.*"},
    "firefox":     {"name": "Firefox",         "cat": "Интернет",     "uid": "FIREFOX",   "default": True,  "match": r"Firefox.*"},
    "openvpn":     {"name": "OpenVPN",         "cat": "Интернет",     "uid": "OPENVPN",   "default": False, "match": r"openvpn.*"},
    "localsend":   {"name": "LocalSend",       "cat": "Интернет",     "uid": "LOCALSEND", "default": False, "match": r"LocalSend.*"},
    "rustdesk":    {"name": "RustDesk",        "cat": "Интернет",     "uid": "RUSTDESK",  "default": True,  "match": r"rustdesk.*"},
    "steam":       {"name": "Steam",           "cat": "Для игр",      "uid": "STEAM",     "default": False, "match": r"SteamSetup.*"},
    "epic":        {"name": "Epic Games",      "cat": "Для игр",      "uid": "EPIC",      "default": False, "match": r"EpicInstaller.*"},
    "fraps":       {"name": "Fraps",           "cat": "Для игр",      "uid": "FRAPS",     "default": False, "match": r"fraps.*"},
    "telegram":    {"name": "Telegram",        "cat": "Applications", "uid": "TELEGRAM",  "default": True,  "match": r"tsetup.*"},
    "notepad":     {"name": "Notepad++",       "cat": "Applications", "uid": "NOTEPAD",   "default": True,  "match": r"npp.*"},
    "wincdemu":    {"name": "WinCDEmu",        "cat": "Iso",          "uid": "WINCDEMU",  "default": False, "match": r"WinCDEmu.*"},
    "revouninst":  {"name": "RevoUninstaller", "cat": "Системные",    "uid": "REVO",      "default": False, "match": r"revo.*"},
}

CRLF = "\r\n"
HEADER = (
        "// WPI Config 8.0.0" + CRLF
        + "CheckOnLoad='default';" + CRLF
        + "Configurations=['Silent','Default'];" + CRLF
        + "ShowMultiDefault=true;" + CRLF
        + "SortOrder=['Защита','Системные','Медиа','Iso','Интернет','Applications','Для игр'];" + CRLF
        + "ConfigSortBy=2;" + CRLF
        + "pn=1;" + CRLF
        + CRLF
)

def get_arch(filename):
    fl = filename.lower()
    if "x86-64" in fl or "x86_64" in fl:
        return "x64"
    if any(m in fl for m in ["x64", "win64", "amd64", "64bit"]):
        return "x64"
    if any(m in fl for m in ["x86", "win32", "32bit"]):
        return "x86"
    return "unknown"

def get_prefix(arch, app_key):
    if arch == "x64": return "{x64} "
    if arch == "x86": return "{x86} "
    return ""

def generate():
    if not os.path.exists(DOWNLOADS_DIR):
        print("ERROR: Downloads dir not found")
        return

    os.makedirs(WPI_INSTALL_PHYSICAL, exist_ok=True)
    items = sorted(os.listdir(DOWNLOADS_DIR))

    grouped = {}
    matched_items = set()

    for item in items:
        for key, rule in APP_RULES.items():
            if re.search(rule["match"], item, re.IGNORECASE):
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(item)
                matched_items.add(item)
                break

    output = HEADER
    dq = chr(34)

    for key, files in grouped.items():
        rule  = APP_RULES[key]
        cat_f = CAT_FOLDER.get(rule["cat"], rule["cat"])
        is_d  = "yes" if rule.get("default") else "no"
        app_folder  = rule.get("folder", "")
        silent_flag = rule.get("silent", "")

        cat_physical_dir = os.path.join(WPI_INSTALL_PHYSICAL, cat_f)
        if app_folder:
            cat_physical_dir = os.path.join(cat_physical_dir, app_folder)

        os.makedirs(cat_physical_dir, exist_ok=True)

        # 1. ФИЗИЧЕСКОЕ КОПИРОВАНИЕ ФАЙЛОВ
        for item in sorted(files, key=lambda f: 0 if get_arch(f)=="x86" else 1 if get_arch(f)=="x64" else 2):
            src_p = os.path.join(DOWNLOADS_DIR, item)

            if app_folder:
                # Включаем сплющивание: вываливаем все файлы из любых папок прямо в корень app_folder
                if os.path.isdir(src_p):
                    for root, _, fs in os.walk(src_p):
                        for f in fs:
                            s_file = os.path.join(root, f)
                            d_file = os.path.join(cat_physical_dir, f)
                            if not os.path.exists(d_file):
                                shutil.copy2(s_file, d_file)
                else:
                    d_file = os.path.join(cat_physical_dir, item)
                    if not os.path.exists(d_file):
                        shutil.copy2(src_p, d_file)
            else:
                # Стандартное копирование без сплющивания
                dst_p = os.path.join(cat_physical_dir, item)
                if not os.path.exists(dst_p):
                    if os.path.isdir(src_p):
                        shutil.copytree(src_p, dst_p)
                    else:
                        shutil.copy2(src_p, dst_p)

        cmd_list = []

        # 2. ГЕНЕРАЦИЯ КОМАНД ДЛЯ CONFIG.JS
        if key == "vcredist":
            # Создаем install_vcredist.bat
            bat_path = os.path.join(cat_physical_dir, "install_vcredist.bat")
            with open(bat_path, "w", encoding="utf-8") as bf:
                bf.write(VCREDIST_BAT_CONTENT)

            # Добавляем всего одну команду запуска батника
            ep = WPI_INSTALL_PATH + r"\\" + app_folder + r"\\install_vcredist.bat"
            cmd_list.append("'" + dq + ep + dq + "'")

        else:
            # Универсальная логика для остальных программ
            for item in sorted(files, key=lambda f: 0 if get_arch(f)=="x86" else 1 if get_arch(f)=="x64" else 2):
                src_p = os.path.join(DOWNLOADS_DIR, item)

                base_ep = WPI_INSTALL_PATH + r"\\" + cat_f + r"\\"
                if app_folder:
                    base_ep += app_folder + r"\\"

                if os.path.isdir(src_p):
                    valid_exts = (".exe", ".bat", ".msi", ".cmd")
                    installers = []

                    for root, _, fs in os.walk(src_p):
                        for f in fs:
                            if f.lower().endswith(valid_exts):
                                rel_dir = os.path.relpath(root, src_p)
                                if rel_dir == ".": installers.append(f)
                                else: installers.append(os.path.join(rel_dir, f))

                    if not installers:
                        continue

                    if key == "cpu_fix":
                        selected_installers = [next((e for e in installers if os.path.basename(e).lower() == "install.bat"), installers[0])]
                    else:
                        selected_installers = sorted(installers, key=lambda x: 0 if get_arch(x)=="x86" else 1 if get_arch(x)=="x64" else 2)

                    for inst in selected_installers:
                        ep = base_ep + item + r"\\" + inst.replace("/", r"\\").replace("\\", r"\\")
                        arch = get_arch(inst)
                        ap = get_prefix(arch, key)
                        cmd_list.append("'" + ap + dq + ep + dq + silent_flag + "'")

                else:
                    ep = base_ep + item
                    arch = get_arch(item)
                    ap = get_prefix(arch, key)
                    cmd_list.append("'" + ap + dq + ep + dq + silent_flag + "'")

        if not cmd_list:
            continue

        output += "prog[pn]=['" + rule["name"] + "'];" + CRLF
        output += "uid[pn]=['" + rule["uid"] + "'];" + CRLF
        output += "dflt[pn]=['" + is_d + "'];" + CRLF
        output += "forc[pn]=['no'];" + CRLF
        output += "cat[pn]=['" + rule["cat"] + "'];" + CRLF
        output += "pfro[pn]=['no'];" + CRLF
        output += "cmds[pn]=[" + ",".join(cmd_list) + "];" + CRLF
        output += "desc[pn]=['" + rule["name"] + "'];" + CRLF
        output += "pn++;" + CRLF + CRLF

    output += CRLF + "//" + "-"*93 + CRLF
    output += "// End of program definitions ..." + CRLF
    output += "//" + "-"*93 + CRLF

    other_dir = os.path.join(WPI_INSTALL_PHYSICAL, "Other")
    for item in items:
        if item not in matched_items:
            src_p = os.path.join(DOWNLOADS_DIR, item)
            dst_p = os.path.join(other_dir, item)
            os.makedirs(other_dir, exist_ok=True)
            if not os.path.exists(dst_p):
                if os.path.isdir(src_p):
                    shutil.copytree(src_p, dst_p)
                else:
                    shutil.copy2(src_p, dst_p)

    with open("config.js", "w", encoding="utf-8-sig") as f:
        f.write(output)

    print("[OK] config.js written successfully and files distributed!")

if __name__ == "__main__":
    generate()