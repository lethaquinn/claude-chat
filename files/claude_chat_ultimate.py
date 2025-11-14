#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Chat Ultimate - 終極版
集成所有功能的完整版本
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, font, colorchooser
import requests
import json
import os
import re
import base64
from datetime import datetime
from pathlib import Path
from io import BytesIO
import threading
import hashlib

# 嘗試導入PDF處理庫
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("提示: 安裝PyPDF2可以處理PDF文件 (pip install PyPDF2)")

# 嘗試導入docx處理庫
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("提示: 安裝python-docx可以處理Word文件 (pip install python-docx)")

# 嘗試導入PIL用於圖片處理
try:
    from PIL import Image, ImageTk, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("提示: 安裝Pillow可以獲得更好的圖片支持 (pip install Pillow)")


class KnowledgeBase:
    """簡化的本地知識庫系統"""
    
    def __init__(self, kb_dir="knowledge_base"):
        self.kb_dir = Path(kb_dir)
        self.kb_dir.mkdir(exist_ok=True)
        self.documents = {}
        self.load_documents()
    
    def load_documents(self):
        """加載所有文檔到內存"""
        for file_path in self.kb_dir.glob("**/*.*"):
            if file_path.suffix.lower() in ['.txt', '.md', '.json']:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        self.documents[file_path.name] = {
                            'content': content,
                            'path': str(file_path),
                            'size': len(content)
                        }
                except Exception as e:
                    print(f"無法加載 {file_path}: {e}")
    
    def add_document(self, filename, content):
        """添加文檔到知識庫"""
        file_path = self.kb_dir / filename
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.documents[filename] = {
                'content': content,
                'path': str(file_path),
                'size': len(content)
            }
            return True
        except Exception as e:
            print(f"保存文檔失敗: {e}")
            return False
    
    def search(self, query, max_results=3):
        """簡單的關鍵詞搜索"""
        results = []
        query_lower = query.lower()
        
        for filename, doc in self.documents.items():
            content_lower = doc['content'].lower()
            if query_lower in content_lower:
                # 計算相關度(簡單的出現次數)
                relevance = content_lower.count(query_lower)
                # 提取相關片段
                snippets = self._extract_snippets(doc['content'], query, num_snippets=2)
                results.append({
                    'filename': filename,
                    'relevance': relevance,
                    'snippets': snippets,
                    'path': doc['path']
                })
        
        # 按相關度排序
        results.sort(key=lambda x: x['relevance'], reverse=True)
        return results[:max_results]
    
    def _extract_snippets(self, content, query, num_snippets=2, context_chars=100):
        """提取包含查詢詞的文本片段"""
        snippets = []
        query_lower = query.lower()
        content_lower = content.lower()
        
        start = 0
        for _ in range(num_snippets):
            pos = content_lower.find(query_lower, start)
            if pos == -1:
                break
            
            snippet_start = max(0, pos - context_chars)
            snippet_end = min(len(content), pos + len(query) + context_chars)
            snippet = content[snippet_start:snippet_end]
            
            if snippet_start > 0:
                snippet = "..." + snippet
            if snippet_end < len(content):
                snippet = snippet + "..."
            
            snippets.append(snippet)
            start = pos + len(query)
        
        return snippets
    
    def get_all_documents(self):
        """獲取所有文檔列表"""
        return list(self.documents.keys())


class MarkdownRenderer:
    """Markdown渲染器"""
    
    @staticmethod
    def render_to_text_widget(text_widget, markdown_text, tags_config):
        """將Markdown文本渲染到Text Widget"""
        lines = markdown_text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 代碼塊
            if line.strip().startswith('```'):
                lang = line.strip()[3:].strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                
                code_text = '\n'.join(code_lines)
                text_widget.insert(tk.END, code_text + '\n', 'code')
                i += 1
                continue
            
            # 標題
            if line.startswith('###'):
                text_widget.insert(tk.END, line[3:].strip() + '\n', 'h3')
            elif line.startswith('##'):
                text_widget.insert(tk.END, line[2:].strip() + '\n', 'h2')
            elif line.startswith('#'):
                text_widget.insert(tk.END, line[1:].strip() + '\n', 'h1')
            # 列表
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                text_widget.insert(tk.END, '  • ' + line.strip()[2:] + '\n', 'list')
            elif re.match(r'^\d+\.', line.strip()):
                text_widget.insert(tk.END, line + '\n', 'list')
            # 行內樣式
            else:
                MarkdownRenderer._render_inline(text_widget, line + '\n', tags_config)
            
            i += 1
    
    @staticmethod
    def _render_inline(text_widget, line, tags_config):
        """處理行內Markdown樣式"""
        # 處理加粗 **text**
        parts = re.split(r'(\*\*.*?\*\*)', line)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                text_widget.insert(tk.END, part[2:-2], 'bold')
            # 處理斜體 *text*
            elif part.startswith('*') and part.endswith('*') and not part.startswith('**'):
                text_widget.insert(tk.END, part[1:-1], 'italic')
            # 處理行內代碼 `code`
            elif '`' in part:
                code_parts = part.split('`')
                for j, code_part in enumerate(code_parts):
                    if j % 2 == 1:  # 奇數索引是代碼
                        text_widget.insert(tk.END, code_part, 'inline_code')
                    else:
                        text_widget.insert(tk.END, code_part)
            else:
                text_widget.insert(tk.END, part)


