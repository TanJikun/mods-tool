import requests
import re
import time
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, DownloadColumn, TransferSpeedColumn
from rich import box
import sys
import os
import msvcrt
import subprocess
from pathlib import Path

console = Console()

# ---------- 配置文件 ----------
CONFIG_FILE = 'config.json'

def load_config():
    default_config = {
        "download": {
            "default_dir": "./downloads",
            "use_gopeed": True,
            "fallback_enabled": True,
            "gopeed": {
                "executable": "gopeed",
                "api_base": "http://127.0.0.1:9999",
                "token": "",
                "connections": 16,
                "auto_start": True,
                "headless": True
            }
        }
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

config = load_config()
DOWNLOAD_CONFIG = config.get('download', {})
DEFAULT_DOWNLOAD_DIR = DOWNLOAD_CONFIG.get('default_dir', './downloads')
USE_GOPEED = DOWNLOAD_CONFIG.get('use_gopeed', True)
FALLBACK_ENABLED = DOWNLOAD_CONFIG.get('fallback_enabled', True)
GOPEED_CONFIG = DOWNLOAD_CONFIG.get('gopeed', {})
GOPEED_EXEC = GOPEED_CONFIG.get('executable', 'gopeed')
GOPEED_API_BASE = GOPEED_CONFIG.get('api_base', 'http://127.0.0.1:9999')
GOPEED_TOKEN = GOPEED_CONFIG.get('token', '')
GOPEED_CONNECTIONS = GOPEED_CONFIG.get('connections', 16)
GOPEED_AUTO_START = GOPEED_CONFIG.get('auto_start', True)
GOPEED_HEADLESS = GOPEED_CONFIG.get('headless', True)

# ---------- 下载管理器（HTTP API 模式） ----------
class DownloadManager:
    def __init__(self):
        self.api_base = GOPEED_API_BASE.rstrip('/')
        self.token = GOPEED_TOKEN
        self.connections = GOPEED_CONNECTIONS
        self.default_dir = DEFAULT_DOWNLOAD_DIR
        self.use_gopeed = USE_GOPEED
        self.fallback_enabled = FALLBACK_ENABLED
        self.gopeed_process = None
        self.service_ready = False

        if self.use_gopeed:
            self._ensure_gopeed_service()

    def _ensure_gopeed_service(self):
        if not self._check_service():
            if GOPEED_AUTO_START:
                self._start_service()
            else:
                console.print("[yellow]⚠️ Gopeed 服务未运行，且 auto_start 为 false，将使用内置下载[/yellow]")
                self.use_gopeed = False
        else:
            self.service_ready = True

    def _check_service(self):
        try:
            resp = requests.get(f"{self.api_base}/api/v1/tasks", timeout=2)
            return resp.status_code == 200
        except:
            return False

    def _start_service(self):
        try:
            cmd = [GOPEED_EXEC]
            if GOPEED_HEADLESS:
                cmd.append('--headless')

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

            console.print("[cyan]正在启动 Gopeed 服务...[/cyan]")
            self.gopeed_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            for _ in range(30):
                time.sleep(0.5)
                if self._check_service():
                    self.service_ready = True
                    console.print("[green]✅ Gopeed 服务已就绪[/green]")
                    return
            console.print("[yellow]⚠️ Gopeed 服务启动超时，将使用内置下载[/yellow]")
            self.use_gopeed = False
        except FileNotFoundError:
            console.print(f"[yellow]⚠️ 未找到 Gopeed 可执行文件: {GOPEED_EXEC}，将使用内置下载[/yellow]")
            self.use_gopeed = False
        except Exception as e:
            console.print(f"[yellow]⚠️ 启动 Gopeed 服务失败: {e}，将使用内置下载[/yellow]")
            self.use_gopeed = False

    def _api_request(self, method, endpoint, data=None):
        url = f"{self.api_base}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        try:
            if method.upper() == 'GET':
                resp = requests.get(url, headers=headers, timeout=10)
            else:
                resp = requests.post(url, json=data, headers=headers, timeout=10)
            return resp
        except Exception as e:
            console.print(f"[dim]API 请求异常: {e}[/dim]")
            return None

    def download_with_gopeed(self, url, filename=None):
        """使用 Gopeed API 下载 - 使用 Gopeed 默认下载目录，不传递 path"""
        if not self._check_service():
            return False, "Gopeed 服务不可用"

        payload = {
            "req": {
                "url": url
            },
            "options": {
                "connections": self.connections
            }
        }
        if filename:
            payload["options"]["name"] = filename

        endpoints = ['/api/v1/tasks', '/api/v1/task/create', '/api/tasks']

        for endpoint in endpoints:
            resp = self._api_request('POST', endpoint, payload)
            if resp:
                if resp.status_code in [200, 201]:
                    try:
                        resp_data = resp.json()
                        task_id = resp_data.get('data') or resp_data.get('id') or resp_data.get('taskId')
                        if task_id:
                            return True, f"任务已创建 (ID: {task_id})"
                        else:
                            return True, "任务已创建"
                    except:
                        return True, "任务已创建"
                elif resp.status_code == 404:
                    continue
                else:
                    console.print(f"[dim]尝试 {endpoint} 失败: {resp.status_code} - {resp.text[:100]}[/dim]")
                    continue

        return False, "创建任务失败，请检查 API 配置"

    def download_with_fallback(self, url, filename=None):
        """内置下载 - 使用配置的 default_dir"""
        dest_dir = self.default_dir
        Path(dest_dir).mkdir(parents=True, exist_ok=True)

        if filename:
            dest_path = os.path.join(dest_dir, filename)
        else:
            dest_path = os.path.join(dest_dir, os.path.basename(urlparse(url).path) or 'download')

        try:
            response = requests.get(url, stream=True, timeout=30)
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            total_size = int(response.headers.get('content-length', 0))
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]内置下载中...", total=total_size)
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))
            return True, f"内置下载完成: {dest_path}"
        except Exception as e:
            return False, f"内置下载失败: {e}"

    def download(self, url, filename=None):
        """统一下载入口 - 不传递路径"""
        if not self.use_gopeed:
            return self.download_with_fallback(url, filename)

        success, msg = self.download_with_gopeed(url, filename)
        if success:
            return success, msg

        if self.fallback_enabled:
            console.print(f"[yellow]⚠️ Gopeed 下载失败，回退到内置下载: {msg}[/yellow]")
            return self.download_with_fallback(url, filename)
        else:
            return False, msg

    def shutdown(self):
        """不再自动关闭，仅用于清理（保留但不再调用）"""
        if self.gopeed_process:
            try:
                self.gopeed_process.terminate()
                self.gopeed_process.wait(timeout=5)
            except:
                self.gopeed_process.kill()

