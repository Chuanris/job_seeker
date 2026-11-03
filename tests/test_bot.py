import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

try:
    from jobbot.extract import extract_jobs
    from jobbot.models import Job
    from jobbot.rules import classify
    from jobbot.state import State
except ImportError:
    extract_jobs = Job = classify = State = None


NOW = datetime(2026, 11, 3, 4, tzinfo=timezone.utc)


class BotTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Job, 'Job bot implementation has not been created')

    def job(self, **kw):
        data = dict(title='Data Scientist', company='Example Co', location='Taipei, Taiwan',
                    description='Welcome new graduates. Python, SQL and machine learning.',
                    url='https://example.com/jobs/1', employment='FULL_TIME', verified=True)
        data.update(kw)
        return Job(**data)

    def test_accepts_explicit_new_graduate(self):
        self.assertEqual(classify(self.job(), NOW).status, 'confirmed')

    def test_required_years_override_new_grad_label(self):
        self.assertEqual(classify(self.job(description='New graduates welcome. Minimum 3 years of professional experience required.'), NOW).status, 'excluded')

    def test_required_chinese_years_override_platform_label(self):
        self.assertEqual(classify(self.job(description='經驗不拘。必要條件：具備2年以上工作經驗。'), NOW).status, 'excluded')

    def test_preferred_years_do_not_disqualify(self):
        self.assertEqual(classify(self.job(description='應屆畢業生可。加分條件：2年以上工作經驗。Python。'), NOW).status, 'confirmed')

    def test_zero_to_two_years_includes_graduates(self):
        self.assertEqual(classify(self.job(description='0–2 years of experience. Python machine learning.'), NOW).status, 'confirmed')

    def test_one_to_two_years_excluded(self):
        self.assertEqual(classify(self.job(description='1-2 years of experience required.'), NOW).status, 'excluded')

    def test_negated_new_grad_is_not_accepted(self):
        self.assertEqual(classify(self.job(description='Not open to new graduates. Python.'), NOW).status, 'excluded')

    def test_mentioning_graduates_is_not_acceptance(self):
        self.assertEqual(classify(self.job(description='未說明是否接受應屆。Python SQL。'), NOW).status, 'review')

    def test_hard_requirement_after_preference_is_not_lost(self):
        self.assertEqual(classify(self.job(description='New graduates welcome. Preferred: Python. Must have 2 years of work experience.'), NOW).status, 'excluded')

    def test_chinese_experience_before_number_is_required(self):
        self.assertEqual(classify(self.job(description='歡迎新鮮人。工作經驗至少2年。'), NOW).status, 'excluded')

    def test_new_grad_in_title_is_acceptance_evidence(self):
        self.assertEqual(classify(self.job(title='New Graduate Data Scientist', description='Python machine learning.'), NOW).status, 'confirmed')

    def test_preferred_skill_does_not_erase_required_years_in_same_sentence(self):
        self.assertEqual(classify(self.job(description='Welcome new graduates. At least 3 years of work experience required, Python preferred.'), NOW).status, 'excluded')

    def test_required_years_with_skill_between_number_and_experience(self):
        cases = ['Must have 3 years of Python experience.', '必備條件：3年以上資料科學相關經驗。', '必要條件：三年以上工作經驗。']
        for sentence in cases:
            with self.subTest(sentence=sentence):
                self.assertEqual(classify(self.job(description='Welcome new graduates. ' + sentence), NOW).status, 'excluded')

    def test_separate_jsonld_qualifications_are_screened(self):
        obj = {'@type': 'JobPosting', 'title': 'Data Scientist', 'description': 'Welcome new graduates.',
               'qualifications': 'At least 3 years of professional experience required.',
               'hiringOrganization': {'name': 'Example'}, 'employmentType': 'FULL_TIME',
               'jobLocation': {'address': {'addressLocality': 'Taipei', 'addressCountry': 'TW'}}}
        jobs = extract_jobs('<script type="application/ld+json">' + json.dumps(obj) + '</script>', 'https://example.com/1')
        self.assertEqual(classify(jobs[0], NOW).status, 'excluded')

    def test_unknown_experience_requires_review(self):
        self.assertEqual(classify(self.job(description='Python SQL and statistics.'), NOW).status, 'review')

    def test_senior_title_excluded_even_with_no_experience_label(self):
        self.assertEqual(classify(self.job(title='Senior Data Scientist'), NOW).status, 'excluded')

    def test_student_intern_excluded(self):
        self.assertEqual(classify(self.job(employment='INTERN', description='Currently enrolled students only.'), NOW).status, 'excluded')

    def test_foreign_role_excluded(self):
        self.assertEqual(classify(self.job(location='Singapore'), NOW).status, 'excluded')

    def test_remote_without_taiwan_eligibility_needs_review(self):
        self.assertEqual(classify(self.job(location='Remote'), NOW).status, 'review')

    def test_expired_role_excluded(self):
        self.assertEqual(classify(self.job(expires='2026-11-01'), NOW).status, 'excluded')

    def test_valid_through_date_keeps_whole_local_day(self):
        self.assertEqual(classify(self.job(expires='2026-11-03'), NOW).status, 'confirmed')

    def test_closed_role_excluded(self):
        self.assertEqual(classify(self.job(closed=True), NOW).status, 'excluded')

    def test_non_ds_software_role_excluded(self):
        self.assertEqual(classify(self.job(title='Backend Engineer'), NOW).status, 'excluded')

    def test_unverified_search_snippet_cannot_be_confirmed(self):
        self.assertEqual(classify(self.job(verified=False), NOW).status, 'review')

    def test_unknown_employment_cannot_be_confirmed(self):
        self.assertEqual(classify(self.job(employment=''), NOW).status, 'review')

    def test_jsonld_graph_extraction_and_html_description(self):
        obj = {'@graph': [{'@type': 'JobPosting', 'title': 'Data Scientist',
               'description': '<p>應屆畢業生可</p><p>Python SQL</p>',
               'hiringOrganization': {'name': 'Example'}, 'employmentType': 'FULL_TIME',
               'jobLocation': {'address': {'addressLocality': '台北市', 'addressCountry': 'TW'}},
               'baseSalary': {'currency': 'TWD', 'value': {'minValue': 60000, 'maxValue': 80000, 'unitText': 'MONTH'}},
               'experienceRequirements': {'monthsOfExperience': 0}}]}
        html = '<script type="application/ld+json">' + json.dumps(obj) + '</script>'
        jobs = extract_jobs(html, 'https://example.com/1')
        self.assertEqual(len(jobs), 1)
        self.assertIn('應屆畢業生可', jobs[0].description)
        self.assertIn('60000', jobs[0].salary)
        self.assertEqual(classify(jobs[0], NOW).status, 'confirmed')

    def test_structured_required_months_exclude(self):
        self.assertEqual(classify(self.job(min_months=12), NOW).status, 'excluded')

    def test_cross_platform_dedupe_and_date_only_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            with State(Path(tmp) / 'state.db') as state:
                first = self.job(posted='2026-10-01')
                state.observe(first, classify(first, NOW), NOW)
                self.assertEqual(len(state.pending()), 1)
                state.acknowledge(state.pending())
                second = self.job(url='https://board.example.com/jobs/2?utm_source=x', posted='2026-11-03')
                state.observe(second, classify(second, NOW), NOW)
                self.assertEqual(state.pending(), [])

    def test_substantive_update_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            with State(Path(tmp) / 'state.db') as state:
                first = self.job()
                state.observe(first, classify(first, NOW), NOW)
                state.acknowledge(state.pending())
                updated = self.job(salary='TWD 70000 / MONTH')
                state.observe(updated, classify(updated, NOW), NOW)
                self.assertEqual(len(state.pending()), 1)
                self.assertTrue(state.pending()[0]['is_update'])

    def test_unacknowledged_report_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'state.db'
            with State(db) as state:
                job = self.job()
                state.observe(job, classify(job, NOW), NOW)
            with State(db) as state:
                self.assertEqual(len(state.pending()), 1)

    def test_pending_expired_vacancy_is_not_retried_as_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with State(Path(tmp) / 'state.db') as state:
                job = self.job(expires='2026-11-03')
                state.observe(job, classify(job, NOW), NOW)
                tomorrow = datetime(2026, 11, 4, 4, tzinfo=timezone.utc)
                self.assertEqual(state.pending(now=tomorrow), [])

    def test_fetch_failure_does_not_create_duplicate_for_known_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            with State(Path(tmp) / 'state.db') as state:
                job = self.job()
                state.observe(job, classify(job, NOW), NOW)
                state.acknowledge(state.pending())
                fallback = self.job(company='', location='', description='Search snippet', verified=False)
                state.observe(fallback, classify(fallback, NOW), NOW)
                self.assertEqual(state.pending(), [])

    def test_malformed_schema_type_cannot_crash_scan(self):
        page = '<script type="application/ld+json">{"@type":[123]}</script>'
        self.assertEqual(extract_jobs(page, 'https://example.com/jobs/1'), [])

    def test_cli_demo_is_labelled_and_second_run_is_quiet(self):
        from jobbot.cli import run
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {'state_path': str(Path(tmp) / 'state.db'), 'report_dir': str(Path(tmp) / 'reports')}
            first = run(cfg, demo=True)
            self.assertGreater(first['pending'], 0)
            self.assertIn('合成示範資料', Path(first['report']).read_text(encoding='utf-8'))
            self.assertEqual(run(cfg, demo=True)['pending'], 0)

    def test_failed_telegram_delivery_does_not_acknowledge(self):
        from jobbot.cli import publish
        with tempfile.TemporaryDirectory() as tmp:
            with State(Path(tmp) / 'state.db') as state:
                job = self.job()
                state.observe(job, classify(job, NOW), NOW)
                with patch('jobbot.cli.send_document', side_effect=RuntimeError('delivery failed')):
                    with self.assertRaises(RuntimeError):
                        publish(state, state.pending(), Path(tmp) / 'report.md', telegram=True)
                self.assertGreater(len(state.pending()), 0)

    def test_missing_key_fails_before_changing_database(self):
        from jobbot.cli import run
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'state.db'
            with patch.dict('os.environ', {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'BRAVE_SEARCH_API_KEY'):
                    run({'state_path': str(db)}, demo=False)
            self.assertFalse(db.exists())

    def test_demo_never_requires_or_sends_real_notifications(self):
        from jobbot.cli import run
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {'state_path': str(Path(tmp) / 'demo.db'), 'report_dir': str(Path(tmp) / 'reports'), 'telegram': True}
            with patch.dict('os.environ', {'TELEGRAM_ENABLED': 'true', 'TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_CHAT_ID': ''}):
                self.assertEqual(run(cfg, demo=True)['pending'], 2)

    def test_page_fetch_failure_is_visible_not_confirmed(self):
        from jobbot.sources import collect
        class Search:
            def search(self, query, config):
                return [{'title': 'Data Scientist Taiwan', 'url': 'https://example.com/jobs/1', 'description': 'New graduates welcome'}]
        class Pages:
            def fetch(self, url):
                raise RuntimeError('robots denied')
        jobs, warnings, stats = collect({'queries': ['test'], 'max_pages': 10}, Search(), Pages())
        self.assertEqual(len(jobs), 1)
        self.assertEqual(classify(jobs[0], NOW).status, 'review')
        self.assertIn('robots denied', warnings[0])

    def test_partial_search_failure_is_reported(self):
        from jobbot.sources import collect
        class Search:
            def search(self, query, config):
                if query == 'bad':
                    raise RuntimeError('HTTP 429')
                return []
        jobs, warnings, stats = collect({'queries': ['bad', 'good']}, Search(), None)
        self.assertEqual(stats['queries_ok'], 1)
        self.assertTrue(warnings)

    def test_all_searches_fail_instead_of_reporting_zero_results(self):
        from jobbot.sources import collect
        class Search:
            def search(self, query, config):
                raise RuntimeError('HTTP 503')
        with self.assertRaisesRegex(RuntimeError, '全部搜尋失敗'):
            collect({'queries': ['test']}, Search(), None)


if __name__ == '__main__':
    unittest.main()
