"""莱德人设构建器：服务端权威版本（App 端的同名文件后续删除）。"""
from datetime import date


def _age_text(birth_date: str, today: date) -> str | None:
    try:
        bd = date.fromisoformat(birth_date)
    except ValueError:
        return None
    if bd >= today:
        return None
    years = today.year - bd.year
    months = today.month - bd.month
    if today.day < bd.day:
        months -= 1
    if months < 0:
        years -= 1
        months += 12
    if years >= 1 and months > 0:
        return f"{years}岁{months}个月"
    if years >= 1:
        return f"{years}岁"
    if months >= 1:
        return f"{months}个月"
    return "刚出生不久"


def build_system_prompt(profile: dict, persona: dict, today: date | None = None) -> str:
    """把记忆档案 + 人设配置拼成 system prompt。两份配置都为空时仍有兜底人设。"""
    today = today or date.today()
    lines: list[str] = []

    name = persona.get("characterName") or "莱德队长"
    lines.append(f"你是{name}（Ryder），汪汪队的队长，正在陪伴一个不到三岁的小女孩。")
    lines.append("")

    # 记忆档案（可能为空）
    p = profile or {}
    about: list[str] = []
    if p.get("nickname"):
        about.append(f"· 小名：{p['nickname']}")
    age = _age_text(p.get("birthDate", ""), today)
    if age:
        about.append(f"· 年龄：{age}")
    for key, label in [
        ("heightWeight", "身高体重"),
        ("likes", "喜欢"),
        ("fears", "害怕"),
        ("routine", "作息"),
        ("familyTitles", "家里人的称呼"),
    ]:
        if p.get(key):
            about.append(f"· {label}：{p[key]}")
    kit = [c for c in (p.get("comfortKit") or []) if str(c).strip()]
    if kit:
        about.append("· 安抚锦囊（她哭闹或害怕时优先使用这些方法）：")
        about.extend(f"  {i + 1}. {c}" for i, c in enumerate(kit))
    if about:
        lines.append("【关于她】")
        lines.extend(about)
        lines.append("")

    # 说话方式（父亲可改，带默认）
    style = persona.get("speakingStyle") or (
        "· 每次只说1到3个短句，总共不超过60个字\n"
        "· 用词简单，像大哥哥一样热情、爱鼓励，常用“哇”“你好棒”\n"
        "· 她害怕或哭闹时，先温柔共情，再引导：“我知道你有点怕，莱德陪着你呢”\n"
        "· 可以叫她的小名，可以自然地提到她喜欢的东西"
    )
    lines.append("【说话方式】")
    lines.append(style)
    catchphrase = persona.get("catchphrase")
    if catchphrase:
        lines.append(f"· 偶尔用口头禅：“{catchphrase}”")
    lines.append("")

    # 安全红线（父亲可改，带默认）
    safety = persona.get("safetyRules") or (
        "· 绝不说可怕、暴力、悲伤的内容，不提死亡、鬼怪\n"
        "· 她想找爸爸妈妈时，温柔回应，并引导她去找家长\n"
        "· 不讨论超出幼儿理解范围的话题，用转移注意力代替解释"
    )
    lines.append("【安全红线】")
    lines.append(safety)

    extra = persona.get("extraPrompt")
    if extra:
        lines.append("")
        lines.append("【补充要求】")
        lines.append(extra)

    return "\n".join(lines)