# ---------- 核心类 ----------
class ModVersionChecker:
    # 内容类型中文显示
    TYPE_LABELS = {
        'mod': '模组',
        'resourcepack': '材质包',
        'shader': '光影',
        'datapack': '数据包',
        'plugin': '插件',
        'modpack': '整合包',
    }

    def __init__(self):
        self.modrinth_api = "https://api.modrinth.com/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # 缓存项目类型，避免重复请求
        self._type_cache = {}

    def _type_label(self, content_type):
        return self.TYPE_LABELS.get(content_type, content_type or '未知')

    def fetch_all_versions_from_modrinth(self):
        try:
            url = "https://api.modrinth.com/v2/tag/game_version"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                versions = [v['version'] for v in data if re.match(r'^\d+\.\d+(\.\d+)?$', v['version'])]
                versions.sort(key=lambda x: [int(p) for p in x.split('.')])
                return versions
            else:
                console.print(f"[yellow]从 Modrinth 获取版本列表失败，状态码: {response.status_code}[/yellow]")
                return []
        except Exception as e:
            console.print(f"[yellow]从 Modrinth 获取版本列表时出错: {e}[/yellow]")
            return []

    def get_version_range(self, min_version, max_version):
        all_versions = self.fetch_all_versions_from_modrinth()
        if not all_versions:
            console.print("[yellow]⚠️ 无法从 Modrinth 获取版本列表，使用内置完整备用列表。[/yellow]")
            all_versions = [
                '1.13', '1.13.1', '1.13.2',
                '1.14', '1.14.1', '1.14.2', '1.14.3', '1.14.4', '1.14.5',
                '1.15', '1.15.1', '1.15.2',
                '1.16', '1.16.1', '1.16.2', '1.16.3', '1.16.4', '1.16.5',
                '1.17', '1.17.1',
                '1.18', '1.18.1', '1.18.2',
                '1.19', '1.19.1', '1.19.2', '1.19.3', '1.19.4',
                '1.20', '1.20.1', '1.20.2', '1.20.3', '1.20.4', '1.20.5', '1.20.6',
                '1.21', '1.21.1', '1.21.2', '1.21.3', '1.21.4', '1.21.5',
                '1.21.6', '1.21.7', '1.21.8', '1.21.9', '1.21.10', '1.21.11',
                '26.1', '26.1.1', '26.1.2', '26.2'
            ]

        if not re.match(r'^\d+\.\d+(\.\d+)?$', min_version) or not re.match(r'^\d+\.\d+(\.\d+)?$', max_version):
            console.print("[red]❌ 版本格式不正确，请使用 数字.数字 或 数字.数字.数字 格式[/red]")
            return []

        result = []
        for v in all_versions:
            if self.compare_versions(min_version, v) <= 0 and self.compare_versions(v, max_version) <= 0:
                result.append(v)
        result.sort(key=lambda x: [int(p) for p in x.split('.')])
        return result

    def compare_versions(self, v1, v2):
        def normalize(v):
            parts = v.split('.')
            return [int(p) for p in parts]
        v1_parts = normalize(v1)
        v2_parts = normalize(v2)
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += [0] * (max_len - len(v1_parts))
        v2_parts += [0] * (max_len - len(v2_parts))
        for i in range(max_len):
            if v1_parts[i] < v2_parts[i]:
                return -1
            elif v1_parts[i] > v2_parts[i]:
                return 1
        return 0

    # ---------- URL 解析（支持模组 + 材质包） ----------
    def parse_url(self, url):
        """
        解析 URL，返回 (platform, identifier, content_type)
        content_type: 'mod' / 'resourcepack' / 'shader' / 'datapack' / ... 或 None(未知)
        """
        url = url.strip()
        url_lower = url.lower()
        if 'modrinth.com' in url_lower:
            identifier = self.extract_modrinth_id(url)
            if not identifier:
                return None, None, None
            if '/resourcepack/' in url_lower or '/resource-pack/' in url_lower:
                return 'modrinth', identifier, 'resourcepack'
            elif '/shader/' in url_lower:
                return 'modrinth', identifier, 'shader'
            elif '/datapack/' in url_lower:
                return 'modrinth', identifier, 'datapack'
            elif '/modpack/' in url_lower:
                return 'modrinth', identifier, 'modpack'
            elif '/plugin/' in url_lower:
                return 'modrinth', identifier, 'plugin'
            elif '/mod/' in url_lower:
                return 'modrinth', identifier, 'mod'
            else:
                return 'modrinth', identifier, None
        elif 'curseforge.com' in url_lower:
            identifier = self.extract_curseforge_id(url)
            if not identifier:
                return None, None, None
            if '/texture-packs/' in url_lower:
                return 'curseforge', identifier, 'resourcepack'
            elif '/shaders/' in url_lower:
                return 'curseforge', identifier, 'shader'
            elif '/worlds/' in url_lower:
                return 'curseforge', identifier, 'world'
            elif '/modpacks/' in url_lower:
                return 'curseforge', identifier, 'modpack'
            elif '/mc-mods/' in url_lower:
                return 'curseforge', identifier, 'mod'
            else:
                return 'curseforge', identifier, None
        else:
            return None, None, None

    def extract_modrinth_id(self, url):
        # 优先匹配带类型前缀的 URL
        match = re.search(
            r'modrinth\.com/(?:mod|resourcepack|resource-pack|shader|datapack|plugin|modpack)/([^/?#]+)',
            url
        )
        if match:
            return match.group(1)
        match = re.search(r'modrinth\.com/project/([^/?#]+)', url)
        if match:
            return match.group(1)
        match = re.search(r'modrinth\.com/([^/?#]+)', url)
        return match.group(1) if match else None

    def extract_curseforge_id(self, url):
        match = re.search(
            r'curseforge\.com/minecraft/(?:mc-mods|texture-packs|shaders|worlds|modpacks|bukkit-plugins)/([^/?#]+)',
            url
        )
        return match.group(1) if match else None

    # ---------- 类型检测 ----------
    def resolve_content_type(self, platform, identifier, content_type):
        """若 URL 未给出类型，则通过 API 探测"""
        if content_type:
            return content_type
        if platform == 'modrinth':
            return self._query_modrinth_type(identifier)
        # CurseForge 无法从 URL 判断时默认按模组
        return 'mod'

    def _query_modrinth_type(self, project_id):
        if project_id in self._type_cache:
            return self._type_cache[project_id]
        try:
            url = f"{self.modrinth_api}/project/{project_id}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                ptype = response.json().get('project_type', 'mod')
                self._type_cache[project_id] = ptype
                return ptype
        except Exception:
            pass
        self._type_cache[project_id] = 'mod'
        return 'mod'

    # ---------- 版本获取 ----------
    def get_modrinth_versions(self, project_id, loader=None):
        try:
            url = f"{self.modrinth_api}/project/{project_id}/version"
            params = {}
            if loader:
                params['loaders'] = f'["{loader}"]'
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                versions = response.json()
                supported_versions = set()
                for v in versions:
                    if 'game_versions' in v:
                        for game_ver in v['game_versions']:
                            if re.match(r'^\d+\.\d+(\.\d+)?$', game_ver):
                                supported_versions.add(game_ver)
                return supported_versions
            elif response.status_code == 404:
                return self.search_modrinth_mod(project_id, loader)
            else:
                console.print(f"[yellow]  Modrinth API返回错误: {response.status_code}[/yellow]")
                return set()
        except Exception as e:
            console.print(f"[yellow]  获取Modrinth版本出错: {e}[/yellow]")
            return set()

    def search_modrinth_mod(self, project_id, loader=None):
        try:
            search_url = f"{self.modrinth_api}/search?query={project_id}"
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('hits'):
                    mod = data['hits'][0]
                    mod_id = mod.get('project_id')
                    if mod_id:
                        console.print(f"  [cyan]🔍 找到替代项目: {mod.get('title')} (ID: {mod_id})[/cyan]")
                        return self.get_modrinth_versions(mod_id, loader)
            return set()
        except:
            return set()

    def get_curseforge_versions(self, project_slug, loader=None, content_type='mod'):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            if content_type == 'resourcepack':
                url = f"https://www.curseforge.com/minecraft/texture-packs/{project_slug}/files"
            elif content_type == 'shader':
                url = f"https://www.curseforge.com/minecraft/shaders/{project_slug}/files"
            else:
                url = f"https://www.curseforge.com/minecraft/mc-mods/{project_slug}/files"

            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                supported_versions = set()
                file_rows = soup.find_all('tr', {'data-game-version': True})
                for row in file_rows:
                    data = row.get('data-game-version', '')
                    if data:
                        for v in data.split(','):
                            v = v.strip()
                            if re.match(r'^\d+\.\d+(\.\d+)?$', v):
                                supported_versions.add(v)
                if not supported_versions:
                    cells = soup.find_all('td', class_='game-version')
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if text:
                            for v in re.findall(r'\d+\.\d+(?:\.\d+)?', text):
                                supported_versions.add(v)
                return supported_versions
            else:
                console.print(f"[yellow]  CurseForge页面访问失败: {response.status_code}[/yellow]")
                return set()
        except Exception as e:
            console.print(f"[yellow]  获取CurseForge版本出错: {e}[/yellow]")
            return set()

    def get_mod_name(self, url, platform, identifier, content_type='mod'):
        try:
            if platform == 'modrinth':
                api_url = f"{self.modrinth_api}/project/{identifier}"
                response = self.session.get(api_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return data.get('title', identifier)
            else:
                if content_type == 'resourcepack':
                    page_url = f"https://www.curseforge.com/minecraft/texture-packs/{identifier}"
                elif content_type == 'shader':
                    page_url = f"https://www.curseforge.com/minecraft/shaders/{identifier}"
                else:
                    page_url = f"https://www.curseforge.com/minecraft/mc-mods/{identifier}"
                response = self.session.get(page_url, timeout=5)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    title_elem = soup.find('h1', class_='project-title')
                    if title_elem:
                        return title_elem.get_text(strip=True)
            return identifier
        except:
            return identifier

    def get_modrinth_download_url(self, project_id, mc_version, loader=None, version_type='release'):
        """
        获取指定项目的下载URL
        loader 为 None 时不进行加载器过滤（材质包 / 数据包等）
        version_type: 'release', 'beta', 'alpha'
        """
        try:
            if version_type == 'alpha':
                type_order = ['alpha', 'beta', 'release']
            elif version_type == 'beta':
                type_order = ['beta', 'release']
            else:
                type_order = ['release']

            url = f"{self.modrinth_api}/project/{project_id}/version"
            params = {
                'game_versions': f'["{mc_version}"]'
            }
            if loader:
                params['loaders'] = f'["{loader}"]'

            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                console.print(f"[yellow]  获取下载链接失败 (HTTP {response.status_code})[/yellow]")
                return None

            versions = response.json()
            if not versions:
                return None

            for type_name in type_order:
                filtered = [v for v in versions if v.get('version_type') == type_name]
                if filtered:
                    filtered.sort(key=lambda x: x.get('date_published', ''), reverse=True)
                    latest = filtered[0]
                    file_data = latest.get('files', [])
                    if file_data:
                        return file_data[0].get('url')

            if versions:
                file_data = versions[0].get('files', [])
                if file_data:
                    return file_data[0].get('url')

            return None
        except Exception as e:
            console.print(f"[yellow]  获取下载链接出错: {e}[/yellow]")
            return None

    # ---------- 兼容性检查 ----------
    def process_mods(self, urls, min_version, max_version, loader=None):
        minecraft_versions = self.get_version_range(min_version, max_version)
        if not minecraft_versions:
            console.print("[red]⚠️ 未找到范围内的Minecraft版本，请检查版本号是否正确。[/red]")
            return None, None

        console.print(f"[cyan]📌 版本范围: {min_version}  →  {max_version}[/cyan]")
        console.print(f"[cyan]📋 共找到 {len(minecraft_versions)} 个Minecraft版本[/cyan]")
        if loader:
            console.print(f"[cyan]📌 加载器过滤: {loader.upper()}（材质包/数据包不受加载器限制）[/cyan]")
        console.print("-" * 70)

        mod_data = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]处理项目...", total=len(urls))

            for i, url in enumerate(urls, 1):
                url = url.strip()
                if not url:
                    progress.advance(task)
                    continue

                progress.update(task, description=f"[cyan]处理 [{i}/{len(urls)}]: {url}")

                platform, identifier, content_type = self.parse_url(url)
                if not platform or not identifier:
                    console.print(f"  [red]❌ 无法解析URL: {url}[/red]")
                    progress.advance(task)
                    continue

                # 若 URL 未给出类型，尝试从 API 探测
                content_type = self.resolve_content_type(platform, identifier, content_type)
                is_resourcepack = (content_type == 'resourcepack')
                # 材质包不参与加载器过滤
                effective_loader = None if is_resourcepack else loader

                mod_name = self.get_mod_name(url, platform, identifier, content_type)

                if platform == 'modrinth':
                    supported_versions = self.get_modrinth_versions(identifier, effective_loader)
                else:
                    supported_versions = self.get_curseforge_versions(identifier, effective_loader, content_type)

                version_check = {}
                for mc_ver in minecraft_versions:
                    version_check[mc_ver] = mc_ver in supported_versions

                supported_count = sum(version_check.values())
                supported_percent = (supported_count / len(minecraft_versions) * 100) if minecraft_versions else 0

                type_label = self._type_label(content_type)

                mod_data.append({
                    'name': mod_name,
                    'platform': platform.upper(),
                    'content_type': content_type,
                    'type_label': type_label,
                    'url': url,
                    'versions': version_check,
                    'supported_count': supported_count,
                    'supported_percent': supported_percent,
                    'supported_list': [v for v in minecraft_versions if version_check[v]]
                })

                console.print(f"  [green]✅ {mod_name}[/green]")
                console.print(f"    平台: {platform.upper()}  |  类型: [bold magenta]{type_label}[/bold magenta]")
                console.print(f"    支持版本: {supported_count}/{len(minecraft_versions)} ({supported_percent:.1f}%)")
                if supported_count > 0 and supported_count <= 10:
                    console.print(f"    支持的版本: {', '.join(mod_data[-1]['supported_list'])}")
                elif supported_count > 10:
                    console.print(f"    支持的版本: {', '.join(mod_data[-1]['supported_list'][:10])} ... (共{supported_count}个)")

                time.sleep(0.3)
                progress.advance(task)

        return mod_data, minecraft_versions

    def export_to_excel(self, mod_data, minecraft_versions, filename='mod_compatibility.xlsx'):
        if not mod_data:
            console.print("[red]没有数据可导出[/red]")
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "模组兼容性矩阵"

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        cell_alignment = Alignment(horizontal="center", vertical="center")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        support_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        support_font = Font(color="006100")
        no_support_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        no_support_font = Font(color="9C0006")

        # 新增“类型”列
        headers = ['序号', '名称', '平台', '类型', 'URL', '支持版本数', '支持率'] + minecraft_versions

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border

        for row_idx, mod in enumerate(mod_data, 2):
            ws.cell(row=row_idx, column=1, value=row_idx-1).alignment = cell_alignment
            ws.cell(row=row_idx, column=2, value=mod['name']).alignment = cell_alignment
            ws.cell(row=row_idx, column=3, value=mod['platform']).alignment = cell_alignment

            type_cell = ws.cell(row=row_idx, column=4, value=mod['type_label'])
            type_cell.alignment = cell_alignment
            if mod['content_type'] == 'resourcepack':
                type_cell.font = Font(color="7030A0", bold=True)
            else:
                type_cell.font = Font(color="0070C0")

            url_cell = ws.cell(row=row_idx, column=5, value=mod['url'])
            url_cell.alignment = Alignment(horizontal="left", vertical="center")
            url_cell.font = Font(color="0563C1", underline="single")

            ws.cell(row=row_idx, column=6, value=mod['supported_count']).alignment = cell_alignment
            ws.cell(row=row_idx, column=7, value=f"{mod['supported_percent']:.1f}%").alignment = cell_alignment

            col_idx = 8
            for mc_ver in minecraft_versions:
                cell = ws.cell(row=row_idx, column=col_idx, value='✔' if mod['versions'][mc_ver] else '✘')
                cell.alignment = cell_alignment
                cell.border = border
                if mod['versions'][mc_ver]:
                    cell.fill = support_fill
                    cell.font = support_font
                else:
                    cell.fill = no_support_fill
                    cell.font = no_support_font
                col_idx += 1

            for col in range(1, len(headers) + 1):
                ws.cell(row=row_idx, column=col).border = border

        column_widths = {'A': 6, 'B': 25, 'C': 10, 'D': 10, 'E': 50, 'F': 14, 'G': 12}
        for i, mc_ver in enumerate(minecraft_versions, 8):
            col_letter = get_column_letter(i)
            column_widths[col_letter] = max(10, len(mc_ver) + 2)

        for col_letter, width in column_widths.items():
            ws.column_dimensions[col_letter].width = width

        ws.freeze_panes = 'A2'
        wb.save(filename)
        console.print(f"\n[green]✅ Excel文件已保存: {filename}[/green]")

    # ---------- 批量下载 ----------
    def batch_download(self, urls, mc_version, loader, version_type='release'):
        console.print(f"[cyan]📌 目标Minecraft版本: {mc_version}[/cyan]")
        if loader:
            console.print(f"[cyan]📌 加载器: {loader.upper()}（材质包/数据包将忽略加载器）[/cyan]")
        else:
            console.print(f"[cyan]📌 加载器: [dim]无（仅材质包/数据包）[/dim][/cyan]")
        console.print(f"[cyan]📌 版本类型: {version_type.upper()}[/cyan]")
        console.print(f"[cyan]📌 下载工具: {'Gopeed API (使用 Gopeed 默认下载目录)' if USE_GOPEED else '内置 (使用配置的 default_dir)'}[/cyan]")
        if not USE_GOPEED or not FALLBACK_ENABLED:
            console.print(f"[dim]  内置下载目录: {DEFAULT_DOWNLOAD_DIR}[/dim]")
        console.print("-" * 70)

        download_mgr = DownloadManager()
        success_count = 0
        skip_count = 0
        fail_count = 0
        no_version_urls = []

        for i, url in enumerate(urls, 1):
            url = url.strip()
            if not url:
                continue

            console.print(f"\n[bold]处理 [{i}/{len(urls)}]: {url}[/bold]")

            platform, identifier, content_type = self.parse_url(url)
            if not platform or not identifier:
                console.print(f"  [red]❌ 无法解析URL[/red]")
                fail_count += 1
                no_version_urls.append(url)
                continue

            content_type = self.resolve_content_type(platform, identifier, content_type)
            is_resourcepack = (content_type == 'resourcepack')
            effective_loader = None if is_resourcepack else loader
            type_label = self._type_label(content_type)

            mod_name = self.get_mod_name(url, platform, identifier, content_type)
            console.print(f"  名称: {mod_name}  [magenta]【{type_label}】[/magenta]")

            if platform == 'modrinth':
                download_url = self.get_modrinth_download_url(
                    identifier, mc_version, effective_loader, version_type
                )
                if download_url:
                    filename = f"{mod_name}_{mc_version}"
                    if effective_loader:
                        filename += f"_{effective_loader}"
                    filename += ".jar"
                    filename = filename.replace(' ', '_')
                    filename = re.sub(r'[\\/*?:"<>|]', '', filename)
                    console.print(f"  开始下载: {filename}")
                    success, msg = download_mgr.download(download_url, filename)
                    if success:
                        console.print(f"  [green]✅ {msg}[/green]")
                        success_count += 1
                    else:
                        console.print(f"  [red]❌ {msg}[/red]")
                        fail_count += 1
                        no_version_urls.append(url)
                else:
                    console.print(f"  [yellow]⚠️ 未找到匹配的版本文件（版本类型: {version_type}）[/yellow]")
                    skip_count += 1
                    no_version_urls.append(url)
            else:
                console.print(f"  [yellow]⚠️ CurseForge 暂不支持自动下载，请手动下载[/yellow]")
                skip_count += 1
                no_version_urls.append(url)

            time.sleep(0.5)

        console.print("\n[dim]提示：Gopeed 服务将继续在后台运行，可手动关闭。[/dim]")

        console.print("\n" + "=" * 70)
        console.print("[bold]📊 下载汇总:[/bold]")
        console.print(f"  成功: [green]{success_count}[/green]")
        console.print(f"  跳过: [yellow]{skip_count}[/yellow]")
        console.print(f"  失败: [red]{fail_count}[/red]")
        console.print(f"  总计: {len(urls)}")

        if no_version_urls:
            console.print(f"\n[cyan]ℹ️  共有 [bold]{len(no_version_urls)}[/bold] 个模组没有找到对应版本或未能自动下载[/cyan]")
            save = Prompt.ask(
                "是否将这些URL保存到新文件？",
                choices=["y", "n"],
                default="n"
            ) == "y"
            if save:
                self._save_missing_urls(no_version_urls)
        else:
            console.print("\n[green]✅ 所有模组均已成功下载，没有遗漏的URL[/green]")

    def _save_missing_urls(self, url_list, base_name='missing_downloads'):
        """将未下载的URL保存到新文件，不覆盖已存在的文件"""
        filename = f"{base_name}.txt"
        if os.path.exists(filename):
            counter = 1
            while os.path.exists(f"{base_name}_{counter}.txt"):
                counter += 1
            filename = f"{base_name}_{counter}.txt"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for url in url_list:
                    f.write(f"{url}\n")
            console.print(f"\n[green]✅ 已保存 {len(url_list)} 个URL到: [cyan]{filename}[/cyan][/green]")
        except Exception as e:
            console.print(f"[red]❌ 保存失败: {e}[/red]")