class ClaudeChatUltimate:
    """終極版Claude聊天界面"""
    
    # 價格配置 (per 1M tokens)
    PRICING = {
        'input': 3.0,
        'output': 15.0,
        'cache_write': 3.75,
        'cache_read': 0.30
    }
    
    # 主題配置
    THEMES = {
        'light': {
            'bg': '#ffffff',
            'fg': '#000000',
            'chat_bg': '#f5f5f5',
            'user_bg': '#e3f2fd',
            'ai_bg': '#f1f8e9',
            'input_bg': '#ffffff',
            'button_bg': '#2196F3',
            'code_bg': '#f5f5f5',
            'accent': '#2196F3'
        },
        'dark': {
            'bg': '#1e1e1e',
            'fg': '#e0e0e0',
            'chat_bg': '#2d2d2d',
            'user_bg': '#1e3a5f',
            'ai_bg': '#2d4a2d',
            'input_bg': '#2d2d2d',
            'button_bg': '#0d47a1',
            'code_bg': '#1e1e1e',
            'accent': '#64b5f6'
        },
        'monokai': {
            'bg': '#272822',
            'fg': '#f8f8f2',
            'chat_bg': '#3e3d32',
            'user_bg': '#49483e',
            'ai_bg': '#3e3d32',
            'input_bg': '#3e3d32',
            'button_bg': '#66d9ef',
            'code_bg': '#23241f',
            'accent': '#a6e22e'
        }
    }
    
    # 字體大小配置
    FONT_SIZES = {
        'small': {'base': 9, 'code': 8, 'title': 11},
        'medium': {'base': 11, 'code': 10, 'title': 13},
        'large': {'base': 13, 'code': 12, 'title': 15}
    }
    
    def __init__(self, root):
        self.root = root
        self.root.title("Claude Chat Ultimate - 終極版")
        self.root.geometry("1200x800")
        
        # 初始化變量
        self.api_key = ""
        self.system_prompt = ""
        self.conversation_history = []
        self.uploaded_images = []
        self.current_theme = 'dark'
        self.current_font_size = 'medium'
        self.background_image_path = None
        self.background_opacity = 0.3
        
        # 統計變量
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_creation_tokens = 0
        self.total_cache_read_tokens = 0
        
        # 知識庫
        self.kb = KnowledgeBase()
        
        # 用戶設置
        self.user_name = "User"
        self.ai_name = "Claude"
        
        # 加載配置
        self.config_file = Path("claude_chat_config.json")
        self.load_config()
        
        # 創建界面
        self.setup_ui()
        
        # 應用主題
        self.apply_theme()
        
        # 應用保存的背景圖片(如果有) - 延遲更長時間確保窗口完全初始化
        if self.background_image_path:
            self.root.after(500, self._apply_background)  # 延遲500ms
        
    def setup_ui(self):
        """設置用戶界面"""
        # 主容器
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 頂部工具欄
        self.create_toolbar(main_frame)
        
        # 創建PanedWindow用於分割界面
        self.paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        # 左側面板 - 設置和知識庫
        left_panel = ttk.Frame(self.paned, width=300)
        self.paned.add(left_panel, weight=1)
        self.create_left_panel(left_panel)
        
        # 右側面板 - 對話區域
        right_panel = ttk.Frame(self.paned)
        self.paned.add(right_panel, weight=3)
        self.create_chat_panel(right_panel)
        
    def create_toolbar(self, parent):
        """創建頂部工具欄"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        # 字體大小選擇
        ttk.Label(toolbar, text="字體:").pack(side=tk.LEFT, padx=5)
        font_combo = ttk.Combobox(toolbar, values=['small', 'medium', 'large'], 
                                   state='readonly', width=8)
        font_combo.set(self.current_font_size)
        font_combo.bind('<<ComboboxSelected>>', self.change_font_size)
        font_combo.pack(side=tk.LEFT, padx=5)
        
        # 主題選擇
        ttk.Label(toolbar, text="主題:").pack(side=tk.LEFT, padx=5)
        theme_combo = ttk.Combobox(toolbar, values=list(self.THEMES.keys()), 
                                    state='readonly', width=10)
        theme_combo.set(self.current_theme)
        theme_combo.bind('<<ComboboxSelected>>', self.change_theme)
        theme_combo.pack(side=tk.LEFT, padx=5)
        
        # 背景設置按鈕
        ttk.Button(toolbar, text="🖼️ 背景", 
                  command=self.set_background).pack(side=tk.LEFT, padx=5)
        
        # 聯網搜索按鈕
        ttk.Button(toolbar, text="🌐 聯網", 
                  command=self.toggle_web_search).pack(side=tk.LEFT, padx=5)
        
        # 導出按鈕
        ttk.Button(toolbar, text="📥 導出", 
                  command=self.show_export_menu).pack(side=tk.LEFT, padx=5)
        
        # 總結對話按鈕
        ttk.Button(toolbar, text="📝 總結", 
                  command=self.summarize_conversation).pack(side=tk.LEFT, padx=5)
        
        # 狀態標籤
        self.web_search_enabled = False
        self.status_label = ttk.Label(toolbar, text="聯網: 關閉", foreground="gray")
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
    def create_left_panel(self, parent):
        """創建左側設置面板"""
        # 使用Notebook創建標籤頁
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 標籤頁1: API設置
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text="API設置")
        self.create_api_settings(api_frame)
        
        # 標籤頁2: 知識庫
        kb_frame = ttk.Frame(notebook)
        notebook.add(kb_frame, text="知識庫")
        self.create_kb_panel(kb_frame)
        
        # 標籤頁3: 個性化
        custom_frame = ttk.Frame(notebook)
        notebook.add(custom_frame, text="個性化")
        self.create_customization_panel(custom_frame)
        
    def create_api_settings(self, parent):
        """創建API設置"""
        # API Key
        ttk.Label(parent, text="OpenRouter API Key:").pack(pady=5, padx=5, anchor=tk.W)
        self.api_key_entry = ttk.Entry(parent, show="*")
        self.api_key_entry.pack(fill=tk.X, padx=5)
        if self.api_key:
            self.api_key_entry.insert(0, self.api_key)
        
        # System Prompt
        ttk.Label(parent, text="System Prompt (會被緩存):").pack(pady=5, padx=5, anchor=tk.W)
        self.system_text = scrolledtext.ScrolledText(parent, height=10, wrap=tk.WORD)
        self.system_text.pack(fill=tk.BOTH, expand=True, padx=5)
        if self.system_prompt:
            self.system_text.insert("1.0", self.system_prompt)
        
        # 保存按鈕
        ttk.Button(parent, text="💾 保存配置", 
                  command=self.save_config).pack(pady=10)
        
    def create_kb_panel(self, parent):
        """創建知識庫面板"""
        # 文檔列表
        ttk.Label(parent, text="知識庫文檔:").pack(pady=5, padx=5, anchor=tk.W)
        
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.kb_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.kb_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.kb_listbox.yview)
        
        self.refresh_kb_list()
        
        # 按鈕
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(button_frame, text="📄 添加文檔", 
                  command=self.add_to_kb).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🔍 測試搜索", 
                  command=self.test_kb_search).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🔄 刷新", 
                  command=self.refresh_kb_list).pack(side=tk.LEFT, padx=2)
        
    def create_customization_panel(self, parent):
        """創建個性化設置面板"""
        # 用戶名設置
        ttk.Label(parent, text="你的名字:").pack(pady=5, padx=5, anchor=tk.W)
        self.user_name_entry = ttk.Entry(parent)
        self.user_name_entry.insert(0, self.user_name)
        self.user_name_entry.pack(fill=tk.X, padx=5)
        
        # AI名字設置
        ttk.Label(parent, text="AI助手名字:").pack(pady=5, padx=5, anchor=tk.W)
        self.ai_name_entry = ttk.Entry(parent)
        self.ai_name_entry.insert(0, self.ai_name)
        self.ai_name_entry.pack(fill=tk.X, padx=5)
        
        # 背景透明度
        ttk.Label(parent, text="背景透明度:").pack(pady=5, padx=5, anchor=tk.W)
        
        # 使用tk.Scale而不是ttk.Scale以獲得連續值
        self.opacity_scale = tk.Scale(parent, from_=0, to=1, resolution=0.01, 
                                      orient=tk.HORIZONTAL,
                                      command=self.update_background_opacity,
                                      length=200)
        self.opacity_scale.set(self.background_opacity)
        self.opacity_scale.pack(fill=tk.X, padx=5)
        
        # 顯示當前透明度值
        self.opacity_value_label = ttk.Label(parent, text=f"當前值: {self.background_opacity:.2f}")
        self.opacity_value_label.pack(pady=2, padx=5, anchor=tk.W)
        
        # 應用按鈕
        ttk.Button(parent, text="✅ 應用設置", 
                  command=self.apply_customization).pack(pady=10)
        
    def create_chat_panel(self, parent):
        """創建對話面板"""
        # 主容器Frame
        main_container = ttk.Frame(parent)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # 對話顯示區 - 使用Frame包裝以支持背景
        chat_container = tk.Frame(main_container)
        chat_container.pack(fill=tk.BOTH, expand=True)
        
        # 創建Canvas作為背景層
        self.bg_canvas = tk.Canvas(chat_container, highlightthickness=0)
        self.bg_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 在Canvas上創建Text Widget
        self.chat_display = tk.Text(self.bg_canvas, wrap=tk.WORD, state=tk.DISABLED)
        
        # 將Text widget放置在Canvas上
        self.canvas_window = self.bg_canvas.create_window(0, 0, anchor='nw', 
                                                           window=self.chat_display)
        
        # 滾動條
        scrollbar = ttk.Scrollbar(chat_container, command=self.chat_display.yview)
        scrollbar.place(relx=1.0, rely=0, relheight=1.0, anchor='ne')
        self.chat_display.config(yscrollcommand=scrollbar.set)
        
        # 綁定resize事件以調整Text widget大小
        def on_canvas_resize(event):
            self.bg_canvas.itemconfig(self.canvas_window, width=event.width, height=event.height)
            # 同時重新應用背景
            if hasattr(self, 'background_image_path') and self.background_image_path:
                self.root.after(10, self._apply_background)
        
        self.bg_canvas.bind('<Configure>', on_canvas_resize)
        
        # 配置文本標籤(會在apply_theme中更新)
        self.configure_text_tags()
        
        # 圖片預覽區
        self.image_preview_frame = ttk.Frame(main_container)
        self.image_preview_frame.pack(fill=tk.X, pady=5)
        
        # 輸入區
        input_frame = ttk.Frame(main_container)
        input_frame.pack(fill=tk.X, pady=5)
        
        # 按鈕行
        button_row = ttk.Frame(input_frame)
        button_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(button_row, text="📎 圖片", 
                  command=self.upload_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row, text="📄 文檔", 
                  command=self.upload_document).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row, text="🗑️ 清除圖片", 
                  command=self.clear_images).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_row, text="🔄 清空對話", 
                  command=self.clear_conversation).pack(side=tk.LEFT, padx=2)
        
        # 輸入框
        self.input_text = scrolledtext.ScrolledText(input_frame, height=4, wrap=tk.WORD)
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.input_text.bind('<Control-Return>', lambda e: self.send_message())
        
        # 發送按鈕
        ttk.Button(input_frame, text="🚀 發送 (Ctrl+Enter)", 
                  command=self.send_message).pack(fill=tk.X)
        
        # 統計信息
        self.stats_label = ttk.Label(main_container, text="等待發送消息...")
        self.stats_label.pack(pady=5)
        
    def configure_text_tags(self):
        """配置文本標籤樣式"""
        sizes = self.FONT_SIZES[self.current_font_size]
        theme = self.THEMES[self.current_theme]
        
        # 基礎字體
        base_font = font.Font(family="Arial", size=sizes['base'])
        code_font = font.Font(family="Courier New", size=sizes['code'])
        
        # 標題
        self.chat_display.tag_config('h1', font=font.Font(family="Arial", size=sizes['title'], weight='bold'))
        self.chat_display.tag_config('h2', font=font.Font(family="Arial", size=sizes['title']-1, weight='bold'))
        self.chat_display.tag_config('h3', font=font.Font(family="Arial", size=sizes['title']-2, weight='bold'))
        
        # 樣式
        self.chat_display.tag_config('bold', font=font.Font(family="Arial", size=sizes['base'], weight='bold'))
        self.chat_display.tag_config('italic', font=font.Font(family="Arial", size=sizes['base'], slant='italic'))
        self.chat_display.tag_config('code', font=code_font, background=theme['code_bg'], 
                                     foreground='#66d9ef')
        self.chat_display.tag_config('inline_code', font=code_font, background=theme['code_bg'])
        self.chat_display.tag_config('list', font=base_font)
        
        # 用戶和AI消息
        self.chat_display.tag_config('user', background=theme['user_bg'], 
                                     foreground=theme['fg'], font=base_font)
        self.chat_display.tag_config('ai', background=theme['ai_bg'], 
                                     foreground=theme['fg'], font=base_font)
        self.chat_display.tag_config('system', foreground='gray', font=base_font)
        
    def apply_theme(self):
        """應用主題"""
        theme = self.THEMES[self.current_theme]
        
        # 配置root背景
        self.root.configure(bg=theme['bg'])
        
        # 配置chat_display
        self.chat_display.config(
            bg=theme['chat_bg'],
            fg=theme['fg'],
            insertbackground=theme['fg']
        )
        
        # 配置input_text
        self.input_text.config(
            bg=theme['input_bg'],
            fg=theme['fg'],
            insertbackground=theme['fg']
        )
        
        # 重新配置標籤
        self.configure_text_tags()
        
    def change_theme(self, event):
        """更改主題"""
        combo = event.widget
        self.current_theme = combo.get()
        self.apply_theme()
        self.save_config()
        
    def change_font_size(self, event):
        """更改字體大小"""
        combo = event.widget
        self.current_font_size = combo.get()
        self.configure_text_tags()
        self.save_config()
        
    def set_background(self):
        """設置背景圖片"""
        if not PIL_AVAILABLE:
            messagebox.showwarning("功能不可用", "需要安裝Pillow庫才能使用背景圖片功能")
            return
        
        filename = filedialog.askopenfilename(
            title="選擇背景圖片",
            filetypes=[("圖片文件", "*.png *.jpg *.jpeg *.gif *.bmp")]
        )
        
        if filename:
            try:
                # 保存背景圖片路徑
                self.background_image_path = filename
                # 立即應用背景圖片
                self.root.after(100, self._apply_background)  # 延遲一點確保對話框已關閉
                messagebox.showinfo("成功", "背景圖片已設置!你可以在個性化標籤調整透明度")
                self.save_config()
            except Exception as e:
                messagebox.showerror("錯誤", f"設置背景失敗: {e}")
    
    def _apply_background(self):
        """應用背景圖片和透明度"""
        if not hasattr(self, 'background_image_path') or not self.background_image_path:
            return
        
        if not PIL_AVAILABLE:
            return
        
        if not hasattr(self, 'bg_canvas'):
            return
        
        try:
            # 加載圖片
            image = Image.open(self.background_image_path)
            
            # 獲取Canvas的尺寸
            width = self.bg_canvas.winfo_width()
            height = self.bg_canvas.winfo_height()
            
            # 如果尺寸太小(窗口還未完全初始化),使用默認值
            if width < 100 or height < 100:
                width = 800
                height = 600
            
            # 調整圖片大小以適應窗口
            image = image.resize((width, height), Image.Resampling.LANCZOS)
            
            # 創建半透明效果
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # 獲取當前主題的背景色
            theme = self.THEMES[self.current_theme]
            bg_color = theme['chat_bg']
            
            # 轉換十六進制顏色為RGB
            bg_rgb = tuple(int(bg_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            
            # 創建背景色圖層
            background = Image.new('RGBA', image.size, bg_rgb + (255,))
            
            # 調整圖片透明度
            alpha = image.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(self.background_opacity)
            image.putalpha(alpha)
            
            # 合成圖片
            combined = Image.alpha_composite(background, image)
            
            # 轉換為RGB
            combined = combined.convert('RGB')
            
            # 保存為PhotoImage
            self.background_photo = ImageTk.PhotoImage(combined)
            
            # 刪除舊的背景圖片(如果有)
            if hasattr(self, 'bg_image_id'):
                self.bg_canvas.delete(self.bg_image_id)
            
            # 在Canvas上創建背景圖片
            self.bg_image_id = self.bg_canvas.create_image(0, 0, anchor='nw', 
                                                           image=self.background_photo)
            
            # 確保背景在最底層
            self.bg_canvas.tag_lower(self.bg_image_id)
            
            # 更新Text widget的背景為透明色(盡可能)
            self.chat_display.config(bg=theme['chat_bg'])
            
        except Exception as e:
            print(f"應用背景失敗: {e}")
            import traceback
            traceback.print_exc()
                
    def update_background_opacity(self, value):
        """更新背景透明度"""
        self.background_opacity = float(value)
        # 更新顯示的透明度值
        if hasattr(self, 'opacity_value_label'):
            self.opacity_value_label.config(text=f"當前值: {self.background_opacity:.2f}")
        # 只在已經有背景圖片時才重新應用
        if hasattr(self, 'background_image_path') and self.background_image_path:
            self._apply_background()
            
    def toggle_web_search(self):
        """切換聯網搜索功能"""
        self.web_search_enabled = not self.web_search_enabled
        status = "開啟" if self.web_search_enabled else "關閉"
        self.status_label.config(text=f"聯網: {status}")
        messagebox.showinfo("聯網搜索", f"聯網搜索已{status}")
        
    def show_export_menu(self):
        """顯示導出菜單"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="導出為Markdown", command=lambda: self.export_conversation('markdown'))
        menu.add_command(label="導出為HTML", command=lambda: self.export_conversation('html'))
        menu.add_command(label="導出為JSON", command=lambda: self.export_conversation('json'))
        
        # 顯示菜單
        menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())
        
    def export_conversation(self, format_type):
        """導出對話"""
        if not self.conversation_history:
            messagebox.showwarning("提示", "沒有對話可以導出")
            return
        
        # 選擇保存位置
        ext = {'markdown': 'md', 'html': 'html', 'json': 'json'}[format_type]
        filename = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=[(f"{format_type.upper()} 文件", f"*.{ext}")]
        )
        
        if not filename:
            return
        
        try:
            if format_type == 'markdown':
                self._export_markdown(filename)
            elif format_type == 'html':
                self._export_html(filename)
            elif format_type == 'json':
                self._export_json(filename)
            
            messagebox.showinfo("成功", f"對話已導出到: {filename}")
        except Exception as e:
            messagebox.showerror("錯誤", f"導出失敗: {e}")
            
    def _export_markdown(self, filename):
        """導出為Markdown"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Claude Chat 對話記錄\n\n")
            f.write(f"導出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            for msg in self.conversation_history:
                role = msg['role']
                content = msg['content']
                
                if isinstance(content, str):
                    f.write(f"## {role.capitalize()}\n\n")
                    f.write(f"{content}\n\n")
                else:
                    # 處理包含圖片的消息
                    f.write(f"## {role.capitalize()}\n\n")
                    for item in content:
                        if item['type'] == 'text':
                            f.write(f"{item['text']}\n\n")
                        elif item['type'] == 'image':
                            f.write(f"[圖片]\n\n")
                            
    def _export_html(self, filename):
        """導出為HTML"""
        theme = self.THEMES[self.current_theme]
        
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Claude Chat 對話記錄</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: {theme['bg']};
            color: {theme['fg']};
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        .message {{
            margin: 20px 0;
            padding: 15px;
            border-radius: 8px;
        }}
        .user {{
            background-color: {theme['user_bg']};
        }}
        .assistant {{
            background-color: {theme['ai_bg']};
        }}
        .role {{
            font-weight: bold;
            margin-bottom: 10px;
        }}
        code {{
            background-color: {theme['code_bg']};
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background-color: {theme['code_bg']};
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <h1>Claude Chat 對話記錄</h1>
    <p>導出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <hr>
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_template)
            
            for msg in self.conversation_history:
                role = msg['role']
                content = msg['content']
                
                role_class = 'user' if role == 'user' else 'assistant'
                f.write(f'<div class="message {role_class}">\n')
                f.write(f'<div class="role">{role.capitalize()}</div>\n')
                
                if isinstance(content, str):
                    # 簡單的Markdown到HTML轉換
                    html_content = content.replace('\n', '<br>')
                    html_content = re.sub(r'```(.*?)```', r'<pre>\1</pre>', html_content, flags=re.DOTALL)
                    html_content = re.sub(r'`([^`]+)`', r'<code>\1</code>', html_content)
                    f.write(f'<div>{html_content}</div>\n')
                else:
                    for item in content:
                        if item['type'] == 'text':
                            html_content = item['text'].replace('\n', '<br>')
                            f.write(f'<div>{html_content}</div>\n')
                        elif item['type'] == 'image':
                            f.write('<div>[圖片]</div>\n')
                
                f.write('</div>\n')
            
            f.write('</body>\n</html>')
            
    def _export_json(self, filename):
        """導出為JSON"""
        data = {
            'export_time': datetime.now().isoformat(),
            'system_prompt': self.system_text.get("1.0", tk.END).strip(),
            'conversation': self.conversation_history,
            'statistics': {
                'total_input_tokens': self.total_input_tokens,
                'total_output_tokens': self.total_output_tokens,
                'total_cache_creation_tokens': self.total_cache_creation_tokens,
                'total_cache_read_tokens': self.total_cache_read_tokens,
                'total_cost': self.calculate_total_cost()
            }
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def summarize_conversation(self):
        """總結對話歷史"""
        if not self.conversation_history:
            messagebox.showwarning("提示", "沒有對話可以總結")
            return
        
        if not self.api_key:
            messagebox.showwarning("提示", "請先設置API Key")
            return
        
        # 構建總結請求
        conversation_text = ""
        for msg in self.conversation_history:
            role = msg['role']
            content = msg['content']
            if isinstance(content, str):
                conversation_text += f"{role}: {content}\n\n"
        
        summary_prompt = f"""請簡潔地總結以下對話的核心內容,提取關鍵信息和重要結論:

