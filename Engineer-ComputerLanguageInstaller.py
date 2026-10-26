#!/usr/bin/env python3
import argparse
import csv
import glob
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from concurrent.futures import ThreadPoolExecutor

APP_VERSION = "Model 1"
APP_TITLE = "工程师-计算机语言安装器"
DEVELOPER = "量方易动工作室 | QuantumMoveStudio"
OFFICIAL_SITE = "https://quantummovestudio.dpdns.org"
OPEN_SOURCE_PLATFORM = "Github"
OPEN_SOURCE_DEPARTMENT = "https://github.com/QuantumMoveStudio-Open/"
PARTNER_MIRROR_SITE = "https://sunworld-fuchuan-technology-organization.dnsglobalnodes.dpdns.org/Resources"
APP_ROOT_NAME = "QuantumMoveStudio"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PLAT = ""
IS_WIN = False
SUDO = ""
ROOT = ""
APP_DIR = ""
TIMEOUT = 900
DRY_RUN = False
FORCE_CLI = False
MIRROR = {}
MIRROR_APT_OK = False
APT_MIRROR_OPTS = ""
HELPER = {}
IMPORT_OK = {}
GOMODCACHE = ""
TOOLS = {}
PY = sys.executable
UA = "Mozilla/5.0 QuantumMoveStudio-Installer/1.0"

PLAN_ORDER = {
    "windows": ["win", "npm", "pip", "extra", "cargo", "go", "composer", "maven"],
    "android": ["termux", "npm", "pip", "extra", "cargo", "go", "composer", "maven"],
    "debian": ["apt", "snap", "npm", "pip", "extra", "cargo", "go", "composer", "maven"],
    "ubuntu": ["apt", "snap", "npm", "pip", "extra", "cargo", "go", "composer", "maven"],
    "freebsd": ["bsd", "npm", "pip", "extra", "cargo", "go", "composer", "maven"],
    "linux": ["apt", "snap", "npm", "pip", "extra", "cargo", "go", "composer", "maven"],
}

FRIENDLY_MOUNTS = ("/sdcard", "/storage/emulated/0", "/data", "/")

TOOL_CMD = {
    "win": "winget",
    "termux": "pkg",
    "bsd": "pkg",
    "apt": "apt-get",
    "snap": "snap",
    "npm": "npm",
    "pip": None,
    "go": "go",
    "cargo": "cargo",
    "composer": "composer",
    "maven": None,
    "extra": None,
}


def pr(msg=""):
    print(msg, flush=True)


def bar():
    return "=" * 42


def banner():
    pr(bar())
    pr("  📋" + APP_TITLE + "｜" + APP_VERSION)
    pr("  🪪开发者｜Developer：" + DEVELOPER)
    pr("  🌐官网｜Official website：" + OFFICIAL_SITE)
    pr("  🪧开源平台｜Open-source platform：" + OPEN_SOURCE_PLATFORM)
    pr("  🏢开源部｜Open Source Department：" + OPEN_SOURCE_DEPARTMENT)
    pr("  📦合作方镜像站｜Partner mirror site：" + PARTNER_MIRROR_SITE)
    pr(bar())
    pr("")


def section(title):
    pr("")
    pr("── " + title + " " + "─" * max(2, 38 - len(title)))


def human(n):
    try:
        n = float(n)
    except Exception:
        return "-"
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if abs(n) < step:
            return ("%.1f %s" % (n, unit)) if unit != "B" else ("%d B" % int(n))
        n /= step
    return "%.1f EB" % n


def detect_platform():
    sysname = platform.system().lower()
    if sysname == "windows":
        return "windows"
    if sysname == "freebsd" or os.path.exists("/usr/sbin/freebsd-update"):
        return "freebsd"
    if os.path.isdir("/data/data/com.termux") or "com.termux" in os.environ.get("PREFIX", ""):
        return "android"
    try:
        rel = platform.release().lower()
    except Exception:
        rel = ""
    if "android" in rel:
        return "android"
    txt = ""
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read().lower()
            break
        except Exception:
            continue
    if "termux" in txt or "android" in txt:
        return "android"
    match = re.search(r'^id="?([^"\n]+)"?', txt, re.M)
    oid = match.group(1).strip() if match else ""
    if oid == "ubuntu":
        return "ubuntu"
    if oid == "debian":
        return "debian"
    return "linux"


def read_os_release():
    data = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        data[k] = v.strip().strip('"')
            break
        except Exception:
            continue
    return data


def has_cmd(name):
    try:
        return shutil.which(name) is not None
    except Exception:
        return False


def run(cmd, timeout=None, env_extra=None, force=False):
    if DRY_RUN and not force:
        return True, "(dry-run) " + cmd
    env = os.environ.copy()
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if MIRROR.get("goproxy"):
        env["GOPROXY"] = MIRROR["goproxy"]
        env.setdefault("GO111MODULE", "on")
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout or TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "执行超时（超过 %d 秒）" % (timeout or TIMEOUT)
    except Exception as exc:
        return False, "无法执行：" + str(exc)
    tail = ""
    if p.stdout:
        tail += p.stdout.strip()
    if p.stderr:
        tail += ("\n" if tail else "") + p.stderr.strip()
    tail = "\n".join(tail.splitlines()[-25:])
    return p.returncode == 0, tail


def ensure_dir(path):
    if not path:
        return path
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


DEFAULTS = {
    "pip": "https://pypi.org/simple",
    "npm": "https://registry.npmjs.org/",
    "goproxy": "https://proxy.golang.org,direct",
    "maven": "https://repo1.maven.org/maven2",
    "cargo": "sparse+https://rsproxy.cn/index/",
    "composer": "https://repo.packagist.org",
    "conda": "https://repo.anaconda.com/miniconda",
}

MIRRORS = [
    {
        "id": "aliyun",
        "name": "阿里云",
        "test": "https://mirrors.aliyun.com/pypi/simple/",
        "pip": "https://mirrors.aliyun.com/pypi/simple/",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://mirrors.aliyun.com/goproxy/,direct",
        "maven": "https://maven.aliyun.com/repository/public",
        "cargo": "sparse+https://mirrors.aliyun.com/crates.io-index/",
        "composer": "https://mirrors.aliyun.com/composer",
        "debian": "https://mirrors.aliyun.com/debian",
        "debian_security": "https://mirrors.aliyun.com/debian-security",
        "ubuntu": "https://mirrors.aliyun.com/ubuntu",
        "conda": "https://mirrors.aliyun.com/anaconda/miniconda",
    },
    {
        "id": "tencent",
        "name": "腾讯云",
        "test": "https://mirrors.cloud.tencent.com/pypi/simple/",
        "pip": "https://mirrors.cloud.tencent.com/pypi/simple/",
        "npm": "https://mirrors.cloud.tencent.com/npm/",
        "goproxy": "https://mirrors.cloud.tencent.com/go/,direct",
        "maven": "https://mirrors.cloud.tencent.com/nexus/repository/maven-public/",
        "cargo": "sparse+https://mirrors.cloud.tencent.com/crates.io-index/",
        "composer": "https://mirrors.cloud.tencent.com/composer/",
        "debian": "https://mirrors.cloud.tencent.com/debian",
        "debian_security": "https://mirrors.cloud.tencent.com/debian-security",
        "ubuntu": "https://mirrors.cloud.tencent.com/ubuntu",
        "conda": "https://mirrors.cloud.tencent.com/anaconda/miniconda",
    },
    {
        "id": "huawei",
        "name": "华为云",
        "test": "https://repo.huaweicloud.com/repository/pypi/simple/",
        "pip": "https://repo.huaweicloud.com/repository/pypi/simple/",
        "npm": "https://repo.huaweicloud.com/repository/npm/",
        "goproxy": "https://repo.huaweicloud.com/repository/goproxy/,direct",
        "maven": "https://repo.huaweicloud.com/repository/maven/",
        "cargo": "sparse+https://repo.huaweicloud.com/repository/crates.io-index/",
        "composer": "https://repo.huaweicloud.com/repository/composer/",
        "debian": "https://repo.huaweicloud.com/debian",
        "debian_security": "https://repo.huaweicloud.com/debian-security",
        "ubuntu": "https://repo.huaweicloud.com/ubuntu",
        "conda": "https://repo.huaweicloud.com/miniconda",
    },
    {
        "id": "baidu",
        "name": "百度云",
        "test": "https://mirror.baidu.com/pypi/simple/",
        "pip": "https://mirror.baidu.com/pypi/simple/",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.bj.bcebos.com/,direct",
        "debian": "https://mirror.baidu.com/debian",
        "ubuntu": "https://mirror.baidu.com/ubuntu",
    },
    {
        "id": "zju",
        "name": "浙江大学",
        "test": "https://mirrors.zju.edu.cn/pypi/web/simple",
        "pip": "https://mirrors.zju.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://mirrors.zju.edu.cn/goproxy/,direct",
        "maven": "https://mirrors.zju.edu.cn/maven",
        "debian": "https://mirrors.zju.edu.cn/debian",
        "ubuntu": "https://mirrors.zju.edu.cn/ubuntu",
        "conda": "https://mirrors.zju.edu.cn/anaconda/miniconda",
    },
    {
        "id": "tuna",
        "name": "清华大学",
        "test": "https://pypi.tuna.tsinghua.edu.cn/simple/",
        "pip": "https://pypi.tuna.tsinghua.edu.cn/simple/",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,https://goproxy.io,direct",
        "maven": "https://mirrors.tuna.tsinghua.edu.cn/maven/",
        "cargo": "sparse+https://mirrors.tuna.tsinghua.edu.cn/crates.io-index/",
        "composer": "https://mirrors.tuna.tsinghua.edu.cn/composer/",
        "debian": "https://mirrors.tuna.tsinghua.edu.cn/debian",
        "debian_security": "https://mirrors.tuna.tsinghua.edu.cn/debian-security",
        "ubuntu": "https://mirrors.tuna.tsinghua.edu.cn/ubuntu",
        "conda": "https://mirrors.tuna.tsinghua.edu.cn/anaconda/miniconda",
    },
    {
        "id": "ustc",
        "name": "中科大",
        "test": "https://pypi.mirrors.ustc.edu.cn/simple/",
        "pip": "https://pypi.mirrors.ustc.edu.cn/simple/",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://mirrors.ustc.edu.cn/goproxy/,direct",
        "maven": "https://mirrors.ustc.edu.cn/maven/",
        "cargo": "sparse+https://mirrors.ustc.edu.cn/crates.io-index/",
        "composer": "https://mirrors.ustc.edu.cn/composer/",
        "debian": "https://mirrors.ustc.edu.cn/debian",
        "debian_security": "https://mirrors.ustc.edu.cn/debian-security",
        "ubuntu": "https://mirrors.ustc.edu.cn/ubuntu",
        "conda": "https://mirrors.ustc.edu.cn/anaconda/miniconda",
    },
    {
        "id": "sjtu",
        "name": "上海交通大学",
        "test": "https://mirror.sjtu.edu.cn/pypi/web/simple",
        "pip": "https://mirror.sjtu.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://mirror.sjtu.edu.cn/golang/,direct",
        "maven": "https://mirror.sjtu.edu.cn/maven/",
        "cargo": "sparse+https://mirror.sjtu.edu.cn/git/crates.io-index/",
        "debian": "https://mirror.sjtu.edu.cn/debian",
        "ubuntu": "https://mirror.sjtu.edu.cn/ubuntu",
        "conda": "https://mirror.sjtu.edu.cn/anaconda/miniconda",
    },
    {
        "id": "nju",
        "name": "南京大学",
        "test": "https://mirror.nju.edu.cn/pypi/web/simple/",
        "pip": "https://mirror.nju.edu.cn/pypi/web/simple/",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://mirror.nju.edu.cn/goproxy/,direct",
        "debian": "https://mirror.nju.edu.cn/debian",
        "ubuntu": "https://mirror.nju.edu.cn/ubuntu",
        "conda": "https://mirror.nju.edu.cn/anaconda/miniconda",
    },
    {
        "id": "fudan",
        "name": "复旦大学",
        "test": "https://mirrors.fudan.edu.cn/pypi/web/simple",
        "pip": "https://mirrors.fudan.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.fudan.edu.cn/debian",
        "ubuntu": "https://mirrors.fudan.edu.cn/ubuntu",
    },
    {
        "id": "whu",
        "name": "武汉大学",
        "test": "https://mirrors.whu.edu.cn/pypi/web/simple",
        "pip": "https://mirrors.whu.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.whu.edu.cn/debian",
        "ubuntu": "https://mirrors.whu.edu.cn/ubuntu",
    },
    {
        "id": "pku",
        "name": "北京大学",
        "test": "https://mirrors.pku.edu.cn/pypi/web/simple",
        "pip": "https://mirrors.pku.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.pku.edu.cn/debian",
        "ubuntu": "https://mirrors.pku.edu.cn/ubuntu",
    },
    {
        "id": "cas",
        "name": "中国科学院",
        "test": "https://mirrors.cas.cn/pypi/web/simple",
        "pip": "https://mirrors.cas.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.cas.cn/debian",
        "ubuntu": "https://mirrors.cas.cn/ubuntu",
    },
    {
        "id": "hust",
        "name": "华中科技大学",
        "test": "https://mirrors.hust.edu.cn/pypi/web/simple",
        "pip": "https://mirrors.hust.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://mirrors.hust.edu.cn/goproxy/,direct",
        "cargo": "sparse+https://mirrors.hust.edu.cn/crates.io-index/",
        "composer": "https://mirrors.hust.edu.cn/composer/",
        "debian": "https://mirrors.hust.edu.cn/debian",
        "ubuntu": "https://mirrors.hust.edu.cn/ubuntu",
        "conda": "https://mirrors.hust.edu.cn/anaconda/miniconda",
    },
    {
        "id": "sustech",
        "name": "南方科技大学",
        "test": "https://mirrors.sustech.edu.cn/pypi/web/simple",
        "pip": "https://mirrors.sustech.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.sustech.edu.cn/debian",
        "ubuntu": "https://mirrors.sustech.edu.cn/ubuntu",
    },
    {
        "id": "bfsu",
        "name": "北京外国语大学",
        "test": "https://mirrors.bfsu.edu.cn/pypi/web/simple",
        "pip": "https://mirrors.bfsu.edu.cn/pypi/web/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.bfsu.edu.cn/debian",
        "ubuntu": "https://mirrors.bfsu.edu.cn/ubuntu",
        "conda": "https://mirrors.bfsu.edu.cn/anaconda/miniconda",
    },
    {
        "id": "qlu",
        "name": "齐鲁工业大学",
        "test": "https://mirrors.qlu.edu.cn/pypi/simple",
        "pip": "https://mirrors.qlu.edu.cn/pypi/simple",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.qlu.edu.cn/debian",
        "ubuntu": "https://mirrors.qlu.edu.cn/ubuntu",
    },
    {
        "id": "douban",
        "name": "豆瓣 PyPI 镜像",
        "test": "https://pypi.doubanio.com/simple/",
        "pip": "https://pypi.doubanio.com/simple/",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
    },
    {
        "id": "netease",
        "name": "网易开源镜像站",
        "test": "https://mirrors.163.com/pypi/simple/",
        "pip": "https://mirrors.163.com/pypi/simple/",
        "npm": "https://registry.npmmirror.com",
        "goproxy": "https://goproxy.cn,direct",
        "debian": "https://mirrors.163.com/debian",
        "ubuntu": "https://mirrors.163.com/ubuntu",
    },
    {
        "id": "official",
        "name": "官方默认源",
        "test": "https://pypi.org/simple/",
        "pip": "https://pypi.org/simple",
        "npm": "https://registry.npmjs.org/",
        "goproxy": "https://proxy.golang.org,direct",
        "maven": "https://repo1.maven.org/maven2",
        "cargo": "https://github.com/rust-lang/crates.io-index",
        "composer": "https://repo.packagist.org",
        "conda": "https://repo.anaconda.com/miniconda",
    },
]