# ---------- 独立功能：URL 排序 ----------
def read_lines_any_encoding(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='gbk') as f:
            return f.readlines()


def sort_url_file(file_path, output_path=None, overwrite=False, checker=None):
    """对URL文件中的有效URL进行排序，并保存"""
    if checker is None:
        checker = ModVersionChecker()

    try:
        lines = read_lines_any_encoding(file_path)
    except Exception as e:
        console.print(f"[red]❌ 读取文件失败: {e}[/red]")
        return False

    valid_urls = []
    invalid_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        platform, identifier, _ = checker.parse_url(stripped)
        if platform and identifier:
            valid_urls.append(stripped)
        else:
            invalid_count += 1

    if not valid_urls:
        console.print("[red]文件中没有有效的 Modrinth 或 CurseForge URL[/red]")
        return False

    valid_urls.sort()

    if output_path is None:
        if overwrite:
            output_path = file_path
        else:
            base, ext = os.path.splitext(file_path)
            output_path = f"{base}_sorted{ext}"

    with open(output_path, 'w', encoding='utf-8') as f:
        for url in valid_urls:
            f.write(url + '\n')

    console.print("\n[green]✅ 排序完成！[/green]")
    console.print(f"  有效 URL: [green]{len(valid_urls)}[/green]")
    if invalid_count:
        console.print(f"  忽略无效行: [yellow]{invalid_count}[/yellow]")
    console.print(f"  保存到: [cyan]{output_path}[/cyan]")

    console.print("\n[dim]预览:[/dim]")
    for i, u in enumerate(valid_urls[:5], 1):
        console.print(f"  [dim]{i}. {u}[/dim]")
    if len(valid_urls) > 5:
        console.print(f"  [dim]... 共 {len(valid_urls)} 个[/dim]")

    return True


