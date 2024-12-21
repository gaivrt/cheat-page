import os
import sys
import keyboard
import google.generativeai as genai
from PIL import Image, ImageGrab
import tempfile
from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk
import threading
import time
import httpx
import urllib3
from PIL import ImageDraw
from tkinter import filedialog
import datetime
import win32gui
import win32ui
import win32con
import win32api
import ctypes
import json
from io import BytesIO
import base64
from pystray import Icon as TrayIcon, Menu as TrayMenu, MenuItem as TrayMenuItem

# 加载环境变量
load_dotenv()

# 模型选择
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()

# 代理配置
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:10809")

# OpenAI配置
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-vision-preview")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "500"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
OPENAI_TOP_P = float(os.getenv("OPENAI_TOP_P", "1.0"))
OPENAI_PRESENCE_PENALTY = float(os.getenv("OPENAI_PRESENCE_PENALTY", "0.0"))
OPENAI_FREQUENCY_PENALTY = float(os.getenv("OPENAI_FREQUENCY_PENALTY", "0.0"))

# Gemini配置
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro-vision")
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
GEMINI_TOP_P = float(os.getenv("GEMINI_TOP_P", "0.8"))
GEMINI_TOP_K = int(os.getenv("GEMINI_TOP_K", "40"))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048"))

# 配置 Google API 使用代理
os.environ['HTTPS_PROXY'] = PROXY_URL
os.environ['HTTP_PROXY'] = PROXY_URL

# 禁用SSL警告
urllib3.disable_warnings()