def probe_mirror(m):
    url = m.get("test") or m.get("pip")
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read(2048)
    except Exception:
        return m["id"], None
    return m["id"], (time.time() - started) * 1000.0


def probe_all(mirrors):
    results = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        for mid, ms in pool.map(probe_mirror, mirrors):
            results[mid] = ms
    return results


def mirror_speed_test():
    pr("  🚀正在测速合作方及国内主流镜像站（阿里云/腾讯云/华为云/百度云/高校源/…）")
    pr("  " + "-" * 60)
    results = probe_all(MIRRORS)
    if not any(v is not None for v in results.values()):
        pr("     （首轮全部超时，自动重试一轮…）")
        results = probe_all(MIRRORS)
    rows = []
    for m in MIRRORS:
        rows.append((m, results.get(m["id"])))
    rows.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0))
    ok_rows = [r for r in rows if r[1] is not None]
    rank = 0
    best = None
    for m, ms in rows:
        if ms is None:
            pr("     %-14s 不可达 / 超时" % m["name"])
            continue
        rank += 1
        pr("     %-14s %8.1f ms   #%d" % (m["name"], ms, rank))
        if best is None:
            best = m
    if len(ok_rows) >= 2:
        top = [m for m, _ in ok_rows[:3]]
        pr("     （对前 3 名复测一次…）")
        again = probe_all(top)
        for m in top:
            ms = again.get(m["id"])
            if ms is not None:
                pr("     %-14s %8.1f ms   复测" % (m["name"], ms))
        ok_rows = [(m, again.get(m["id"])) for m in top] + [r for r in ok_rows if r[0] not in top]
        ok_rows.sort(key=lambda x: (x[1] is None, x[1] if x[1] is not None else 0))
        best = ok_rows[0][0]
    if best is None:
        best = MIRRORS[-1]
        pr("  ⚠️ 所有镜像站均不可达，回落到 " + best["name"])
    pr("  ✅最优源：" + best["name"] + "（后续 pip / npm / Go / Maven / Cargo / Composer 均优先使用该源）")
    return best


def fill_mirror(m):
    data = dict(DEFAULTS)
    data.update({k: v for k, v in m.items() if isinstance(v, str) and v})
    data["name"] = m["name"]
    data["id"] = m["id"]
    host = urllib.parse.urlsplit(data["pip"]).hostname or ""
    data["pip_host"] = host
    return data


def write_file(path, text):
    try:
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception:
        return False


def apply_mirror(m):
    global MIRROR, MIRROR_APT_OK, APT_MIRROR_OPTS
    MIRROR = m
    cfg_dir = ensure_dir(APP_DIR)
    if has_cmd("pip3") or has_cmd("pip"):
        run("pip config set global.index-url " + m["pip"], timeout=60)
        run("pip config set global.trusted-host " + m["pip_host"], timeout=60)
    if IS_WIN:
        pip_ini = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "pip", "pip.ini")
    elif os.geteuid() == 0 if hasattr(os, "geteuid") else False:
        pip_ini = "/etc/pip.conf"
    else:
        pip_ini = os.path.join(os.path.expanduser("~"), ".config", "pip", "pip.conf")
    write_file(
        pip_ini,
        "[global]\nindex-url = %s\ntrusted-host = %s\ntimeout = 30\nretries = 3\n"
        % (m["pip"], m["pip_host"]),
    )
    if has_cmd("npm"):
        run("npm config set registry " + m["npm"], timeout=120)
    if has_cmd("go"):
        run("go env -w GO111MODULE=on", timeout=120)
        run("go env -w GOPROXY=" + m["goproxy"], timeout=120)
    cargo_home = os.path.join(os.path.expanduser("~"), ".cargo")
    ensure_dir(cargo_home)
    cargo_url = (m.get("cargo") or "").strip()
    if cargo_url and "github.com/rust-lang/crates.io-index" not in cargo_url:
        cargo_cfg = os.path.join(cfg_dir, "cargo-config.toml")
        if write_file(
            cargo_cfg,
            "[source.crates-io]\nreplace-with = 'qms-mirror'\n\n"
            "[source.qms-mirror]\nregistry = \"%s\"\n\n[net]\nretry = 3\n" % cargo_url,
        ):
            MIRROR["cargo_config"] = cargo_cfg
    if has_cmd("composer"):
        run("composer config -g repositories.packagist composer " + m["composer"], timeout=120)
    m2_settings = os.path.join(cfg_dir, "settings-mirror.xml")
    write_file(
        m2_settings,
        '<?xml version="1.0" encoding="UTF-8"?>\n<settings>\n  <mirrors>\n'
        "    <mirror>\n      <id>qms-mirror</id>\n      <name>%s</name>\n"
        "      <url>%s</url>\n      <mirrorOf>central</mirrorOf>\n    </mirror>\n"
        "  </mirrors>\n</settings>\n" % (m["name"], m["maven"]),
    )
    MIRROR["maven_settings"] = m2_settings
    MIRROR_APT_OK, APT_MIRROR_OPTS = build_apt_mirror(m)
    if MIRROR_APT_OK:
        pr("  🐧apt 已切换到 " + m["name"] + "（独立 sources 文件，未修改 /etc/apt/sources.list）")
    return m


def build_apt_mirror(m):
    if PLAT not in ("debian", "ubuntu"):
        return False, ""
    if not has_cmd("apt-get"):
        return False, ""
    info = read_os_release()
    codename = info.get("VERSION_CODENAME", "")
    if not codename:
        return False, ""
    if PLAT == "debian":
        base = m.get("debian")
        sec = m.get("debian_security")
        if not base:
            return False, ""
        lines = [
            "deb %s %s main contrib non-free non-free-firmware" % (base, codename),
            "deb %s %s-updates main contrib non-free non-free-firmware" % (base, codename),
            "deb %s %s-backports main contrib non-free non-free-firmware" % (base, codename),
        ]
        if sec:
            lines.append("deb %s %s-security main contrib non-free non-free-firmware" % (sec, codename))
    else:
        base = m.get("ubuntu")
        if not base:
            return False, ""
        lines = [
            "deb %s %s main restricted universe multiverse" % (base, codename),
            "deb %s %s-updates main restricted universe multiverse" % (base, codename),
            "deb %s %s-backports main restricted universe multiverse" % (base, codename),
            "deb %s %s-security main restricted universe multiverse" % (base, codename),
        ]
    work = os.path.join(APP_DIR, "apt-mirror")
    empty = os.path.join(work, "empty")
    lists = os.path.join(work, "lists")
    ensure_dir(empty)
    ensure_dir(os.path.join(lists, "partial"))
    src = os.path.join(work, "sources-mirror.list")
    if not write_file(src, "\n".join(lines) + "\n"):
        return False, ""
    opts = (
        '-o Dir::Etc::sourcelist="%s" -o Dir::Etc::sourceparts="%s" '
        '-o Dir::State::lists="%s" -o Dir::Etc::preferencesparts="%s" '
        '-o Acquire::Retries=3 -o Acquire::http::Timeout=15'
        % (src, empty, lists, empty)
    )
    ok, out = run("%sapt-get %s update" % (SUDO, opts), timeout=420)
    if not ok:
        return False, ""
    return True, opts