# ---------- TUI 键盘输入 ----------
def get_key():
    key = msvcrt.getch()
    if key == b'\xe0':
        key = msvcrt.getch()
        if key == b'H':
            return 'up'
        elif key == b'P':
            return 'down'
        elif key == b'M':
            return 'right'
        elif key == b'K':
            return 'left'
    elif key == b'\r':
        return 'enter'
    elif key == b'\x1b':
        return 'esc'
    return None

# ---------- 选择器 ----------
def select_mode_with_arrows():
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]模组版本兼容性检查工具[/bold cyan]\n"
        "[dim]选择运行模式 (↑↓ 选择，Enter 确认)[/dim]",
        border_style="cyan"
    ))

    modes = [
        {"key": "check", "display": "兼容性检查", "desc": "检查模组/材质包对版本范围的兼容性并生成Excel报告", "color": "blue"},
        {"key": "download", "display": "批量下载", "desc": "根据指定版本和加载器下载模组/材质包文件", "color": "green"},
        {"key": "sort", "display": "排序URL", "desc": "对选定文本文件中的URL按字母顺序排序并保存", "color": "yellow"},
    ]

    selected_idx = 0
    console.print("\n")

    def render_menu():
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        table.add_column("", width=4)
        table.add_column("模式", width=20)
        table.add_column("描述", width=45)
        table.add_column("状态", width=10)

        for i, mode in enumerate(modes):
            if i == selected_idx:
                prefix = "[bold cyan]▶[/bold cyan]"
                display = f"[bold white on cyan] {mode['display']} [/bold white on cyan]"
                status = "[cyan]← 当前选择[/cyan]"
            else:
                prefix = "  "
                display = f"[{mode['color']}]{mode['display']}[/{mode['color']}]"
                status = ""

            table.add_row(prefix, display, mode['desc'], status)

        return table

    def draw():
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]模组版本兼容性检查工具[/bold cyan]\n"
            "[dim]选择运行模式 (↑↓ 选择，Enter 确认)[/dim]",
            border_style="cyan"
        ))
        console.print("\n")
        console.print(render_menu())
        console.print("\n[dim]提示: 使用 ↑↓ 选择，Enter 确认[/dim]")

    draw()

    while True:
        key = get_key()
        if key == 'up':
            selected_idx = (selected_idx - 1) % len(modes)
            draw()
        elif key == 'down':
            selected_idx = (selected_idx + 1) % len(modes)
            draw()
        elif key == 'enter':
            return modes[selected_idx]["key"]
        elif key == 'esc':
            return None

