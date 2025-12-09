import wx
import wx.lib.mixins.listctrl as listmix
import time
import json
import os
import wget
import socket
import re
import csv
import UnityPy
from PIL import Image
from urllib.parse import urljoin
from wx.lib.delayedresult import startWorker
import threading
import portalocker
import socks
import re

NEW_AZHASH_TYPE = wx.NewEventType()
NEW_AZHASH = wx.PyEventBinder(NEW_AZHASH_TYPE, 1)

class NewAzhashEvent(wx.PyCommandEvent):
    '''监控消息类'''
    def __init__(self, data):
        super().__init__(NEW_AZHASH_TYPE, wx.ID_ANY)
        self.data = data

class LogTextCtrl(wx.TextCtrl):
    """自定义文本控件用于显示日志"""
    def __init__(self, parent):
        super().__init__(parent, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.TE_RICH2)
        self.SetBackgroundColour(wx.Colour(240, 240, 240))
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(font)
    
    def append_log(self, message):
        """添加日志消息"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp}: {message}\n"
        self.AppendText(log_message)
        self.ShowPosition(self.GetLastPosition())

class AzHashListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """azhash_file列表控件"""
    def __init__(self, parent, title):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        self.title = title
        self.setup_columns()
        
    def setup_columns(self):
        """设置列"""
        self.InsertColumn(0, "资源版本", width=150)
        self.InsertColumn(1, "获取时间", width=150)
        
    def add_item(self, id, version, time):
        """添加项目到列表"""
        index = self.InsertItem(self.GetItemCount(), str(id))
        self.SetItem(index, 0, version)
        self.SetItem(index, 1, time)
        return index

class BgListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    """bg_file列表控件"""
    def __init__(self, parent, title):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        self.title = title
        self.setup_columns()
        
    def setup_columns(self):
        """设置列"""
        self.InsertColumn(0, "资源名", width=200)
        self.InsertColumn(1, "MD5", width=250)
        self.InsertColumn(2, "新资源", width=60)
        self.InsertColumn(3, "下载", width=60)
        self.InsertColumn(4, "资源版本", width=70)
        
    def add_item(self, id: int, name:str, md5: str, ifnew: bool, ifdl: bool, version: str):
        """添加项目到列表"""
        index = self.InsertItem(self.GetItemCount(), str(id))
        self.SetItem(index, 0, name)
        self.SetItem(index, 1, md5)
        if ifnew:
            self.SetItem(index, 2, "新资源")
        else:
            self.SetItem(index, 2, "旧资源")
        if ifdl:
            self.SetItem(index, 3, "已下载")
        else:
            self.SetItem(index, 3, "未下载")
        self.SetItem(index, 4, version)
    
        return index

class ImageViewer(wx.Frame):
    def __init__(self, parent, title, imgs):
        super(ImageViewer, self).__init__(parent, title=title, size=(800, 600))
        
        self.imgs = imgs
        self.current_index = 0
        
        self.init_ui()
        wx.CallAfter(self.load_image)
        
        self.Centre()
        self.Show()
        
        # 绑定窗口大小变化事件
        self.Bind(wx.EVT_SIZE, self.on_size)
        
    def init_ui(self):
        # 创建面板
        panel = wx.Panel(self)
        
        # 创建垂直布局
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # 创建图片显示区域，并设置初始最小大小
        self.image_ctrl = wx.StaticBitmap(panel)
        # 设置图片显示区域的最小大小，确保初始时有足够的空间显示图片
        self.image_ctrl.SetMinSize((700, 500))
        
        vbox.Add(self.image_ctrl, proportion=1, flag=wx.EXPAND|wx.ALL, border=10)
        
        # 创建按钮区域
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.prev_btn = wx.Button(panel, label="上一张")
        self.next_btn = wx.Button(panel, label="下一张")
        
        self.prev_btn.Bind(wx.EVT_BUTTON, self.on_prev)
        self.next_btn.Bind(wx.EVT_BUTTON, self.on_next)
        
        hbox.Add(self.prev_btn, flag=wx.RIGHT, border=10)
        hbox.Add(self.next_btn, flag=wx.LEFT, border=10)
        
        vbox.Add(hbox, flag=wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, border=10)
        
        panel.SetSizer(vbox)
        
    def load_image(self):
            
        # 使用PIL打开图片
        pil_image = self.imgs[self.current_index]['data']
        
        # 获取图片显示区域的大小
        display_size = self.image_ctrl.GetSize()
        # 如果显示区域大小无效，使用默认大小
        if display_size.width <= 10 or display_size.height <= 10:
            display_size = wx.Size(700, 500)
        
        # 计算缩放比例，保持宽高比
        img_width, img_height = pil_image.size
        display_width, display_height = display_size.width, display_size.height
        
        width_ratio = display_width / img_width
        height_ratio = display_height / img_height
        scale_ratio = min(width_ratio, height_ratio)
        
        new_width = int(img_width * scale_ratio)
        new_height = int(img_height * scale_ratio)
        
        # 缩放图片
        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 转换为wxPython可用的图像
        wx_image = wx.Image(new_width, new_height)
        wx_image.SetData(pil_image.convert("RGB").tobytes())
        
        # 显示图片
        self.image_ctrl.SetBitmap(wx_image.ConvertToBitmap())
        self.image_ctrl.Refresh()  # 强制刷新显示
        
        # 更新按钮状态
        self.prev_btn.Enable(self.current_index > 0)
        self.next_btn.Enable(self.current_index < len(self.imgs) - 1)
        
        # 更新窗口标题显示当前图片信息
        self.SetTitle(f"图片查看器 - {self.current_index + 1}/{len(self.imgs)} - {self.imgs[self.current_index]['name']} - {self.imgs[self.current_index]['container']}")
        
    def on_prev(self, event):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_image()
            
    def on_next(self, event):
        if self.current_index < len(self.imgs) - 1:
            self.current_index += 1
            self.load_image()
            
    def on_size(self, event):
        # 窗口大小改变时重新加载图片以适应新的大小
        self.load_image()
        event.Skip()

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="TEST", size=(1200, 800))
        self.panel = wx.Panel(self)
        
        # 创建主布局
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # 创建左侧面板（包含两个列表和日志）
        left_panel = wx.Panel(self.panel)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 创建列表区域
        list_panel = wx.Panel(left_panel)
        list_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # 创建第一个列表
        self.azhash_list = AzHashListCtrl(list_panel, "Azhash List")
        list_sizer.Add(self.azhash_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # 创建第二个列表
        self.bg_list = BgListCtrl(list_panel, "Bg List")
        list_sizer.Add(self.bg_list, 2, wx.EXPAND | wx.ALL, 5)
        
        list_panel.SetSizer(list_sizer)
        list_panel.SetMinSize((-1, 300))
        
        # 创建日志区域
        self.log_text = LogTextCtrl(left_panel)
        
        # 将列表和日志添加到左侧sizer
        left_sizer.Add(list_panel, 2, wx.EXPAND)
        left_sizer.Add(self.log_text, 1, wx.EXPAND | wx.ALL, 5)
        
        left_panel.SetSizer(left_sizer)
        
        # 创建右侧按钮面板
        right_panel = wx.Panel(self.panel)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 创建按钮
        buttons = [
            # ("开始监控最新资源列表", self.on_auto_renew_azhash),
            ("手动获取最新资源列表", self.on_manual_renew_azhash),
            ("导入指定资源列表", self.on_manual_input_azhash),
            ("下载选中资源", self.on_download_bg),
            ("导出选中资源", self.on_export_bg),
            ("删除选中资源", self.on_delete_azhash),
            ("打开工作目录", self.on_open_work_dir),
            # ("导出日志", self.on_export_log),
            ("退出", self.on_exit)
        ]
        
        for label, handler in buttons:
            btn = wx.Button(right_panel, label=label)
            btn.Bind(wx.EVT_BUTTON, handler)
            right_sizer.Add(btn, 0, wx.EXPAND | wx.ALL, 5)
        
        right_panel.SetSizer(right_sizer)
        right_panel.SetMinSize((150, -1))
        
        # 将左右面板添加到主sizer
        main_sizer.Add(left_panel, 1, wx.EXPAND)
        main_sizer.Add(right_panel, 0, wx.EXPAND)
        
        self.panel.SetSizer(main_sizer)
        
        self.on_initialize_program()
        
        # 添加状态栏
        self.CreateStatusBar()
        self.SetStatusText("Powered by love_the_lover@outlook.com")
        
        # 绑定事件
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_click_azhash_list, self.azhash_list)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_double_click_bg_list, self.bg_list)
        self.Bind(NEW_AZHASH, self.event_download_azhash)
        self.Bind(wx.EVT_CLOSE, self.on_exit)
        
        # self.log_text.append_log("启动成功")
        self.auto_renew_stop_event = threading.Event()

        self.Centre()
        self.Show()
    
    def read_data(self):
        '''读取历史数据文件 data.json'''
        with portalocker.Lock(os.path.join(os.getcwd(), 'data.json'), mode="r", timeout=60) as azhash_file:
            azhash_data = json.load(azhash_file)
        return azhash_data

    def save_data(self, azhash_data):
        '''写入历史数据文件 data.json'''
        with portalocker.Lock(os.path.join(os.getcwd(), 'data.json'), mode="w", timeout=60) as azhash_file:
            json.dump(azhash_data, azhash_file)
    
    def send_tcp_request(self, server_ip: str, server_port: int, hex_message: str) -> bytes:
        '''发送tcp请求'''
        # if len(proxy):
        #     proxy_ip = proxy['ip']
        #     proxy_port = proxy['port']

        #     socks.set_default_proxy(socks.SOCKS5, proxy_ip, proxy_port)
        #     socket.socket = socks.socksocket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((server_ip, server_port))

        message_bytes = bytes.fromhex(hex_message)

        s.sendall(message_bytes)
        data = s.recv(1024)
        s.close()
        
        return data

    def extract_version_regex(self, azhash_name: str):
        '''提取hash文件名中的资源版本号'''
        # 匹配 $数字$数字$数字 的模式
        pattern = r'\$(\d+)\$(\d+)\$(\d+)\$'
        match = re.search(pattern, azhash_name)
        
        if match:
            return '.'.join(match.groups())
        else:
            return None
    
    def extract_textures_from_unity_file(self, file_path: str):
        """从资源文件中解析PIL图片数据和信息"""
        env = UnityPy.load(file_path)
        imgs = []
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                data = obj.read()
                img = {
                    'data': data.image,
                    'name': data.m_Name,
                    'width': data.m_Width,
                    'height': data.m_Height,
                    'container': obj.container
                }
                imgs.append(img)
        return imgs

    def on_show_yesno_dialog(self, content: str):
        '''弹出是否选择对话框'''
        dialog = wx.MessageDialog(
            self, content, "请确认", 
            wx.YES_NO | wx.ICON_QUESTION | wx.CANCEL
        )
        
        result = dialog.ShowModal()
        
        dialog.Destroy()
        return result
    
    def on_show_input_dialog(self, content: str):
        '''弹出输入对话框'''
        dialog = wx.TextEntryDialog(self, content, "请输入")
        result = dialog.ShowModal()
        user_input = dialog.GetValue()

        return {
            'code': result,
            'input': user_input.strip()
        }
   
    def validate_azhash_input(self, input_str):
        """
        验证用户输入的azhash格式
        格式：$azhash$9$1$187$c3b3f06560d1eb2d
        """
        
        # 检查输入是否为空
        if not input_str:
            return False
        
        # 检查是否以$开头
        if not input_str.startswith('$'):
            return False
        
        # 使用$分割字符串
        parts = input_str.split('$')
        
        # 分割后应该有6个部分（包括开头的空字符串）
        if len(parts) != 6:
            return False
        
        # 提取各个部分
        _, azhash, part1, part2, part3, final_part = parts
        
        # 检查第一部分是否为"azhash"
        if azhash != "azhash":
            return False
        
        # 检查第2-4部分是否为纯数字
        numeric_parts = [part1, part2, part3]
        for i, part in enumerate(numeric_parts, 2):
            if not part.isdigit():
                return False
        
        # 检查最后一部分是否为16位数字和小写字母混合
        if len(final_part) != 16:
            return False
        
        if not re.match(r'^[a-z0-9]{16}$', final_part):
            return False
        
        return True

    def on_show_alert_dialog(self, content: str):
        '''弹出信息提示框'''
        dialog = wx.MessageDialog(
            self, content, "请确认", 
            wx.OK | wx.ICON_INFORMATION
        )
                
        result = dialog.ShowModal()
        
        dialog.Destroy()
        return result

    def on_initialize_program(self):
        '''事件:程序初始化'''
        startWorker(self.ui_refresh_azhash_list, self.initialize_program)

    def initialize_program(self) -> dict:
        '''工作线程:程序初始化'''

        # 检测data.json是否存在
        data_file_path = os.path.join(os.getcwd(), 'data.json')
        if not os.path.exists(data_file_path):
            self.save_data({
                'azhash':[],
                'bghash':[]
            })

        azhash_data = self.read_data()
        message = '程序初始化完成'
        return {
            'code': True,
            'azhash_data': azhash_data,
            'message': message
        }

    def ui_refresh_azhash_list(self, *args):
        '''UI主线程:刷新azhash列表界面'''
        if len(args) > 1:
            btn = args[1]
            btn.Enable()
        
        delayed_result = args[0]
        result = delayed_result.get()
        code = result['code']
        azhash_data = result['azhash_data']
        message = result['message']
        
        index = 0
        if code:
            selected_index = self.azhash_list.GetFirstSelected()        
            self.azhash_list.DeleteAllItems()
            for azhash in azhash_data['azhash']:
                self.azhash_list.add_item(index, azhash['version'], azhash['time'])
                index = index + 1
            if selected_index != -1:
                self.azhash_list.Select(selected_index)
        self.log_text.append_log(message)

    def on_manual_renew_azhash(self, event):
        '''事件:点击手动获取最新资源列表 按钮'''
        btn = event.GetEventObject()
        btn.Disable()
        startWorker(self.ui_download_azhash, self.get_new_azhash, cargs=(btn, ))
    
    def get_new_azhash(self) -> dict:
        '''工作线程:获取最新azhash'''
        raw_data = self.send_tcp_request('blhxjploginapi.azurlane.jp', 80, '000a002a300000083c120130')
        data = raw_data.decode("utf-8", "ignore")
        # apk_version = re.findall(r'(https?://\S+)\"', data)
        hashes = re.findall(r'\$(.*?)hash(.*?)\"', data)
        hashfile_names = {}
        for h in hashes:
            hashfile_names[h[0]] = f"${h[0]}hash{h[1]}"
        
        azhash_name = hashfile_names['az']
        result = self.ifnew_azhash(azhash_name)

        return result
        
    def ifnew_azhash(self, azhash_name: str) -> dict:
        '''工作线程:判断是否为库中的azhash'''
        azhash_version = self.extract_version_regex(azhash_name)
        azhash_data = self.read_data()
        ifnew = True
        message = f'发现新版本资源列表: {azhash_name}'
        for azhash in azhash_data['azhash']:
            if azhash_name == azhash['name']:
                ifnew = False
                message = '无新版本资源列表'
        
        return {
            'code': ifnew,
            'azhash_name': azhash_name,
            'azhash_version': azhash_version,
            'message': message
        }

    def ui_download_azhash(self, *args):
        '''UI主线程:是否下载新的azhash'''
        btn = args[1]

        delayed_result = args[0]
        result = delayed_result.get()
        ifnew = result['code']
        azhash_name = result['azhash_name']
        azhash_version = result['azhash_version']
        message = result['message']

        if ifnew:
            startWorker(self.ui_refresh_azhash_list, self.download_azhash,cargs=(btn, ), wargs=(azhash_name, azhash_version))
        else:
            btn.Enable()
        self.log_text.append_log(message)

    def download_azhash(self, *args):
        '''工作线程:下载azhash文件'''
        azhash_name = args[0]
        azhash_version = args[1]

        azhash_data = self.read_data()
        base_url = "https://blhxstatic.yo-star.com/android/hash/"

        azhashfile_dir = os.path.join(os.getcwd(), "az_hash")
        if not os.path.exists(azhashfile_dir):
            os.makedirs(azhashfile_dir)

        azhashfile_path = os.path.join(azhashfile_dir, azhash_name)

        if os.path.exists(azhashfile_path):
            os.remove(azhashfile_path)
        wget.download(urljoin(base_url, azhash_name), azhashfile_path)

        azhash_time = time.strftime("%Y-%m-%d %H:%M:%S")

        bg_rows = []
        with open(azhashfile_path, mode='r', newline='', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile, delimiter=',')
            for row in csv_reader:
                if row and len(row) > 0:
                    if "loadingbg/" in row[0]:
                        bg_rows.append(row)
                    if re.search(r'^bg/.*', row[0]):
                        bg_rows.append(row)
        
        # 将azhash中的bg 判断是否为新 是否已下载 并写入bgs[] 
        bgs = []
        for row in bg_rows:
            # name = row[0].split('/')[1]
            name = row[0]
            md5 = row[2]
            ifnew = True
            if md5 in azhash_data['bghash']:
                ifnew = False
            if ifnew:
                azhash_data['bghash'].append(md5)
            
            bgfile_path = os.path.join(os.getcwd(), name.split('/')[0], azhash_version, name.split('/')[1])
            if os.path.exists(bgfile_path):
                ifdl = True
            else:
                ifdl = False
            
            bgs.append({
                'name': name,
                'md5': md5,
                'ifnew': ifnew,
                'ifdl': ifdl
            })
        
        # 对bgs中bg按照name排序
        bgs = sorted(bgs, key=lambda x: (-x['ifnew'] ,x['name']))

        azhash_data['azhash'].append({
            'name': azhash_name,
            'version': azhash_version,
            'time': azhash_time,
            'bg': bgs
        })

        self.save_data(azhash_data)

        return {
            'code': True,
            'azhash_data': azhash_data,
            'message': f'已下载资源列表: {azhash_name}'
        }

    def on_manual_input_azhash(self, event):
        '''事件:点击导入指定资源列表 按钮'''
        result = self.on_show_input_dialog("请输入azhash文件名: ")
        code = result['code']
        user_input = result['input']

        if code == wx.ID_OK and self.validate_azhash_input(user_input):
            azhash_name = user_input
            try:
                btn = event.GetEventObject()
                btn.Disable()
            except Exception as e:
                print(e)
            startWorker(self.ui_download_azhash, self.get_input_azhash,cargs=(btn, ), wargs=(azhash_name, ))
        else:
            self.log_text.append_log('输入有误 请检查')

    def get_input_azhash(self, *args):
        '''工作线程:获取指定azhash'''
        azhash_name = args[0]
        res = self.ifnew_azhash(azhash_name)
        return res

    def on_click_azhash_list(self, event):
        '''事件:点击azhash列表'''
        azhash_index = event.GetIndex()
        startWorker(self.ui_refresh_bg_list, self.refresh_bg_list, wargs=(azhash_index, ))

    def refresh_bg_list(self, *args):
        '''工作线程:刷新bg_list'''
        index = args[0]
        azhash_data = self.read_data()
        azhash_verison = azhash_data['azhash'][index]['name']
        
        return{
            'index': index,
            'azhash_data': azhash_data,
            'message': f'查看资源列表: {azhash_verison}'
        }

    def ui_refresh_bg_list(self, *args):
        '''UI主线程:刷新bg列表'''
        if len(args) > 1:
            btn = args[1]
            btn.Enable()

        delayed_result = args[0]
        res = delayed_result.get()
        azhash_index = res['index']
        azhash_data = res['azhash_data']
        message = res['message']
        azhash_version = azhash_data['azhash'][azhash_index]['version']

        bgs = azhash_data['azhash'][azhash_index]['bg']
        bg_index = 0
        self.bg_list.DeleteAllItems()
        for bg in bgs:
            self.bg_list.add_item(bg_index, bg['name'], bg['md5'], bg['ifnew'], bg['ifdl'], azhash_version)
        
        self.log_text.append_log(message)

    def on_double_click_bg_list(self, event):
        '''事件:双击bglist'''
        bg_index = event.GetIndex()
        bg_name = self.bg_list.GetItemText(bg_index, col=0)
        az_version = self.bg_list.GetItemText(bg_index, col=4)
        bg_ifdl = True if self.bg_list.GetItemText(bg_index, col=3) == '已下载' else False
        
        if bg_ifdl:
            startWorker(self.ui_show_imgs, self.show_imgs, wargs=(bg_name, az_version))
        else:
            self.on_show_alert_dialog('该资源未下载 请先下载')

    def show_imgs(self, *args):
        '''工作线程:解析bg'''
        bg_name = args[0].split('/')[1]
        bg_type = args[0].split('/')[0]
        az_version = args[1]
        
        bgfile_path = os.path.join(os.getcwd(), bg_type, az_version, bg_name)
        if os.path.exists(bgfile_path):
            imgs = self.extract_textures_from_unity_file(bgfile_path)
            message = f'查看资源: {bgfile_path}'
        else:
            imgs = []
            message = f'文件不存在: {bgfile_path}'
        
        return {
            'imgs': imgs,
            'message': message
        }

    def ui_show_imgs(self, delayed_result: dict):
        '''UI主线程:打开图片预览窗口'''
        res = delayed_result.get()
        imgs = res['imgs']
        message = res['message']

        if len(imgs) > 0:
            ImageViewer(self, title="资源查看器", imgs=imgs)
        self.log_text.append_log(message)

    def on_download_bg(self, event):
        '''事件:点击下载选中资源 按钮'''
        btn = event.GetEventObject()
        btn.Disable()
        azhash_index = self.azhash_list.GetFirstSelected()
        if azhash_index != -1:
            ifonlynew = self.on_show_yesno_dialog('是否只下载新的资源文件\n已下载的资源将会重新下载')
            if ifonlynew == wx.ID_YES:
                ifonlynew_bool = True
            elif ifonlynew == wx.ID_NO:
                ifonlynew_bool = False
            else:
                self.log_text.append_log("取消下载")
                btn.Enable()
                return
            self.log_text.append_log("开始下载")
            startWorker(self.ui_refresh_bg_list, self.download_bg, cargs=(btn,), wargs=(ifonlynew_bool, azhash_index))
        else:
            self.log_text.append_log("没有选中任何资源")
            btn.Enable()

    def download_bg(self, *args):
        '''工作线程:下载bg'''
        ifonlynew = args[0]
        azhash_index = args[1]
        azhash_data = self.read_data()
        azhash_version = azhash_data['azhash'][azhash_index]['version']
        bgs = azhash_data['azhash'][azhash_index]['bg']
        base_url = "https://blhxstatic.yo-star.com/android/resource/"
        bg_dir_path = os.path.join(os.getcwd(), 'loadingbg', azhash_version)
        if not os.path.exists(bg_dir_path):
            os.makedirs(bg_dir_path)

        bg_index = 0
        for bg in bgs:
            bg_name = bg['name'].split('/')[1]
            bg_type = bg['name'].split('/')[0]
            bg_md5 = bg['md5']

            bg_dir_path = os.path.join(os.getcwd(), bg_type, azhash_version)
            if not os.path.exists(bg_dir_path):
                os.makedirs(bg_dir_path)
            
            if (not ifonlynew) or (ifonlynew and bg['ifnew'] == True):
                bg_file_path = os.path.join(bg_dir_path, bg_name)
                if os.path.exists(bg_file_path):
                    os.remove(bg_file_path)
                wget.download(urljoin(base_url, bg_md5), bg_file_path)
                if os.path.exists(bg_file_path):
                    azhash_data['azhash'][azhash_index]['bg'][bg_index]['ifdl'] = True
            bg_index = bg_index + 1
        
        self.save_data(azhash_data)

        return {
            'index': azhash_index,
            'azhash_data':azhash_data,
            'message': f'下载完成: {azhash_version}'
        }

    def on_export_bg(self, event):
        '''事件:点击导出选中资源 按钮'''
        azhash_index = self.azhash_list.GetFirstSelected()
        if azhash_index != -1:
            self.on_show_alert_dialog('只能导出已下载资源\n已导出的资源将会被覆盖')
            self.log_text.append_log("开始导出")
            btn = event.GetEventObject()
            btn.Disable()
            startWorker(self.ui_refresh_bg_list, self.export_bg, cargs=(btn,), wargs=(azhash_index, ))
        else:
            self.log_text.append_log("没有选中任何资源")

    def export_bg(self, *args):
        '''工作线程:导出bg'''
        azhash_index = args[0]
        azhash_data = self.read_data()
        azhash_version = azhash_data['azhash'][azhash_index]['version']
        bgs = azhash_data['azhash'][azhash_index]['bg']

        for bg in bgs:
            bg_name = bg['name'].split('/')[1]
            bg_type = bg['name'].split('/')[0]
            bg_ifdl = bg['ifdl']

            export_dir_path = os.path.join(os.getcwd(), 'export', azhash_version, bg_type)
            if not os.path.exists(export_dir_path):
                os.makedirs(export_dir_path)

            bg_file_path = os.path.join(os.getcwd(), bg_type, azhash_version, bg_name)
            if bg_ifdl == True and os.path.exists(bg_file_path):
                imgs = self.extract_textures_from_unity_file(bg_file_path)
                img_index = 0
                for img in imgs:
                    img_name = img['name']
                    img_data = img['data']
                    img_path = os.path.join(export_dir_path, f'{img_name}_{img_index}.png')
                    if os.path.exists(img_path):
                        os.remove(img_path)
                    img_data.save(img_path, "PNG")
                    img_index = img_index + 1
        
        os.startfile(export_dir_path)
        return {
            'index': azhash_index,
            'azhash_data': azhash_data,
            'message': f'导出完成: {azhash_version}'
        }

    def on_delete_azhash(self, event):
        '''事件:点击删除选中资源 按钮'''
        azhash_index = self.azhash_list.GetFirstSelected()
        ifdel = self.on_show_yesno_dialog("请确定是否删除资源\n只删除记录 不删除实际文件")
        btn = event.GetEventObject()
        btn.Disable()
        if ifdel == wx.ID_YES:
            startWorker(self.ui_delete_azhash, self.delete_azhash, cargs=(btn,), wargs=(azhash_index,))

    def delete_azhash(self, *args):
        '''工作线程:删除指定资源'''
        azhash_index = args[0]
        azhash_data = self.read_data()
        azhash_version = azhash_data['azhash'][azhash_index]['name']
        del azhash_data['azhash'][azhash_index]
        self.save_data(azhash_data)

        return{
            'azhash_data':azhash_data,
            'message': f'已删除{azhash_version}'
        }

    def ui_delete_azhash(self, *args):
        '''UI主线程:删除指定资源后清空显示'''
        btn = args[1]
        btn.Enable()

        delayed_result = args[0]
        res = delayed_result.get()
        azhash_data = res['azhash_data']
        message = res['message']

        self.azhash_list.DeleteAllItems()
        self.bg_list.DeleteAllItems()

        azhash_index = 0
        for azhash in azhash_data['azhash']:
            self.azhash_list.add_item(azhash_index, azhash['version'], azhash['time'])
            azhash_index = azhash_index + 1
        self.log_text.append_log(message)
 
    def on_exit(self, event):
        """退出按钮事件"""
        self.auto_renew_stop_event.set()
        self.log_text.append_log("应用程序退出")
        wx.MilliSleep(200)
        self.Destroy()
    
    def on_auto_renew_azhash(self, event):
        '''事件:点击监控资源 按钮'''
        btn = event.GetEventObject()
        btn_txt = btn.GetLabel()
        btn.Disable()
        # if "停止" in btn_txt:
        #     self.auto_renew_stop_event.set()
        #     btn.SetLabel("开始监控最新资源列表")
        #     btn.Disable()
        # else:
        #     self.auto_renew_stop_event.clear()
        #     btn.SetLabel("停止监控最新资源列表")
        #     startWorker(self.ui_auto_renew_azhash_result, self.auto_renew_azhash, cargs=(btn, ))
        #     self.log_text.append_log("开始监控资源列表")
    
    def auto_renew_azhash(self):
        '''工作线程:监控资源'''
        try:
            timer = 0
            while timer < 300:
                time.sleep(1)
                timer = timer + 1
                if self.auto_renew_stop_event.is_set():
                    return {
                        'message': '已停止监控'
                    }
                if timer == 300:
                    timer = 0
                    res = self.get_new_azhash()
                    ifnew = res['code']    
                    if ifnew:
                        event = NewAzhashEvent(res)
                        wx.PostEvent(self, event)
        except Exception as e:
            return {
                'message': str(e)
            }

    def event_download_azhash(self, event):
        '''UI主线程:处理监控发现的新资源'''
        res = event.data
        azhash_name = res['azhash_name']
        azhash_version = res['azhash_version']
        self.log_text.append_log(f'发现新资源列表: {azhash_name}')
        startWorker(self.ui_refresh_azhash_list, self.download_azhash, wargs=(azhash_name, azhash_version))

    def ui_auto_renew_azhash_result(self, *args):
        '''UI主线程:处理监控停止'''
        btn = args[1]
        btn.Enable()

        delayed_result = args[0]
        res = delayed_result.get()
        message = res['message']
        self.log_text.append_log(message)

    def on_open_work_dir(self, event):
        '''事件:点击打开工作目录 按钮'''
        dir_path = os.getcwd()
        os.startfile(dir_path)


if __name__ == "__main__":
    app = wx.App()
    frame = MainFrame()
    app.MainLoop()