def windows_disks_raw():
    cmd = (
        "powershell -NoProfile -Command \"Get-CimInstance -ClassName Win32_LogicalDisk | "
        "Select-Object DeviceID,VolumeName,FileSystem,DriveType,Size,FreeSpace | "
        'ConvertTo-Csv -NoTypeInformation"'
    )
    ok, out = run(cmd, timeout=120)
    rows = []
    if ok and out:
        try:
            reader = csv.DictReader([line for line in out.splitlines() if line.strip()])
            for r in reader:
                rows.append(r)
        except Exception:
            rows = []
    media = ""
    ok2, out2 = run(
        "powershell -NoProfile -Command \"Get-PhysicalDisk | "
        "Select-Object FriendlyName,MediaType,Size | ConvertTo-Csv -NoTypeInformation\"",
        timeout=120,
    )
    if ok2 and out2:
        try:
            reader = csv.DictReader([line for line in out2.splitlines() if line.strip()])
            mt = [r.get("MediaType", "") for r in reader]
            mt = [x for x in mt if x]
            media = mt[0] if len(mt) == 1 else ""
        except Exception:
            media = ""
    return rows, media


def windows_disks():
    disks = []
    rows, media = windows_disks_raw()
    dtype_map = {"2": "可移动磁盘", "3": "本地磁盘", "4": "网络驱动器", "5": "光盘", "6": "RAM 磁盘"}
    if rows:
        for r in rows:
            try:
                total = float(r.get("Size") or 0)
                free = float(r.get("FreeSpace") or 0)
            except Exception:
                total, free = 0, 0
            if total <= 0:
                continue
            disks.append(
                {
                    "drive": r.get("DeviceID", ""),
                    "label": r.get("VolumeName", "") or "本地磁盘",
                    "mount": r.get("DeviceID", "") + "\\",
                    "type": dtype_map.get(str(r.get("DriveType", "")), "Unknown") + (" / " + media if media else ""),
                    "fs": r.get("FileSystem", "") or "-",
                    "total": total,
                    "free": free,
                }
            )
    if not disks:
        for code in range(65, 91):
            letter = chr(code)
            path = letter + ":\\"
            try:
                usage = shutil.disk_usage(path)
            except Exception:
                continue
            disks.append(
                {
                    "drive": letter + ":",
                    "label": "本地磁盘",
                    "mount": path,
                    "type": "本地磁盘",
                    "fs": "-",
                    "total": usage.total,
                    "free": usage.free,
                }
            )
    return disks


def posix_disks():
    disks = []
    mounts = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    mounts.append((parts[0], parts[1], parts[2]))
    except Exception:
        ok, out = run("mount", timeout=60)
        if ok:
            for line in out.splitlines():
                m = re.match(r"^(\S+)\s+on\s+(\S+)\s+type\s+(\S+)", line)
                if m:
                    mounts.append((m.group(1), m.group(2), m.group(3)))
    skip_fs = {
        "proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2", "debugfs",
        "securityfs", "pstore", "bpf", "tracefs", "configfs", "selinuxfs",
        "autofs", "mqueue", "hugetlbfs", "binfmt_misc", "fusectl", "nsfs",
    }
    skip_prefix = (
        "/apex", "/proc", "/sys", "/dev", "/run", "/boot", "/etc", "/snap", "/tmp/",
        "/var/lib/docker", "/var/lib/containerd", "/var/cache", "/media/", "/mnt/cdrom",
        "/system", "/system_ext", "/vendor", "/product", "/odm", "/mi_ext", "/cust",
        "/metadata", "/cache", "/debug_ramdisk", "/second_stage_resources", "/linkerconfig",
        "/mnt/vendor", "/mnt/product", "/mnt/system", "/mnt/expand", "/apex",
    )
    ro_fs = {"erofs", "squashfs"}
    min_size = 512 * 1024 * 1024
    for dev, mount, fs in mounts:
        if fs in skip_fs or fs.startswith("cgroup") or fs in ro_fs:
            continue
        if mount != "/" and any(mount == p or mount.startswith(p.rstrip("/") + "/") for p in skip_prefix):
            continue
        if re.match(r"^/dev/(block/)?loop\d+$", dev):
            continue
        if not (dev.startswith("/dev/") or fs in ("sdcardfs", "fuse", "overlay", "zfs", "ufs", "exfat")):
            continue
        try:
            usage = shutil.disk_usage(mount)
        except Exception:
            continue
        if usage.total <= 0 or usage.total < min_size:
            continue
        dtype = "内置存储"
        if fs in ("sdcardfs", "fuse", "exfat", "vfat", "fuseblk", "ntfs3", "ntfs"):
            dtype = "外部存储/SD 卡"
        disks.append(
            {
                "drive": dev,
                "label": os.path.basename(mount.rstrip("/")) or mount,
                "mount": mount,
                "type": dtype,
                "fs": fs,
                "total": usage.total,
                "free": usage.free,
            }
        )
    cand = []
    seen_dev = set()
    for d in disks:
        if d["drive"] in seen_dev:
            continue
        same = [x for x in disks if x["drive"] == d["drive"]]
        best = max(same, key=lambda x: x["total"])
        seen_dev.add(d["drive"])
        cand.append(best)
    for extra in ("/sdcard", "/storage/emulated/0", os.environ.get("PREFIX", "")):
        if not extra or extra in {d["mount"] for d in cand}:
            continue
        if not os.path.isdir(extra):
            continue
        try:
            usage = shutil.disk_usage(extra)
        except Exception:
            continue
        cand.append(
            {
                "drive": extra,
                "label": os.path.basename(extra.rstrip("/")) or extra,
                "mount": extra,
                "type": "内置存储/共享存储",
                "fs": "-",
                "total": usage.total,
                "free": usage.free,
            }
        )
    paths = sorted({d["mount"].rstrip("/") or "/" for d in cand}, key=lambda x: len(x))
    drop = set()
    for short in paths:
        for p in paths:
            if p != short and (p == short + "/" or p.startswith(short + "/")):
                drop.add(p)
    cand = [d for d in cand if (d["mount"].rstrip("/") or "/") not in drop]

    def rank(d):
        if d["mount"] in FRIENDLY_MOUNTS:
            return FRIENDLY_MOUNTS.index(d["mount"])
        return len(FRIENDLY_MOUNTS)

    uniq = []
    seen_size = {}
    for d in cand:
        key = (d["total"], d["free"])
        prev = seen_size.get(key)
        if prev is None:
            seen_size[key] = d
            uniq.append(d)
            continue
        if rank(d) < rank(prev) or (rank(d) == rank(prev) and len(d["mount"]) < len(prev["mount"])):
            uniq.remove(prev)
            seen_size[key] = d
            uniq.append(d)
    uniq.sort(key=lambda x: (-x["total"], len(x["mount"])))
    return uniq


def scan_disks():
    disks = windows_disks() if IS_WIN else posix_disks()
    section("💽磁盘信息扫描")
    pr("  %-3s %-13s %-10s %-13s %-8s %9s %9s" % ("序号", "盘符/设备", "磁盘名", "类型", "文件系统", "总容量", "剩余"))
    pr("  " + "-" * 62)
    if not disks:
        pr("  （未获取到磁盘信息，按默认路径继续）")
    for i, d in enumerate(disks, 1):
        pr(
            "  %-3s %-13s %-10s %-13s %-8s %9s %9s"
            % (
                str(i),
                d["drive"][:13],
                d["label"][:10],
                d["type"][:13],
                d["fs"][:8],
                human(d["total"]),
                human(d["free"]),
            )
        )
    return disks


def pick_root(disks, forced=None):
    global ROOT, APP_DIR
    if IS_WIN:
        default_root = os.environ.get("SystemDrive", "C:") + "\\"
        tip = "请输入安装盘符或目录（如 D:\\ 或 E:\\Apps 或 D），直接回车默认 " + default_root
    elif PLAT == "android":
        default_root = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        tip = "请输入安装路径（如 /sdcard/qms 或 /data/data/com.termux/files/usr），直接回车默认 " + default_root
    else:
        default_root = "/opt" if os.path.isdir("/opt") else "/usr/local"
        tip = "请输入安装路径（如 /opt、/srv、/home/<用户名>/apps），直接回车默认 " + default_root
    section("📂安装位置选择")
    pr("  💡系统包管理器（apt / pkg / winget / npm / pip 等）会安装到各自的系统默认目录；")
    pr("     此处路径用于存放手动下载安装的组件、Java 依赖仓库、Go/Rust/PHP 依赖工程与安装日志。")
    pr("")
    if forced:
        ROOT = forced
        if IS_WIN:
            if re.fullmatch(r"[A-Za-z]", ROOT):
                ROOT = ROOT.upper() + "\\"
            elif re.fullmatch(r"[A-Za-z]:", ROOT):
                ROOT = ROOT.upper() + "\\"
        ROOT = os.path.abspath(ROOT)
        ensure_dir(ROOT)
        APP_DIR = ensure_dir(os.path.join(ROOT, APP_ROOT_NAME))
        pr("  📥已通过命令行指定：" + os.path.abspath(ROOT))
        return ROOT
    while True:
        try:
            ans = input("  📥" + tip + "\n  >> ").strip().strip('"').strip("'")
        except EOFError:
            ans = ""
        if not ans:
            ROOT = default_root
            break
        if IS_WIN:
            if re.fullmatch(r"[A-Za-z]", ans):
                ans = ans.upper() + ":\\"
            elif re.fullmatch(r"[A-Za-z]:", ans):
                ans = ans.upper() + "\\"
            elif not ans.endswith("\\"):
                ans = ans + "\\"
            if re.fullmatch(r"[A-Za-z]:\\", ans) and disks:
                hit = [d for d in disks if d["drive"].upper() == ans[:2].upper()]
                if not hit:
                    pr("  ⚠️ 未检测到盘符 " + ans + "，请从上面的磁盘列表中选择。")
                    continue
            ROOT = ans
        else:
            ROOT = os.path.abspath(ans)
            if not os.path.isdir(ROOT):
                try:
                    os.makedirs(ROOT, exist_ok=True)
                except Exception:
                    pr("  ⚠️ 无法创建目录 " + ROOT + "，请重新输入或直接回车。")
                    continue
        break
    if os.path.isdir(ROOT) and not os.access(ROOT, os.W_OK):
        fallback = os.path.join(os.path.expanduser("~"), APP_ROOT_NAME)
        pr("  ⚠️ 目录不可写，自动改用：" + fallback)
        ROOT = os.path.abspath(fallback)
    ensure_dir(ROOT)
    APP_DIR = ensure_dir(os.path.join(ROOT, APP_ROOT_NAME))
    pr("  ✅安装根目录：" + os.path.abspath(ROOT))
    return ROOT


def scan_imports(mods):
    if not mods:
        return {}
    script = (
        "import importlib.util as u, json, sys\n"
        "mods = json.loads(sys.argv[1])\n"
        "out = {}\n"
        "for m in mods:\n"
        "    try:\n"
        "        out[m] = u.find_spec(m) is not None\n"
        "    except Exception:\n"
        "        out[m] = False\n"
        "sys.stdout.write(json.dumps(out))\n"
    )
    try:
        p = subprocess.run(
            [PY, "-c", script, json.dumps(sorted(set(mods)))],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
        )
        return json.loads(p.stdout.strip() or "{}")
    except Exception:
        return {m: False for m in mods}


def gomod_cache_dir():
    global GOMODCACHE
    if GOMODCACHE:
        return GOMODCACHE
    ok, out = run("go env GOMODCACHE", timeout=60, force=True)
    GOMODCACHE = out.strip() if ok and out.strip() else os.path.join(os.path.expanduser("~"), "go", "pkg", "mod")
    return GOMODCACHE


def m2_installed(g, a):
    repo = os.path.join(os.path.expanduser("~"), ".m2", "repository")
    d = os.path.join(repo, *g.split("."), a)
    if not os.path.isdir(d):
        return False
    for f in os.listdir(d):
        if f.endswith(".jar") or f.endswith(".pom"):
            return True
    return False


