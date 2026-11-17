"""Reproducible matched-figure before/after audit; control clicks exclude typing.

Before: run against bec32bc. After: run against the current app. Each journey
starts on My Plan with the same restored fictional profile; setup is not counted.
"""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect
from browser_smoke import upload_workspace

FIGURES=[dict(id='pay',kind='income',name='Take-home pay',monthly_amount='2400'),
         dict(id='rent',kind='expense',name='Rent',monthly_amount='1500'),
         dict(id='bills',kind='expense',name='Other regular costs',monthly_amount='500'),
         dict(id='dining',kind='expense',name='Dining out & takeaways',monthly_amount='300'),
         dict(id='cash',kind='cash',name='Checking',balance='2500'),
         dict(id='goal',kind='goal',name='Emergency fund',balance='3620',annual_rate='0',monthly_contribution='100',target='5000',target_months=6)]


def assert_original(blocks):
    # JSON formatting may normalize cents; compare every recorded field and
    # reject added/removed entries, including incidental engine mutations.
    numeric={'monthly_amount','balance','target','monthly_contribution','annual_rate'}
    def normalized(items):
        return [{k:Decimal(v) if k in numeric else v for k,v in b.items()} for b in items]
    assert normalized(blocks)==normalized(FIGURES), 'A hypothetical test changed the saved plan'


def nav(page,label,audit=None):
    link=page.get_by_test_id('stSidebar').get_by_role('link',name=label,exact=True)
    box=link.bounding_box()
    if not link.is_visible() or box is None or box['x']<0:
        page.get_by_role('button',name='Expand sidebar',exact=True).click()
        if audit: audit.actions.append('Open mobile menu')
    link.click()
    if audit: audit.actions.append('Open '+label);audit.screen();audit.view(label)
    if page.viewport_size['width']<768:
        collapse=page.get_by_role('button',name='Collapse sidebar',exact=True)
        if collapse.is_visible():
            collapse.click()
            expect(link).not_to_be_in_viewport()
            if audit: audit.actions.append('Close mobile menu')


