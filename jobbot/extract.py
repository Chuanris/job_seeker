"""Extract public schema.org JobPosting data without executing page scripts."""
import html
from html.parser import HTMLParser
import json
import re
from .models import Job


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self.parts = []
        self.script = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'script' and dict(attrs).get('type', '').lower() == 'application/ld+json':
            self.script = []
        if tag in ('p', 'li', 'div', 'br', 'h1', 'h2', 'h3') and not self.hidden:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.scripts.append(''.join(self.script))
            self.script = None
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'li', 'div') and not self.hidden:
            self.parts.append('\n')

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)
        if not self.hidden:
            self.parts.append(data)


def text(value):
    if isinstance(value, list):
        return '; '.join(text(x) for x in value)
    if isinstance(value, dict):
        if 'name' in value:
            return text(value['name'])
        return '; '.join(text(v) for k, v in value.items() if not k.startswith('@'))
    parser = PageParser()
    parser.feed(html.unescape(str(value if value is not None else '')))
    return re.sub(r'[ \t]+', ' ', ''.join(parser.parts)).strip()


def walk(value):
    if isinstance(value, list):
        for item in value:
            yield from walk(item)
    elif isinstance(value, dict):
        kinds = value.get('@type', [])
        if isinstance(kinds, str):
            kinds = [kinds]
        if not isinstance(kinds, list):
            kinds = []
        if any(isinstance(k, str) and k.rsplit('/', 1)[-1] == 'JobPosting' for k in kinds):
            yield value
        else:
            for child in value.values():
                yield from walk(child)


def extract_jobs(page, url):
    parser = PageParser()
    parser.feed(page)
    objects = []
    for script in parser.scripts:
        try:
            objects.extend(walk(json.loads(script)))
        except (ValueError, TypeError):
            continue
    visible = ''.join(parser.parts)
    closed = bool(re.search(r'no longer accepting applications|job (?:is |has been )?closed|position (?:is |has been )?filled|職缺已關閉|停止(?:接受)?(?:應徵|收件)|職缺已下架|招募已結束', visible, re.I))
    jobs = []
    for obj in objects:
        description = text(obj.get('description', ''))
        experience = obj.get('experienceRequirements', '')
        months = experience.get('monthsOfExperience') if isinstance(experience, dict) else None
        if isinstance(experience, str) and experience:
            description += '\n' + experience
        elif isinstance(experience, (dict, list)):
            description += '\n' + text(experience)
        for field in ('qualifications', 'skills', 'responsibilities'):
            if obj.get(field):
                description += '\n' + text(obj[field])
        location = text(obj.get('jobLocation', ''))
        if obj.get('jobLocationType') == 'TELECOMMUTE':
            location = 'Remote; ' + location + '; ' + text(obj.get('applicantLocationRequirements', ''))
        salary_obj = obj.get('baseSalary', '')
        salary = text(salary_obj)
        title = text(obj.get('title', ''))
        if not title:
            continue
        jobs.append(Job(title=title, company=text(obj.get('hiringOrganization', '')),
                        location=location, description=description, url=url,
                        employment=text(obj.get('employmentType', '')),
                        salary=salary, education=text(obj.get('educationRequirements', '')),
                        posted=text(obj.get('datePosted', '')), expires=text(obj.get('validThrough', '')),
                        identifier=text(obj.get('identifier', '')), min_months=months,
                        verified=bool(description) and len(objects) == 1,
                        closed=closed if len(objects) == 1 else False))
    return jobs
