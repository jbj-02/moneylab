"""Explicit deployed MoneyLab QA with fictional data and real browser screenshots.

Run manually after deployment, not against a PR preview in CI. Normal TLS
verification stays enabled. --chromium-profile may select an isolated test
profile configured with an environment's required trust roots.
"""
import argparse
import base64
from datetime import datetime
from html import escape
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, expect
from browser_smoke import confirm, download_workspace, fictional_profile, navigate, restore_profile


class HostedApp:
    """Expose the same test controls inside Streamlit Cloud's hosted iframe."""
    def __init__(self, page, frame):
        self.page, self.frame = page, frame

    def __getattr__(self, name):
        if name in ('viewport_size', 'expect_download', 'screenshot'):
            return getattr(self.page, name)
        return getattr(self.frame, name)


def open_app(context, url):
    page = context.new_page()
    response = page.goto(url, wait_until='domcontentloaded', timeout=60000)
    iframe = page.locator('iframe').first
    if urlparse(url).hostname.endswith('.streamlit.app') or iframe.count():
        frame = iframe.content_frame
        frame.get_by_role('heading', name='My Plan', exact=True).wait_for(timeout=60000)
        actual = next(f for f in page.frames if f != page.main_frame and '/~/+/' in f.url)
    else:
        page.get_by_role('heading', name='My Plan', exact=True).wait_for(timeout=60000)
        actual = page.main_frame
    return HostedApp(page, actual), response


def capture(app, folder, label, title, screenshots):
    page = app.page
    old = page.viewport_size
    height = 1300 if old['width'] >= 768 else 1850
    page.set_viewport_size({'width':old['width'], 'height':height})
    app.get_by_test_id('stMain').evaluate('(e)=>e.scrollTo(0,0)')
    path = folder / f'{label}.png'
    page.screenshot(path=str(path), full_page=True)
    screenshots.append({'file':path.name, 'title':title, 'viewport':{'width':old['width'],'height':height}})
    page.set_viewport_size(old)


