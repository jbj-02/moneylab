"""Desktop/mobile acceptance for the move result's monthly summary and rent edit."""
import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


BASE = os.environ.get('MONEYLAB_TEST_URL', 'http://127.0.0.1:8501')
OUT = Path(os.environ.get('BROWSER_ARTIFACT_DIR', 'artifacts/browser/move-result'))


def number(page, label, value):
    page.get_by_role('spinbutton', name=label, exact=True).fill(str(value))


def capture(page, name):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 4')
    expect(page.get_by_test_id('stException')).to_have_count(0)
    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTo(0,0)')
    page.screenshot(path=str(OUT / f'{name}.png'), full_page=True, animations='disabled')


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
        for viewport, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
            context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
            page = context.new_page()
            page.goto(f'{BASE}/moving-alpha', wait_until='domcontentloaded')
            expect(page.get_by_role('heading', name='Plan a move', exact=True)).to_be_visible()
            expect(page.get_by_role('spinbutton', name='Monthly take-home pay ($)', exact=True)).to_be_enabled()
            for label, value in [
                ('Monthly take-home pay ($)', 3500),
                ('Current rent / housing ($/month)', 0),
                ('Other monthly commitments ($)', 1900),
                ('Available checking / cash ($)', 2200),
                ('New rent share ($/month)', 1500),
                ('Other monthly costs: change ($)', 150),
                ('Total upfront costs ($)', 3000),
            ]:
                number(page, label, value)
            page.get_by_role('button', name='See impact', exact=True).click()
            expect(page.get_by_text('Upfront costs exceed available cash by $800.00', exact=False)).to_be_visible()
            if mode == 'after':
                expect(page.get_by_test_id('stMetric').filter(has_text='Money left in first month')).to_contain_text('$50.00 short')
                expect(page.get_by_test_id('stMetric').filter(has_text='Monthly take-home pay')).to_contain_text('$3,500.00')
                expect(page.get_by_test_id('stMetric').filter(has_text='Projected monthly expenses and commitments')).to_contain_text('$3,550.00')
            else:
                expect(page.get_by_test_id('stMetric').filter(has_text='Money left each month')).to_contain_text('-$50.00')
            capture(page, f'{viewport}-{mode}-move-result')
            if mode == 'after':
                rent = page.get_by_role('spinbutton', name='Proposed rent ($/month)', exact=True)
                rent.fill('1300')
                rent.press('Enter')
                expect(page.get_by_test_id('stMetric').filter(has_text='Money left in first month')).to_contain_text('$150.00 left')
                expect(page.get_by_test_id('stMetric').filter(has_text='Projected monthly expenses and commitments')).to_contain_text('$3,350.00')
                expect(page.get_by_text('Upfront costs exceed available cash by $800.00', exact=False)).to_be_visible()
                expect(page.get_by_role('spinbutton', name='Proposed rent ($/month)', exact=True)).to_have_value('1300.00')
                capture(page, f'{viewport}-{mode}-rent-edited')
            records.append({'viewport': viewport, 'mode': mode, 'status': 'passed'})
            context.close()
        browser.close()
    (OUT / f'{mode}-validation.json').write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['before', 'after'], default='after')
    run(parser.parse_args().mode)
