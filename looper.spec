# -*- mode: python -*-

block_cipher = None

fontawesome = Tree('C:\\Python34\\Lib\\site-packages\\qtawesome\\fonts', prefix = 'qtawesome\\fonts')

a = Analysis(['.\\main.py'],
             pathex=['C:\\Dev\\looper'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None,
             excludes=None,
             cipher=block_cipher)
pyz = PYZ(a.pure,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='main.exe',
          debug=False,
          strip=None,
          upx=False,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               [('gui/application.qss', 'gui/application.qss', 'DATA')],
               [('gui/main_window.ui', 'gui/main_window.ui', 'DATA')],
               fontawesome,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=False,
               name='main')