def select_loader_with_arrows():
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]模组版本兼容性检查工具[/bold cyan]\n"
        "[dim]使用 ↑↓ 方向键选择，Enter 确认，ESC 取消[/dim]",
        border_style="cyan"
    ))

    loaders = [
        {"key": "fabric", "display": "Fabric", "desc": "轻量级模组加载器", "color": "green"},
        {"key": "forge", "display": "Forge", "desc": "最流行的模组加载器", "color": "orange1"},
        {"key": "neoforge", "display": "NeoForge", "desc": "Forge的现代分支", "color": "magenta"},
        {"key": "quilt", "display": "Quilt", "desc": "Fabric的继任者", "color": "blue"},
        {"key": "all", "display": "全部", "desc": "不过滤加载器", "color": "white"},
    ]

    selected_idx = 0
    console.print("\n")

    def render_menu():
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        table.add_column("", width=4)
        table.add_column("加载器", width=15)
        table.add_column("描述", width=35)
        table.add_column("状态", width=10)

        for i, loader in enumerate(loaders):
            if i == selected_idx:
                prefix = "[bold cyan]▶[/bold cyan]"
                display = f"[bold white on cyan] {loader['display']} [/bold white on cyan]"
                status = "[cyan]← 当前选择[/cyan]"
            else:
                prefix = "  "
                display = f"[{loader['color']}]{loader['display']}[/{loader['color']}]"
                status = ""

            table.add_row(prefix, display, loader['desc'], status)

        return table

    def draw():
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]模组版本兼容性检查工具[/bold cyan]\n"
            "[dim]使用 ↑↓ 方向键选择，Enter 确认，ESC 取消[/dim]",
            border_style="cyan"
        ))
        console.print("\n")
        console.print(render_menu())
        console.print("\n[dim]提示: 使用 ↑↓ 选择，Enter 确认[/dim]")

    draw()

    while True:
        key = get_key()
        if key == 'up':
            selected_idx = (selected_idx - 1) % len(loaders)
            draw()
        elif key == 'down':
            selected_idx = (selected_idx + 1) % len(loaders)
            draw()
        elif key == 'enter':
            return loaders[selected_idx]["key"]
        elif key == 'esc':
            return None