class ScreenshotSelector(tk.Toplevel):
    def __init__(self, callback, cancel_callback):
        super().__init__()
        self.callback = callback
        self.cancel_callback = cancel_callback
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        
        # 获取屏幕缩放因子
        self.scale_factor = self.winfo_fpixels('1i') / 96.0
        
        self.setup_window()
        
    def setup_window(self):
        # 禁用DPI缩放
        try:
            from ctypes import windll
            windll.shcore.SetProcessDPIAware(1)
        except:
            pass
            
        # 获取真实的屏幕分辨率
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        
        # 获取真实的屏幕分辨率
        self.real_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        self.real_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        self.screen_width = self.real_width
        self.screen_height = self.real_height
        
        print(f"[DEBUG] Screen Size: {self.screen_width}x{self.screen_height}")
        
        # 先隐藏窗口
        self.withdraw()
        
        # 配置根窗口
        self.attributes('-alpha', 0.01)  # 设置窗口几乎完全透明
        self.configure(bg='black')
        self.attributes('-topmost', True)  # 确保窗口始终在最顶层
        
        # 设置窗口属性
        self.overrideredirect(True)
        
        # 设置窗口大小和位置
        self.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
        
        # 创建全屏画布
        self.canvas = tk.Canvas(
            self,
            width=self.screen_width,
            height=self.screen_height,
            highlightthickness=0,
            borderwidth=0,
            bg='black',
            cursor="crosshair"
        )
        
        # 使用place确保画布完全覆盖窗口
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        # 绑定事件
        self.canvas.bind('<Button-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.bind('<Escape>', lambda e: self.cancel_screenshot())
        
        # 更新所有挂起的空闲任务
        self.update_idletasks()
        
        # 平滑显示窗口
        self.deiconify()
        self.attributes('-alpha', 0.01)
        
        # 确保窗口在最顶层
        self.lift()
        self.focus_force()

    def capture_screen(self, bbox=None):
        """使用win32api捕获屏幕"""
        try:
            # 在截图前完全隐藏窗口
            self.attributes('-alpha', 0)
            self.update()
            
            # 获取真实的屏幕分辨率
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            
            # 获取主显示器信息
            monitor = win32api.EnumDisplayMonitors(None, None)[0][0]
            monitor_info = win32api.GetMonitorInfo(monitor)
            monitor_area = monitor_info['Monitor']
            
            print(f"[DEBUG] Capture - Monitor Area: {monitor_area}")
            
            # 获取实际显示区域
            if bbox:
                x1, y1, x2, y2 = bbox
                print(f"[DEBUG] Original bbox: ({x1}, {y1}, {x2}, {y2})")
                
                # 确保坐标不超出屏幕边界
                x1 = max(0, min(x1, self.real_width))
                y1 = max(0, min(y1, self.real_height))
                x2 = max(0, min(x2, self.real_width))
                y2 = max(0, min(y2, self.real_height))
                
                print(f"[DEBUG] Adjusted bbox: ({x1}, {y1}, {x2}, {y2})")
                
                width = x2 - x1
                height = y2 - y1
            else:
                x1, y1 = 0, 0
                width = self.real_width
                height = self.real_height
            
            print(f"[DEBUG] Capture dimensions: {width}x{height}")
            
            # 创建设备上下文
            hwnd = win32gui.GetDesktopWindow()
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            # 创建位图
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)
            
            # 复制屏幕内容
            result = saveDC.BitBlt((0, 0), (width, height), mfcDC, (x1, y1), win32con.SRCCOPY)
            print(f"[DEBUG] BitBlt result: {result}")
            
            # 获取位图信息
            bmpinfo = saveBitMap.GetInfo()
            print(f"[DEBUG] Bitmap info: {bmpinfo}")
            
            bmpstr = saveBitMap.GetBitmapBits(True)
            
            # 转换为PIL图像
            image = Image.frombytes(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX'
            )
            
            print(f"[DEBUG] Final image size: {image.size}")
            
            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            
            return image
            
        except Exception as e:
            print(f"[DEBUG] Screenshot error: {str(e)}")
            print(f"[DEBUG] Error type: {type(e)}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return None

    def cancel_screenshot(self):
        self.destroy()
        if self.cancel_callback:
            self.cancel_callback()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
        # 删除之前的选择框
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        
        # 创建新的选择框
        self.current_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline='white',
            width=1  # 减小边框宽度
        )

    def on_drag(self, event):
        if self.current_rect:
            # 更新选择框
            self.canvas.coords(
                self.current_rect,
                self.start_x, self.start_y,
                event.x, event.y
            )
            
            # 清除之前的遮罩
            for item in self.canvas.find_all():
                if item != self.current_rect:
                    self.canvas.delete(item)
            
            # 创建新的遮罩（排除选择区域）
            x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
            x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
            
            # 上方遮罩
            self.canvas.create_rectangle(0, 0, self.real_width, y1, 
                                      fill='black', stipple='gray12')  # 使用更透明的stipple模式
            # 下方遮罩
            self.canvas.create_rectangle(0, y2, self.real_width, self.real_height, 
                                      fill='black', stipple='gray12')
            # 左侧遮罩
            self.canvas.create_rectangle(0, y1, x1, y2, 
                                      fill='black', stipple='gray12')
            # 右侧遮罩
            self.canvas.create_rectangle(x2, y1, self.real_width, y2, 
                                      fill='black', stipple='gray12')
            
    def on_release(self, event):
        if self.start_x is None:
            self.cancel_screenshot()
            return
            
        # 如果点击位置和释放位置相同或非常接近（说明是点击而不是拖动）
        if abs(self.start_x - event.x) < 5 and abs(self.start_y - event.y) < 5:
            self.cancel_screenshot()
            return
            
        # 计算实际坐标（考虑DPI缩放）
        x1 = int(min(self.start_x, event.x) * self.scale_factor)
        y1 = int(min(self.start_y, event.y) * self.scale_factor)
        x2 = int(max(self.start_x, event.x) * self.scale_factor)
        y2 = int(max(self.start_y, event.y) * self.scale_factor)
        
        print(f"[DEBUG] Mouse coordinates: start({self.start_x}, {self.start_y}), end({event.x}, {event.y})")
        print(f"[DEBUG] Scaled coordinates: ({x1}, {y1}, {x2}, {y2})")
        
        # 确保选择框不超出屏幕边界
        x1 = max(0, min(x1, self.real_width))
        y1 = max(0, min(y1, self.real_height))
        x2 = max(0, min(x2, self.real_width))
        y2 = max(0, min(y2, self.real_height))
        
        print(f"[DEBUG] Screen-adjusted coordinates: ({x1}, {y1}, {x2}, {y2})")
        
        # 最小选择区域
        if x2 - x1 < 10 or y2 - y1 < 10:
            self.cancel_screenshot()
            return
        
        try:
            # 使用新的截图方法
            screenshot = self.capture_screen((x1, y1, x2, y2))
            if screenshot:
                # 先隐藏窗口但不销毁
                self.withdraw()
                self.update()
                # 回调处理截图
                self.callback(screenshot)
                # 最后再销毁窗口
                self.after(100, self.destroy)
            else:
                self.cancel_screenshot()
        except Exception as e:
            print(f"[DEBUG] Screenshot process error: {str(e)}")
            self.cancel_screenshot()

    def process_screenshot(self, screenshot):
        try:
            # 显示截图区域信息
            width, height = screenshot.size
            self.show_result(f"已截取区域：{width}x{height}像素\n正在分析图片...")
            
            # 创建临时文件用于分析
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                screenshot.save(tmp_file.name)
                # 分析图片
                self.analyze_image(tmp_file.name)
        
        except Exception as e:
            self.show_result(f"截图过程出错：{str(e)}")
        finally:
            self.is_processing = False