def run(args):
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=True)
    shots, journeys = [], []
    with sync_playwright() as pw:
        for width, height, label in ((1440,1000,'desktop'), (390,844,'mobile')):
            context = pw.chromium.launch_persistent_context(args.chromium_profile, channel='chromium',
                headless=True, args=['--no-sandbox'], viewport={'width':width,'height':height},
                reduced_motion='reduce', accept_downloads=True)
            try:
                app, response = open_app(context, args.url)
                tls = response.security_details()
                restore_profile(app, fictional_profile())
                confirm(app)
                summary = app.get_by_role('region', name='Recommended action', exact=True)
                expect(summary).to_contain_text('Save $333.34/month')
                expect(summary).to_contain_text('4 months sooner')
                expect(summary).to_contain_text('$133.34 of the $600.00')
                expect(summary).to_contain_text('$466.66')
                expect(app.get_by_role('button', name='Compare a later deadline', exact=True)).to_be_visible()
                expect(app.get_by_role('button', name='Compare a smaller target', exact=True)).to_be_visible()
                expander = app.get_by_test_id('stExpander').filter(has=app.get_by_text('How MoneyLab worked this out', exact=True))
                collapsed = expander.evaluate('(e)=>{const d=e.matches("details")?e:e.querySelector("details");return d?!d.open:null}')
                assert collapsed is True, 'Supporting calculations must start collapsed'
                assert app.evaluate('document.documentElement.scrollWidth <= innerWidth + 4')
                capture(app,folder,f'{label}-01-dashboard','Recommendation, benefit, funding and two alternatives',shots)
                app.get_by_role('button',name='Compare a later deadline',exact=True).click()
                expect(app.get_by_role('heading',name='Current plan vs alternative',exact=True)).to_be_visible()
                expect(app.get_by_text('10,000.00 at month 10',exact=False)).to_be_visible()
                capture(app,folder,f'{label}-02-later','Alternative: keep $200/month and allow ten months',shots)
                app.get_by_role('button',name='Discard alternative',exact=True).click()
                expect(app.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
                app.get_by_role('button',name='Compare a smaller target',exact=True).click()
                expect(app.get_by_role('heading',name='Current plan vs alternative',exact=True)).to_be_visible()
                expect(app.get_by_text('savings target: $10,000.00 → $9,200.00',exact=False)).to_be_visible()
                capture(app,folder,f'{label}-03-smaller','Alternative: a smaller $9,200 target at six months',shots)
                app.get_by_role('button',name='Discard alternative',exact=True).click()
                expect(app.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
                app.get_by_role('button',name='Preview this saving pace',exact=True).click()
                expect(app.get_by_role('heading',name='Current plan vs alternative',exact=True)).to_be_visible()
                capture(app,folder,f'{label}-04-recommendation','Recommended option before explicit approval',shots)
                original = download_workspace(app)
                assert original['workspace']['blocks'][3]['monthly_contribution'] == '200.00'
                navigate(app,'My Plan')
                app.get_by_role('link',name='Review pending alternative',exact=True).click()
                app.get_by_text('I want to replace my plan with these exact changes',exact=True).click()
                app.get_by_role('button',name='Apply these changes to my plan',exact=True).click()
                expect(app.get_by_role('heading',name='My Plan',exact=True)).to_be_visible()
                expect(app.get_by_text('Your chosen plan:',exact=False).first.locator('..')).to_contain_text('$333.34/month')
                # Complete the existing post-change review, then capture the final plan.
                confirm(app)
                capture(app,folder,f'{label}-05-approved','Approved plan with the chosen $333.34/month schedule',shots)
                chosen = download_workspace(app)
                assert chosen['workspace']['blocks'][3]['monthly_contribution'] == '333.34'
                assert chosen['plan']['accepted_plan']['blocks'][3]['monthly_contribution'] == '333.34'
                assert not app.get_by_test_id('stException').count()
                journeys.append({'viewport':label,'status':'passed','url':app.page.url,
                                 'app_frame_url':app.frame.url,'tls':tls,
                                 'checks':['visible recommendation/benefit/funding/two alternatives',
                                           'supporting calculations initially collapsed','both alternatives opened and discarded',
                                           'exploration preserved exported profile','explicit approval updated and tracked the contribution']})
                print(f'{label}: deployed journey passed',flush=True)
            except Exception:
                if context.pages:
                    context.pages[-1].screenshot(path=str(folder/f'{label}-failure.png'),full_page=True)
                raise
            finally:
                context.close()
    captured = datetime.now(ZoneInfo('America/New_York')).isoformat()
    result = {'url':args.url,'captured_at':captured,'fictional_data':True,'journeys':journeys,'screenshots':shots}
    (folder/'validation.json').write_text(json.dumps(result,indent=2))
    cards=[]
    for shot in shots:
        encoded=base64.b64encode((folder/shot['file']).read_bytes()).decode()
        cards.append(f'<figure><figcaption>{escape(shot["file"])} · {escape(shot["title"])}</figcaption><img src="data:image/png;base64,{encoded}" alt="{escape(shot["title"])}"></figure>')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MoneyLab deployed journey</title><style>body{font:16px/1.5 system-ui;background:#f6f7f3;color:#173f3e;max-width:1100px;margin:32px auto;padding:0 20px}figure{margin:30px 0}figcaption{font-weight:650;margin-bottom:10px}img{display:block;max-width:100%;border:1px solid #d3dfd7;border-radius:12px}a{color:inherit}</style><h1>MoneyLab: deployed user journey</h1>'''
    html+=f'<p>Validated <a href="{escape(args.url)}">{escape(args.url)}</a> on desktop and mobile. Captured {escape(captured)}. All figures are fictional. TLS verification remained enabled.</p><p>Passed: visible recommendation, benefit, funding and two alternatives; expandable calculations; both alternatives; immutable exploration; explicit approval; selected schedule in exported data.</p>'
    html+=''.join(cards)+'</html>'
    (folder/'index.html').write_text(html)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='https://moneylab-dev.streamlit.app/')
    parser.add_argument('--chromium-profile',required=True,help='An isolated test profile, not an everyday browser profile')
    parser.add_argument('--output',default='artifacts/deployed')
    run(parser.parse_args())