def restore(page):
    nav(page,'Settings & data')
    data={'schema_version':5,'workspace':{'schema_version':3,'blocks':FIGURES,'scenarios':[],'decision_drafts':[]},
          'plan':{'priority':'Build an emergency fund','unknown':[],'is_example':False}}
    upload_workspace(page,'audit.json',data)
    page.get_by_text("I understand this replaces my current session's data",exact=True).click()
    page.get_by_role('button',name='Restore selected workspace',exact=True).click()
    expect(page.get_by_text('Workspace restored. Review your figures and recalculate any decision.',exact=True)).to_be_visible()
    nav(page,'My Plan')
    expect(page.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
    page.wait_for_function("location.pathname === '/'")


def export(page):
    nav(page,'Settings & data')
    with page.expect_download() as dl:
        page.get_by_role('button',name='Download workspace (JSON)',exact=True).click()
    return json.loads(Path(dl.value.path()).read_text())


class Audit:
    def __init__(self,page,name):
        self.page,self.name=page,name
        self.actions=[];self.inputs=[];self.screens=[];self.views=['My Plan'];self.screen()
    def view(self,label):
        if label not in self.views: self.views.append(label)
    def screen(self):
        route=urlparse(self.page.url).path or '/'
        if route not in self.screens: self.screens.append(route)
    def click(self,label,role='button'):
        self.page.get_by_role(role,name=label,exact=True).click()
        self.actions.append(label);self.screen()
        if label=='Test this change': self.view('Goal comparison')
        elif label in ('Test a purchase','Can I buy this?'): self.view('Purchase form')
        elif label=='Open move-out comparison': self.view('Move form')
        elif label in ('See impact','Compare with my current plan','Compare stay vs move','Test this purchase'): self.view('Result')
    def text(self,label):
        self.page.get_by_text(label,exact=True).click();self.actions.append(label);self.screen()
    def enter(self,label,value):
        field=self.page.get_by_role('spinbutton',name=label,exact=True)
        field.fill(str(value));field.press('Tab')
        self.inputs.append({'label':label,'value':value})
    def record(self):
        self.screen()
        return dict(journey=self.name,screens=len(self.screens),routes=self.screens.copy(),visible_screens=len(self.views),views=self.views.copy(),inputs=len(self.inputs),clicks=len(self.actions),actions=self.actions,entered=self.inputs)


def shot(page,folder,name):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+4')
    assert not page.get_by_test_id('stException').count()
    page.get_by_test_id('stMain').evaluate('(e)=>e.scrollTo(0,0)')
    page.screenshot(path=str(folder/(name+'.png')),full_page=True,animations='disabled')


def run(args):
    folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    records=[];before=args.mode=='before'
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        for label,width,height in [('desktop',1440,1000),('mobile',390,844)]:
            for task in ('goal','purchase','move','guest_purchase'):
                context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce',accept_downloads=True)
                page=context.new_page();page.goto(args.url,wait_until='domcontentloaded')
                expect(page.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
                if task!='guest_purchase': restore(page)
                audit=Audit(page,task)
                try:
                    if task=='goal':
                        expect(page.get_by_role('region',name='Your goal result')).to_contain_text('$780.00 short')
                        records.append(dict(viewport=label,**audit.record()))
                        shot(page,folder,f'{label}-{args.mode}-goal')
                        audit.click('Test this change')
                        expect(page.get_by_role('heading',name='Current plan vs alternative',exact=True)).to_be_visible()
                        records.append(dict(viewport=label,**{**audit.record(),'journey':'goal_test'}))
                        shot(page,folder,f'{label}-{args.mode}-goal-test')
                        original=export(page)['workspace']['blocks']
                        assert_original(original)
                        assert next(b for b in original if b['id']=='goal')['monthly_contribution']=='100.00'
                    elif task=='purchase':
                        nav(page,'Test a decision' if before else 'Can I buy this?',audit)
                        audit.enter('Cost amount ($)' if before else 'Purchase price ($)',200)
                        audit.click('Compare with my current plan' if before else 'See impact')
                        if before: expect(page.get_by_role('heading',name='Current plan vs alternative',exact=True)).to_be_visible()
                        else: expect(page.get_by_test_id('stMetric').filter(has_text='Cash after purchase')).to_contain_text('$2,300.00')
                        records.append(dict(viewport=label,**audit.record()));shot(page,folder,f'{label}-{args.mode}-purchase')
                        original=export(page)['workspace']['blocks']
                        assert_original(original)
                        assert next(b for b in original if b['id']=='cash')['balance']=='2500.00'
                        if not before:
                            nav(page,'Can I buy this?')
                            page.get_by_role('button',name='Back',exact=True).click()
                            expect(page.get_by_role('spinbutton',name='Purchase price ($)',exact=True)).to_have_value('200.00')
                            page.get_by_role('button',name='See impact',exact=True).click()
                            expect(page.get_by_role('button',name='Apply these changes to my plan',exact=True)).to_be_disabled()
                            page.get_by_text('I want to replace my plan with these exact changes',exact=True).click()
                            page.get_by_role('button',name='Apply these changes to my plan',exact=True).click()
                            expect(page.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
                            saved=export(page)['workspace']['blocks']
                            assert next(b for b in saved if b['id']=='cash')['balance']=='2300.00'
                    elif task=='move':
                        if before:
                            nav(page,'Test a decision',audit);audit.text('Moving out');audit.click('Open move-out comparison')
                            audit.click('Use My Money figures')
                            expect(page.get_by_role('spinbutton',name='Monthly take-home pay ($)',exact=True)).to_have_value('2400.00')
                            audit.text('All inputs')
                            audit.enter('Your share of new rent ($/month)',1700);audit.enter('Security deposit & fees ($)',1000);audit.enter('Moving costs ($)',200)
                            page.get_by_text('Monthly bills & lifestyle changes',exact=False).click();audit.actions.append('Open monthly cost changes')
                            audit.enter('Utilities ($/month)',150);audit.text('Include my 1 existing savings goal(s)')
                            audit.click('Compare stay vs move')
                            expect(page.get_by_role('heading',name='Your moving decision, side by side',exact=True)).to_be_visible()
                        else:
                            nav(page,'Plan a move',audit)
                            for field,value in [('New rent share ($/month)',1700),('Other monthly costs: change ($)',150),('Total upfront costs ($)',1200)]: audit.enter(field,value)
                            audit.click('See impact')
                            expect(page.get_by_test_id('stMetric').filter(has_text='Money left each month')).to_contain_text('-$250.00')
                            expect(page.get_by_role('button',name='Test this alternative',exact=True)).to_be_visible()
                        records.append(dict(viewport=label,**audit.record()));shot(page,folder,f'{label}-{args.mode}-move')
                        original=export(page)['workspace']['blocks']
                        assert_original(original)
                        assert next(b for b in original if b['id']=='rent')['monthly_amount']=='1500.00'
                        assert next(b for b in original if b['id']=='cash')['balance']=='2500.00'
                        if not before:
                            nav(page,'Plan a move');page.get_by_role('button',name='Back',exact=True).click()
                            for field,value in [('New rent share ($/month)','1700.00'),('Other monthly costs: change ($)','150.00'),('Total upfront costs ($)','1200.00')]:
                                expect(page.get_by_role('spinbutton',name=field,exact=True)).to_have_value(value)
                            page.get_by_role('button',name='See impact',exact=True).click();page.get_by_role('button',name='Test this alternative',exact=True).click()
                            expect(page.get_by_test_id('stMetric').filter(has_text='Money left each month')).to_contain_text('$0.00')
                            shot(page,folder,f'{label}-after-move-alternative')
                            assert_original(export(page)['workspace']['blocks'])
                            nav(page,'Plan a move')
                            expect(page.get_by_role('button',name='Apply these changes to my plan',exact=True)).to_be_disabled()
                            page.get_by_text('I want to replace my plan with these exact changes',exact=True).click()
                            page.get_by_role('button',name='Apply these changes to my plan',exact=True).click()
                            expect(page.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
                            saved=export(page)['workspace']['blocks']
                            assert next(b for b in saved if b['id']=='rent')['monthly_amount']=='1350.00'
                            assert next(b for b in saved if b['id']=='cash')['balance']=='1300.00'
                    else:
                        audit.click('Test a purchase' if before else 'Can I buy this?')
                        fields=[('Purchase or recurring cost ($)',200),('Monthly take-home pay ($)',2400),('Monthly bills, debt payments and planned savings ($)',2400),('Checking / cash available for this purchase ($)',2500)] if before else [('Purchase price ($)',200),('Available checking / cash ($)',2500)]
                        for field,value in fields: audit.enter(field,value)
                        audit.click('Test this purchase' if before else 'See impact')
                        expect(page.get_by_text('This $200.00 purchase would leave',exact=False)).to_be_visible()
                        records.append(dict(viewport=label,**audit.record()));shot(page,folder,f'{label}-{args.mode}-guest-purchase')
                        assert export(page)['workspace']['blocks']==[]
                    print(f'{label}: {task} {args.mode} passed',flush=True)
                except Exception:
                    page.screenshot(path=str(folder/f'{label}-{task}-failure.png'),full_page=True)
                    raise
                finally:
                    context.close()
        browser.close()
    payload=dict(mode=args.mode,url=args.url,figures=FIGURES,records=records,
                 definitions={'screens':'Distinct task routes/steps visited, including My Plan. Inline results on the same task route are not an extra screen.',
                              'visible_screens':'Logical views visited, including My Plan, the task form and the result; an inline replacement result is a separate visible view. Layout toggles and disclosures are not separate screens.',
                              'inputs':'New scenario figures entered for the matched case; existing profile fields and defaults not edited are excluded.',
                              'clicks':'Control activations, including navigation, disclosures and mobile menu controls; input typing/focus and fixture setup are excluded.',
                              'move_before':'Working All inputs path. Counts include choosing the move, loading the profile, switching layout, expanding changed bills and including the existing goal.'})
    (folder/f'{args.mode}-audit.json').write_text(json.dumps(payload,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['before','after'],default='after');parser.add_argument('--url',default=os.environ.get('MONEYLAB_TEST_URL','http://127.0.0.1:8501'));parser.add_argument('--output',default='artifacts/browser/journey-audit')
    run(parser.parse_args())
