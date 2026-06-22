# -*- mode: python ; coding: utf-8 -*-
"""Receita de empacotamento do Otimizador PC (PyInstaller).

Gera um único OtimizadorPC.exe (modo --onefile, JANELA/windowed) com:
  * a whitelist de servicos embutida (dados/servicos_seguros.json);
  * os modulos do WMI / pywin32 que o PyInstaller costuma nao detectar
    sozinho (win32timezone e companhia) declarados como hidden imports.

A partir da v2.0 o programa abre em JANELA (PySide6/Qt) por padrao, por isso o
executavel e' "windowed" (console=False): o duplo-clique abre a janela limpa,
sem um terminal preto atras. O modo terminal continua acessivel com a flag
--cli (o programa anexa/aloca um console sob demanda nesse caso).

Como usar (no Windows, com as dependencias instaladas):
    pyinstaller OtimizadorPC.spec

O .exe final aparece em dist\\OtimizadorPC.exe e NAO exige Python instalado.
As pastas logs\\ e backups\\ sao criadas ao lado do .exe na 1a execucao.
"""

# Recursos somente-leitura embutidos no executavel.
datas = [
    ("dados/servicos_seguros.json", "dados"),
]

# O pacote `wmi` se apoia no pywin32 (win32com). O PyInstaller normalmente
# encontra pythoncom/pywintypes, mas costuma esquecer win32timezone (usado pelo
# WMI ao ler datas) e o win32com.client — por isso declaramos explicitamente.
hiddenimports = [
    "wmi",
    "win32timezone",
    "win32com",
    "win32com.client",
    "pythoncom",
    "pywintypes",
]

# O PySide6 traz a janela. Os hooks do PyInstaller para PySide6 ja coletam os
# plugins de plataforma (ex.: 'windows') e as DLLs do Qt automaticamente, entao
# nao precisamos listar binarios manualmente aqui.


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OtimizadorPC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX desligado de proposito: a compressao UPX dispara muitos falsos
    # positivos de antivirus, ruim para um programa que o usuario roda como
    # administrador. Preferimos um .exe um pouco maior, porem "limpo".
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Janela (windowed): sem console preto atras da interface grafica. O modo
    # --cli anexa/aloca um console por conta propria quando necessario.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