def select_version_type_with_arrows():
    """选择版本类型：release, beta, alpha"""
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]选择版本类型[/bold cyan]\n"
        "[dim]使用 ↑↓ 方向键选择，Enter 确认，ESC 取消[/dim]",
        border_style="cyan"
    ))

    types = [
        {"key": "release", "display": "Release", "desc": "稳定版", "color": "green"},
        {"key": "beta", "display": "Beta", "desc": "测试版", "color": "yellow"},
        {"key": "alpha", "display": "Alpha", "desc": "早期测试版", "color": "red"},
    ]

    selected_idx = 0
    console.print("\n")

    def render_menu():
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        table.add_column("", width=4)
        table.add_column("类型", width=15)
        table.add_column("描述", width=35)
        table.add_column("状态", width=10)

        for i, typ in enumerate(types):
            if i == selected_idx:
                prefix = "[bold cyan]▶[/bold cyan]"
                display = f"[bold white on cyan] {typ['display']} [/bold white on cyan]"
                status = "[cyan]← 当前选择[/cyan]"
            else:
                prefix = "  "
                display = f"[{typ['color']}]{typ['display']}[/{typ['color']}]"
                status = ""

            table.add_row(prefix, display, typ['desc'], status)

        return table

    def draw():
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]选择版本类型[/bold cyan]\n"
            "[dim]使用 ↑↓ 方向键选择，Enter 确认，ESC 取消[/dim]",
            border_style="cyan"
        ))
        console.print("\n")
        console.print(render_menu())
        console.print("\n[dim]提示: 使用 ↑↓ 选择，Enter 确认[/dim]")

    draw()

    while True:
        key = get_key()
        if key == 'up':
            selected_idx = (selected_idx - 1) % len(types)
            draw()
        elif key == 'down':
            selected_idx = (selected_idx + 1) % len(types)
            draw()
        elif key == 'enter':
            return types[selected_idx]["key"]
        elif key == 'esc':
            return None

