#!/usr/bin/env python3
"""On-demand Windows quota window; data comes from the existing Python reader."""
import ctypes
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'workruns' / 'windows-quota-config.json'
OWNER = 'Codex Pet Atelier Windows Quota v2.1'
WINDOW_TITLE = 'Codex Pet Atelier · Quota'


def single_instance():
    """A second launch asks this app's existing window to close, without a global hook."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    user.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user.FindWindowW.restype = ctypes.c_void_p
    user.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    ctypes.set_last_error(0)
    handle = kernel.CreateMutexW(None, False, 'Local\\CodexPetAtelierQuotaV21')
    if not handle:
        raise OSError('无法建立额度窗口的单实例锁。')
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        window = user.FindWindowW(None, WINDOW_TITLE)
        if window:
            user.PostMessageW(window, 0x0010, 0, 0)  # WM_CLOSE, only to this window.
        kernel.CloseHandle(handle)
        return None
    return (kernel, handle)


def terminate_tree(process):
    """Stop only our reader and its app-server child when the window closes."""
    if process.poll() is not None:
        return
    system_root = os.environ.get('SystemRoot', r'C:\Windows')
    taskkill = str(Path(system_root) / 'System32' / 'taskkill.exe')
    try:
        result = subprocess.run([taskkill, '/PID', str(process.pid), '/T', '/F'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=5, check=False,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode and process.poll() is None:
            process.terminate()
    except (OSError, subprocess.SubprocessError):
        if process.poll() is None:
            process.terminate()


def load_config():
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('owner') != OWNER or data.get('ui') != str(Path(__file__).resolve()):
        raise ValueError('配置不可用，请重新运行 Windows 安装命令。')
    return data


def local_time(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return '未提供'
    try:
        return datetime.fromtimestamp(value).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
    except (ValueError, OSError, OverflowError):
        return '未提供'


def duration(value):
    if value == 300:
        return '5 小时'
    if value == 10080:
        return '每周'
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return f'{value:g} 分钟'
    return '窗口时长未提供'


def dark_mode():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            return winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0
    except OSError:
        return False


class QuotaWindow:
    def __init__(self, tk, ttk, root, config):
        self.tk, self.ttk, self.root, self.config = tk, ttk, root, config
        self.lock = threading.Lock()
        self.process = None
        self.closing = False
        self.results = queue.Queue()
        dark = dark_mode()
        self.bg, self.fg, self.muted = (('#252432', '#f1edf7', '#bbb4c7') if dark
                                         else ('#faf8fb', '#28283d', '#756e80'))
        self.accent = '#a899c1'
        root.title(WINDOW_TITLE)
        root.configure(background=self.bg)
        root.attributes('-topmost', True)
        root.minsize(300, 240)
        width = min(380, max(300, root.winfo_screenwidth() - 32))
        height = min(500, max(240, root.winfo_screenheight() - 80))
        root.geometry(f'{width}x{height}+{max(0, root.winfo_screenwidth()-width-20)}+35')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Escape>', lambda _event: self.close())
        top = tk.Frame(root, bg=self.bg)
        top.pack(fill='x', padx=18, pady=(16, 4))
        tk.Label(top, text='Codex 额度', bg=self.bg, fg=self.fg,
                 font=('Segoe UI', 14, 'bold')).pack(side='left')
        tk.Button(top, text='×', command=self.close, bg=self.bg, fg=self.fg,
                  relief='flat', font=('Segoe UI', 16), takefocus=True).pack(side='right')
        tk.Label(root, text='来自官方 App Server', bg=self.bg, fg=self.muted,
                 font=('Segoe UI', 9)).pack(anchor='w', padx=18)
        tk.Label(root, text='安装时快捷键：' + config.get('hotkey', 'CTRL+ALT+Q') + '（以系统设置为准）',
                 bg=self.bg, fg=self.muted, font=('Segoe UI', 9)).pack(anchor='w', padx=18, pady=(6, 0))
        self.canvas = tk.Canvas(root, bg=self.bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True, padx=18, pady=8)
        self.body = tk.Frame(self.canvas, bg=self.bg)
        self.body_id = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda event: self.canvas.itemconfigure(self.body_id, width=event.width))
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Quota.Horizontal.TProgressbar', troughcolor=('#3b3948' if dark else '#e9e6ee'),
                        background=self.accent, borderwidth=0, lightcolor=self.accent, darkcolor=self.accent)
        actions = tk.Frame(root, bg=self.bg)
        actions.pack(fill='x', padx=18, pady=(0, 16))
        self.retry = tk.Button(actions, text='重试', command=self.start, takefocus=True)
        self.retry.pack(side='left', padx=(0, 6))
        tk.Button(actions, text='快捷键设置', command=self.help, takefocus=True).pack(side='left')
        tk.Button(actions, text='关闭', command=self.close, takefocus=True).pack(side='right')
        self.message('正在查询额度…')
        root.after(50, self.start)
        root.after(100, self.check_result)

    def label(self, text, bold=False, muted=False):
        label = self.tk.Label(self.body, text=text, bg=self.bg, fg=self.muted if muted else self.fg,
                              font=('Segoe UI', 10, 'bold' if bold else 'normal'),
                              anchor='w', justify='left', wraplength=320)
        label.pack(fill='x', pady=(2, 3))

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()

    def message(self, text):
        self.clear()
        self.label(text)

    def render(self, data):
        self.clear()
        if data.get('status') != 'ok':
            self.label('未获取额度', bold=True)
            self.label(data.get('message') or '请检查 Codex CLI 和登录状态后重试。', muted=True)
            return
        allowed = data.get('ordinaryUsageAllowed')
        self.label('正常使用：' + ('允许' if allowed is True else '暂不允许' if allowed is False else '状态未提供'), muted=True)
        for bucket in data.get('buckets', []):
            self.label(bucket.get('name') or bucket.get('id') or '额度桶', bold=True)
            if bucket.get('rateLimitReachedType'):
                self.label('限制状态：' + str(bucket['rateLimitReachedType']), muted=True)
            for item in bucket.get('windows', []):
                remaining, used = item.get('remainingPercent'), item.get('usedPercent')
                left = f'{remaining:g}%' if isinstance(remaining, (int, float)) and not isinstance(remaining, bool) else '未提供'
                spent = f'{used:g}%' if isinstance(used, (int, float)) and not isinstance(used, bool) else '未提供'
                self.label(f"{duration(item.get('durationMins'))}　剩余 {left}")
                if isinstance(remaining, (int, float)) and not isinstance(remaining, bool):
                    self.ttk.Progressbar(self.body, style='Quota.Horizontal.TProgressbar',
                                         maximum=100, value=max(0, min(100, remaining))).pack(fill='x', pady=3)
                self.label(f"已用 {spent} · 重置 {local_time(item.get('resetsAt'))}", muted=True)
            credits = bucket.get('credits')
            if isinstance(credits, dict):
                parts = []
                if 'balance' in credits: parts.append('余额 ' + str(credits['balance']))
                if 'hasCredits' in credits: parts.append('有积分：' + ('是' if credits['hasCredits'] else '否'))
                if 'unlimited' in credits: parts.append('无限：' + ('是' if credits['unlimited'] else '否'))
                if parts: self.label('额外积分：' + ' · '.join(parts), muted=True)
        if data.get('resetCreditsAvailable') is not None:
            self.label('可用额度重置次数：' + str(data['resetCreditsAvailable']), muted=True)
        try:
            fetched = datetime.fromisoformat(data['fetchedAt'].replace('Z', '+00:00')).astimezone()
            stamp = fetched.strftime('%Y-%m-%d %H:%M:%S %Z')
        except (KeyError, ValueError, AttributeError):
            stamp = '未提供'
        self.label('查询时间：' + stamp, muted=True)
        self.label('比例不代表剩余消息数。', muted=True)

    def start(self):
        with self.lock:
            if self.process is not None or self.closing:
                return
            self.process = 'starting'
        self.message('正在查询额度…')
        self.retry.configure(state='disabled')
        # Keep the worker alive until a close during process creation is cleaned up.
        threading.Thread(target=self.query).start()

    def query(self):
        process = None
        result = {'status': 'error', 'message': '无法启动额度查询器，请检查 Python 和 Codex CLI。'}
        try:
            cmd = [self.config['python'], str(ROOT / 'scripts/codex_usage.py'), '--json', '--timeout', '15']
            if self.config.get('codexCLI'):
                cmd.extend(['--codex-cli', self.config['codexCLI']])
            env = os.environ.copy()
            if self.config.get('codexHome'):
                env['CODEX_HOME'] = self.config['codexHome']
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       text=True, encoding='utf-8', errors='replace', env=env,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            with self.lock:
                self.process = process
                closing = self.closing
            if closing:
                terminate_tree(process)
                return
            try:
                output, _ = process.communicate(timeout=24)
                parsed = json.loads(output)
                if not isinstance(parsed, dict):
                    raise ValueError('invalid response')
                result = parsed
            except subprocess.TimeoutExpired:
                terminate_tree(process)
                result = {'status': 'error', 'message': '额度查询超时，请重试。'}
            except (ValueError, json.JSONDecodeError):
                result = {'status': 'error', 'message': '额度查询响应无效，请检查 CLI 版本后重试。'}
        except (OSError, KeyError):
            result = {'status': 'error', 'message': '无法启动额度查询器，请检查 Python 和 Codex CLI。'}
        finally:
            with self.lock:
                self.process = None
                closing = self.closing
            if not closing:
                self.results.put(result)

    def check_result(self):
        try:
            result = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.finish(result)
        if not self.closing:
            self.root.after(100, self.check_result)

    def finish(self, result):
        if not self.closing:
            self.retry.configure(state='normal')
            self.render(result)

    def help(self):
        path = ROOT / 'docs/WINDOWS_QUOTA_HOTKEY.md'
        try:
            os.startfile(str(path))
        except OSError:
            from tkinter import messagebox
            messagebox.showinfo('快捷键设置', '请打开工具目录中的 docs/WINDOWS_QUOTA_HOTKEY.md。')

    def close(self):
        with self.lock:
            self.closing = True
            process = self.process
        if process is not None and process != 'starting':
            terminate_tree(process)
        self.root.destroy()


def main():
    if sys.platform != 'win32':
        print('Windows quota window requires Windows.', file=sys.stderr)
        return 1
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        ctypes.windll.user32.MessageBoxW(None, 'Python 未安装 Tk，请安装包含 Tk 的 Python。', WINDOW_TITLE, 0x10)
        return 1
    instance = single_instance()
    if instance is None:
        return 0
    kernel, handle = instance
    try:
        try:
            config = load_config()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            ctypes.windll.user32.MessageBoxW(None, str(exc), WINDOW_TITLE, 0x10)
            return 1
        root = tk.Tk()
        QuotaWindow(tk, ttk, root, config)
        root.mainloop()
        return 0
    finally:
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    raise SystemExit(main())