def gomod_installed(mod):
    base = os.path.join(gomod_cache_dir(), "cache", "download", *mod.split("/"))
    if os.path.isdir(base):
        return True
    gomod_file = os.path.join(HELPER.get("go", ""), "go.mod")
    try:
        with open(gomod_file, "r", encoding="utf-8", errors="ignore") as f:
            return mod in f.read()
    except Exception:
        return False


def cargo_installed(crate):
    manifest = os.path.join(HELPER.get("rust", ""), "Cargo.toml")
    try:
        with open(manifest, "r", encoding="utf-8", errors="ignore") as f:
            if re.search(r'(?m)^[\s"\']*' + re.escape(crate) + r'[\s"\']*[,=]', f.read()):
                return True
    except Exception:
        pass
    patterns = [
        os.path.join(os.path.expanduser("~"), ".cargo", "registry", "cache", "*", crate + "-*.crate"),
        os.path.join(os.path.expanduser("~"), ".cargo", "registry", "src", "*", crate + "-*"),
    ]
    for pat in patterns:
        if glob.glob(pat):
            return True
    return False


def composer_installed(pkg):
    base = HELPER.get("php", "")
    if base and os.path.isdir(os.path.join(base, "vendor", pkg)):
        return True
    manifest = os.path.join(base, "composer.json") if base else ""
    try:
        with open(manifest, "r", encoding="utf-8", errors="ignore") as f:
            return pkg in f.read()
    except Exception:
        return False


def eval_check(c):
    if not c:
        return False
    if isinstance(c, list):
        return any(eval_check(x) for x in c)
    if "cmd" in c:
        return has_cmd(c["cmd"])
    if "import" in c:
        return bool(IMPORT_OK.get(c["import"]))
    if "shell" in c:
        ok, _ = run(c["shell"], timeout=120, force=True)
        return ok
    if "shell_posix" in c and not IS_WIN:
        ok, _ = run(c["shell_posix"], timeout=120, force=True)
        return ok
    if "shell_win" in c and IS_WIN:
        ok, _ = run(c["shell_win"], timeout=120, force=True)
        return ok
    if "m2" in c:
        g, a = c["m2"].split(":")
        return m2_installed(g, a)
    if "gomod" in c:
        return gomod_installed(c["gomod"])
    if "cargo" in c:
        return cargo_installed(c["cargo"])
    if "composer" in c:
        return composer_installed(c["composer"])
    if "file" in c:
        return os.path.exists(os.path.expanduser(c["file"]))
    return False


def K(name, cat, url="", check=None, win=None, apt=None, termux=None, bsd=None,
      npm=None, pip=None, go=None, cargo=None, composer=None, mvn=None, extra=None):
    item = {
        "name": name,
        "cat": cat,
        "url": url,
        "check": check,
        "win": win or [],
        "apt": apt or [],
        "termux": termux or [],
        "bsd": bsd or [],
        "npm": [npm] if isinstance(npm, str) else (npm or []),
        "pip": [pip] if isinstance(pip, str) else (pip or []),
        "go": [go] if isinstance(go, str) else (go or []),
        "cargo": [cargo] if isinstance(cargo, str) else (cargo or []),
        "composer": [composer] if isinstance(composer, str) else (composer or []),
        "mvn": [mvn] if isinstance(mvn, str) else (mvn or []),
        "extra": extra or [],
    }
    return item


