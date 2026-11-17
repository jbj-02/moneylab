"""Result-first acceptance journeys in real desktop and mobile Chromium.

Run alongside browser_smoke.py against the same local server. All data is fictional.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from browser_smoke import BASE, REVIEW, check, confirm, download_workspace, navigate, number

OUTPUT=Path(os.environ.get('BROWSER_ARTIFACT_DIR','artifacts/browser'))


def profile():
    return [
        dict(id='pay',kind='income',name='Take-home pay',monthly_amount='2400'),
        dict(id='bills',kind='expense',name='Rent & essentials',monthly_amount='2000'),
        dict(id='dining',kind='expense',name='Dining out & takeaways',monthly_amount='300'),
        dict(id='cash',kind='cash',name='Checking',balance='500'),
        dict(id='goal',kind='goal',name='Emergency fund',balance='3620',annual_rate='0',monthly_contribution='100',target='5000',target_months=6),
    ]


def restore(page,blocks,missing=()):
    navigate(page,'Settings & data')
    payload={'schema_version':5,'workspace':{'schema_version':3,'blocks':blocks,'scenarios':[],'decision_drafts':[]},
             'plan':{'priority':'Build an emergency fund','unknown':list(missing),'is_example':False}}
    page.get_by_test_id('stFileUploader').locator('input[type=file]').set_input_files({
        'name':'fictional-plan.json','mimeType':'application/json','buffer':json.dumps(payload).encode()})
    page.get_by_text("I understand this replaces my current session's data",exact=True).click()
    page.get_by_role('button',name='Restore selected workspace',exact=True).click()
    expect(page.get_by_text('Workspace restored. Review your figures and recalculate any decision.',exact=True)).to_be_visible()
    navigate(page,'My Plan')


def capture(page,label,*,focus=None):
    check(page,label)
    old=page.viewport_size
    page.set_viewport_size({'width':old['width'],'height':1100})
    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTo(0,0)')
    if focus:
        focus.scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT/f'{label}.png'),full_page=True,animations='disabled')
    page.set_viewport_size(old)


def start(browser,viewport):
    context=browser.new_context(viewport=viewport,reduced_motion='reduce',accept_downloads=True)
    page=context.new_page();page.goto(BASE,wait_until='domcontentloaded')
    expect(page.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
    return context,page


def assert_details_collapsed(page):
    exp=page.get_by_test_id('stExpander').filter(has=page.get_by_text('How we calculated this',exact=True))
    assert exp.evaluate('(e)=>!e.querySelector("details").open')
    exp.locator('summary').click()
    expect(exp.get_by_text('Monthly take-home',exact=True)).to_be_visible()
    exp.locator('summary').click()
    expect(exp.get_by_text('Monthly take-home',exact=True)).not_to_be_visible()


def rescue_onboarding(browser,viewport,label):
    context,page=start(browser,viewport)
    capture(page,f'{label}-after-welcome')
    page.get_by_role('button',name='Plan a savings goal',exact=True).click()
    page.get_by_role('textbox',name='Give your goal a name',exact=True).fill('Emergency fund')
    number(page,'How much do you want to save? ($)',5000)
    number(page,'In how many months?',6)
    page.get_by_role('button',name='Continue',exact=True).click()
    for field,value in [('Monthly take-home pay ($)',2400),('Rent / housing ($)',1500),('Groceries ($)',300),
                        ('Dining out & takeaways ($)',300),('Transport ($)',100),('Utilities, phone & subscriptions ($)',100),('Other regular spending ($)',0)]:
        number(page,field,value)
    capture(page,f'{label}-after-inputs')
    page.get_by_role('button',name='Back',exact=True).click()
    expect(page.get_by_role('spinbutton',name='How much do you want to save? ($)',exact=True)).to_have_value('5000.00')
    page.get_by_role('button',name='Continue',exact=True).click()
    expect(page.get_by_role('spinbutton',name='Dining out & takeaways ($)',exact=True)).to_have_value('300.00')
    page.get_by_role('button',name='Continue',exact=True).click()
    page.get_by_text('I have no debt',exact=True).click()
    for field,value in [('Checking / cash today ($)',500),('Total savings today ($)',3620),
                        ('Of your total savings, already set aside for this goal ($)',3620),('What do you currently plan to save each month? ($)',100)]:
        number(page,field,value)
    page.get_by_text('Use these figures to build my preliminary plan',exact=True).click()
    page.get_by_role('button',name='Build my plan',exact=True).click()
    finding=page.get_by_role('region',name='Your goal result',exact=True)
    expect(finding).to_contain_text('$780.00 short')
    expect(finding).to_contain_text('$5,000.00')
    expect(finding).to_contain_text('6 months')
    expect(page.get_by_text('Cutting Dining out & takeaways by $130.00',exact=False)).to_be_visible()
    expect(page.get_by_role('button',name='Test this change',exact=True)).to_have_count(1)
    assert_details_collapsed(page)
    capture(page,f'{label}-after-rescue-result')
    original=download_workspace(page)['workspace']['blocks']
    navigate(page,'My Plan')
    page.get_by_role('button',name='Test this change',exact=True).click()
    expect(page.get_by_role('heading',name='Current plan vs alternative',exact=True)).to_be_visible()
    expect(page.get_by_role('button',name='Apply these changes to my plan',exact=True)).to_be_disabled()
    metrics=page.get_by_test_id('stMetric')
    expect(metrics.filter(has_text='Emergency fund in 6 months').nth(0)).to_contain_text('$4,220.00')
    expect(metrics.filter(has_text='Emergency fund in 6 months').nth(1)).to_contain_text('$5,000.00')
    expect(metrics.filter(has_text='Money left each month').nth(0)).to_contain_text('$0.00')
    expect(metrics.filter(has_text='Money left each month').nth(1)).to_contain_text('$0.00')
    capture(page,f'{label}-after-comparison')
    assert download_workspace(page)['workspace']['blocks']==original, 'Testing must not alter the plan'
    navigate(page,'Edit figures')
    page.get_by_role('button',name='Edit',exact=True).first.click()
    dialog=page.get_by_role('dialog')
    dialog.get_by_role('spinbutton',name='Amount each monthly period ($)',exact=True).fill('2500')
    dialog.get_by_role('button',name='Save changes',exact=True).click()
    expect(dialog).not_to_be_visible()
    navigate(page,'My Plan')
    page.get_by_role('link',name='Review pending alternative',exact=True).click()
    expect(page.get_by_text('Your figures changed.',exact=False).first).to_be_visible()
    expect(page.get_by_role('button',name='Apply these changes to my plan',exact=True)).to_have_count(0)
    capture(page,f'{label}-after-stale-edit')
    page.get_by_role('button',name='Discard alternative',exact=True).click()
    expect(page.get_by_role('button',name='Test this change',exact=True)).to_be_visible()
    page.get_by_role('button',name='Test this change',exact=True).click()
    expect(page.get_by_text('monthly amount: $300.00 → $270.00',exact=False)).to_be_visible()
    confirm(page)
    expect(page.get_by_role('button',name='Apply these changes to my plan',exact=True)).to_be_disabled()
    page.get_by_text('I want to replace my plan with these exact changes',exact=True).click()
    page.get_by_role('button',name='Apply these changes to my plan',exact=True).click()
    expect(page.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
    chosen=page.get_by_text('Your chosen plan:',exact=False).first
    expect(chosen.locator('..')).to_contain_text('$230.00/month')
    capture(page,f'{label}-after-applied',focus=chosen)
    exported=download_workspace(page)
    entries={b['id']:b for b in exported['workspace']['blocks']}
    assert entries['setup_dining']['monthly_amount']=='270.00'
    assert entries['setup_goal']['monthly_contribution']=='230.00'
    assert exported['plan']['accepted_plan']['blocks']==exported['workspace']['blocks']
    context.close()


def on_track(browser,viewport,label):
    context,page=start(browser,viewport)
    blocks=profile();blocks[0]['monthly_amount']='2800';blocks[4]['monthly_contribution']='300'
    restore(page,blocks)
    expect(page.get_by_role('region',name='Your goal result')).to_contain_text("You're on track")
    expect(page.get_by_text('Setting aside $230.00 a month instead of $300.00',exact=False)).to_be_visible()
    capture(page,f'{label}-after-on-track')
    page.get_by_role('button',name='Test this change',exact=True).click()
    expect(page.get_by_test_id('stMetric').filter(has_text='Money left each month').nth(1)).to_contain_text('$270.00')
    assert download_workspace(page)['workspace']['blocks'][4]['monthly_contribution']=='300.00'
    context.close()


def later_date(browser,viewport,label):
    context,page=start(browser,viewport)
    blocks=profile();blocks[2]['name']='Other bills'
    restore(page,blocks)
    expect(page.get_by_text('allowing 14 months would reach the goal.',exact=False)).to_be_visible()
    capture(page,f'{label}-after-later-date')
    page.get_by_role('button',name='Test this change',exact=True).click()
    expect(page.get_by_role('heading',name='Current plan',exact=True)).to_be_visible()
    expect(page.get_by_text('allow 14 months instead of 6',exact=False)).to_be_visible()
    assert download_workspace(page)['workspace']['blocks'][4]['target_months']==6
    context.close()


def missing_figure(browser,viewport,label):
    context,page=start(browser,viewport)
    restore(page,profile()[1:],['income'])
    expect(page.get_by_role('region',name='Your goal result')).to_contain_text('Add your take-home income')
    expect(page.get_by_role('button',name='Test this change',exact=True)).to_have_count(0)
    income=page.get_by_role('spinbutton',name='Take-home income per month ($)',exact=True)
    expect(income).to_be_empty()
    capture(page,f'{label}-after-missing-figure')
    page.get_by_role('button',name='Use this figure',exact=True).click()
    expect(page.get_by_text('Enter a figure, including $0',exact=False)).to_be_visible()
    income.fill('0')
    page.get_by_role('button',name='Use this figure',exact=True).click()
    saved=download_workspace(page)
    assert saved['plan']['unknown']==[]
    assert next(b for b in saved['workspace']['blocks'] if b['kind']=='income')['monthly_amount']=='0.00'
    context.close()


def direct_purchase(browser,viewport,label):
    context,page=start(browser,viewport)
    page.get_by_role('button',name='Test a purchase',exact=True).click()
    for field,value in [('Purchase or recurring cost ($)',1200),('Monthly take-home pay ($)',3500),
                        ('Monthly bills, debt payments and planned savings ($)',2000),('Checking / cash available for this purchase ($)',6000)]:
        number(page,field,value)
    page.get_by_role('button',name='Test this purchase',exact=True).click()
    expect(page.get_by_text('This $1,200.00 purchase would leave $4,800.00',exact=False)).to_be_visible()
    capture(page,f'{label}-after-purchase')
    assert download_workspace(page)['workspace']['blocks']==[]
    context.close()


def run():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        for label,viewport in [('desktop',{'width':1440,'height':1000}),('mobile',{'width':390,'height':844})]:
            for journey in (rescue_onboarding,on_track,later_date,missing_figure,direct_purchase):
                journey(browser,viewport,label)
                print(f'{label}: {journey.__name__} passed',flush=True)
        browser.close()


if __name__=='__main__':
    run()
