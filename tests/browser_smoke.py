"""Fictional end-to-end financial journeys in desktop and mobile Chromium.

Run separately against a local server. No bank data or public deployment is
used. CI retains screenshots; the Python suite validates exact amounts.
"""
from decimal import Decimal
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

OUTPUT = Path(os.environ.get('BROWSER_ARTIFACT_DIR', 'artifacts/browser'))
BASE = os.environ.get('MONEYLAB_TEST_URL', 'http://127.0.0.1:8501')
REVIEW = 'My entries include all income, regular spending, balances and debts (including any $0 amounts)'


def check(page, label):
    expect(page.get_by_test_id('stException')).to_have_count(0)
    width = page.evaluate('document.documentElement.scrollWidth')
    viewport = page.evaluate('window.innerWidth')
    if width > viewport + 4:
        raise AssertionError(f'{label}: horizontal overflow {width}px > {viewport}px')


def shot(page, label):
    check(page, label)
    page.screenshot(path=str(OUTPUT / f'{label}.png'), full_page=True)


def navigate(page, label):
    link = page.get_by_role('link', name=label, exact=True)
    box = link.bounding_box()
    if not link.is_visible() or box is None or box['x'] < 0:
        page.get_by_role('button', name='Expand sidebar', exact=True).click()
    link.click()
    # Streamlit keeps its mobile drawer open after choosing a destination.
    if page.viewport_size['width'] < 768:
        collapse = page.get_by_role('button', name='Collapse sidebar', exact=True)
        if collapse.is_visible():
            collapse.click()


def number(page, label, value):
    field = page.get_by_role('spinbutton', name=label, exact=True)
    field.fill(str(value))
    field.press('Tab')


def confirm(page):
    page.get_by_text(REVIEW, exact=True).click()
    page.get_by_role('button', name='Confirm my figures', exact=True).click()
    expect(page.get_by_role('button', name='Confirm my figures', exact=True)).to_have_count(0)


def fictional_profile(income='3000', spending='2200', cash='2000'):
    return [
        {'id':'pay','kind':'income','name':'Take-home pay','monthly_amount':income},
        {'id':'bills','kind':'expense','name':'Rent & living costs','monthly_amount':spending},
        {'id':'cash','kind':'cash','name':'Checking','balance':cash},
        {'id':'reserve','kind':'goal','name':'Emergency fund','balance':'8000','annual_rate':'0',
         'monthly_contribution':'200','target':'10000','target_months':6},
    ]


def restore_profile(page, blocks):
    navigate(page, 'Settings & data')
    expect(page.get_by_role('heading', name='Save or restore your workspace')).to_be_visible()
    page.get_by_test_id('stFileUploader').locator('input[type=file]').set_input_files({
        'name':'fictional-profile.json', 'mimeType':'application/json',
        'buffer':json.dumps({'schema_version':1,'blocks':blocks}).encode(),
    })
    page.get_by_text("I understand this replaces my current session's data", exact=True).click()
    page.get_by_role('button', name='Restore selected workspace', exact=True).click()
    expect(page.get_by_text('Workspace restored. Review your figures and recalculate any decision.', exact=True)).to_be_visible()
    navigate(page, 'My Plan')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()


def download_workspace(page):
    navigate(page, 'Settings & data')
    with page.expect_download() as download:
        page.get_by_role('button', name='Download workspace (JSON)', exact=True).click()
    data = json.loads(Path(download.value.path()).read_text())
    return data


def export_profile(page):
    return download_workspace(page)['workspace']['blocks']


