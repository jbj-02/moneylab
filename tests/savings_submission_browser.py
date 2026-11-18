"""Desktop/mobile acceptance for the initial savings-goal submission result."""
import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from browser_smoke import check, number


BASE = os.environ.get('MONEYLAB_TEST_URL', 'http://127.0.0.1:8501')
OUT = Path(os.environ.get('BROWSER_ARTIFACT_DIR', 'artifacts/browser/savings-submission'))
CASES = {
    'on-track': {'rent': 2750, 'dining': 0, 'monthly': 250},
    'budget-change': {'rent': 2700, 'dining': 100, 'monthly': 200},
    'revise-goal': {'rent': 2900, 'dining': 0, 'monthly': 100},
}


def submit_goal(page, case):
    page.goto(BASE, wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    page.get_by_role('button', name='Plan a savings goal', exact=True).click()
    page.get_by_role('textbox', name='Give your goal a name', exact=True).fill('Emergency fund')
    number(page, 'How much do you want to save? ($)', 4000)
    number(page, 'In how many months?', 6)
    page.get_by_role('spinbutton', name='How much do you want to save? ($)', exact=True).locator(
        'xpath=ancestor::div[@data-testid="stForm"]').get_by_role('button', name='Continue', exact=True).click()
    values = [
        ('Monthly take-home pay ($)', 3000),
        ('Rent / housing ($)', case['rent']),
        ('Groceries ($)', 0),
        ('Dining out & takeaways ($)', case['dining']),
        ('Transport ($)', 0),
        ('Utilities, phone & subscriptions ($)', 0),
        ('Other regular spending ($)', 0),
    ]
    for label, value in values:
        number(page, label, value)
    page.get_by_role('spinbutton', name='Monthly take-home pay ($)', exact=True).locator(
        'xpath=ancestor::div[@data-testid="stForm"]').get_by_role('button', name='Continue', exact=True).click()
    page.get_by_text('I have no debt', exact=True).click()
    for label, value in [
        ('Checking / cash today ($)', 0),
        ('Total savings today ($)', 2500),
        ('Of your total savings, already set aside for this goal ($)', 2500),
        ('What do you currently plan to save each month? ($)', case['monthly']),
    ]:
        number(page, label, value)
    page.get_by_text('Use these figures to build my preliminary plan', exact=True).click()
    page.get_by_role('button', name='Build my plan', exact=True).click()
    expect(page.get_by_role('region', name='Your goal result', exact=True)).to_be_visible()


def capture(page, name):
    check(page, name)
    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTo(0,0)')
    page.screenshot(path=str(OUT / f'{name}.png'), full_page=True, animations='disabled')


def run(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
        for viewport, width, height in [('desktop', 1440, 1000), ('mobile', 390, 844)]:
            for name, case in CASES.items():
                context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
                page = context.new_page()
                submit_goal(page, case)
                result = page.get_by_role('region', name='Your goal result', exact=True)
                if mode == 'after':
                    if name == 'on-track':
                        expect(result).to_contain_text('On track')
                        expect(result).to_contain_text('$4,000.00 projected in 6 months')
                        expect(result).to_contain_text('target exactly')
                        expect(page.get_by_text('Keep saving $250.00 each month', exact=False)).to_be_visible()
                    elif name == 'budget-change':
                        expect(result).to_contain_text('$300.00 behind')
                        expect(result).to_contain_text('$3,700.00 projected in 6 months')
                        expect(result).to_contain_text('$50.00 more each month')
                        expect(page.get_by_text('Reduce Dining out & takeaways by $50.00', exact=False)).to_be_visible()
                        expect(page.get_by_text('$4,000.00 by the deadline', exact=False)).to_be_visible()
                    else:
                        expect(result).to_contain_text('$900.00 behind')
                        expect(result).to_contain_text('$3,100.00 projected in 6 months')
                        expect(result).to_contain_text('$150.00 more each month')
                        expect(page.get_by_text('$3,100.00 as the six-month target', exact=False)).to_be_visible()
                        expect(page.get_by_text('15 months to reach $4,000.00', exact=False)).to_be_visible()
                capture(page, f'{viewport}-{mode}-{name}')
                records.append({'viewport': viewport, 'case': name, 'mode': mode, 'status': 'passed'})
                context.close()
        browser.close()
    (OUT / f'{mode}-validation.json').write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['before', 'after'], default='after')
    run(parser.parse_args().mode)