def build_catalog():
    A_LANG = "language"
    A_ENV = "environment"
    A_TOOL = "tool"
    A_MID = "middleware"
    A_FW = "framework"
    A_LIB = "library"
    items = []

    items.append(K("Java", A_LANG, "https://www.oracle.com/java/technologies/downloads/",
                   check={"cmd": "java"},
                   win=["winget install -e --id Microsoft.OpenJDK.21 --accept-package-agreements --accept-source-agreements",
                        "winget install -e --id EclipseAdoptium.Temurin.21.JDK --accept-package-agreements --accept-source-agreements"],
                   apt=["default-jdk", "openjdk-17-jdk"], termux=["openjdk-17"], bsd=["openjdk17", "openjdk21"]))
    items.append(K("Go", A_LANG, "https://go.dev/dl/", check={"cmd": "go"},
                   win=["winget install -e --id GoLang.Go --accept-package-agreements --accept-source-agreements"],
                   apt=["golang-go"], termux=["golang"], bsd=["go"]))
    items.append(K("PHP", A_LANG, "https://www.php.net/downloads.php", check={"cmd": "php"},
                   win=["winget install -e --id PHP.PHP.8.4 --accept-package-agreements --accept-source-agreements",
                        "winget install -e --id PHP.PHP.8.3 --accept-package-agreements --accept-source-agreements",
                        "winget install -e --id PHP.PHP --accept-package-agreements --accept-source-agreements"],
                   apt=["php-cli php-common", "php"], termux=["php"], bsd=["php83", "php82"],
                   extra=["curl -fsSL https://windows.php.net/downloads/releases/latest/php-8.4-nts-Win32-vs16-x64-latest.zip -o \"{ROOT}/php.zip\" && powershell -NoProfile -Command \"Expand-Archive -Force '{ROOT}/php.zip' '{ROOT}/php'\""]))
    items.append(K("Rust", A_LANG, "https://www.rust-lang.org/tools/install", check={"cmd": "rustc"},
                   win=["winget install -e --id Rustlang.Rustup --accept-package-agreements --accept-source-agreements"],
                   apt=["rustc cargo"], termux=["rust"], bsd=["rust"],
                   extra=["curl -fsSL https://sh.rustup.rs -o /tmp/rustup-init.sh && sh /tmp/rustup-init.sh -y --no-modify-path"]))

    items.append(K("Node.js", A_ENV, "https://nodejs.org/en/download", check={"cmd": "node"},
                   win=["winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements"],
                   apt=["nodejs npm", "nodejs"], termux=["nodejs", "nodejs-lts"], bsd=["node npm", "node20 npm-node20"]))
    items.append(K("JRE", A_ENV, "https://adoptium.net/temurin/releases/", check={"cmd": "java"},
                   win=["winget install -e --id EclipseAdoptium.Temurin.21.JRE --accept-package-agreements --accept-source-agreements"],
                   apt=["default-jre", "openjdk-17-jre"], termux=["openjdk-17"], bsd=["openjdk17-jre", "openjdk17"]))
    items.append(K("JDK", A_ENV, "https://adoptium.net/temurin/releases/", check={"cmd": "javac"},
                   win=["winget install -e --id Microsoft.OpenJDK.21 --accept-package-agreements --accept-source-agreements",
                        "winget install -e --id EclipseAdoptium.Temurin.21.JDK --accept-package-agreements --accept-source-agreements"],
                   apt=["default-jdk", "openjdk-17-jdk"], termux=["openjdk-17"], bsd=["openjdk17"]))
    items.append(K("JVM", A_ENV, "https://adoptium.net/temurin/releases/", check={"cmd": "java"},
                   win=["winget install -e --id EclipseAdoptium.Temurin.21.JRE --accept-package-agreements --accept-source-agreements"],
                   apt=["default-jre-headless", "default-jre"], termux=["openjdk-17"], bsd=["openjdk17"]))
    items.append(K("CPython", A_ENV, "https://www.python.org/downloads/", check={"cmd": "python3"},
                   win=["winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements"],
                   apt=["python3 python3-dev python3-pip"], termux=["python"], bsd=["python311", "python3"]))
    items.append(K("PHP-Zend Engine", A_ENV, "https://www.php.net/downloads.php",
                   check={"shell_posix": "php -v | grep -i 'zend engine'", "shell_win": "php -v | findstr /I \"Zend Engine\""},
                   win=["winget install -e --id PHP.PHP --accept-package-agreements --accept-source-agreements"],
                   apt=["php-cli php-common"], termux=["php"], bsd=["php83"]))
    items.append(K("PHP-FPM", A_ENV, "https://www.php.net/manual/en/install.fpm.php", check={"cmd": "php-fpm"},
                   apt=["php-fpm"], termux=["php-fpm"], bsd=["php83-fpm", "php82-fpm"]))
    items.append(K("Python venv", A_ENV, "https://docs.python.org/3/library/venv.html",
                   check={"shell_posix": "python3 -c \"import venv\"", "shell_win": "python -c \"import venv\""},
                   win=["winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements"],
                   apt=["python3-venv"], termux=["python"], bsd=["python311"]))
    items.append(K("Python-Conda", A_ENV, "https://docs.conda.io/projects/miniconda/en/latest/",
                   check={"cmd": "conda"},
                   win=["winget install -e --id Anaconda.Miniconda3 --accept-package-agreements --accept-source-agreements"],
                   extra=["curl -fsSL {CONDA_URL}/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh && sh /tmp/miniconda.sh -b -p {ROOT}/miniconda3",
                          "curl -fsSL {CONDA_URL}/Miniconda3-latest-MacOSX-arm64.sh -o /tmp/miniconda.sh && sh /tmp/miniconda.sh -b -p {ROOT}/miniconda3"]))
    items.append(K("Docker", A_ENV, "https://www.docker.com/products/docker-desktop/", check={"cmd": "docker"},
                   win=["winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements"],
                   apt=["docker.io docker-compose-plugin", "docker.io"], bsd=["docker"]))

    tools = []
    tools.append(K("Cloudflare Tunnel", A_TOOL, "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/",
                   check={"cmd": "cloudflared"},
                   win=["winget install -e --id Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements"],
                   apt=["cloudflared"], termux=["cloudflared"], bsd=["cloudflared"]))
    tools.append(K("npm", A_TOOL, "https://nodejs.org/en/download", check={"cmd": "npm"},
                   win=["winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements"],
                   apt=["npm"], termux=["nodejs"], bsd=["npm", "npm-node20"]))
    tools.append(K("yarn", A_TOOL, "https://yarnpkg.com/getting-started/install", check={"cmd": "yarn"},
                   win=["winget install -e --id Yarn.Yarn --accept-package-agreements --accept-source-agreements"],
                   apt=["yarn"], npm=["yarn"], termux=["yarn"], bsd=["yarn"]))
    tools.append(K("pnpm", A_TOOL, "https://pnpm.io/installation", check={"cmd": "pnpm"},
                   win=["winget install -e --id pnpm.pnpm --accept-package-agreements --accept-source-agreements"],
                   apt=["pnpm"], npm=["pnpm"], termux=["pnpm"]))
    tools.append(K("pip", A_TOOL, "https://pip.pypa.io/en/stable/installation/", check={"cmd": "pip3"},
                   win=["winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements"],
                   apt=["python3-pip"], termux=["python"], bsd=["py311-pip"],
                   extra=["\"%s\" -m ensurepip --upgrade" % PY, "\"%s\" -m ensurepip --default-pip" % PY]))
    tools.append(K("Maven", A_TOOL, "https://maven.apache.org/download.cgi", check={"cmd": "mvn"},
                   win=["winget install -e --id Apache.Maven --accept-package-agreements --accept-source-agreements"],
                   apt=["maven"], termux=["maven"], bsd=["maven"]))
    tools.append(K("Gradle", A_TOOL, "https://gradle.org/install/", check={"cmd": "gradle"},
                   win=["winget install -e --id Gradle.Gradle --accept-package-agreements --accept-source-agreements"],
                   apt=["gradle"], bsd=["gradle"]))
    tools.append(K("Composer", A_TOOL, "https://getcomposer.org/download/", check={"cmd": "composer"},
                   win=["winget install -e --id Composer.Composer --accept-package-agreements --accept-source-agreements",
                        "winget install -e --id Composer.Composer.2 --accept-package-agreements --accept-source-agreements"],
                   apt=["composer"], termux=["composer"], bsd=["composer", "php83-composer"],
                   extra=["curl -fsSL https://getcomposer.org/installer -o /tmp/composer-setup.php && php /tmp/composer-setup.php --install-dir=/usr/local/bin --filename=composer",
                          "curl -fsSL https://getcomposer.org/Composer-Setup.exe -o \"{ROOT}/Composer-Setup.exe\" && \"{ROOT}/Composer-Setup.exe\" /VERYSILENT /NORESTART"]))
    tools.append(K("Cargo", A_TOOL, "https://rustup.rs", check={"cmd": "cargo"},
                   win=["winget install -e --id Rustlang.Rustup --accept-package-agreements --accept-source-agreements"],
                   apt=["cargo"], termux=["rust"], bsd=["rust"],
                   extra=["curl -fsSL https://sh.rustup.rs -o /tmp/rustup-init.sh && sh /tmp/rustup-init.sh -y --no-modify-path"]))
    tools.append(K("Go Modules", A_TOOL, "https://go.dev/ref/mod", check={"cmd": "go"},
                   win=["winget install -e --id GoLang.Go --accept-package-agreements --accept-source-agreements"],
                   apt=["golang-go"], termux=["golang"], bsd=["go"],
                   extra=["go env -w GO111MODULE=on"]))
    tools.append(K("nvm", A_TOOL, "https://github.com/nvm-sh/nvm#installing-and-updating",
                   check=[{"file": "~/.nvm/nvm.sh"}, {"cmd": "nvm"}],
                   win=["winget install -e --id CoreyButler.NVMforWindows --accept-package-agreements --accept-source-agreements"],
                   extra=["curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"]))
    tools.append(K("pyenv", A_TOOL, "https://github.com/pyenv/pyenv#getting-pyenv",
                   check=[{"file": "~/.pyenv/bin/pyenv"}, {"cmd": "pyenv"}],
                   win=["winget install -e --id pyenv-win --accept-package-agreements --accept-source-agreements"],
                   extra=["curl -fsSL https://pyenv.run | bash"]))
    tools.append(K("sdkman", A_TOOL, "https://sdkman.io/install",
                   check=[{"file": "~/.sdkman/bin/sdkman-init.sh"}, {"cmd": "sdk"}],
                   extra=["curl -fsSL \"https://get.sdkman.io\" | bash"]))
    tools.append(K("ESLint", A_TOOL, "https://eslint.org/docs/latest/use/getting-started", check={"cmd": "eslint"}, npm=["eslint"]))
    tools.append(K("Prettier", A_TOOL, "https://prettier.io/docs/en/install", check={"cmd": "prettier"}, npm=["prettier"]))
    tools.append(K("SonarQube", A_TOOL, "https://www.sonarsource.com/products/sonarqube/downloads/",
                   check={"shell_posix": "docker image inspect sonarqube >/dev/null 2>&1",
                          "shell_win": "docker image inspect sonarqube >nul 2>&1"},
                   extra=["docker pull sonarqube:latest"], win=["winget install -e --id SonarSource.SonarQube --accept-package-agreements --accept-source-agreements"]))
    tools.append(K("JUnit", A_TOOL, "https://junit.org/junit5/docs/current/user-guide/",
                   check={"m2": "org.junit.jupiter:junit-jupiter"}, mvn=["org.junit.jupiter:junit-jupiter"]))
    tools.append(K("pytest", A_TOOL, "https://docs.pytest.org/en/stable/getting-started.html",
                   check={"import": "pytest"}, pip=["pytest"]))
    tools.append(K("Postman", A_TOOL, "https://www.postman.com/downloads/", check={"cmd": "postman"},
                   win=["winget install -e --id Postman.Postman --accept-package-agreements --accept-source-agreements"],
                   extra=["snap install postman"]))
    tools.append(K("Insomnia", A_TOOL, "https://insomnia.rest/download", check={"cmd": "insomnia"},
                   win=["winget install -e --id Insomnia.Insomnia --accept-package-agreements --accept-source-agreements"],
                   extra=["snap install insomnia"]))
    tools.append(K("Wireshark", A_TOOL, "https://www.wireshark.org/download.html", check={"cmd": "wireshark"},
                   win=["winget install -e --id WiresharkFoundation.Wireshark --accept-package-agreements --accept-source-agreements"],
                   apt=["wireshark"], bsd=["wireshark"], extra=["snap install wireshark"]))
    tools.append(K("Charles", A_TOOL, "https://www.charlesproxy.com/download/", check={"cmd": "charles"},
                   apt=["charles-proxy"]))
    tools.append(K("Fiddler", A_TOOL, "https://www.telerik.com/fiddler/fiddler-everywhere",
                   check={"cmd": "Fiddler Everywhere"},
                   win=["winget install -e --id Progress.Telerik.Fiddler.Everywhere --accept-package-agreements --accept-source-agreements",
                        "winget install -e --id Telerik.Fiddler.Everywhere --accept-package-agreements --accept-source-agreements"]))
    tools.append(K("Docker Compose", A_TOOL, "https://docs.docker.com/compose/install/",
                   check=[{"shell_posix": "docker compose version", "shell_win": "docker compose version"}],
                   win=["winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements"],
                   apt=["docker-compose-plugin", "docker-compose"], bsd=["docker-compose"],
                   extra=["curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose"]))
    tools.append(K("Kubernetes", A_TOOL, "https://kubernetes.io/docs/tasks/tools/", check={"cmd": "kubectl"},
                   win=["winget install -e --id Kubernetes.kubectl --accept-package-agreements --accept-source-agreements"],
                   apt=["kubernetes-client"], termux=["kubectl"], bsd=["kubectl"],
                   extra=["curl -fsSL \"https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl\" -o /usr/local/bin/kubectl && chmod +x /usr/local/bin/kubectl",
                          "snap install kubectl --classic"]))
    tools.append(K("Helm", A_TOOL, "https://helm.sh/docs/intro/install/", check={"cmd": "helm"},
                   win=["winget install -e --id Helm.Helm --accept-package-agreements --accept-source-agreements"],
                   apt=["helm"], bsd=["helm"],
                   extra=["curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash",
                          "snap install helm --classic"]))
    tools.append(K("Jenkins", A_TOOL, "https://www.jenkins.io/download/", check={"cmd": "jenkins"},
                   win=["winget install -e --id Jenkins.Jenkins --accept-package-agreements --accept-source-agreements"],
                   apt=["jenkins"]))
    tools.append(K("GitHub Actions", A_TOOL, "https://github.com/features/actions",
                   check={"file": "~/.github-runner/README.md"}))
    tools.append(K("GitLab CI", A_TOOL, "https://docs.gitlab.com/runner/install/",
                   check={"cmd": "gitlab-runner"},
                   apt=["gitlab-runner"], bsd=["gitlab-runner"]))
    items.extend(tools)

    mw = []
    for pkg in ["gunicorn", "uvicorn", "uwsgi", "hypercorn", "waitress", "daphne", "granian"]:
        mw.append(K(pkg if pkg != "uwsgi" else "uWSGI", A_MID,
                    "https://pypi.org/project/" + pkg + "/",
                    check=[{"cmd": pkg}, {"import": "uwsgi" if pkg == "uwsgi" else pkg}],
                    pip=[pkg]))
    mw[0]["name"] = "Gunicorn"
    mw[1]["name"] = "Uvicorn"
    mw[3]["name"] = "Hypercorn"
    mw[4]["name"] = "Waitress"
    mw[5]["name"] = "Daphne"
    mw[6]["name"] = "Granian"
    mw.append(K("Nginx", A_MID, "https://nginx.org/en/download.html", check={"cmd": "nginx"},
                apt=["nginx"], termux=["nginx"], bsd=["nginx"]))
    mw.append(K("Apache", A_MID, "https://httpd.apache.org/download.cgi", check={"cmd": "httpd"},
                apt=["apache2"], termux=["apache2"], bsd=["apache24"]))
    mw.append(K("Redis", A_MID, "https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/",
                check={"cmd": "redis-server"},
                win=["winget install -e --id Memurai.Memurai-Developer --accept-package-agreements --accept-source-agreements",
                     "winget install -e --id Memurai.MemuraiDeveloper --accept-package-agreements --accept-source-agreements"],
                apt=["redis-server"], termux=["redis"], bsd=["redis"],
                extra=["curl -fsSL https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip -o \"{ROOT}/redis.zip\" && powershell -NoProfile -Command \"Expand-Archive -Force '{ROOT}/redis.zip' '{ROOT}/redis'\""]))
    mw.append(K("MongoDB", A_MID, "https://www.mongodb.com/try/download/community", check={"cmd": "mongod"},
                win=["winget install -e --id MongoDB.Server --accept-package-agreements --accept-source-agreements",
                     "winget install -e --id MongoDB.MongoDBServer --accept-package-agreements --accept-source-agreements"],
                apt=["mongodb-server", "mongodb"], bsd=["mongodb70", "mongodb"]))
    mw.append(K("MySQL", A_MID, "https://dev.mysql.com/downloads/mysql/", check={"cmd": "mysqld"},
                win=["winget install -e --id Oracle.MySQL --accept-package-agreements --accept-source-agreements",
                     "winget install -e --id Oracle.MySQL.Server --accept-package-agreements --accept-source-agreements"],
                apt=["default-mysql-server", "mysql-server", "mariadb-server"],
                termux=["mariadb"], bsd=["mysql80-server", "mysql84-server"]))
    mw.append(K("SQLite", A_MID, "https://www.sqlite.org/download.html", check={"cmd": "sqlite3"},
                win=["winget install -e --id SQLite.SQLite --accept-package-agreements --accept-source-agreements"],
                apt=["sqlite3"], termux=["sqlite"], bsd=["sqlite3"]))
    mw.append(K("RabbitMQ", A_MID, "https://www.rabbitmq.com/download.html", check={"cmd": "rabbitmq-server"},
                win=["winget install -e --id RabbitMQ.RabbitMQ --accept-package-agreements --accept-source-agreements"],
                apt=["rabbitmq-server"], bsd=["rabbitmq"]))
    mw.append(K("Kafka", A_MID, "https://kafka.apache.org/downloads", check={"cmd": "kafka-server-start"},
                extra=["docker pull apache/kafka:latest"]))
    mw.append(K("RocketMQ", A_MID, "https://rocketmq.apache.org/download", check={"cmd": "mqbroker"},
                extra=["docker pull apache/rocketmq:latest"]))
    mw.append(K("Pulsar", A_MID, "https://pulsar.apache.org/download/", check={"cmd": "pulsar"},
                extra=["docker pull apachepulsar/pulsar:latest"]))
    mw.append(K("Memcached", A_MID, "https://memcached.org/downloads", check={"cmd": "memcached"},
                apt=["memcached"], termux=["memcached"], bsd=["memcached"]))
    mw.append(K("Elasticsearch", A_MID, "https://www.elastic.co/downloads/elasticsearch",
                check={"cmd": "elasticsearch"}, extra=["docker pull docker.elastic.co/elasticsearch/elasticsearch:latest"]))
    mw.append(K("Meilisearch", A_MID, "https://www.meilisearch.com/docs/learn/getting_started/installation",
                check={"cmd": "meilisearch"}, extra=["docker pull getmeili/meilisearch:latest"]))
    mw.append(K("Kong", A_MID, "https://konghq.com/install/", check={"cmd": "kong"},
                extra=["docker pull kong:latest"]))
    mw.append(K("APISIX", A_MID, "https://apisix.apache.org/docs/apisix/installation-guide/",
                check={"cmd": "apisix"}, extra=["docker pull apache/apisix:latest"]))
    mw.append(K("Zuul", A_MID, "https://github.com/Netflix/zuul",
                check={"m2": "com.netflix.zuul:zuul-core"}, mvn=["com.netflix.zuul:zuul-core"]))
    mw.append(K("Consul", A_MID, "https://developer.hashicorp.com/consul/downloads", check={"cmd": "consul"},
                win=["winget install -e --id Hashicorp.Consul --accept-package-agreements --accept-source-agreements"],
                apt=["consul"], bsd=["consul"]))
    mw.append(K("Zookeeper", A_MID, "https://zookeeper.apache.org/releases.html", check={"cmd": "zkServer"},
                apt=["zookeeperd", "zookeeper"], bsd=["zookeeper"]))
    mw.append(K("Eureka", A_MID, "https://github.com/Netflix/eureka",
                check={"m2": "com.netflix.eureka:eureka-client"}, mvn=["com.netflix.eureka:eureka-client"]))
    mw.append(K("HAProxy", A_MID, "https://www.haproxy.org/#down", check={"cmd": "haproxy"},
                win=["winget install -e --id HAProxy.HAProxy --accept-package-agreements --accept-source-agreements"],
                apt=["haproxy"], termux=["haproxy"], bsd=["haproxy"]))
    mw.append(K("MinIO", A_MID, "https://min.io/download", check={"cmd": "minio"},
                win=["winget install -e --id MinIO.MinIO.Server --accept-package-agreements --accept-source-agreements"],
                bsd=["minio"],
                extra=["curl -fsSL https://dl.min.io/server/minio/release/linux-amd64/minio -o /usr/local/bin/minio && chmod +x /usr/local/bin/minio",
                       "curl -fsSL https://dl.min.io/server/minio/release/windows-amd64/minio.exe -o \"{ROOT}/minio.exe\"",
                       "docker pull quay.io/minio/minio:latest"]))
    mw.append(K("Tomcat", A_MID, "https://tomcat.apache.org/download-10.cgi", check={"cmd": "catalina"},
                win=["winget install -e --id Apache.Tomcat --accept-package-agreements --accept-source-agreements"],
                apt=["tomcat11", "tomcat10"], bsd=["tomcat10", "tomcat9"]))
    mw.append(K("Jetty", A_MID, "https://jetty.org/download.html", check={"cmd": "jetty"},
                apt=["jetty9"], bsd=["jetty10"]))
    mw.append(K("PostgreSQL", A_MID, "https://www.postgresql.org/download/", check={"cmd": "psql"},
                win=["winget install -e --id PostgreSQL.PostgreSQL --accept-package-agreements --accept-source-agreements"],
                apt=["postgresql"], termux=["postgresql"], bsd=["postgresql16-server", "postgresql15-server"]))
    items.extend(mw)

    fw = []
    for pipname, impname in [("fastapi", "fastapi"), ("bottle", "bottle"), ("cherrypy", "cherrypy"),
                             ("pyramid", "pyramid"), ("flask", "flask"), ("sanic", "sanic"),
                             ("falcon", "falcon"), ("aiohttp", "aiohttp"), ("django", "django"),
                             ("tornado", "tornado")]:
        fw.append(K(pipname, A_FW, "https://pypi.org/project/" + pipname + "/",
                    check={"import": impname}, pip=[pipname]))
    for idx, display in enumerate(["FastAPI", "Bottle", "CherryPy", "Pyramid", "Flask", "Sanic", "Falcon", "Aiohttp", "Django", "Tornado"]):
        fw[idx]["name"] = display
    for name, coord in [("Spring Boot", "org.springframework.boot:spring-boot-starter-web"),
                        ("Quarkus", "io.quarkus:quarkus-core"),
                        ("Micronaut", "io.micronaut:micronaut-inject"),
                        ("Vert.x", "io.vertx:vertx-core"),
                        ("Jakarta", "jakarta.platform:jakarta.jakartaee-api")]:
        fw.append(K(name, A_FW, "https://start.spring.io/" if name == "Spring Boot" else "https://mvnrepository.com/",
                    check={"m2": coord}, mvn=[coord]))
    for name, mod in [("Gin", "github.com/gin-gonic/gin"), ("Echo", "github.com/labstack/echo/v4"),
                      ("Fiber", "github.com/gofiber/fiber/v2"), ("Chi", "github.com/go-chi/chi/v5"),
                      ("Beego", "github.com/beego/beego/v2"), ("GoFrame", "github.com/gogf/gf/v2")]:
        fw.append(K(name, A_FW, "https://pkg.go.dev/" + mod, check={"gomod": mod}, go=[mod]))
    for name, pkg in [("Laravel", "laravel/installer"), ("Symfony", "symfony/cli"),
                      ("CodeIgniter", "codeigniter4/framework"), ("Yii", "yiisoft/yii2"),
                      ("CakePHP", "cakephp/cakephp"), ("Slim", "slim/slim")]:
        fw.append(K(name, A_FW, "https://packagist.org/packages/" + pkg,
                    check={"composer": pkg}, composer=[pkg]))
    for name, crate in [("Axum", "axum"), ("Actix Web", "actix-web"), ("Rocket", "rocket"),
                        ("Warp", "warp"), ("Poem", "poem"), ("Loco", "loco-rs")]:
        fw.append(K(name, A_FW, "https://crates.io/crates/" + crate, check={"cargo": crate}, cargo=[crate]))
    items.extend(fw)

    libs = []
    for pipname, impname in [("requests", "requests"), ("numpy", "numpy"), ("pandas", "pandas"),
                             ("SQLAlchemy", "sqlalchemy"), ("Pillow", "PIL")]:
        libs.append(K(pipname, A_LIB, "https://pypi.org/project/" + pipname + "/",
                      check={"import": impname}, pip=[pipname]))
    for name, coord in [("Guava", "com.google.guava:guava"), ("Hutool", "cn.hutool:hutool-all"),
                        ("Jackson", "com.fasterxml.jackson.core:jackson-databind"),
                        ("Gson", "com.google.code.gson:gson"),
                        ("Logback", "ch.qos.logback:logback-classic"),
                        ("Log4j2", "org.apache.logging.log4j:log4j-core"),
                        ("HikariCP", "com.zaxxer:HikariCP")]:
        libs.append(K(name, A_LIB, "https://mvnrepository.com/artifact/" + coord.replace(":", "/"),
                      check={"m2": coord}, mvn=[coord]))
    for name, mod in [("Zap", "go.uber.org/zap"), ("Logrus", "github.com/sirupsen/logrus"),
                      ("GORM", "gorm.io/gorm"), ("Viper", "github.com/spf13/viper"),
                      ("Cobra", "github.com/spf13/cobra"), ("go-redis", "github.com/redis/go-redis/v9")]:
        libs.append(K(name, A_LIB, "https://pkg.go.dev/" + mod, check={"gomod": mod}, go=[mod]))
    for name, pkg in [("Guzzle", "guzzlehttp/guzzle"), ("Monolog", "monolog/monolog"),
                      ("PHPUnit", "phpunit/phpunit"), ("Carbon", "nesbot/carbon"),
                      ("Intervention Image", "intervention/image")]:
        libs.append(K(name, A_LIB, "https://packagist.org/packages/" + pkg,
                      check={"composer": pkg}, composer=[pkg]))
    for name, crate in [("Serde", "serde"), ("Tokio", "tokio"), ("Reqwest", "reqwest"),
                        ("Clap", "clap"), ("Anyhow", "anyhow"), ("Thiserror", "thiserror")]:
        libs.append(K(name, A_LIB, "https://crates.io/crates/" + crate, check={"cargo": crate}, cargo=[crate]))
    items.extend(libs)
    return items