def select_file_with_arrows(files, prompt="选择输入文件"):
    """从多个文件中选择一个（使用方向键）"""
    if not files:
        return None
    if len(files) == 1:
        return files[0]

    selected_idx = 0

    def render_menu():
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2))
        table.add_column("", width=4)
        table.add_column("文件名", width=50)
        table.add_column("状态", width=12)

        for i, file in enumerate(files):
            if i == selected_idx:
                prefix = "[bold cyan]▶[/bold cyan]"
                display = f"[bold white on cyan] {file} [/bold white on cyan]"
                status = "[cyan]← 当前选择[/cyan]"
            else:
                prefix = "  "
                display = f"[white]{file}[/white]"
                status = ""

            table.add_row(prefix, display, status)

        return table

    def draw():
        console.clear()
        console.print(Panel.fit(
            f"[bold cyan]{prompt}[/bold cyan]\n"
            "[dim]使用 ↑↓ 方向键选择，Enter 确认，ESC 取消[/dim]",
            border_style="cyan"
        ))
        console.print("\n")
        console.print(render_menu())
        console.print("\n[dim]提示: 使用 ↑↓ 选择，Enter 确认[/dim]")

    draw()

    while True:
        key = get_key()
        if key == 'up':
            selected_idx = (selected_idx - 1) % len(files)
            draw()
        elif key == 'down':
            selected_idx = (selected_idx + 1) % len(files)
            draw()
        elif key == 'enter':
            return files[selected_idx]
        elif key == 'esc':
            return None


# ---------- 扫描有效URL文件 ----------
def scan_valid_url_files(checker):
    """扫描当前目录下含有效模组/材质包URL的 .txt 文件"""
    txt_files = [f for f in os.listdir('.') if f.lower().endswith('.txt') and os.path.isfile(f)]
    valid_files = []
    for fname in txt_files:
        try:
            lines = read_lines_any_encoding(fname)
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                platform, identifier, _ = checker.parse_url(line)
                if platform and identifier:
                    valid_files.append(fname)
                    break
        except Exception:
            continue
    return valid_files


