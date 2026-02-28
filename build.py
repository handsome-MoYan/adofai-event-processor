#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADOFAI Event Processor 打包脚本
"""
import shutil
import subprocess
import sys
from pathlib import Path


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ['build', 'dist', '*.egg-info']
    for pattern in dirs_to_remove:
        for path in Path('.').glob(pattern):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                print(f"已删除: {path}")

    # 清理 __pycache__
    for pycache in Path('.').rglob('__pycache__'):
        if pycache.is_dir():
            shutil.rmtree(pycache, ignore_errors=True)


def install_deps():
    """安装依赖"""
    print("\n安装依赖...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-e', '.[dev]'], check=True)


def build_exe():
    """使用 PyInstaller 打包"""
    print("\n开始打包...")
    spec_file = Path('ADOFAI_Event_Processing.spec')

    if not spec_file.exists():
        print(f"错误: 找不到 {spec_file}")
        sys.exit(1)

    # 运行 PyInstaller
    result = subprocess.run([
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        str(spec_file)
    ], capture_output=False)

    if result.returncode != 0:
        print("打包失败！")
        sys.exit(1)

    print("打包成功！")


def create_portable():
    """创建便携版目录"""
    dist_dir = Path('dist')
    exe_file = dist_dir / 'ADOFAI_Event_Processor_v4.4.0.exe'

    if not exe_file.exists():
        print(f"错误: 找不到 {exe_file}")
        return False

    # 创建便携版目录
    portable_dir = dist_dir / 'ADOFAI_Event_Processor_v4.4.0_Windows'

    if portable_dir.exists():
        shutil.rmtree(portable_dir)

    portable_dir.mkdir(parents=True)

    # 复制主程序
    shutil.copy2(exe_file, portable_dir / 'ADOFAI_Event_Processor.exe')

    # 创建使用说明
    readme = portable_dir / '使用说明.txt'
    readme.write_text('''ADOFAI Event Processor v4.4.0
冰与火之舞事件处理工具
作者: NeoMoyelle
邮箱: handsomemoyan@outlook.com

【使用方法】
1. 直接运行 ADOFAI_Event_Processor.exe
2. 点击"浏览..."选择 .adofai 谱面文件
3. 或使用拖拽功能将文件拖入程序窗口
4. 选择处理模式和关键词，点击"开始处理"

【快捷键】
Ctrl+O      - 打开文件
Ctrl+S      - 选择输出目录
Ctrl+Shift+S - 自动填充输出目录
Ctrl+P      - 预览处理结果
Ctrl+Shift+P - 开始处理
Ctrl+Enter  - 添加主关键词
Shift+Enter - 添加子关键词
Delete      - 删除选中项
Ctrl+Delete - 清空所有
F12         - 调试窗口

【配置文件】
首次运行后会自动生成 adofai_ep_config.json

【GitHub】
https://github.com/NeoMoyelle/adofai-event-processor
''', encoding='utf-8')

    # 创建配置文件模板
    config_template = portable_dir / 'config_template.json'
    config_template.write_text('''{
  "encoding": "utf-8-sig",
  "turbo": false,
  "theme": "cosmo",
  "lang": "zh_CN",
  "max_history": 10,
  "console": true,
  "save_log": false,
  "check_presets_on_startup": true,
  "debug": false
}''', encoding='utf-8')

    print(f"\n便携版创建完成: {portable_dir}")
    return True


def main():
    print("=" * 60)
    print("ADOFAI Event Processor v4.4.0 打包脚本")
    print("作者: NeoMoyelle")
    print("=" * 60)

    if not Path('adofai_ep').exists():
        print("\n错误: 请在项目根目录运行此脚本！")
        print(f"当前目录: {Path.cwd()}")
        print("确保 adofai_ep 文件夹在当前目录下")
        sys.exit(1)

    # 执行构建
    clean_build()
    install_deps()
    build_exe()
    create_portable()

    print("\n" + "=" * 60)
    print("构建完成！")
    print("输出目录: dist/ADOFAI_Event_Processor_v4.4.0_Windows/")
    print("=" * 60)

    print("\n【下一步】")
    print("1. 测试运行: dist/ADOFAI_Event_Processor_v4.4.0_Windows/ADOFAI_Event_Processor.exe")
    print("2. 压缩 ZIP 文件准备上传 GitHub")
    print("3. 创建 GitHub 仓库并推送代码")


if __name__ == '__main__':
    main()