def pkg_install_cmds(names):
    out = []
    for n in names:
        out.append("%spkg install -y %s" % (SUDO, n))
    return out


def apt_install_cmds(names):
    out = []
    for n in names:
        if MIRROR_APT_OK and APT_MIRROR_OPTS:
            out.append("%sapt-get %s install -y %s" % (SUDO, APT_MIRROR_OPTS, n))
        out.append("%sapt-get install -y %s" % (SUDO, n))
    return out


def npm_cmd(pkg):
    return "npm install -g %s --registry %s" % (pkg, MIRROR.get("npm", DEFAULTS["npm"]))


def pip_cmd(spec, index, flags):
    host = urllib.parse.urlsplit(index).hostname or ""
    base = ['"%s"' % PY, "-m", "pip", "install", "--disable-pip-version-check", "-i", index]
    if host:
        base += ["--trusted-host", host]
    base += flags
    return " ".join(base + [spec])


BUILD_HINTS = (
    "failed to build",
    "rust",
    "maturin",
    "is not a supported wheel",
    "cargo, the rust package manager",
)

TOOLCHAIN_CMD = {
    "android": "pkg install -y tur-repo && pkg update -y && pkg install -y rust clang make binutils maturin",
    "debian": "apt-get install -y build-essential rustc cargo python3-dev",
    "ubuntu": "apt-get install -y build-essential rustc cargo python3-dev",
    "freebsd": "pkg install -y rust gmake gcc",
    "windows": "winget install -e --id Rustlang.Rustup --accept-package-agreements --accept-source-agreements",
    "linux": "apt-get install -y build-essential rustc cargo python3-dev",
}


def pip_install(spec):
    indexes = [MIRROR.get("pip", DEFAULTS["pip"])]
    if "pypi.org" not in indexes[0]:
        indexes.append("https://pypi.org/simple")
    last = ""
    toolchain_done = False
    for idx in indexes:
        ok, out = run(pip_cmd(spec, idx, []), timeout=TIMEOUT)
        last = out
        if ok:
            return True, out
        follow = []
        low = (out or "").lower()
        if "externally-managed-environment" in low:
            follow.append(["--break-system-packages"])
        elif "permission denied" in low or "could not install packages" in low:
            follow.append(["--user"])
        for flags in follow:
            ok, out = run(pip_cmd(spec, idx, flags), timeout=TIMEOUT)
            last = out
            if ok:
                return True, out
        if any(h in low for h in BUILD_HINTS) and TOOLCHAIN_CMD.get(PLAT) and not toolchain_done:
            toolchain_done = True
            print("  [i] 检测到需要编译，正在安装 Rust/编译工具链后重试 ...")
            ok2, _ = run("%s%s" % (SUDO, TOOLCHAIN_CMD[PLAT]), timeout=TIMEOUT)
            if ok2:
                retries = (["--no-build-isolation"], ["--no-build-isolation", "--break-system-packages"]) if PLAT == "android" else (["--break-system-packages"], [])
                for flags in retries:
                    ok, out = run(pip_cmd(spec, idx, flags), timeout=TIMEOUT)
                    last = out
                    if ok:
                        return True, out
    return False, last


MAVEN_BASES = [
    "https://maven.aliyun.com/repository/public",
    "https://repo1.maven.org/maven2",
    "https://mirrors.cloud.tencent.com/nexus/repository/maven-public",
]

GOPROXY_FALLBACKS = [
    "https://goproxy.cn,https://goproxy.io,direct",
    "https://mirrors.aliyun.com/goproxy/,direct",
    "https://proxy.golang.org,direct",
]


