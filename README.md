# AI截图助手

这是一个智能截图分析工具，支持使用OpenAI Vision或Google Gemini API进行图像分析。它可以在后台运行，通过快捷键进行截图，并自动分析图片内容，将结果显示在桌面上。

## 功能特点

- 系统托盘运行，轻量级后台运行
- 快捷键截图 (Ctrl+Shift+A)
- 双模型支持：
  - OpenAI GPT-4 Vision
  - Google Gemini Pro Vision
- 可在系统托盘菜单中快速切换模型
- 桌面浮窗显示分析结果
- 支持结果窗口拖动和自动隐藏

## 安装步骤

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置API密钥：
- 复制`.env.example`为`.env`
- 在`.env`文件中设置你的API密钥：
  - 如果使用Gemini，设置`GOOGLE_API_KEY`
  - 如果使用OpenAI，设置`OPENAI_API_KEY`
- 在`.env`中设置`MODEL_PROVIDER`为`openai`或`gemini`

3. 运行程序：
```bash
python main.py
```
或直接运行`run.bat`

## 使用说明

1. 程序启动后会在系统托盘显示图标
2. 使用Ctrl+Shift+A进行截图
3. 分析结果会显示在桌面浮窗中
4. 右键系统托盘图标可以：
   - 切换AI模型
   - 退出程序

## 注意事项

- 需要Python 3.8+
- 需要有效的API密钥（OpenAI或Google）
- 确保系统支持系统托盘功能
- 如果使用代理，可在`.env`中配置`PROXY_URL`

## 更新日志

### 2024-12-22
- 新增OpenAI Vision支持
- 优化截图界面，减少闪烁
- 添加模型切换功能
- 改进浮窗交互体验
