"""复现微博 Nt 加密, 试调用 /sso/v2/sms/send"""
import urllib.request, urllib.parse, http.cookiejar, json, re, time

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

def Pr(s):
    """JS Pr: 每个字符转 2 位 hex"""
    return "".join(f"{ord(c):02x}" for c in s)

def Nt(i, key="MwmL8jWA"):
    """JS Nt: XOR -> reverse -> hex"""
    out = []
    for n, ch in enumerate(i):
        out.append(chr(ord(ch) ^ ord(key[n % len(key)])))
    return Pr("".join(out[::-1]))

# 测试加密
phone = "15380400412"
enc = Nt(phone)
print(f"phone={phone}")
print(f"Nt(phone)={enc}")
print(f"len={len(enc)}")

# 拿访客 cookie
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", UA), ("Referer", "https://passport.weibo.com/")]

# genvisitor
req = urllib.request.Request(
    "https://passport.weibo.com/visitor/genvisitor",
    data=urllib.parse.urlencode({"cb":"gen_callback","fp":json.dumps({"os":"2","browser":"Safari17"})}).encode(),
)
resp = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
tid = re.search(r'"tid":"([^"]+)"', resp).group(1)
print(f"tid={tid[:20]}...")

# incarnate
req = urllib.request.Request(
    f"https://passport.weibo.com/visitor/visitor?a=incarnate&t={tid}&w=2&c=100&cb=cross_domain&from=weibo&_rand={int(time.time()*1000)}",
)
opener.open(req, timeout=15).read()
cookies = {c.name: c.value for c in jar}
print(f"visitor cookies: {list(cookies.keys())}")

# 试调用 /sso/v2/sms/send
payload = {
    "entry": "mweibo",
    "mobile": enc,
    "mfa_id": "",
    "el": "1",
}
req = urllib.request.Request(
    "https://passport.weibo.com/sso/v2/sms/send",
    data=urllib.parse.urlencode(payload).encode(),
    headers={
        "Referer": "https://passport.weibo.com/sso/signin",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)
try:
    resp = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    print(f"[200] {resp[:500]}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="ignore")
    print(f"[HTTP {e.code}] {body[:500]}")
