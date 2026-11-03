"""Conservative, inspectable screening. No model inference is used."""
from datetime import datetime, time
import re
from .models import Decision, TAIPEI

ROLE = re.compile(r'data scien(?:tist|ce)|資料科學|數據科學|machine learning (?:engineer|scientist)|機器學習(?:工程師|科學家)', re.I)
SENIOR = re.compile(r'\b(?:senior|sr\.?|staff|principal|lead|manager|director|head)\b|資深|主管|經理', re.I)
TAIWAN = re.compile(r'台灣|臺灣|Taiwan|台北|臺北|新北|桃園|新竹|苗栗|台中|臺中|彰化|南投|雲林|嘉義|台南|臺南|高雄|屏東|宜蘭|花蓮|台東|臺東|基隆|澎湖|金門|連江|Taipei|Taoyuan|Hsinchu|Miaoli|Taichung|Changhua|Nantou|Yunlin|Chiayi|Tainan|Kaohsiung|Pingtung|Yilan|Hualien|Taitung|Keelung|Penghu|Kinmen|\bTW\b', re.I)
GRAD_TERM = r'(?:new (?:college )?grad(?:uate)?s?|fresh grad(?:uate)?s?|recent grad(?:uate)?s?)'
GRAD = re.compile(r'(?:welcome|accept(?:ing)?|open to|suitable for)\s+' + GRAD_TERM + r'|' + GRAD_TERM + r'\s+(?:are\s+)?(?:welcome|accepted|encouraged)|(?:歡迎|接受|適合)(?:應屆畢業生|應屆生|新鮮人)|應屆(?:畢業生|生)?(?:亦可|可|也可)|經(?:驗|歷)不拘|無(?:工作)?經驗(?:亦可|可|要求)|不需(?:要)?(?:工作)?經驗|no (?:prior |professional |work )?experience (?:required|necessary)|no requirements', re.I)
PREFERRED = re.compile(r'preferred|nice.to.have|bonus|a plus|加分|尤佳|優先', re.I)
REQUIRED = re.compile(r'required|minimum|must have|at least|必要|必備|至少|需具備', re.I)
YEARS = re.compile(r'(?<![\d.])(\d+)\s*(?:(?:[-–—~～]|to|至)\s*\d+\s*)?(?:\+\s*)?(?:years?|年)[^。\n;；.!]{0,60}?(?:經驗|經歷|experience)', re.I)


def classify(job, now=None):
    now = now or datetime.now(TAIPEI)
    if job.closed:
        return Decision('excluded', '頁面標示停止收件')
    if job.expires:
        try:
            end = datetime.fromisoformat(job.expires.replace('Z', '+00:00'))
            if len(job.expires) == 10:
                end = datetime.combine(end.date(), time.max, TAIPEI)
            elif end.tzinfo is None:
                end = end.replace(tzinfo=TAIPEI)
            if end < now:
                return Decision('excluded', '已超過申請截止日')
        except ValueError:
            return Decision('review', '截止日期格式無法核實')
    if not ROLE.search(job.title):
        return Decision('excluded', '職稱不屬於設定的 Data Science / ML 範圍')
    if SENIOR.search(job.title):
        return Decision('excluded', '資深或管理職稱')
    if re.search(r'intern|part.?time|contract|temporary|實習|兼職|約聘', job.employment + ' ' + job.title, re.I):
        return Decision('excluded', '非全職正式職缺')
    if re.search(r'目前(?:仍)?在學|限在學|currently enrolled|student (?:status|identity) required', job.description, re.I):
        return Decision('excluded', '只接受在學學生')
    if job.location and not TAIWAN.search(job.location) and not re.search(r'remote|遠端', job.location, re.I):
        return Decision('excluded', '工作地點不在台灣')
    body = job.description
    if re.search(r'not (?:open to|for|accepting) (?:new |fresh )?grad|不接受(?:應屆|新鮮人)', body, re.I):
        return Decision('excluded', '內文明確不接受新鮮人')
    if job.min_months is not None:
        try:
            if float(job.min_months) > 0:
                return Decision('excluded', '結構化資格要求至少 %s 個月經驗' % job.min_months)
        except (ValueError, TypeError):
            return Decision('review', '年資欄位無法解讀')
    # Keep preference headings in scope until a requirements/responsibilities heading.
    preferred = False
    zero_range = None
    words = {'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'}
    for clause in re.split(r'[\n。;；.!]', body):
        clause = re.sub(r'\b(' + '|'.join(words) + r')\b', lambda m: words[m[0].lower()], clause, flags=re.I)
        digits = {'零': '0', '一': '1', '二': '2', '兩': '2', '三': '3', '四': '4', '五': '5', '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
        clause = re.sub(r'[零一二兩三四五六七八九十](?=\s*年)', lambda m: digits[m[0]], clause)
        if re.match(r'^\s*(?:preferred(?: qualifications)?|nice.to.have|加分(?:條件|項目)?)[\s:：]', clause, re.I):
            preferred = True
        elif REQUIRED.search(clause) or re.search(r'^\s*(?:qualifications|requirements|responsibilities|必要條件|必備條件|工作內容)', clause, re.I):
            preferred = False
        # Preference for one comma-separated skill cannot weaken another requirement.
        for part in re.split(r'[,，]', clause):
            optional = bool(PREFERRED.search(part)) or preferred
            if REQUIRED.search(part):
                optional = False
            reverse = re.search(r'(?:工作經驗|相關經驗|工作經歷|年資)\s*(?:至少|需|要求|[:：])?\s*(\d+)\s*(?:[-–~至]\s*\d+\s*)?年', part)
            if reverse and int(reverse[1]) > 0 and not optional:
                return Decision('excluded', '必要年資：' + clause.strip()[:180])
            for match in YEARS.finditer(part):
                if int(match[1]) > 0 and not optional:
                    return Decision('excluded', '必要年資：' + clause.strip()[:180])
                if int(match[1]) == 0:
                    zero_range = match[0]
    missing = []
    evidence = GRAD.search(body) or re.search(GRAD_TERM + r'|新鮮人|應屆', job.title, re.I)
    if not (evidence or zero_range or job.min_months == 0 or job.min_months == '0'):
        missing.append('未明確接受零年經驗/應屆畢業生')
    if not TAIWAN.search(job.location):
        missing.append('未明確標示台灣工作資格/地點')
    if not re.search(r'full[ _-]?time|全職', job.employment, re.I):
        missing.append('未明確標示全職')
    if not job.company:
        missing.append('雇主名稱不明')
    if not job.verified:
        missing.append('未取得單一職缺的完整公開內文')
    if missing:
        return Decision('review', '；'.join(missing))
    return Decision('confirmed', '資格依據：' + (evidence[0] if evidence else zero_range or '必要經驗 0 個月'))
