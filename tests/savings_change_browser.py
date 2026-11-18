"""Desktop/mobile acceptance for the inline one-expense savings scenario."""

import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from browser_smoke import check, download_workspace, navigate
from savings_submission_browser import submit_goal


BASE=os.environ.get('MONEYLAB_TEST_URL','http://127.0.0.1:8501')
OUT=Path(os.environ.get('BROWSER_ARTIFACT_DIR','artifacts/browser/savings-change'))
CASE={'rent':2450,'dining':350,'monthly':200}


def scenario_card(page,label):
    heading=page.get_by_role('heading',name=label,exact=True)
    return heading.locator('xpath=ancestor::div[@data-testid="stVerticalBlock"][1]')


def expect_facts(card,spending,available,saving,left,projected,completion):
    expectations={
        'Monthly take-home pay':'$3,000.00',
        'Spending and bills':spending,
        'Available before savings':available,
        'Savings contributions':saving,
        'Left after savings':left,
        'Projected goal balance':projected,
    }
    for label,value in expectations.items():
        if label=='Projected goal balance':
            expect(card.locator('.ml-compare-goal')).to_contain_text(value)
        else:
            expect(card.locator('.ml-compare-row').filter(has_text=label)).to_contain_text(value)
    expect(card.locator('.ml-compare-goal')).to_contain_text(f'Estimated time to goal: {completion}')


def set_amount(page,label,value):
    field=page.get_by_role('spinbutton',name=label,exact=True)
    field.fill(str(value));field.press('Enter')


def capture(page,name):
    check(page,name)
    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTo(0,0)')
    page.screenshot(path=str(OUT/f'{name}.png'),full_page=True,animations='disabled')


def run():
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        for viewport,width,height in [('desktop',1440,1000),('mobile',390,844)]:
            context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce',accept_downloads=True)
            page=context.new_page();submit_goal(page,CASE)
            expect(page.get_by_text('TRY A CHANGE',exact=True)).to_be_visible()
            spending=page.get_by_role('spinbutton',name='Monthly spending in test scenario ($)',exact=True)
            redirect=page.get_by_role('spinbutton',name='Of that reduction, put toward this goal ($)',exact=True)
            expect(spending).to_have_value('300.00');expect(redirect).to_have_value('50.00')
            current=scenario_card(page,'Current plan');tested=scenario_card(page,'Test scenario')
            expect_facts(current,'$2,800.00','$200.00','$200.00','$0.00','$3,700.00','8 months')
            expect_facts(tested,'$2,750.00','$250.00','$250.00','$0.00','$4,000.00','6 months')
            expect(page.get_by_role('button',name='Apply these changes to my plan',exact=True)).to_be_disabled()
            capture(page,f'{viewport}-prefilled-change')

            set_amount(page,'Of that reduction, put toward this goal ($)',0)
            expect_facts(scenario_card(page,'Test scenario'),'$2,750.00','$250.00','$200.00','$50.00','$3,700.00','8 months')
            capture(page,f'{viewport}-keep-cash')

            set_amount(page,'Monthly spending in test scenario ($)',325)
            set_amount(page,'Of that reduction, put toward this goal ($)',25)
            expect_facts(scenario_card(page,'Test scenario'),'$2,775.00','$225.00','$225.00','$0.00','$3,850.00','7 months')
            capture(page,f'{viewport}-partial-change')

            page.get_by_role('button',name='Reset scenario',exact=True).click()
            expect(spending).to_have_value('350.00');expect(redirect).to_have_value('0.00')
            expect_facts(scenario_card(page,'Test scenario'),'$2,800.00','$200.00','$200.00','$0.00','$3,700.00','8 months')
            exported=download_workspace(page)
            entries={item['id']:item for item in exported['workspace']['blocks']}
            assert entries['setup_dining']['monthly_amount']=='350.00'
            assert entries['setup_goal']['monthly_contribution']=='200.00'
            records.append({'viewport':viewport,'status':'passed','saved_plan_unchanged':True})
            context.close()
        browser.close()
    (OUT/'validation.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':
    run()