def graduate_journey(browser, viewport, label):
    context = browser.new_context(viewport=viewport, reduced_motion='reduce')
    page = context.new_page()
    page.goto(BASE, wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    shot(page, f'{label}-welcome')
    page.get_by_role('button', name='Set up my finances', exact=True).click()
    expect(page.get_by_text('Step 1 of 3 · What matters to you', exact=True)).to_be_visible()
    page.get_by_text('Move out', exact=True).click()
    number(page, 'How much do you want to save? ($)', 8000)
    page.get_by_role('button', name='Continue', exact=True).click()
    expect(page.get_by_text('Step 2 of 3 · Your monthly picture', exact=True)).to_be_visible()
    for field,value in [('Monthly take-home pay ($)',3500), ('Rent / housing ($)',900),
                        ('Groceries & dining ($)',400), ('Transport ($)',150),
                        ('Utilities, phone & subscriptions ($)',150), ('Other regular spending ($)',200)]:
        number(page, field, value)
    page.get_by_role('button', name='Continue', exact=True).click()
    expect(page.get_by_text('Step 3 of 3 · Balances & review', exact=True)).to_be_visible()
    page.get_by_role('button', name='Back', exact=True).click()
    expect(page.get_by_text('Step 2 of 3 · Your monthly picture', exact=True)).to_be_visible()
    expect(page.get_by_role('spinbutton', name='Monthly take-home pay ($)', exact=True)).to_have_value('3500.00')
    page.get_by_role('button', name='Continue', exact=True).click()
    expect(page.get_by_text('Step 3 of 3 · Balances & review', exact=True)).to_be_visible()
    page.get_by_text('I have debt', exact=True).click()
    for field,value in [('Checking / cash today ($)',2500), ('Total savings today ($)',5000),
                        ('Of your total savings, already set aside for this goal ($)',3000),
                        ('What do you currently plan to save each month? ($)',300), ('Debt balance ($)',18000),
                        ('Annual interest rate (%)',5), ('Monthly debt payment ($)',200)]:
        number(page, field, value)
    shot(page, f'{label}-setup')
    page.get_by_text('Use these figures to build my preliminary plan', exact=True).click()
    page.get_by_role('button', name='Build my plan', exact=True).click()
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    expect(page.get_by_text('Move-out fund', exact=True)).to_be_visible()
    confirm(page)
    shot(page, f'{label}-graduate-plan')
    navigate(page, 'My Finances')
    page.get_by_role('button', name='Edit', exact=True).nth(1).click()
    dialog = page.get_by_role('dialog')
    expect(dialog).to_be_visible()
    dialog.get_by_role('spinbutton', name='Amount each monthly period ($)', exact=True).fill('950')
    dialog.get_by_role('button', name='Save changes', exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_text('Rent / housing · $950.00', exact=True)).to_be_visible()
    navigate(page, 'Test a decision')
    page.get_by_text('Can I move out?', exact=True).click()
    page.get_by_role('button', name='Open move-out comparison', exact=True).click()
    expect(page.get_by_role('heading', name='Can I move out?', exact=True)).to_be_visible()
    expect(page.get_by_text('Using your recorded figures.', exact=False)).to_be_visible()
    expect(page.get_by_role('spinbutton', name='Your current housing cost ($/month)', exact=True)).to_have_value('950.00')
    page.get_by_role('button', name='Continue', exact=True).click()
    expect(page.get_by_text('Step 2 of 2 · The proposed move', exact=True)).to_be_visible()
    number(page, 'Your share of new rent ($/month)', 1100)
    expect(page.get_by_role('spinbutton', name='Your share of new rent ($/month)', exact=True)).to_have_value('1100.00')
    number(page, 'Security deposit & fees ($)', 600)
    expect(page.get_by_role('spinbutton', name='Security deposit & fees ($)', exact=True)).to_have_value('600.00')
    page.get_by_role('button', name='Back', exact=True).click()
    expect(page.get_by_text('Step 1 of 2 · Your situation', exact=True)).to_be_visible()
    page.get_by_role('button', name='Continue', exact=True).click()
    expect(page.get_by_text('Step 2 of 2 · The proposed move', exact=True)).to_be_visible()
    expect(page.get_by_role('spinbutton', name='Your share of new rent ($/month)', exact=True)).to_have_value('1100.00')
    page.get_by_role('button', name='Compare stay vs move', exact=True).click()
    expect(page.get_by_role('heading', name='What moving would change')).to_be_visible()
    expect(page.get_by_text('Preliminary estimate.', exact=False).first).to_be_visible()
    expect(page.get_by_text('after recorded bills, debt and planned goal transfers.', exact=False).first).to_be_visible()
    shot(page, f'{label}-move-decision')
    page.get_by_role('button', name='Edit move', exact=True).click()
    expect(page.get_by_text('Step 1 of 2 · Your situation', exact=True)).to_be_visible()
    page.get_by_role('button', name='Continue', exact=True).click()
    expect(page.get_by_role('spinbutton', name='Security deposit & fees ($)', exact=True)).to_have_value('600.00')
    original = export_profile(page)
    assert not any(b.get('monthly_amount') == '1100.00' for b in original)
    context.close()


def savings_and_purchase_journey(browser, viewport, label):
    context = browser.new_context(viewport=viewport, reduced_motion='reduce', accept_downloads=True)
    page = context.new_page()
    page.goto(BASE, wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    restore_profile(page, fictional_profile())
    confirm(page)
    expect(page.get_by_text('$333.34', exact=False).first).to_be_visible()
    page.get_by_role('button', name='Preview this saving pace', exact=True).click()
    expect(page.get_by_role('heading', name='Current plan vs alternative')).to_be_visible()
    apply = page.get_by_role('button', name='Apply these changes to my plan', exact=True)
    expect(apply).to_be_disabled()
    shot(page, f'{label}-savings-comparison')
    before = export_profile(page)
    assert before[3]['monthly_contribution'] == '200.00'
    navigate(page, 'My Plan')
    page.get_by_role('link', name='Review pending alternative', exact=True).click()
    page.get_by_text('I want to replace my plan with these exact changes', exact=True).click()
    page.get_by_role('button', name='Apply these changes to my plan', exact=True).click()
    expect(page.get_by_text('Your approved changes are now in your plan.', exact=False)).to_be_visible()
    after = export_profile(page)
    assert after[3]['monthly_contribution'] == '333.34'
    navigate(page, 'My Plan')
    confirm(page)
    navigate(page, 'Test a decision')
    number(page, 'Cost amount ($)', 1200)
    number(page, 'Minimum cash to keep ($)', 1000)
    page.get_by_role('button', name='Compare with my current plan', exact=True).click()
    expect(page.get_by_role('heading', name='What this purchase changes')).to_be_visible()
    expect(page.get_by_text('Buying now leaves $800.00 in checking and cash.', exact=True)).to_be_visible()
    expect(page.get_by_text('$200.00 below your $1,000.00 cushion', exact=False).first).to_be_visible()
    expect(page.get_by_text('You can spend up to $1,000.00 today', exact=False)).to_be_visible()
    shot(page, f'{label}-purchase-comparison')
    page.get_by_role('link', name='Edit purchase', exact=True).click()
    expect(page.get_by_role('spinbutton', name='Cost amount ($)', exact=True)).to_have_value('1200.00')
    expect(page.get_by_role('spinbutton', name='Minimum cash to keep ($)', exact=True)).to_have_value('1000.00')
    number(page, 'Cost amount ($)', 900)
    page.get_by_role('button', name='Compare with my current plan', exact=True).click()
    expect(page.get_by_text('This keeps $100.00 above your cushion today.', exact=False)).to_be_visible()
    exported = export_profile(page)
    assert exported == after, 'Exploring a purchase must not change the actual plan'
    navigate(page, 'Test a decision')
    page.get_by_role('link', name='Review pending alternative', exact=True).click()
    page.get_by_role('button', name='Discard alternative', exact=True).click()
    expect(page.get_by_role('heading', name='What this purchase changes')).to_have_count(0)
    context.close()


def struggling_journey(browser, viewport, label):
    context = browser.new_context(viewport=viewport, reduced_motion='reduce')
    page = context.new_page()
    page.goto(BASE, wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    restore_profile(page, fictional_profile('2000', '2200', '100'))
    expect(page.get_by_text('-$200.00', exact=True)).to_be_visible()
    expect(page.get_by_text('Cash runs short in month 1', exact=False).first).to_be_visible()
    expect(page.get_by_role('button', name='Preview this saving pace', exact=True)).to_have_count(0)
    shot(page, f'{label}-shortfall')
    context.close()


def action_plan_journey(browser, viewport, label):
    context = browser.new_context(viewport=viewport, reduced_motion='reduce', accept_downloads=True)
    page = context.new_page()
    page.goto(BASE, wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    blocks = fictional_profile()
    blocks.append(dict(blocks[3], id='move', name='Move-out fund', balance='1000', target='3000',
                       target_months=12, monthly_contribution='100'))
    restore_profile(page, blocks)
    confirm(page)
    page.get_by_role('button', name='View action & alternatives', exact=True).click()
    expect(page.get_by_role('heading', name='What should I do?', exact=True)).to_be_visible()
    page.get_by_text('Keep my current pace', exact=True).click()
    expect(page.get_by_text('10 months from the plan date', exact=False)).to_be_visible()
    shot(page, f'{label}-action-options')
    page.get_by_text('Try my own adjustment or expense reduction', exact=True).click()
    page.get_by_role('combobox', name='Optional: choose a recorded expense to reduce', exact=True).click()
    page.get_by_role('option', name='Rent & living costs', exact=True).click()
    number(page, 'Reduce this expense each month by ($)', 200)
    page.get_by_role('spinbutton', name='Reduce this expense each month by ($)', exact=True).press('Tab')
    redirect = page.get_by_role('spinbutton', name='Of that reduction, put toward this goal ($)', exact=True)
    expect(redirect).to_have_value('200.00')
    redirect.fill('133.34')
    redirect.press('Tab')
    expect(page.get_by_text('Proposed goal saving:', exact=False)).to_contain_text('$333.34/month')
    shot(page, f'{label}-explicit-expense-funding')
    page.get_by_role('button', name='Inspect my adjustment', exact=True).click()
    expect(page.get_by_role('heading', name='Current plan vs alternative', exact=True)).to_be_visible()
    page.get_by_role('button', name='Discard alternative', exact=True).click()
    expect(page.get_by_role('heading', name='What should I do?', exact=True)).to_be_visible()
    page.get_by_text('Save more to meet the deadline', exact=True).click()
    page.get_by_role('button', name='Inspect this option', exact=True).click()
    expect(page.get_by_role('heading', name='Current plan vs alternative', exact=True)).to_be_visible()
    page.get_by_text('What if things change?', exact=True).click()
    page.get_by_text('Lower income', exact=True).click()
    expect(page.get_by_role('combobox', name='Recorded item to stress-test', exact=True)).to_have_value('Take-home pay')
    number(page, 'Monthly change to test ($)', 600)
    page.get_by_role('spinbutton', name='Monthly change to test ($)', exact=True).press('Tab')
    expect(page.get_by_role('spinbutton', name='Monthly change to test ($)', exact=True)).to_have_value('600.00')
    page.get_by_role('button', name='Run stress test', exact=True).click()
    expect(page.get_by_text('Chosen option under stress:', exact=False)).to_be_visible()
    shot(page, f'{label}-stress-test')
    original = download_workspace(page)
    assert original['workspace']['blocks'][3]['monthly_contribution'] == '200.00'
    assert 'accepted_plan' not in original['plan']
    navigate(page, 'My Plan')
    page.get_by_role('link', name='Review pending alternative', exact=True).click()
    page.get_by_text('I want to replace my plan with these exact changes', exact=True).click()
    page.get_by_role('button', name='Apply these changes to my plan', exact=True).click()
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    expect(page.get_by_text('Your chosen plan:', exact=False).first).to_be_visible()
    chosen = download_workspace(page)
    assert chosen['schema_version'] == 5
    assert chosen['workspace']['blocks'][3]['monthly_contribution'] == '333.34'
    assert chosen['plan']['accepted_plan']['blocks'][3]['monthly_contribution'] == '333.34'
    navigate(page, 'My Plan')
    confirm(page)
    page.get_by_text('Check my progress for Emergency fund', exact=True).click()
    number(page, 'Recorded goal balance ($)', 7900)
    page.get_by_role('button', name='Compare my progress', exact=True).click()
    expect(page.get_by_text('Your recorded balance is $100.00 behind', exact=False)).to_be_visible()
    expect(page.get_by_text('350.00', exact=False).first).to_be_visible()
    shot(page, f'{label}-progress-gap')
    page.get_by_text('I want to replace my plan with these exact changes', exact=True).click()
    page.get_by_role('button', name='Apply these changes to my plan', exact=True).click()
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    checked = download_workspace(page)
    assert checked['workspace']['blocks'][3]['balance'] == '7900.00'
    assert checked['workspace']['blocks'][3]['monthly_contribution'] == '333.34'
    assert checked['plan']['accepted_plan']['blocks'][3]['balance'] == '8000.00'
    context.close()


def dashboard_summary_journey(browser, viewport, label):
    context = browser.new_context(viewport=viewport, reduced_motion='reduce', accept_downloads=True)
    page = context.new_page()
    page.goto(BASE, wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    restore_profile(page, fictional_profile())
    confirm(page)
    summary = page.get_by_role('region', name='Recommended action', exact=True)
    expect(summary).to_contain_text('Save $333.34/month')
    expect(summary).to_contain_text('4 months sooner')
    expect(summary).to_contain_text('$133.34 of the $600.00')
    expect(summary).to_contain_text('$466.66')
    expect(page.get_by_role('button', name='Compare a later deadline', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='Compare a smaller target', exact=True)).to_be_visible()
    page.get_by_role('heading', name='My Plan', exact=True).scroll_into_view_if_needed()
    shot(page, f'{label}-dashboard-summary')
    page.get_by_role('button', name='Compare a later deadline', exact=True).click()
    expect(page.get_by_role('heading', name='Current plan vs alternative', exact=True)).to_be_visible()
    expect(page.get_by_text('10,000.00 at month 10', exact=False)).to_be_visible()
    shot(page, f'{label}-dashboard-alternative')
    page.get_by_role('button', name='Discard alternative', exact=True).click()
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    page.get_by_role('button', name='Compare a smaller target', exact=True).click()
    expect(page.get_by_role('heading', name='Current plan vs alternative', exact=True)).to_be_visible()
    expect(page.get_by_text('savings target: $10,000.00 → $9,200.00', exact=False)).to_be_visible()
    page.get_by_role('button', name='Discard alternative', exact=True).click()
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    page.get_by_role('button', name='Preview this saving pace', exact=True).click()
    expect(page.get_by_role('heading', name='Current plan vs alternative', exact=True)).to_be_visible()
    original = download_workspace(page)
    assert original['workspace']['blocks'][3]['monthly_contribution'] == '200.00'
    navigate(page, 'My Plan')
    page.get_by_role('link', name='Review pending alternative', exact=True).click()
    page.get_by_text('I want to replace my plan with these exact changes', exact=True).click()
    page.get_by_role('button', name='Apply these changes to my plan', exact=True).click()
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    expect(page.get_by_text('Your chosen plan:', exact=False).first.locator('..')).to_contain_text('$333.34/month')
    shot(page, f'{label}-dashboard-approved')
    chosen = download_workspace(page)
    assert chosen['workspace']['blocks'][3]['monthly_contribution'] == '333.34'
    assert chosen['plan']['accepted_plan']['blocks'][3]['monthly_contribution'] == '333.34'
    context.close()


def legacy_move_journey(browser, viewport, label):
    context = browser.new_context(viewport=viewport, reduced_motion='reduce')
    page = context.new_page()
    page.goto(f'{BASE}/moving-alpha', wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='Moving Out Decision Lab')).to_be_visible()
    for step, title in ((2, 'The proposed move'), (3, 'Review')):
        page.get_by_role('button', name='Continue', exact=True).click()
        expect(page.get_by_text(f'Step {step} of 3 · {title}', exact=True)).to_be_visible()
    page.get_by_role('button', name='Compare stay vs move', exact=True).click()
    expect(page.get_by_text('Included in this comparison', exact=True).first).to_be_visible()
    shot(page, f'{label}-move-results')
    context.close()


def local_continuity_journey(browser):
    url = os.environ.get('MONEYLAB_PERSISTENCE_TEST_URL')
    if not url:
        return
    context = browser.new_context(viewport={'width':1280,'height':900})
    page = context.new_page()
    page.goto(url, wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='My Plan', exact=True)).to_be_visible()
    restore_profile(page, fictional_profile())
    context.close()
    # A new browser context has no Streamlit session or cookies to reuse.
    context = browser.new_context(viewport={'width':1280,'height':900})
    page = context.new_page()
    page.goto(url, wait_until='domcontentloaded')
    expect(page.get_by_text('Emergency fund', exact=True)).to_be_visible()
    expect(page.get_by_text('Saved locally on this computer', exact=True)).to_be_visible()
    shot(page, 'local-returning-session')
    navigate(page, 'Settings & data')
    page.get_by_text('Delete my financial data', exact=True).click()
    page.get_by_text('Delete my plan and decision drafts', exact=True).click()
    page.get_by_role('button', name='Delete my data', exact=True).click()
    expect(page.get_by_text('Your financial data has been deleted.', exact=True)).to_be_visible()
    context.close()
    context = browser.new_context(viewport={'width':1280,'height':900})
    page = context.new_page()
    page.goto(url, wait_until='domcontentloaded')
    expect(page.get_by_role('button', name='Set up my finances', exact=True)).to_be_visible()
    check(page, 'local-deleted-session')
    context.close()
    print('local: new-session persistence and deletion passed', flush=True)


def purchase_feedback_journey(browser, viewport, label):
    for baseline in (True, False):
        url = os.environ.get("MONEYLAB_BASELINE_TEST_URL") if baseline else BASE
        if not url:
            continue
        context = browser.new_context(viewport=viewport, reduced_motion="reduce")
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.get_by_role("button", name="Try a fictional plan", exact=True).click()
        navigate(page, "Explore Decisions" if baseline else "Test a decision")
        number(page, "Cost amount ($)", 200)
        if not baseline:
            number(page, "Minimum cash to keep ($)", 2100)
        page.get_by_role("button", name="Compare with my current plan", exact=True).click()
        if baseline:
            expect(page.get_by_text("$1,650.00 at month 18", exact=False)).to_be_visible()
        else:
            expect(page.get_by_text("Buying now leaves $2,000.00 in checking and cash.", exact=True)).to_be_visible()
            expect(page.get_by_text("The $350.00 gap at month 18 was already there.", exact=False)).to_be_visible()
            expect(page.get_by_text("You can spend up to $100.00 today", exact=False)).to_be_visible()
            expect(page.get_by_text("Preliminary estimate.", exact=False)).to_be_visible()
        shot(page, f"{label}-purchase-{'before' if baseline else 'after'}")
        if not baseline:
            page.get_by_role("button", name="Test a $100.00 price", exact=True).click()
            expect(page.get_by_role("spinbutton", name="Cost amount ($)", exact=True)).to_have_value("100.00")
            page.get_by_role("button", name="Compare with my current plan", exact=True).click()
            expect(page.get_by_text("This leaves exactly your chosen cushion today.", exact=False)).to_be_visible()
        context.close()



def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox'],
                                     executable_path=os.environ.get('MONEYLAB_CHROMIUM_PATH'))
        for viewport, label in (({'width':1440,'height':1000}, 'desktop'),
                                ({'width':390,'height':844}, 'mobile')):
            for journey in (graduate_journey, savings_and_purchase_journey, struggling_journey, legacy_move_journey, action_plan_journey, dashboard_summary_journey, purchase_feedback_journey):
                journey(browser, viewport, label)
                print(f'{label}: {journey.__name__} passed', flush=True)
        local_continuity_journey(browser)
        browser.close()


if __name__ == '__main__':
    run()
