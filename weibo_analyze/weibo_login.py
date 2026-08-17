"""
微博短信验证码登录 + 抓取博主近三年微博

流程:
  1. python weibo_login.py send <手机号>
       -> 微博下发验证码, 脚本暂存手机号到 .weibo_phone.txt
  2. python weibo_login.py login <验证码>
       -> 用暂存的手机号 + 验证码换登录态 cookie, 存到 .weibo_cookies.json
  3. python weibo_login.py fetch <uid> [years]
       -> 用 cookie 翻页抓取该 uid 博主近 years 年(默认3)的微博, 存 weibo_<uid>.json
  4. python weibo_login.py analyze <uid>
       -> 读取 weibo_<uid>.json, 输出人格特征分析报告

注意: cookie 等同账号登录态, 用完请执行 logout 或删除 .weibo_cookies.json
"""

import sys
import json
import time
import re
import os
import urllib.parse
import urllib.request
import http.cookiejar

# ---------- 公共配置 ----------

UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
UA_M = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

PHONE_FILE = ".weibo_phone.txt"
COOKIE_FILE = ".weibo_cookies.json"

# ---------- HTTP 工具 ----------

def make_opener(use_mobile=False, extra_cookies=None):
    """构造带 cookie jar 的 urllib opener"""
    jar = http.cookiejar.CookieJar()
    if extra_cookies:
        for c in extra_cookies:
            jar.set_cookie(c)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    ua = UA_M if use_mobile else UA_PC
    opener.addheaders = [
        ("User-Agent", ua),
        ("Accept", "application/json, text/plain, */*"),
        ("Accept-Language", "zh-CN,zh;q=0.9"),
        ("Referer", "https://weibo.com/"),
    ]
    return opener, jar

def jar_to_dict(jar):
    return {c.name: c.value for c in jar}

def save_cookies(jar):
    cookies = []
    for c in jar:
        cookies.append({
            "name": c.name, "value": c.value,
            "domain": c.domain, "path": c.path,
        })
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[cookie] 已保存 {len(cookies)} 条到 {COOKIE_FILE}")