# ---------- 主程序 ----------
def main():
    try:
        mode = select_mode_with_arrows()
        if mode is None:
            console.print("[yellow]已取消操作[/yellow]")
            return

        checker = ModVersionChecker()

        # ================= 排序模式（独立功能） =================
        if mode == 'sort':
            console.clear()
            console.print(Panel.fit(
                "[bold cyan]排序URL[/bold cyan]\n"
                "[dim]对模组/材质包 URL 文本文件按字母顺序排序[/dim]",
                border_style="cyan"
            ))

            valid_files = scan_valid_url_files(checker)

            if not valid_files:
                console.print("\n[yellow]未在当前目录找到包含有效URL的 .txt 文件[/yellow]")
                manual = Prompt.ask(
                    "[cyan]请输入文件路径（留空退出）[/cyan]",
                    default=""
                ).strip().strip('"')
                if not manual or not os.path.isfile(manual):
                    console.print("[yellow]已取消[/yellow]")
                    return
                input_file = manual
            elif len(valid_files) == 1:
                input_file = valid_files[0]
                console.print(f"\n[green]📄 找到唯一有效的URL文件: {input_file}[/green]")
            else:
                console.print(f"\n[cyan]找到 {len(valid_files)} 个有效的URL文件，请选择：[/cyan]")
                input_file = select_file_with_arrows(valid_files, "请选择要排序的URL文件")
                if input_file is None:
                    console.print("[yellow]已取消选择[/yellow]")
                    return

            console.print("\n[bold]请选择输出方式：[/bold]")
            overwrite = Prompt.ask("是否覆盖原文件？", choices=["y", "n"], default="n") == "y"
            if overwrite:
                output_path = input_file
            else:
                base, ext = os.path.splitext(input_file)
                output_path = f"{base}_sorted{ext}"
                console.print(f"[dim]将保存到: {output_path}[/dim]")

            sort_url_file(input_file, output_path, overwrite, checker)
            return

        # ================= 检查 / 下载模式（共用文件读取） =================
        valid_files = scan_valid_url_files(checker)

        if not valid_files:
            console.print("[red]❌ 未找到有效的URL文件（.txt）[/red]")
            console.print("   请创建至少一个 .txt 文件，每行一个URL，例如：")
            console.print("  https://modrinth.com/mod/sodium")
            console.print("  https://modrinth.com/resourcepack/faithful")
            console.print("  https://www.curseforge.com/minecraft/mc-mods/jei")
            console.print("  https://www.curseforge.com/minecraft/texture-packs/faithful")
            console.print("\n[dim]提示：你也可以手动创建 mod_urls.txt 并放入上述内容。[/dim]")
            return

        if len(valid_files) == 1:
            input_file = valid_files[0]
            console.print(f"[green]📄 找到唯一有效的URL文件: {input_file}[/green]")
        else:
            console.print(f"[cyan]找到 {len(valid_files)} 个有效的URL文件，请选择：[/cyan]")
            input_file = select_file_with_arrows(valid_files, "请选择要使用的URL文件")
            if input_file is None:
                console.print("[yellow]已取消选择[/yellow]")
                return

        lines = read_lines_any_encoding(input_file)

        # 解析 URL 并检测类型
        url_entries = []  # (url, platform, identifier, content_type)
        invalid_count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            platform, identifier, content_type = checker.parse_url(line)
            if not platform or not identifier:
                invalid_count += 1
                continue
            # 未知类型通过 API 探测（带缓存）
            content_type = checker.resolve_content_type(platform, identifier, content_type)
            url_entries.append((line, platform, identifier, content_type))

        urls = [e[0] for e in url_entries]

        if not urls:
            console.print(f"[red]❌ 错误: {input_file} 中未找到任何有效的 Modrinth 或 CurseForge URL[/red]")
            return

        console.print(f"[green]📄 从 {input_file} 读取到 {len(urls)} 个有效的URL[/green]")
        if invalid_count > 0:
            console.print(f"[dim]（已忽略 {invalid_count} 行无效URL）[/dim]")

        # 判断文件中是否存在模组（模组需要加载器选择）
        has_mod = any(ct != 'resourcepack' for _, _, _, ct in url_entries)
        has_rp = any(ct == 'resourcepack' for _, _, _, ct in url_entries)

        if has_mod and has_rp:
            console.print("[cyan]📋 检测到文件包含 [bold]模组[/bold] 与 [bold]材质包[/bold]，仍需选择加载器（材质包将忽略加载器）[/cyan]")
        elif has_mod:
            console.print("[cyan]📋 检测到文件仅包含 [bold]模组[/bold][/cyan]")
        else:
            console.print("[cyan]📋 检测到文件仅包含 [bold]材质包[/bold]，无需选择加载器[/cyan]")

        # ---------------- 兼容性检查 ----------------
        if mode == 'check':
            console.print("\n[bold]请输入版本范围（支持格式: 1.18.2, 26.1, 26.1.2 等）[/bold]")
            min_version = Prompt.ask("[cyan]最低Minecraft版本[/cyan]")
            max_version = Prompt.ask("[cyan]最高Minecraft版本[/cyan]")

            if not min_version or not max_version:
                console.print("[red]❌ 版本范围不能为空[/red]")
                return

            if not re.match(r'^\d+\.\d+(\.\d+)?$', min_version) or not re.match(r'^\d+\.\d+(\.\d+)?$', max_version):
                console.print("[red]❌ 版本格式不正确，请使用 数字.数字 或 数字.数字.数字 格式[/red]")
                return

            if checker.compare_versions(min_version, max_version) > 0:
                console.print("[red]❌ 最低版本不能大于最高版本[/red]")
                return

            # 只有材质包时跳过加载器选择
            if has_mod:
                loader = select_loader_with_arrows()
                if loader is None:
                    console.print("[yellow]已取消操作[/yellow]")
                    return
                loader_param = None if loader == 'all' else loader
            else:
                console.print("\n[cyan]⏭️ 仅包含材质包，跳过加载器选择[/cyan]")
                loader = 'all'
                loader_param = None

            console.clear()
            console.print(Panel.fit(
                f"[bold cyan]兼容性检查[/bold cyan]\n"
                f"[dim]加载器: {loader.upper() if loader != 'all' else '全部（不过滤）'}[/dim]",
                border_style="cyan"
            ))

            mod_data, minecraft_versions = checker.process_mods(urls, min_version, max_version, loader_param)

            if mod_data and minecraft_versions:
                loader_suffix = f"_{loader}" if loader != 'all' else ""
                output_file = f'mod_compatibility_{min_version}_to_{max_version}{loader_suffix}.xlsx'
                checker.export_to_excel(mod_data, minecraft_versions, output_file)

                console.print("\n" + "=" * 70)
                console.print("[bold]📊 汇总信息:[/bold]")
                console.print(f"  总项目数: {len(mod_data)}")
                console.print(f"  Minecraft版本范围: {min_version}  ~  {max_version}")
                console.print(f"  检查的版本数: {len(minecraft_versions)}")
                console.print(f"  加载器过滤: {loader.upper() if loader != 'all' else '全部（不过滤）'}")

                if mod_data:
                    best = max(mod_data, key=lambda x: x['supported_percent'])
                    worst = min(mod_data, key=lambda x: x['supported_percent'])
                    console.print(f"  支持率最高: [green]{best['name']}[/green] ({best['supported_percent']:.1f}%)")
                    console.print(f"  支持率最低: [red]{worst['name']}[/red] ({worst['supported_percent']:.1f}%)")

                    table = Table(title="各项目支持率", box=box.ROUNDED)
                    table.add_column("名称", style="cyan")
                    table.add_column("平台", style="yellow")
                    table.add_column("类型", style="magenta")
                    table.add_column("支持率", style="green")
                    table.add_column("支持/总数")

                    for mod in sorted(mod_data, key=lambda x: x['supported_percent'], reverse=True):
                        color = "green" if mod['supported_percent'] >= 70 else "yellow" if mod['supported_percent'] >= 40 else "red"
                        table.add_row(
                            mod['name'],
                            mod['platform'],
                            mod['type_label'],
                            f"[{color}]{mod['supported_percent']:.1f}%[/{color}]",
                            f"{mod['supported_count']}/{len(minecraft_versions)}"
                        )

                    console.print(table)
            else:
                console.print("[red]❌ 处理失败，请检查网络连接或URL是否正确[/red]")

        # ---------------- 批量下载 ----------------
        elif mode == 'download':
            # 只有材质包时不询问加载器
            if has_mod:
                loader = select_loader_with_arrows()
                if loader is None or loader == 'all':
                    console.print("[yellow]下载模式包含模组时必须选择一个具体的加载器，已取消[/yellow]")
                    return
            else:
                console.print("\n[cyan]⏭️ 仅包含材质包，跳过加载器选择[/cyan]")
                loader = None

            console.print("\n[bold]请输入要下载的Minecraft版本（例如: 1.21.1）[/bold]")
            mc_version = Prompt.ask("[cyan]Minecraft版本[/cyan]")
            if not mc_version:
                console.print("[red]版本不能为空[/red]")
                return
            if not re.match(r'^\d+\.\d+(\.\d+)?$', mc_version):
                console.print("[red]版本格式不正确，请使用 数字.数字 或 数字.数字.数字 格式[/red]")
                return

            version_type = select_version_type_with_arrows()
            if version_type is None:
                console.print("[yellow]已取消操作[/yellow]")
                return

            console.clear()
            loader_display = loader.upper() if loader else "无（仅材质包）"
            console.print(Panel.fit(
                f"[bold cyan]批量下载[/bold cyan]\n"
                f"[dim]加载器: {loader_display}  |  版本: {mc_version}  |  类型: {version_type.upper()}[/dim]\n"
                f"[dim]下载将使用 Gopeed 的默认下载目录[/dim]",
                border_style="cyan"
            ))

            checker.batch_download(urls, mc_version, loader, version_type)

    except KeyboardInterrupt:
        console.print("\n[yellow]用户中断[/yellow]")
    finally:
        console.print("\n[bold yellow]按 Enter 键退出...[/bold yellow]")
        try:
            input()
        except EOFError:
            pass

if __name__ == "__main__":
    main()