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
from http.server import HTTPServer, BaseHTTPRequestHandler
import base64
from io import BytesIO

# 代理配置
PROXY_URL = "http://127.0.0.1:10809"  # 改用 HTTP 代理，通常 Clash 的 HTTP 代理端口是 7890

# 配置 Google API 使用代理
os.environ['HTTPS_PROXY'] = PROXY_URL
os.environ['HTTP_PROXY'] = PROXY_URL

# 禁用SSL警告
urllib3.disable_warnings()

# 加载环境变量
load_dotenv()

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
        self.configure(bg='black')
        
        # 设置窗口属性
        self.overrideredirect(True)
        self.attributes('-alpha', 0.01)  # 设置为几乎全透明
        self.attributes('-topmost', True)
        
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
        # 初始化计时相关变量
        self.start_time = None
        self.loading_timer = None
        self.hide_timer = None
        
        # 先创建窗口
        self.setup_window()
        self.setup_hotkey()
        self.is_processing = False
        
        # 直接加载模型
        threading.Thread(target=self.setup_gemini, daemon=True).start()

    def setup_gemini(self):
        """设置和加载Gemini模型"""
        try:
            # 配置API密钥
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            
            # 从环境变量获取模型名称，如果没有设置则使用默认值
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')
            
            # 设置生成参数
            generation_config = {
                "temperature": 0.4,
                "top_p": 1,
                "top_k": 32,
                "max_output_tokens": 4096,
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
            # 打开图片
            img = Image.open(image_path)
            
            # 准备提示词
            prompt = """
            You hold a Ph.D. in computer networking, and your task is to analyze the questions I will provide. These questions will include multiple-choice and matching types. Please understand the content of the questions and directly provide the answers to each one.
            """
            
            # 发送请求
            response = self.model.generate_content([prompt, img])
            
            # 只显示 parts[1] 的内容
            if response.candidates and response.candidates[0].content.parts:
                try:
                    # 尝试获取 parts[1] 的内容
                    result = response.candidates[0].content.parts[1].text
                except IndexError:
                    # 如果没有 parts[1]，则使用最后一个 part 的内容
                    result = response.candidates[0].content.parts[0].text
                
                self.show_result(result.strip())
            else:
                self.show_result("无法获取答案")
                
        except Exception as e:
            error_msg = f"分析图片时出错:\n{str(e)}"
            print(error_msg)
            self.show_result(error_msg)
        finally:
            try:
                os.unlink(image_path)
            except Exception:
                pass

    def test_proxy(self):
        try:
            print(f"正在测试代理 {PROXY_URL}...")
            
            # 使用更长的超时时间
            timeout = httpx.Timeout(30.0, connect=30.0)
            
            with httpx.Client(
                proxies={"all://": PROXY_URL},
                timeout=timeout,
                verify=False,  # 禁用SSL验证
                follow_redirects=True
            ) as client:
                # 测试连接到 Google AI Studio
                print("测试连接到 Google AI Studio...")
                response = client.get('https://aistudio.google.com/')
                if response.status_code == 200:
                    print("成功连接到 Google AI Studio!")
                else:
                    print(f"连接返回状态码: {response.status_code}")
                
                print("测试获取IP信息...")
                response = client.get('https://api.ipify.org?format=json')
                ip_info = response.json()
                success_msg = f"代理测试成功！\n当前IP: {ip_info['ip']}\nGoogle AI Studio 可访问\n代理服务器: {PROXY_URL}"
                print(success_msg)
                self.show_result(success_msg)
                
        except httpx.TimeoutException:
            error_msg = f"代理连接超时\n请检查:\n1. 代理服务器 {PROXY_URL} 是否在运行\n2. 防火墙设置\n3. 代理服务器是否支持HTTP"
            print(error_msg)
            self.show_result(error_msg)
        except httpx.ConnectError:
            error_msg = f"无法连接到代理服务器\n请检查代理服务器 {PROXY_URL} 是否正确"
            print(error_msg)
            self.show_result(error_msg)
        except Exception as e:
            error_msg = f"代理测试失败: {str(e)}"
            print(error_msg)
            self.show_result(error_msg)

    def quit_app(self):
        # 取消注册所有快捷键
        keyboard.unhook_all()
        # 销毁所有窗口
        self.popup.destroy()
        self.root.destroy()
        # 强制退出
        os._exit(0)

    def run(self):
        print("程序已启动！使用Ctrl+Shift+Q截图，Ctrl+Shift+T测试代理，Ctrl+C退出")
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            # 确保程序能够正常退出
            self.quit_app()

    def setup_hotkey(self):
        keyboard.add_hotkey('ctrl+shift+q', self.take_screenshot)
        # 添加代理测试快捷键
        keyboard.add_hotkey('ctrl+shift+t', self.test_proxy)
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

class APIHandler(BaseHTTPRequestHandler):
    def _send_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        if self.path == '/v1/chat/completions':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode())

            # 检查是否包含图像
            messages = request_data.get('messages', [])
            image_content = None
            prompt = ""

            for message in messages:
                if message.get('role') == 'user':
                    content = message.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                if item.get('type') == 'text':
                                    prompt += item.get('text', '')
                                elif item.get('type') == 'image_url':
                                    image_url = item.get('image_url', {}).get('url', '')
                                    if image_url.startswith('data:image'):
                                        # 处理base64图像
                                        image_data = image_url.split(',')[1]
                                        image_content = base64.b64decode(image_data)
                    else:
                        prompt += str(content)

            if image_content:
                # 保存图像到临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                    temp_file.write(image_content)
                    temp_path = temp_file.name

                try:
                    # 使用现有的Gemini分析功能
                    image = Image.open(temp_path)
                    app = FloatingWindow()
                    result = app.analyze_image(temp_path)

                    # 构造OpenAI格式的响应
                    response_data = {
                        'id': 'chatcmpl-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                        'object': 'chat.completion',
                        'created': int(time.time()),
                        'model': 'gpt-4-vision-preview',
                        'usage': {
                            'prompt_tokens': 0,
                            'completion_tokens': 0,
                            'total_tokens': 0
                        },
                        'choices': [
                            {
                                'message': {
                                    'role': 'assistant',
                                    'content': result
                                },
                                'finish_reason': 'stop',
                                'index': 0
                            }
                        ]
                    }

                    self._send_response(200, response_data)

                finally:
                    # 清理临时文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
            else:
                self._send_response(400, {'error': 'No image found in request'})
        else:
            self._send_response(404, {'error': 'Not found'})

class APIServer:
    def __init__(self, port=8000):
        self.port = port
        self.server = None

    def start(self):
        self.server = HTTPServer(('localhost', self.port), APIHandler)
        print(f"API server started on port {self.port}")
        self.server.serve_forever()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

if __name__ == '__main__':
    app = FloatingWindow()
    
    # 启动API服务器
    api_server = APIServer(port=8000)
    api_thread = threading.Thread(target=api_server.start, daemon=True)
    api_thread.start()
    
    try:
        app.run()
    finally:
        api_server.stop()