def load_cookies():
    if not os.path.exists(COOKIE_FILE):
        return None
    with open(COOKIE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    jar = http.cookiejar.CookieJar()
    for c in data:
        cookie = http.cookiejar.Cookie(
            version=0, name=c["name"], value=c["value"],
            port=None, port_specified=False,
            domain=c["domain"], domain_specified=True,
            path=c["path"], path_specified=True,
            secure=False, expires=None, discard=False,
            comment=None, comment_url=None, rest={}, rfc2109=False,
        )
        jar.set_cookie(cookie)
    return jar

def restore_opener(use_mobile=False):
    """从文件恢复 cookie, 构造 opener"""
    jar = load_cookies()
    if jar is None:
        raise RuntimeError(f"未找到 {COOKIE_FILE}, 请先 login")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    ua = UA_M if use_mobile else UA_PC
    opener.addheaders = [
        ("User-Agent", ua),
        ("Accept", "application/json, text/plain, */*"),
        ("Referer", "https://weibo.com/"),
    ]
    return opener, jar

# ---------- 第1步: 发送验证码 ----------

def send_sms(phone):
    """提交手机号, 让微博下发短信验证码"""
    # 先访问登录页拿初始 cookie (visitor 流程)
    opener, jar = make_opener(use_mobile=True)
    # 访问 passport 登录页
    req = urllib.request.Request(
        "https://passport.weibo.com/sso/signin?entry=mweibo&source=loginpage&wm=3349&r=https%3A%2F%2Fm.weibo.cn",
        headers={"Referer": "https://m.weibo.cn/"}
    )
    try:
        opener.open(req, timeout=15).read()
    except Exception as e:
        print(f"[访客初始化] {e}")

    # 构造预检 token (csrf 防护)
    req = urllib.request.Request(
        "https://passport.weibo.com/visitor/genvisitor",
        data=urllib.parse.urlencode({
            "cb": "gen_callback",
            "fp": json.dumps({"os": "2", "browser": "Safari17", "fonts": "", "screenInfo": "", "plugins": ""}),
        }).encode(),
        headers={"Referer": "https://passport.weibo.com/"}
    )
    resp = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    m = re.search(r'"tid"\s*:\s*"([^"]+)"', resp)
    if not m:
        print("[genvisitor 响应]", resp[:300])
        raise RuntimeError("未拿到 tid")
    tid = m.group(1)
    print(f"[访客] tid={tid[:20]}...")

    # incarnate 换 SUB
    req = urllib.request.Request(
        f"https://passport.weibo.com/visitor/visitor?a=incarnate&t={tid}&w=2&c=100&gc=&cb=cross_domain&from=weibo&_rand={int(time.time()*1000)}",
        headers={"Referer": "https://passport.weibo.com/"}
    )
    opener.open(req, timeout=15).read()
    print(f"[访客] cookie 就绪: {list(jar_to_dict(jar).keys())}")

    # 调用发送验证码接口 (m.weibo.cn ajax)
    # 接口路径: https://passport.weibo.com/aj/checkuser/login
    # 实际发短信走 aj/sms/send
    csrf = jar_to_dict(jar).get("xsrf_token", "")
    payload = {
        "phone": phone,
        "type": "1",        # 1=短信验证码登录
        "countrycode": "86",
        "_t": str(int(time.time()*1000)),
    }
    req = urllib.request.Request(
        "https://passport.weibo.com/aj/sms/send",
        data=urllib.parse.urlencode(payload).encode(),
        headers={
            "Referer": "https://passport.weibo.com/sso/signin",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        }
    )
    try:
        resp = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        resp = e.read().decode("utf-8", errors="ignore")
        print(f"[HTTP {e.code}] {resp[:300]}")
    print("[发短信响应]", resp[:400])

    # 暂存手机号
    with open(PHONE_FILE, "w") as f:
        f.write(phone)
    print(f"[ok] 手机号已暂存 {PHONE_FILE}")
    print("[next] 收到验证码后执行: python weibo_login.py login <验证码>")

# ---------- 第2步: 用验证码换登录态 ----------

def login_with_code(code):
    if not os.path.exists(PHONE_FILE):
        raise RuntimeError(f"未找到 {PHONE_FILE}, 请先 send <手机号>")
    phone = open(PHONE_FILE).read().strip()

    opener, jar = make_opener(use_mobile=True)
    # 重新走访客流程拿 SUB
    req = urllib.request.Request(
        "https://passport.weibo.com/visitor/genvisitor",
        data=urllib.parse.urlencode({
            "cb": "gen_callback",
            "fp": json.dumps({"os": "2", "browser": "Safari17"}),
        }).encode(),
    )
    resp = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    tid = re.search(r'"tid"\s*:\s*"([^"]+)"', resp).group(1)
    opener.open(
        urllib.request.Request(
            f"https://passport.weibo.com/visitor/visitor?a=incarnate&t={tid}&w=2&c=100&cb=cross_domain",
            headers={"Referer": "https://passport.weibo.com/"}
        ), timeout=15
    ).read()

    # 提交手机号+验证码换登录
    payload = {
        "phone": phone,
        "code": code,
        "countrycode": "86",
        "type": "1",
        "remember": "on",
        "_t": str(int(time.time()*1000)),
    }
    req = urllib.request.Request(
        "https://passport.weibo.com/aj/checkuser/login",
        data=urllib.parse.urlencode(payload).encode(),
        headers={
            "Referer": "https://passport.weibo.com/sso/signin",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    try:
        resp = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        resp = e.read().decode("utf-8", errors="ignore")
    print("[登录响应]", resp[:500])

    try:
        data = json.loads(re.sub(r"^[^{]*", "", resp))
    except Exception:
        data = {}
    if data.get("code") == "100000" or data.get("retcode") == 0 or "uid" in str(data):
        save_cookies(jar)
        print("[ok] 登录成功")
    else:
        print("[warn] 响应未确认登录成功, 但仍保存 cookie 供试抓")
        save_cookies(jar)

# ---------- 第3步: 抓取博主微博 ----------

def clean_text(html_text):
    """清洗微博文本: 去 HTML 标签, 去 emoji 标记"""
    if not html_text:
        return ""
    # 去 <a> 等
    t = re.sub(r"<[^>]+>", "", html_text)
    # 去emoji span
    t = re.sub(r'\[.*?\]', lambda m: m.group(0), t)  # 保留 [emoji名]
    import html as html_mod
    t = html_mod.unescape(t)
    return t.strip()

def fetch_blogs(uid, years=3):
    opener, jar = restore_opener(use_mobile=True)
    opener.addheaders = [h for h in opener.addheaders if h[0] != "Referer"]
    opener.addheaders.append(("Referer", f"https://m.weibo.cn/u/{uid}"))

    cutoff = time.time() - years * 365 * 86400
    print(f"[抓取] uid={uid} 近{years}年 (created_at >= {time.strftime('%Y-%m-%d', time.localtime(cutoff))})")

    containerid = f"107603{uid}"
    all_blogs = []
    page = 1
    seen_ids = set()
    since_id = ""

    while True:
        url = f"https://m.weibo.cn/api/container/getIndex?type=uid&value={uid}&containerid={containerid}&page={page}"
        if since_id:
            url += f"&since_id={since_id}"
        req = urllib.request.Request(url)
        try:
            resp = opener.open(req, timeout=20).read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:200]
            print(f"[第{page}页] HTTP {e.code}: {body}")
            if e.code == 432:
                print("[!] 432 = cookie 失效, 请重新 login")
                break
            time.sleep(3)
            page += 1
            continue
        except Exception as e:
            print(f"[第{page}页] 异常 {e}, sleep 5")
            time.sleep(5)
            page += 1
            continue

        try:
            data = json.loads(resp)
        except Exception:
            print(f"[第{page}页] 非 JSON: {resp[:150]}")
            break

        if data.get("ok") != 1:
            print(f"[第{page}页] ok!=1: {str(data)[:200]}")
            break

        cards = data.get("data", {}).get("cards", [])
        mblogs = []
        for card in cards:
            if card.get("card_type") == 9:
                mblogs.append(card.get("mblog", {}))
            elif card.get("card_type") == 11 and card.get("cards"):
                # 列表内嵌
                for sub in card["cards"]:
                    if sub.get("card_type") == 9:
                        mblogs.append(sub.get("mblog", {}))

        if not mblogs:
            print(f"[第{page}页] 无微博, 结束")
            break

        new_count = 0
        for m in mblogs:
            mid = str(m.get("id") or m.get("mid") or "")
            if not mid or mid in seen_ids:
                continue
            seen_ids.add(mid)
            created_at = m.get("created_at", "")
            ts = parse_weibo_time(created_at)
            if ts and ts < cutoff:
                print(f"[第{page}页] 已到截止时间 ({created_at}), 结束")
                page = -1
                break
            text = clean_text(m.get("text", ""))
            retweeted = None
            if m.get("retweeted_status"):
                retweeted = clean_text(m["retweeted_status"].get("text", ""))
            all_blogs.append({
                "id": mid,
                "created_at": created_at,
                "ts": ts,
                "text": text,
                "source": m.get("source", ""),
                "pic_num": m.get("pic_num", 0),
                "reposts_count": m.get("reposts_count", 0),
                "comments_count": m.get("comments_count", 0),
                "attitudes_count": m.get("attitudes_count", 0),
                "retweeted_text": retweeted,
                "region_name": m.get("region_name", ""),
            })
            new_count += 1

        print(f"[第{page}页] +{new_count} 条, 累计 {len(all_blogs)}")
        if page == -1:
            break

        # 卡下一页 since_id
        card_group_info = data.get("data", {}).get("cardlistInfo", {})
        since_id = str(card_group_info.get("since_id") or "")
        if not since_id or since_id == "0":
            print(f"[第{page}页] since_id 空, 翻页结束")
            break

        page += 1
        time.sleep(1.5)  # 限速

    out = f"weibo_{uid}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "uid": uid,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total": len(all_blogs),
            "years_window": years,
            "blogs": all_blogs,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[ok] 共 {len(all_blogs)} 条 -> {out}")

def parse_weibo_time(s):
    """微博 created_at 格式: '今天 12:30' / '昨天 12:30' / '10-13' / '2024-10-13 12:30' / '10分钟前'"""
    if not s:
        return None
    import datetime
    now = datetime.datetime.now()
    try:
        if "前" in s:
            m = re.match(r"(\d+)\s*(分钟|小时|天)前", s)
            if m:
                n = int(m.group(1))
                if m.group(2) == "分钟": return (now - datetime.timedelta(minutes=n)).timestamp()
                if m.group(2) == "小时": return (now - datetime.timedelta(hours=n)).timestamp()
                if m.group(2) == "天": return (now - datetime.timedelta(days=n)).timestamp()
        if s.startswith("今天"):
            t = s.replace("今天", "").strip()
            d = datetime.datetime.strptime(t, "%H:%M")
            return datetime.datetime(now.year, now.month, now.day, d.hour, d.minute).timestamp()
        if s.startswith("昨天"):
            t = s.replace("昨天", "").strip()
            d = datetime.datetime.strptime(t, "%H:%M")
            y = now - datetime.timedelta(days=1)
            return datetime.datetime(y.year, y.month, y.day, d.hour, d.minute).timestamp()
        # YYYY-MM-DD HH:MM
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.datetime.strptime(s[:16], "%Y-%m-%d %H:%M").timestamp()
        # MM-DD (本年)
        if re.match(r"\d{2}-\d{2}$", s):
            d = datetime.datetime.strptime(s, "%m-%d")
            return datetime.datetime(now.year, d.month, d.day).timestamp()
        # MM-DD HH:MM (本年)
        if re.match(r"\d{2}-\d{2} \d{2}:\d{2}", s):
            d = datetime.datetime.strptime(s, "%m-%d %H:%M")
            return datetime.datetime(now.year, d.month, d.day, d.hour, d.minute).timestamp()
    except Exception:
        pass
    return None

# ---------- 入口 ----------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "send":
        if len(sys.argv) < 3:
            print("用法: send <手机号>")
            return
        send_sms(sys.argv[2])
    elif cmd == "login":
        if len(sys.argv) < 3:
            print("用法: login <验证码>")
            return
        login_with_code(sys.argv[2])
    elif cmd == "fetch":
        if len(sys.argv) < 3:
            print("用法: fetch <uid> [years]")
            return
        uid = sys.argv[2]
        years = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        fetch_blogs(uid, years)
    elif cmd == "logout":
        for f in [PHONE_FILE, COOKIE_FILE]:
            if os.path.exists(f):
                os.remove(f)
                print(f"已删除 {f}")
        print("[ok] 登录态已清除")
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