{conversation_text}

請用2-3個段落總結,每個段落不超過50字。"""
        
        # 在新線程中執行總結
        def do_summarize():
            try:
                response = self.call_claude_api(summary_prompt, use_cache=False)
                
                # 顯示總結
                self.root.after(0, lambda: self.show_summary(response))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("錯誤", f"總結失敗: {e}"))
        
        threading.Thread(target=do_summarize, daemon=True).start()
        messagebox.showinfo("提示", "正在生成總結,請稍候...")
        
    def show_summary(self, summary):
        """顯示總結結果"""
        # 創建總結窗口
        summary_window = tk.Toplevel(self.root)
        summary_window.title("對話總結")
        summary_window.geometry("600x400")
        
        # 總結文本
        text = scrolledtext.ScrolledText(summary_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert("1.0", summary)
        text.config(state=tk.DISABLED)
        
        # 按鈕
        button_frame = ttk.Frame(summary_window)
        button_frame.pack(fill=tk.X, pady=5)
        
        def replace_history():
            """用總結替換對話歷史"""
            if messagebox.askyesno("確認", "是否用總結替換當前對話歷史?這將清除原有對話但保留總結內容。"):
                self.conversation_history = [
                    {
                        'role': 'user',
                        'content': '請總結我們之前的對話'
                    },
                    {
                        'role': 'assistant',
                        'content': summary
                    }
                ]
                self.refresh_chat_display()
                summary_window.destroy()
                messagebox.showinfo("成功", "已用總結替換對話歷史")
        
        ttk.Button(button_frame, text="✅ 用總結替換歷史", 
                  command=replace_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ 關閉", 
                  command=summary_window.destroy).pack(side=tk.RIGHT, padx=5)
        
    def upload_image(self):
        """上傳圖片"""
        if not PIL_AVAILABLE:
            messagebox.showwarning("功能不可用", "需要安裝Pillow庫才能上傳圖片")
            return
        
        filenames = filedialog.askopenfilenames(
            title="選擇圖片",
            filetypes=[("圖片文件", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")]
        )
        
        for filename in filenames:
            try:
                # 讀取並轉換圖片
                with open(filename, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                # 檢測圖片類型
                ext = Path(filename).suffix.lower()
                media_type = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp',
                    '.webp': 'image/webp'
                }.get(ext, 'image/jpeg')
                
                self.uploaded_images.append({
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': image_data
                    }
                })
                
                # 顯示預覽
                self.show_image_preview(filename)
                
            except Exception as e:
                messagebox.showerror("錯誤", f"讀取圖片失敗: {e}")
                
    def upload_document(self):
        """上傳文檔(PDF或Word)"""
        filename = filedialog.askopenfilename(
            title="選擇文檔",
            filetypes=[
                ("所有支持的文檔", "*.pdf *.docx *.txt *.md"),
                ("PDF文件", "*.pdf"),
                ("Word文檔", "*.docx"),
                ("文本文件", "*.txt *.md")
            ]
        )
        
        if not filename:
            return
        
        try:
            ext = Path(filename).suffix.lower()
            
            if ext == '.pdf':
                text = self.extract_pdf_text(filename)
            elif ext == '.docx':
                text = self.extract_docx_text(filename)
            elif ext in ['.txt', '.md']:
                with open(filename, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                messagebox.showerror("錯誤", "不支持的文檔格式")
                return
            
            if text:
                # 將文檔內容添加到知識庫
                doc_name = Path(filename).name
                if self.kb.add_document(doc_name, text):
                    messagebox.showinfo("成功", f"文檔已添加到知識庫: {doc_name}")
                    self.refresh_kb_list()
                else:
                    messagebox.showerror("錯誤", "添加文檔到知識庫失敗")
            else:
                messagebox.showwarning("警告", "無法從文檔中提取文本")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"處理文檔失敗: {e}")
            
    def extract_pdf_text(self, filename):
        """從PDF提取文本"""
        if not PDF_AVAILABLE:
            messagebox.showwarning("功能不可用", "需要安裝PyPDF2庫才能處理PDF文件")
            return None
        
        try:
            text = ""
            with open(filename, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            messagebox.showerror("錯誤", f"提取PDF文本失敗: {e}")
            return None
            
    def extract_docx_text(self, filename):
        """從Word文檔提取文本"""
        if not DOCX_AVAILABLE:
            messagebox.showwarning("功能不可用", "需要安裝python-docx庫才能處理Word文件")
            return None
        
        try:
            doc = docx.Document(filename)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            messagebox.showerror("錯誤", f"提取Word文本失敗: {e}")
            return None
            
    def show_image_preview(self, filename):
        """顯示圖片預覽"""
        try:
            # 創建預覽標籤
            preview = ttk.Frame(self.image_preview_frame)
            preview.pack(side=tk.LEFT, padx=5)
            
            # 加載並縮放圖片
            img = Image.open(filename)
            img.thumbnail((100, 100))
            photo = ImageTk.PhotoImage(img)
            
            label = ttk.Label(preview, image=photo)
            label.image = photo  # 保持引用
            label.pack()
            
            # 文件名
            name = Path(filename).name
            if len(name) > 15:
                name = name[:12] + "..."
            ttk.Label(preview, text=name).pack()
            
        except Exception as e:
            print(f"顯示預覽失敗: {e}")
            
    def clear_images(self):
        """清除已上傳的圖片"""
        self.uploaded_images.clear()
        for widget in self.image_preview_frame.winfo_children():
            widget.destroy()
        messagebox.showinfo("提示", "已清除所有圖片")
        
    def add_to_kb(self):
        """添加文檔到知識庫"""
        # 讓用戶輸入文本或選擇文件
        choice = messagebox.askquestion("添加文檔", "是否從文件添加?\n(否則手動輸入文本)")
        
        if choice == 'yes':
            self.upload_document()
        else:
            # 創建輸入窗口
            input_window = tk.Toplevel(self.root)
            input_window.title("添加文檔到知識庫")
            input_window.geometry("600x400")
            
            ttk.Label(input_window, text="文檔名稱:").pack(pady=5)
            name_entry = ttk.Entry(input_window)
            name_entry.pack(fill=tk.X, padx=10)
            
            ttk.Label(input_window, text="文檔內容:").pack(pady=5)
            text_widget = scrolledtext.ScrolledText(input_window, height=15)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10)
            
            def save_doc():
                name = name_entry.get().strip()
                content = text_widget.get("1.0", tk.END).strip()
                
                if not name or not content:
                    messagebox.showwarning("警告", "請填寫文檔名稱和內容")
                    return
                
                if not name.endswith('.txt'):
                    name += '.txt'
                
                if self.kb.add_document(name, content):
                    messagebox.showinfo("成功", f"文檔已添加: {name}")
                    self.refresh_kb_list()
                    input_window.destroy()
                else:
                    messagebox.showerror("錯誤", "添加文檔失敗")
            
            ttk.Button(input_window, text="💾 保存", command=save_doc).pack(pady=10)
            
    def test_kb_search(self):
        """測試知識庫搜索"""
        query = tk.simpledialog.askstring("測試搜索", "輸入搜索關鍵詞:")
        if not query:
            return
        
        results = self.kb.search(query)
        
        if not results:
            messagebox.showinfo("搜索結果", "沒有找到相關文檔")
            return
        
        # 顯示結果
        result_window = tk.Toplevel(self.root)
        result_window.title("搜索結果")
        result_window.geometry("700x500")
        
        text = scrolledtext.ScrolledText(result_window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text.insert("1.0", f"搜索: {query}\n\n")
        text.insert(tk.END, f"找到 {len(results)} 個相關文檔:\n\n")
        
        for i, result in enumerate(results, 1):
            text.insert(tk.END, f"{'='*60}\n")
            text.insert(tk.END, f"{i}. {result['filename']} (相關度: {result['relevance']})\n")
            text.insert(tk.END, f"路徑: {result['path']}\n\n")
            
            for snippet in result['snippets']:
                text.insert(tk.END, f"  {snippet}\n\n")
        
        text.config(state=tk.DISABLED)
        
    def refresh_kb_list(self):
        """刷新知識庫列表"""
        self.kb_listbox.delete(0, tk.END)
        for doc_name in self.kb.get_all_documents():
            self.kb_listbox.insert(tk.END, doc_name)
            
    def apply_customization(self):
        """應用個性化設置"""
        self.user_name = self.user_name_entry.get().strip() or "User"
        self.ai_name = self.ai_name_entry.get().strip() or "Claude"
        self.background_opacity = self.opacity_scale.get()
        
        self.save_config()
        messagebox.showinfo("成功", "設置已保存")
        
    def send_message(self):
        """發送消息"""
        message = self.input_text.get("1.0", tk.END).strip()
        if not message:
            return
        
        if not self.api_key:
            messagebox.showwarning("警告", "請先設置API Key")
            return
        
        # 清空輸入框
        self.input_text.delete("1.0", tk.END)
        
        # 構建消息內容
        content = []
        
        # 添加圖片
        if self.uploaded_images:
            content.extend(self.uploaded_images)
        
        # 檢查是否需要搜索知識庫
        if self.kb.documents:
            kb_results = self.kb.search(message)
            if kb_results:
                kb_context = "相關知識庫內容:\n\n"
                for result in kb_results:
                    kb_context += f"來源: {result['filename']}\n"
                    for snippet in result['snippets']:
                        kb_context += f"{snippet}\n"
                    kb_context += "\n"
                
                content.append({
                    'type': 'text',
                    'text': f"{kb_context}\n---\n用戶問題: {message}"
                })
            else:
                content.append({'type': 'text', 'text': message})
        else:
            content.append({'type': 'text', 'text': message})
        
        # 添加到對話歷史
        user_message = {
            'role': 'user',
            'content': content if len(content) > 1 else message
        }
        self.conversation_history.append(user_message)
        
        # 顯示用戶消息
        self.display_message(self.user_name, message, is_user=True)
        
        # 清除圖片
        self.uploaded_images.clear()
        for widget in self.image_preview_frame.winfo_children():
            widget.destroy()
        
        # 在新線程中調用API
        threading.Thread(target=self.get_response, daemon=True).start()
        
    def get_response(self):
        """獲取AI響應"""
        try:
            response_text = self.call_claude_api(None)
            
            # 添加到對話歷史
            self.conversation_history.append({
                'role': 'assistant',
                'content': response_text
            })
            
            # 在主線程中更新UI
            self.root.after(0, lambda: self.display_message(self.ai_name, response_text, is_user=False))
            
        except Exception as e:
            error_msg = f"API調用失敗: {e}"
            self.root.after(0, lambda: messagebox.showerror("錯誤", error_msg))
            
    def call_claude_api(self, single_message=None, use_cache=True):
        """調用Claude API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # 如果啟用了Prompt Caching,添加beta header
        if use_cache:
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"
        
        # 構建消息
        if single_message:
            messages = [{'role': 'user', 'content': single_message}]
        else:
            messages = self.conversation_history.copy()
        
        # 構建System Prompt
        system_prompt = self.system_text.get("1.0", tk.END).strip()
        system_content = []
        
        if system_prompt:
            system_content.append({
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"} if use_cache else None
            })
        
        # 如果啟用聯網搜索,添加提示
        if self.web_search_enabled:
            system_content.append({
                "type": "text",
                "text": "\n你有聯網搜索能力,可以搜索實時信息。如果需要最新信息,請告訴用戶你正在搜索。"
            })
        
        data = {
            "model": "anthropic/claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "messages": messages
        }
        
        if system_content:
            data["system"] = system_content
        
        # 發送請求
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            raise Exception(f"API返回錯誤: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # 提取響應文本
        response_text = result['choices'][0]['message']['content']
        
        # 更新統計(如果有usage信息)
        if 'usage' in result:
            usage = result['usage']
            input_tokens = usage.get('prompt_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0)
            cache_creation = usage.get('cache_creation_input_tokens', 0)
            cache_read = usage.get('cache_read_input_tokens', 0)
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cache_creation_tokens += cache_creation
            self.total_cache_read_tokens += cache_read
            
            # 更新統計顯示
            self.root.after(0, self.update_stats)
        
        return response_text
        
    def display_message(self, sender, message, is_user=False):
        """顯示消息"""
        self.chat_display.config(state=tk.NORMAL)
        
        # 添加發送者標籤
        tag = 'user' if is_user else 'ai'
        self.chat_display.insert(tk.END, f"\n{sender}:\n", tag)
        
        # 渲染消息內容
        if is_user:
            self.chat_display.insert(tk.END, message + "\n", tag)
        else:
            # 使用Markdown渲染器
            MarkdownRenderer.render_to_text_widget(
                self.chat_display, 
                message,
                None
            )
            self.chat_display.insert(tk.END, "\n")
        
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        
    def refresh_chat_display(self):
        """刷新整個對話顯示"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        
        for msg in self.conversation_history:
            role = msg['role']
            content = msg['content']
            
            sender = self.user_name if role == 'user' else self.ai_name
            is_user = (role == 'user')
            
            if isinstance(content, str):
                self.display_message(sender, content, is_user)
            else:
                # 處理包含多個部分的消息
                text_parts = [item['text'] for item in content if item['type'] == 'text']
                if text_parts:
                    self.display_message(sender, '\n'.join(text_parts), is_user)
        
        self.chat_display.config(state=tk.DISABLED)
        
    def update_stats(self):
        """更新統計信息"""
        total_cost = self.calculate_total_cost()
        cost_without_cache = self.calculate_cost_without_cache()
        saved = cost_without_cache - total_cost
        saved_percent = (saved / cost_without_cache * 100) if cost_without_cache > 0 else 0
        
        stats_text = (
            f"💰 總成本: ${total_cost:.4f} | "
            f"💸 節省: ${saved:.4f} ({saved_percent:.1f}%) | "
            f"📊 Input: {self.total_input_tokens} | Output: {self.total_output_tokens} | "
            f"Cache: {self.total_cache_read_tokens}"
        )
        
        self.stats_label.config(text=stats_text)
        
    def calculate_total_cost(self):
        """計算總成本"""
        cost = (
            (self.total_input_tokens / 1_000_000) * self.PRICING['input'] +
            (self.total_output_tokens / 1_000_000) * self.PRICING['output'] +
            (self.total_cache_creation_tokens / 1_000_000) * self.PRICING['cache_write'] +
            (self.total_cache_read_tokens / 1_000_000) * self.PRICING['cache_read']
        )
        return cost
        
    def calculate_cost_without_cache(self):
        """計算不使用緩存的成本"""
        total_input = self.total_input_tokens + self.total_cache_creation_tokens + self.total_cache_read_tokens
        cost = (
            (total_input / 1_000_000) * self.PRICING['input'] +
            (self.total_output_tokens / 1_000_000) * self.PRICING['output']
        )
        return cost
        
    def clear_conversation(self):
        """清空對話"""
        if messagebox.askyesno("確認", "確定要清空對話嗎?"):
            self.conversation_history.clear()
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.config(state=tk.DISABLED)
            messagebox.showinfo("完成", "對話已清空")
            
    def save_config(self):
        """保存配置"""
        config = {
            'api_key': self.api_key_entry.get(),
            'system_prompt': self.system_text.get("1.0", tk.END).strip(),
            'theme': self.current_theme,
            'font_size': self.current_font_size,
            'user_name': self.user_name,
            'ai_name': self.ai_name,
            'background_opacity': self.background_opacity,
            'background_image_path': self.background_image_path if hasattr(self, 'background_image_path') else None
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 更新當前API key
        self.api_key = config['api_key']
        
        messagebox.showinfo("成功", "配置已保存")
        
    def load_config(self):
        """加載配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.api_key = config.get('api_key', '')
                self.system_prompt = config.get('system_prompt', '')
                self.current_theme = config.get('theme', 'dark')
                self.current_font_size = config.get('font_size', 'medium')
                self.user_name = config.get('user_name', 'User')
                self.ai_name = config.get('ai_name', 'Claude')
                self.background_opacity = config.get('background_opacity', 0.3)
                self.background_image_path = config.get('background_image_path', None)
            except Exception as e:
                print(f"加載配置失敗: {e}")


def main():
    root = tk.Tk()
    app = ClaudeChatUltimate(root)
    root.mainloop()


if __name__ == "__main__":
    main()