def http_get_text(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def http_download(url, dest, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    ensure_dir(os.path.dirname(dest))
    with open(dest, "wb") as f:
        f.write(data)
    return True


def maven_versions(base, path):
    try:
        txt = http_get_text("%s/%s/maven-metadata.xml" % (base, path), timeout=15)
    except Exception:
        return None
    try:
        root = ElementTree.fromstring(txt.strip())
    except Exception:
        return None
    node = root.find("./versioning/release")
    if node is None or not (node.text or "").strip():
        node = root.find("./versioning/latest")
    if node is None or not (node.text or "").strip():
        versions = [v.text.strip() for v in root.findall("./versioning/versions/version") if (v.text or "").strip()]
        if versions:
            return versions[-1]
        return None
    return node.text.strip()


def maven_download(g, a):
    if DRY_RUN:
        return True, "(dry-run) maven %s:%s" % (g, a)
    repo = os.path.join(os.path.expanduser("~"), ".m2", "repository")
    path = g.replace(".", "/") + "/" + a
    bases = [MIRROR.get("maven")] if MIRROR.get("maven") else []
    bases += [b for b in MAVEN_BASES if b not in bases]
    last = "无可用 Maven 仓库"
    for base in bases:
        base = (base or "").rstrip("/")
        if not base:
            continue
        version = maven_versions(base, path)
        if not version:
            last = "无法获取版本列表：" + base
            continue
        dest_dir = os.path.join(repo, *path.split("/"), version)
        try:
            http_download(
                "%s/%s/%s/%s-%s.jar" % (base, path, version, a, version),
                os.path.join(dest_dir, "%s-%s.jar" % (a, version)),
            )
        except Exception as exc:
            last = "下载 jar 失败：" + str(exc)
            continue
        try:
            http_download(
                "%s/%s/%s/%s-%s.pom" % (base, path, version, a, version),
                os.path.join(dest_dir, "%s-%s.pom" % (a, version)),
            )
        except Exception:
            pass
        return True, "已下载 %s:%s:%s" % (g, a, version)
    return False, last


def cd_cmd(d, rest):
    if IS_WIN:
        return 'cd /d "%s" && %s' % (d, rest)
    return 'cd "%s" && %s' % (d, rest)


def ensure_go_module_dir():
    d = ensure_dir(HELPER["go"])
    if not os.path.isfile(os.path.join(d, "go.mod")):
        run(cd_cmd(d, "go mod init qmslang"), timeout=180)
    return d


def ensure_cargo_dir():
    d = ensure_dir(HELPER["rust"])
    src = ensure_dir(os.path.join(d, "src"))
    manifest = os.path.join(d, "Cargo.toml")
    if not os.path.isfile(manifest):
        write_file(
            manifest,
            '[package]\nname = "qmsdeps"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n',
        )
    lib = os.path.join(src, "lib.rs")
    if not os.path.isfile(lib):
        write_file(lib, "")
    return d


def ensure_composer_dir():
    d = ensure_dir(HELPER["php"])
    manifest = os.path.join(d, "composer.json")
    if not os.path.isfile(manifest):
        write_file(manifest, '{\n    "name": "qms/deps",\n    "require": {}\n}\n')
    return d


def substitute(cmd):
    root_final = APP_DIR
    return cmd.replace("{ROOT}", root_final).replace("{APP_DIR}", APP_DIR).replace(
        "{CONDA_URL}", MIRROR.get("conda", DEFAULTS["conda"])
    )


def attempts_for(item):
    out = []
    order = PLAN_ORDER.get(PLAT, PLAN_ORDER["linux"])
    for stage in order:
        tool = TOOL_CMD.get(stage)
        if stage == "extra":
            for raw in item.get("extra", []):
                cmd = substitute(raw)
                if IS_WIN and ("| bash" in cmd or "/usr/local/bin" in cmd or "/tmp/" in cmd):
                    continue
                need = "curl" in cmd
                if need and not (has_cmd("curl") or has_cmd("wget")):
                    continue
                out.append({"t": "sh", "cmd": cmd, "stage": stage})
            continue
        if tool and not has_cmd(tool):
            continue
        if stage == "win":
            for c in item.get("win", []):
                out.append({"t": "sh", "cmd": c, "stage": stage})
        elif stage == "apt":
            for c in apt_install_cmds(item.get("apt", [])):
                out.append({"t": "sh", "cmd": c, "stage": stage})
        elif stage in ("termux", "bsd"):
            key = "termux" if PLAT == "android" else "bsd"
            for c in pkg_install_cmds(item.get(key, [])):
                out.append({"t": "sh", "cmd": c, "stage": stage})
        elif stage == "snap":
            out.append({"t": "sh", "cmd": "%ssnap install %s" % (SUDO, item["name"].lower().replace(" ", "-")), "stage": stage})
        elif stage == "npm":
            for pkg in item.get("npm", []):
                out.append({"t": "sh", "cmd": npm_cmd(pkg), "stage": stage})
        elif stage == "pip":
            for spec in item.get("pip", []):
                out.append({"t": "pip", "spec": spec, "stage": stage})
                if PLAT == "android":
                    out.append(
                        {
                            "t": "sh",
                            "cmd": "pkg install -y python-%s" % spec.lower().replace("_", "-").replace(" ", "-"),
                            "stage": "termux_pypkg",
                        }
                    )
        elif stage == "go":
            for mod in item.get("go", []):
                out.append({"t": "gomod", "mod": mod, "stage": stage})
        elif stage == "cargo":
            for crate in item.get("cargo", []):
                out.append({"t": "cargo", "crate": crate, "stage": stage})
        elif stage == "composer":
            for pkg in item.get("composer", []):
                out.append({"t": "composer", "pkg": pkg, "stage": stage})
        elif stage == "maven":
            for coord in item.get("mvn", []):
                if ":" in coord:
                    g, at = coord.split(":", 1)
                    out.append({"t": "maven_dl", "g": g, "a": at, "stage": "maven_dl"})
                    out.append({"t": "maven", "g": g, "a": at, "stage": stage})
    return out


def exec_attempt(a):
    kind = a.get("t")
    if kind == "sh":
        return run(a["cmd"], timeout=TIMEOUT)
    if kind == "pip":
        return pip_install(a["spec"])
    if kind == "gomod":
        d = ensure_go_module_dir()
        mod = a["mod"]
        proxies = [MIRROR.get("goproxy")] + GOPROXY_FALLBACKS
        last = ""
        for px in proxies:
            if not px:
                continue
            ok, out = run(cd_cmd(d, "go get %s@latest" % mod), timeout=TIMEOUT, env_extra={"GOPROXY": px})
            if not ok:
                ok, out = run(cd_cmd(d, "go mod download %s@latest" % mod), timeout=TIMEOUT, env_extra={"GOPROXY": px})
            if ok:
                return True, out
            last = out
        return False, last
    if kind == "cargo":
        d = ensure_cargo_dir()
        cfgs = []
        if MIRROR.get("cargo_config"):
            cfgs.append('--config "%s"' % MIRROR["cargo_config"])
        cfgs.append("")
        last = ""
        for cfg in cfgs:
            ok, out = run(cd_cmd(d, "cargo add %s %s" % (a["crate"], cfg)), timeout=TIMEOUT)
            if not ok:
                ok, out = run(cd_cmd(d, "cargo fetch %s" % cfg), timeout=TIMEOUT)
            if ok:
                return True, out
            last = out
        return False, last
    if kind == "composer":
        d = ensure_composer_dir()
        pkg = a["pkg"]
        ok, out = run("composer global require %s --no-interaction" % pkg, timeout=TIMEOUT)
        if not ok:
            ok, out = run('composer require %s --no-interaction --working-dir="%s"' % (pkg, d), timeout=TIMEOUT)
        if not ok:
            ok, out = run(cd_cmd(d, "composer require %s --no-interaction" % pkg), timeout=TIMEOUT)
        return ok, out
    if kind == "maven_dl":
        return maven_download(a["g"], a["a"])
    if kind == "maven":
        if not has_cmd("mvn"):
            return False, "未检测到 mvn 命令"
        settings = MIRROR.get("maven_settings", "")
        if settings and os.path.isfile(settings):
            df = '-s "%s"' % settings
        else:
            df = ""
        for ver in ("RELEASE", "LATEST"):
            ok, out = run(
                "mvn -B %s dependency:get -Dartifact=%s:%s:%s -Dtransitive=false" % (df, a["g"], a["a"], ver),
                timeout=TIMEOUT,
            )
            if ok:
                return ok, out
        return False, out
    return False, "未知安装方式"


STAGE_LABEL = {
    "win": "winget",
    "termux": "pkg(Termux)",
    "bsd": "pkg(FreeBSD)",
    "apt": "apt",
    "snap": "snap",
    "npm": "npm",
    "pip": "pip",
    "go": "go get",
    "cargo": "cargo add",
    "composer": "composer",
    "maven": "mvn dependency:get",
    "maven_dl": "Maven 仓库直下载",
    "extra": "脚本下载",
}


def install_item(item, installed_map, report):
    name = item["name"]
    if installed_map.get(name):
        pr("  ⏭️  %-22s 已存在，跳过安装/更新" % name)
        report.append((name, item["cat"], "跳过（已安装）", ""))
        return
    attempts = attempts_for(item)
    if not attempts:
        pr("  🔗 %-22s 当前系统无可用安装方式 → %s" % (name, item["url"] or PARTNER_MIRROR_SITE))
        report.append((name, item["cat"], "需手动安装", item["url"]))
        return
    pr("  ▶️ %-22s 开始安装（%s）" % (name, " / ".join(sorted({STAGE_LABEL.get(a["stage"], a["stage"]) for a in attempts}))))
    last_out = ""
    for a in attempts:
        label = STAGE_LABEL.get(a["stage"], a["stage"])
        ok, out = exec_attempt(a)
        last_out = out or ""
        if ok:
            pr("  ✅ %-22s 安装成功（%s）" % (name, label))
            report.append((name, item["cat"], "安装成功", label))
            return
        pr("      · 方式 %s 失败，继续尝试下一个…" % label)
        if out:
            for line in out.splitlines()[-3:]:
                pr("        " + line[:150])
    pr("  🔗 %-22s 自动安装失败，请手动下载：%s" % (name, item["url"] or PARTNER_MIRROR_SITE))
    low = (last_out or "").lower()
    if any(h in low for h in BUILD_HINTS) and TOOLCHAIN_CMD.get(PLAT):
        pr("      💡该组件需要在本机编译（多为 Rust/本地扩展），可先手工执行：")
        pr("         " + TOOLCHAIN_CMD[PLAT])
        pr("         之后再重跑本安装器，该组件会自动跳过重装。")
    report.append((name, item["cat"], "自动安装失败", item["url"]))


def cli_choose(title, names, required, marks):
    section("🔢" + title)
    pr("  请输入编号选择，多选用“、”分隔（示例：1、3、5），支持 1-5 区间；直接回车跳过。")
    pr("")
    for i, n in enumerate(names, 1):
        tag = " ✔ 已安装" if marks.get(n) else ""
        pr("   [%2d] %s%s" % (i, n, tag))
    pr("")
    while True:
        try:
            raw = input("  👉请选择" + title + " >> ").strip()
        except EOFError:
            return []
        if not raw:
            if required:
                pr("  ⚠️ 该项为必选，请至少选择一个编号。")
                continue
            return []
        picks = set()
        bad = []
        for token in re.split(r"[、,，;；\s]+", raw):
            if not token:
                continue
            m = re.fullmatch(r"(\d+)-(\d+)", token)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
                if 1 <= lo <= hi <= len(names):
                    picks.update(range(lo, hi + 1))
                else:
                    bad.append(token)
                continue
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(names):
                    picks.add(idx)
                else:
                    bad.append(token)
            else:
                bad.append(token)
        if bad:
            pr("  ⚠️ 忽略无效输入：" + "、".join(bad))
        chosen = [names[i - 1] for i in sorted(picks)]
        if not chosen:
            if required:
                pr("  ⚠️ 该项为必选，请至少选择一个编号。")
                continue
            return []
        pr("  ✅已选择：" + "、".join(chosen))
        return chosen


def gui_available():
    if IS_WIN and not FORCE_CLI:
        try:
            return importlib.util.find_spec("tkinter") is not None
        except Exception:
            return False
    return False


def gui_choose(sections_info, marks):
    import tkinter as tk
    from tkinter import ttk

    result = {"ok": False, "picks": {}}

    win = tk.Tk()
    win.title("工程师-计算机语言安装器｜Model 1  -  " + DEVELOPER)
    win.geometry("900x640")
    win.minsize(760, 520)

    outer = ttk.Frame(win, padding=8)
    outer.pack(fill="both", expand=True)
    top = ttk.Label(
        outer,
        text="请勾选需要安装的项目（可直接多选；“✔”表示本机已检测到，会跳过）",
        anchor="w",
    )
    top.pack(fill="x")

    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    body = ttk.Frame(canvas)
    body_id = canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    def relayout(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(body_id, width=canvas.winfo_width())

    body.bind("<Configure>", relayout)
    canvas.bind("<Configure>", relayout)

    def on_wheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", on_wheel)

    vars_map = {}
    for si, sec in enumerate(sections_info):
        frame = ttk.LabelFrame(body, text=sec["title"] + ("（必选）" if sec["required"] else "（非必选）"))
        frame.pack(fill="x", pady=6, padx=4)
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x")
        row_vars = []
        ttk.Button(btn_row, text="全选", command=lambda rv=row_vars: [v.set(True) for v in rv]).pack(side="left")
        ttk.Button(btn_row, text="清空", command=lambda rv=row_vars: [v.set(False) for v in rv]).pack(side="left", padx=4)
        grid = ttk.Frame(frame)
        grid.pack(fill="x")
        for ni, name in enumerate(sec["names"]):
            v = tk.BooleanVar(value=False)
            text = name + ("  ✔" if marks.get(name) else "")
            cb = ttk.Checkbutton(grid, text=text, variable=v)
            cb.grid(row=ni // 3, column=ni % 3, sticky="w", padx=6, pady=2)
            row_vars.append(v)
            vars_map[(si, ni)] = v

    tip = ttk.Label(outer, foreground="#b00020", text="")
    tip.pack(fill="x", pady=4)

    def commit():
        picks = {}
        for si, sec in enumerate(sections_info):
            chosen = [sec["names"][ni] for ni in range(len(sec["names"])) if vars_map[(si, ni)].get()]
            if sec["required"] and not chosen:
                tip.configure(text="【%s】为必选项，请至少勾选一项。" % sec["title"])
                return
            picks[sec["title"]] = chosen
        result["ok"] = True
        result["picks"] = picks
        win.destroy()

    def cancel():
        win.destroy()

    btns = ttk.Frame(outer)
    btns.pack(fill="x")
    ttk.Button(btns, text="开始安装", command=commit).pack(side="right")
    ttk.Button(btns, text="取消", command=cancel).pack(side="right", padx=6)
    try:
        win.mainloop()
    except Exception:
        return {}
    if result["ok"]:
        return result["picks"]
    return {}


SECTION_TITLES = [
    ("计算机语言", "language", True),
    ("运行环境", "environment", False),
    ("开发工具", "tool", False),
    ("中间件", "middleware", False),
    ("开发框架", "framework", False),
    ("第三方库", "library", False),
]


def choose_all(catalog, installed_map):
    marks = {it["name"]: bool(installed_map.get(it["name"])) for it in catalog}
    sections_info = []
    for title, cat, required in SECTION_TITLES:
        names = [it["name"] for it in catalog if it["cat"] == cat]
        sections_info.append({"title": title, "cat": cat, "names": names, "required": required})
    picks = {}
    if gui_available():
        pr("  🪟已检测到 Windows 桌面环境，正在弹出可视化勾选窗口…")
        got = gui_choose(sections_info, marks)
        if got:
            for sec in sections_info:
                picks[sec["cat"]] = got.get(sec["title"], [])
            return picks
        pr("  ⚠️ 弹窗已取消或不可用，改用控制台数字选择。")
    for sec in sections_info:
        picks[sec["cat"]] = cli_choose(sec["title"] + ("（必选）" if sec["required"] else "（非必选）"),
                                       sec["names"], sec["required"], marks)
    return picks


def env_scan(catalog):
    global IMPORT_OK
    mods = []
    for it in catalog:
        chk = it.get("check")
        if isinstance(chk, dict) and "import" in chk:
            mods.append(chk["import"])
        elif isinstance(chk, list):
            for c in chk:
                if isinstance(c, dict) and "import" in c:
                    mods.append(c["import"])
    IMPORT_OK = scan_imports(mods)
    section("🔍环境扫描（已安装组件将被自动跳过）")
    found = []
    for it in catalog:
        try:
            ok = eval_check(it.get("check"))
        except Exception:
            ok = False
        if ok:
            found.append(it["name"])
    pr("  🧩扫描组件总数：%d，检测到已安装：%d" % (len(catalog), len(found)))
    if found:
        line = "     "
        for n in found:
            if len(line) + len(n) + 2 > 100:
                pr(line)
                line = "     "
            line += n + "、"
        if line.strip():
            pr(line.rstrip("、"))
    return found


def build_installed_map(catalog, found):
    return {name: True for name in found}


def write_report(report, log_path):
    lines = []
    lines.append(bar())
    lines.append("  " + APP_TITLE + "｜" + APP_VERSION + " 安装报告")
    lines.append("  开发者：" + DEVELOPER)
    lines.append("  官网：" + OFFICIAL_SITE)
    lines.append("  开源部：" + OPEN_SOURCE_DEPARTMENT)
    lines.append("  合作方镜像站：" + PARTNER_MIRROR_SITE)
    lines.append(bar())
    lines.append("操作系统：" + platform.platform())
    lines.append("平台标识：" + PLAT)
    lines.append("安装目录：" + os.path.abspath(APP_DIR))
    lines.append("使用镜像源：" + MIRROR.get("name", "-") + "  pip=" + MIRROR.get("pip", "-") + "  npm=" + MIRROR.get("npm", "-"))
    lines.append("")
    ok_cnt = sum(1 for r in report if r[2] == "安装成功")
    skip_cnt = sum(1 for r in report if r[2].startswith("跳过"))
    fail_cnt = sum(1 for r in report if "失败" in r[2] or "手动" in r[2])
    for name, cat, status, extra in report:
        lines.append("[%-14s] %-22s %s %s" % (cat, name, status, extra))
    lines.append("")
    lines.append("汇总：成功 %d 项 / 跳过（已安装） %d 项 / 需手动安装或失败 %d 项" % (ok_cnt, skip_cnt, fail_cnt))
    text = "\n".join(lines) + "\n"
    write_file(log_path, text)
    return ok_cnt, skip_cnt, fail_cnt


def parse_args():
    p = argparse.ArgumentParser(add_help=True, description=APP_TITLE)
    p.add_argument("-p", "-t", "--timeout", type=int, default=900, help="单条安装命令超时时间（秒）")
    p.add_argument("-r", "--root", default="", help="指定安装根目录，跳过交互式路径输入")
    p.add_argument("--no-gui", action="store_true", help="Windows 下也使用控制台数字选择")
    p.add_argument("--dry-run", action="store_true", help="只演练不真正执行安装命令")
    p.add_argument("--no-mirror", action="store_true", help="跳过源测速，直接使用系统默认源")
    return p.parse_args()


def main():
    global PLAT, IS_WIN, SUDO, TIMEOUT, DRY_RUN, FORCE_CLI, HELPER, MIRROR
    args = parse_args()
    TIMEOUT = max(60, args.timeout)
    DRY_RUN = args.dry_run
    FORCE_CLI = args.no_gui

    banner()
    pr("  🖥️ 运行环境：" + platform.platform() + " / Python " + platform.python_version())
    PLAT = detect_platform()
    IS_WIN = PLAT == "windows"
    labelmap = {
        "windows": "Windows",
        "android": "Android（Termux）",
        "debian": "Debian GNU/Linux",
        "ubuntu": "Ubuntu Linux",
        "freebsd": "FreeBSD",
        "linux": "Linux",
    }
    pr("  🎯已适配：" + labelmap.get(PLAT, PLAT) + "，后续将调用系统包管理器完成安装")

    SUDO = ""
    if not IS_WIN and hasattr(os, "geteuid") and os.geteuid() != 0 and has_cmd("sudo"):
        SUDO = "sudo "

    found_mgr = [m for m in ("winget", "apt-get", "pkg", "npm", "pip", "pip3", "go", "cargo", "composer", "mvn", "snap", "curl", "docker") if has_cmd(m)]
    pr("  🧰可用命令：" + ("、".join(found_mgr) if found_mgr else "（未检测到常见包管理器）"))

    disks = scan_disks()
    pick_root(disks, args.root)
    HELPER = {
        "go": os.path.join(APP_DIR, "go-modules"),
        "rust": os.path.join(APP_DIR, "rust-crates"),
        "php": os.path.join(APP_DIR, "php-packages"),
        "logs": ensure_dir(os.path.join(APP_DIR, "logs")),
    }

    section("🌐镜像源测速")
    best = MIRROR
    if args.no_mirror:
        best = fill_mirror(MIRRORS[-1])
        pr("  ⏭️ 已跳过测速，使用系统默认源")
    else:
        best = mirror_speed_test()
        best = fill_mirror(best)
    if not DRY_RUN:
        apply_mirror(best)
    else:
        MIRROR = best
    pr("  📌pip 源：" + MIRROR["pip"])
    pr("  📌npm 源：" + MIRROR["npm"])
    pr("  📌Go 代理：" + MIRROR["goproxy"])
    pr("  📌Maven 仓库：" + MIRROR["maven"])
    pr("  📌Cargo 源：" + MIRROR["cargo"])

    catalog = build_catalog()
    found = env_scan(catalog)
    installed_map = build_installed_map(catalog, found)

    picks = choose_all(catalog, installed_map)

    selected = []
    by_name = {it["name"]: it for it in catalog}
    for title, cat, required in SECTION_TITLES:
        for name in picks.get(cat, []):
            selected.append(by_name[name])

    if not selected:
        pr("")
        pr("  ℹ️ 未选择任何可安装项，程序结束。")
        return

    section("📝安装清单确认")
    for i, it in enumerate(selected, 1):
        mark = "（已安装，将跳过）" if installed_map.get(it["name"]) else ""
        pr("   %2d. [%s] %s %s" % (i, cat_label(it["cat"]), it["name"], mark))
    pr("")
    try:
        ans = input("  ❓确认开始安装？直接回车=开始，输入 n/N 取消 >> ").strip().lower()
    except EOFError:
        ans = ""
    if ans in ("n", "no", "nope"):
        pr("  ⏹️ 已取消安装。")
        return

    section("🚀开始安装")
    pr("  💡任一组件失败不会中断整体流程，失败项会给出下载地址并继续下一个。")
    report = []
    for it in selected:
        try:
            install_item(it, installed_map, report)
        except KeyboardInterrupt:
            pr("  ⏹️ 用户中断（Ctrl+C），已安装结果仍会写入报告。")
            break
        except Exception as exc:
            pr("  ❌ %-22s 安装过程异常：%s" % (it["name"], str(exc)))
            report.append((it["name"], it["cat"], "异常中断", it["url"]))

    log_path = os.path.join(HELPER["logs"], "install_report_%s.txt" % time.strftime("%Y%m%d_%H%M%S"))
    ok_cnt, skip_cnt, fail_cnt = write_report(report, log_path)

    section("📊安装结果汇总")
    for name, cat, status, extra in report:
        pr("   [%-14s] %-22s %-16s %s" % (cat, name, status, extra))
    pr("")
    pr("  ✅成功：%d   ⏭️ 跳过（已安装）：%d   🔗 失败/需手动：%d" % (ok_cnt, skip_cnt, fail_cnt))
    pr("  📄安装报告：" + log_path)
    pr("  🤝合作方镜像站：" + PARTNER_MIRROR_SITE)
    pr("  ♻️ 镜像配置已写入 pip / npm / go 等配置，如需恢复官方源可执行：")
    pr("      pip config unset global.index-url  ·  npm config set registry https://registry.npmjs.org/  ·  go env -u GOPROXY")
    pr("")
    pr(bar())
    pr("  🎉感谢使用 " + APP_TITLE + "｜" + DEVELOPER)
    pr(bar())


def cat_label(cat):
    return {
        "language": "语言",
        "environment": "运行环境",
        "tool": "工具",
        "middleware": "中间件",
        "framework": "框架",
        "library": "第三方库",
    }.get(cat, cat)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pr("")
        pr("  ⏹️ 已取消。")