class FloatingWindow:
    def __init__(self):
        self.popup = None
        self.screenshot = None
        self.hide_timer = None
        self.is_processing = False  # 添加处理状态标志
        
        # 先创建窗口
        self.setup_window()
        self.setup_hotkey()
        
        # 当前选择的模型配置
        self.current_model_provider = MODEL_PROVIDER
        self.current_model = OPENAI_MODEL if MODEL_PROVIDER == "openai" else GEMINI_MODEL
        
        # 保存环境变量的原始值
        self.original_env = {
            "MODEL_PROVIDER": MODEL_PROVIDER,
            "OPENAI_MODEL": OPENAI_MODEL,
            "GEMINI_MODEL": GEMINI_MODEL
        }
        
        # 设置系统托盘
        self.setup_tray()
        
        # 直接加载模型
        threading.Thread(target=self.setup_gemini, daemon=True).start()

    def get_model_menu(self, provider, models):
        return TrayMenu(*[
            TrayMenuItem(
                f"{model} {'✓' if self.current_model_provider == provider and self.current_model == model else ''}",
                lambda item, model=model: self.switch_model(provider, str(model))  # 确保model是字符串
            ) for model in models
        ])

    def create_tray_icon(self):
        """创建系统托盘图标"""
        # 创建一个简单的图标
        icon_size = 64
        icon_image = Image.new('RGBA', (icon_size, icon_size), color=(255, 255, 255, 0))
        draw = ImageDraw.Draw(icon_image)
        
        # 绘制圆形背景
        draw.ellipse([2, 2, icon_size-3, icon_size-3], fill='white', outline='black', width=2)
        
        # 添加文字
        try:
            # 尝试使用微软雅黑字体
            from PIL import ImageFont
            font = ImageFont.truetype("msyh.ttc", 24)
        except:
            font = None
        
        # 计算文字位置使其居中
        text = "AI"
        if font:
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        else:
            text_width = 20
            text_height = 20
        
        x = (icon_size - text_width) // 2
        y = (icon_size - text_height) // 2
        
        # 绘制文字
        draw.text((x, y), text, fill='black', font=font)
        
        def create_menu():
            """创建右键菜单"""
            openai_models = [
                "gpt-4-vision-preview",
                "gpt-4o",
                "o1-mini"
            ]
            
            gemini_models = [
                "gemini-pro-vision",
                "gemini-2.0-flash-thinking-exp-1219"
            ]

            return TrayMenu(
                TrayMenuItem(
                    "OpenAI Models",
                    self.get_model_menu("openai", openai_models)
                ),
                TrayMenuItem(
                    "Gemini Models",
                    self.get_model_menu("gemini", gemini_models)
                ),
                TrayMenu.SEPARATOR,
                TrayMenuItem(
                    "退出",
                    lambda: self.quit_app()
                )
            )

        # 创建系统托盘图标
        self.tray_icon = TrayIcon(
            "AI Assistant",
            icon_image,
            "AI Assistant",
            create_menu()
        )

    def switch_model(self, provider, model):
        """切换模型"""
        try:
            print(f"\n切换到 {provider} 的 {model} 模型")
            
            # 更新当前选择
            self.current_model_provider = provider
            self.current_model = model
            
            # 更新环境变量
            os.environ["MODEL_PROVIDER"] = str(provider)
            if provider == "openai":
                os.environ["OPENAI_MODEL"] = str(model)
            else:
                os.environ["GEMINI_MODEL"] = str(model)
                
            # 停止当前托盘图标
            self.tray_icon.stop()
            
            # 重新创建托盘图标
            self.create_tray_icon()
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            
            # 显示提示
            self.show_result(f"已切换到 {provider} 的 {model} 模型")
            
        except Exception as e:
            print(f"切换模型时出错: {str(e)}")
            self.show_result(f"切换模型失败: {str(e)}")

    def setup_tray(self):
        """设置系统托盘"""
        self.create_tray_icon()
        # 在新线程中运行托盘图标
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def quit_app(self, icon=None):
        """退出应用"""
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        # 取消注册所有快捷键
        keyboard.unhook_all()
        # 还原环境变量
        os.environ["MODEL_PROVIDER"] = self.original_env["MODEL_PROVIDER"]
        os.environ["OPENAI_MODEL"] = self.original_env["OPENAI_MODEL"]
        os.environ["GEMINI_MODEL"] = self.original_env["GEMINI_MODEL"]
        # 销毁所有窗口
        if hasattr(self, 'popup') and self.popup:
            self.popup.destroy()
        if hasattr(self, 'root') and self.root:
            self.root.destroy()
        # 强制退出
        os._exit(0)

    def setup_gemini(self):
        """设置和加载Gemini模型"""
        try:
            # 配置API密钥
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            
            # 从环境变量获取模型名称，如果没有设置则使用默认值
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')
            
            # 设置生成参数
            generation_config = {
                "temperature": GEMINI_TEMPERATURE,
                "top_p": GEMINI_TOP_P,
                "top_k": GEMINI_TOP_K,
                "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
            }
            
            # 设置安全设置
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
            ]
            
            # 创建模型
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
        except Exception as e:
            error_msg = f"设置Gemini时出错:\n{str(e)}"
            print(error_msg)
            self.root.after(0, lambda: self.show_result(error_msg))

    def cancel_auto_hide(self):
        if self.hide_timer:
            self.root.after_cancel(self.hide_timer)
            self.hide_timer = None

    def start_auto_hide(self):
        self.cancel_auto_hide()  # 先取消现有的定时器
        self.hide_timer = self.root.after(2000, self.popup.withdraw)

    def check_click_outside(self, event):
        if not self.popup.winfo_ismapped():
            return
            
        # 获取点击位置和弹窗位置
        click_x, click_y = event.x_root, event.y_root
        popup_x = self.popup.winfo_x()
        popup_y = self.popup.winfo_y()
        popup_width = self.popup.winfo_width()
        popup_height = self.popup.winfo_height()
        
        # 检查点击是否在弹窗外
        if not (popup_x <= click_x <= popup_x + popup_width and
                popup_y <= click_y <= popup_y + popup_height):
            self.popup.withdraw()
            self.cancel_auto_hide()

    def show_result(self, text):
        # 更新标签文本
        self.label.configure(text=text)
        
        # 获取真实的屏幕尺寸（考虑DPI缩放）
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            screen_width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            
            # 获取工作区（考虑任务栏）
            monitor = win32api.EnumDisplayMonitors(None, None)[0][0]
            monitor_info = win32api.GetMonitorInfo(monitor)
            work_area = monitor_info['Work']
        except Exception as e:
            print(f"[DEBUG] Error getting screen metrics: {e}")
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            work_area = [0, 0, screen_width, screen_height - 40]
        
        # 计算位置（左下角，使用工作区）
        x = work_area[0] + 20
        y = work_area[3] - self.popup.winfo_reqheight() - 20
        
        # 设置弹窗位置
        self.popup.geometry(f"+{x}+{y}")  # 只设置位置，不设置大小
        
        # 实现淡入效果
        self.popup.attributes('-alpha', 0.0)
        self.popup.deiconify()
        
        # 更新滚动区域
        self.content_frame.update_idletasks()
        self._on_frame_configure()
        
        # 滚动到底部
        self.popup.after(10, lambda: self.canvas.yview_moveto(1.0))
        
        # 淡入动画
        def fade_in(alpha=0.0):
            alpha += 0.1
            if alpha <= 0.70:
                self.popup.attributes('-alpha', alpha)
                self.popup.after(20, lambda: fade_in(alpha))
            else:
                self.popup.attributes('-alpha', 0.70)
                
        fade_in()
        
    def take_screenshot(self):
        if self.is_processing:
            self.show_result("正在处理上一个请求，请稍后再试...")
            return
            
        try:
            # 先隐藏弹窗
            if hasattr(self, 'popup') and self.popup.winfo_ismapped():
                self.popup.withdraw()
                
            self.is_processing = True
            selector = ScreenshotSelector(self.process_screenshot, self.cancel_screenshot)
        except Exception as e:
            print(f"截图错误: {e}")
            self.is_processing = False

    def cancel_screenshot(self):
        print("截图已取消")
        self.is_processing = False

    def process_screenshot(self, screenshot):
        try:
            # 显示截图区域信息
            width, height = screenshot.size
            self.show_result(f"已截取区域：{width}x{height}像素\n正在分析图片...")
            
            # 创建临时文件用于分析
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                screenshot.save(tmp_file.name)
                # 分析图片
                self.analyze_image(tmp_file.name)
        
        except Exception as e:
            self.show_result(f"截图过程出错：{str(e)}")
        finally:
            self.is_processing = False

    def analyze_image(self, image_path):
        """分析图片内容"""
        try:
            print("\n=== 开始分析图片 ===")
            print(f"使用模型提供商: {MODEL_PROVIDER}")
            
            # 根据配置选择使用哪个模型
            if MODEL_PROVIDER == "openai":
                return self._analyze_with_openai(image_path)
            elif MODEL_PROVIDER == "gemini":
                return self._analyze_with_gemini(image_path)
            else:
                error_msg = f"未知的模型提供商: {MODEL_PROVIDER}，请在 .env 文件中设置 MODEL_PROVIDER 为 'openai' 或 'gemini'"
                print(error_msg)
                self.show_result(error_msg)
                return error_msg

        except Exception as e:
            print(f"图片分析失败: {str(e)}")
            print(f"异常类型: {type(e).__name__}")
            error_msg = "图片分析失败，请重试"
            self.show_result(error_msg)
            return error_msg

    def _analyze_with_openai(self, image_path):
        """使用OpenAI API分析图片"""
        try:
            print("\n=== 使用OpenAI API ===")
            print(f"使用的API基础URL: {OPENAI_API_BASE}")
            print(f"代理设置: {PROXY_URL}")
            
            with open(image_path, "rb") as image_file:
                print("正在读取图片并转换为base64...")
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}"
                }
                print("API请求头:", {k: v if k != 'Authorization' else '***' for k, v in headers.items()})
                
                print("正在准备发送API请求...")
                print(f"请求URL: {OPENAI_API_BASE}/chat/completions")
                print(f"使用模型: {OPENAI_MODEL}")
                print(f"参数配置:")
                print(f"- 最大tokens: {OPENAI_MAX_TOKENS}")
                print(f"- 温度: {OPENAI_TEMPERATURE}")
                print(f"- top_p: {OPENAI_TOP_P}")
                print(f"- presence_penalty: {OPENAI_PRESENCE_PENALTY}")
                print(f"- frequency_penalty: {OPENAI_FREQUENCY_PENALTY}")
                
                # 基础payload
                payload = {
                    "model": OPENAI_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "You hold a Ph.D. in computer networking, and your task is to analyze the questions I will provide. These questions will include multiple-choice and matching types. Please understand the content of the questions and directly provide the answers to each one."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_data}"
                                    }
                                }
                            ]
                        }
                    ],
                    "temperature": OPENAI_TEMPERATURE,
                    "top_p": OPENAI_TOP_P,
                    "presence_penalty": OPENAI_PRESENCE_PENALTY,
                    "frequency_penalty": OPENAI_FREQUENCY_PENALTY
                }
                
                # 根据模型类型添加不同的token限制参数
                if OPENAI_MODEL.startswith("o1-"):
                    payload["max_completion_tokens"] = OPENAI_MAX_TOKENS
                else:
                    payload["max_tokens"] = OPENAI_MAX_TOKENS
                
                try:
                    print("发送API请求中...")
                    client = httpx.Client(
                        verify=False,
                        proxies={
                            "http://": PROXY_URL,
                            "https://": PROXY_URL
                        } if PROXY_URL else None,
                        timeout=30
                    )
                    response = client.post(
                        f"{OPENAI_API_BASE}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    
                    print(f"API响应状态码: {response.status_code}")
                    if response.status_code == 200:
                        result = response.json()
                        print("API请求成功！")
                        print("API响应:", result)
                        response_text = result['choices'][0]['message']['content']
                        print("分析结果:", response_text)
                        self.show_result(response_text)
                        return response_text
                    else:
                        print(f"API请求失败: {response.status_code}")
                        print("错误响应:", response.text)
                        raise Exception(f"API请求失败: {response.status_code}")
                        
                except Exception as e:
                    print(f"API请求异常: {str(e)}")
                    print(f"异常类型: {type(e).__name__}")
                    if isinstance(e, httpx.TimeoutException):
                        print("请求超时，可能是网络问题或代理设置有误")
                    elif isinstance(e, httpx.ConnectError):
                        print("连接错误，请检查网络连接和代理设置")
                    raise
                finally:
                    client.close()
                    
        except Exception as e:
            print(f"OpenAI分析失败: {str(e)}")
            print(f"异常类型: {type(e).__name__}")
            raise

    def _analyze_with_gemini(self, image_path):
        """使用Gemini API分析图片（作为备用）"""
        try:
            print("\n=== 使用Gemini API ===")
            print("正在加载图片...")
            image = Image.open(image_path)
            
            print("正在初始化Gemini模型...")
            print(f"使用模型: {GEMINI_MODEL}")
            print(f"参数配置:")
            print(f"- 温度: {GEMINI_TEMPERATURE}")
            print(f"- top_p: {GEMINI_TOP_P}")
            print(f"- top_k: {GEMINI_TOP_K}")
            print(f"- 最大输出tokens: {GEMINI_MAX_OUTPUT_TOKENS}")
            
            model = genai.GenerativeModel(
                GEMINI_MODEL,
                generation_config={
                    "temperature": GEMINI_TEMPERATURE,
                    "top_p": GEMINI_TOP_P,
                    "top_k": GEMINI_TOP_K,
                    "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
                }
            )
            
            print("发送Gemini API请求...")
            response = model.generate_content(["You hold a Ph.D. in computer networking, and your task is to analyze the questions I will provide. These questions will include multiple-choice and matching types. Please understand the content of the questions and directly provide the answers to each one.", image])
            
            # 根据模型类型处理响应
            if GEMINI_MODEL == "gemini-2.0-flash-thinking-exp-1219":
                result = response.candidates[0].content.parts[1].text
            else:
                result = response.text
                
            print("Gemini分析结果:", result)
            self.show_result(result)
            return result
        except Exception as e:
            print(f"Gemini分析失败: {str(e)}")
            print(f"异常类型: {type(e).__name__}")
            error_msg = "图片分析失败，请重试"
            self.show_result(error_msg)
            return error_msg

    def run(self):
        print("程序已启动！使用Ctrl+Shift+Q截图，Ctrl+C退出")
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            # 确保程序能够正常退出
            self.quit_app()

    def setup_hotkey(self):
        keyboard.add_hotkey('ctrl+shift+q', self.take_screenshot)
        keyboard.add_hotkey('ctrl+c', self.quit_app)

    def setup_window(self):
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏主窗口
        
        # 创建弹窗
        self.popup = tk.Toplevel(self.root)
        self.popup.overrideredirect(True)  # 无边框窗口
        self.popup.attributes('-topmost', True)  # 保持在最顶层
        self.popup.attributes('-alpha', 0.70)  # 设置整体透明度
        self.popup.withdraw()  # 初始隐藏
        
        # 设置弹窗样式 - 使用透明背景
        self.popup.configure(bg='white')  # 设置为白色背景
        
        # 创建圆角边框效果的框架
        self.frame = tk.Frame(
            self.popup,
            bg='white',  # 设置为白色背景
            highlightbackground='#e0e0e0',  # 淡化边框颜色
            highlightthickness=1,  # 边框厚度
        )
        self.frame.pack(expand=True, fill='both', padx=2, pady=2)

        # 创建Canvas和Scrollbar
        self.canvas = tk.Canvas(
            self.frame,
            bg='white',
            width=400,  # 固定宽度
            height=150,  # 固定高度
            highlightthickness=0  # 移除边框
        )
        self.scrollbar = ttk.Scrollbar(
            self.frame,
            orient="vertical",
            command=self.canvas.yview
        )
        
        # 创建内容框架
        self.content_frame = tk.Frame(
            self.canvas,
            bg='white'
        )
        
        # 配置Canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 创建标签
        self.label = ttk.Label(
            self.content_frame,  # 放在content_frame中
            text="准备就绪...",
            style='Custom.TLabel',
            wraplength=380,  # 稍微小于canvas宽度
            justify='left'  # 文本左对齐
        )
        self.label.pack(padx=25, pady=20, expand=True, fill='both')
        
        # 放置Canvas和Scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # 将content_frame放入Canvas
        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.content_frame,
            anchor="nw",
            width=self.canvas.winfo_reqwidth()  # 设置内容框架宽度
        )
        
        # 创建自定义样式
        style = ttk.Style()
        style.configure('Custom.TLabel', 
                       background='white',  # 设置为白色背景
                       foreground='black',  # 黑色文字
                       font=('Microsoft YaHei UI', 13))
        
        # 绑定鼠标事件
        self._bind_mouse_events()
        
    def _bind_mouse_events(self):
        """绑定所有鼠标相关事件"""
        # 鼠标进入和离开事件
        for widget in [self.popup, self.frame, self.canvas, self.content_frame, self.label]:
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
            widget.bind('<Double-Button-1>', self._on_double_click)  # 双击事件
            
        # 全局点击事件（检查点击是否在弹窗外）
        self.root.bind_all('<Button-1>', self.check_click_outside)
        
        # 鼠标滚轮事件
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # 内容框架大小变化事件
        self.content_frame.bind('<Configure>', self._on_frame_configure)
        
    def _on_enter(self, event):
        """鼠标进入事件处理"""
        self.cancel_auto_hide()
        
    def _on_leave(self, event):
        """鼠标离开事件处理"""
        # 检查鼠标是否真的离开了整个弹窗区域
        x, y = self.popup.winfo_pointerxy()
        widget_under_mouse = event.widget.winfo_containing(x, y)
        
        # 如果鼠标下面的部件不是弹窗的一部分，才开始自动隐藏
        if not widget_under_mouse or not any(
            widget_under_mouse.winfo_toplevel() is widget 
            for widget in [self.popup, self.frame, self.canvas, self.content_frame, self.label]
        ):
            self.start_auto_hide()
            
    def _on_double_click(self, event):
        """双击事件处理"""
        self.popup.withdraw()
        self.cancel_auto_hide()
        
    def _on_mousewheel(self, event):
        """处理鼠标滚轮事件"""
        if self.popup.winfo_ismapped():
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
    def _on_frame_configure(self, event=None):
        """当内容框架大小改变时，更新Canvas的滚动区域"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

if __name__ == '__main__':
    app = FloatingWindow()
    try:
        app.run()
    except KeyboardInterrupt:
        app.quit_app()
    except Exception as e:
        print(f"程序异常退出: {e}")
        os._exit(1)
