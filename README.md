# AI截图助手

这是一个基于Gemini API的智能截图分析工具。它可以在后台运行，通过快捷键进行截图，并自动分析图片内容，将结果显示在桌面上。

## 功能特点

- 系统托盘运行
- 快捷键截图 (Ctrl+Shift+A)
- 使用Google Gemini API进行图像分析
- 桌面显示分析结果

## 安装步骤

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置API密钥：
- 复制`.env.example`为`.env`
- 在`.env`文件中设置你的Google API密钥

3. 运行程序：
```bash
python main.py
```

## 使用说明

1. 程序启动后会在系统托盘显示图标
2. 使用Ctrl+Shift+A进行截图
3. 等待分析结果显示在桌面左下角

## 注意事项

- 需要Python 3.8+
- 需要有效的Google API密钥
- 确保系统支持系统托盘功能
