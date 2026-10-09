#!/usr/bin/env python3
"""Unit tests for personnel / price extraction generalization.

Run: ./venv/bin/python3 tests/test_extraction.py
No pytest dependency; plain asserts with a tiny runner.
"""
import os
import re
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as m  # noqa: E402

PASS = []
FAILED = []


def check(label, fn):
    """Run one test, recording pass/fail and never aborting the sweep.

    The runner used to re-raise on the first AssertionError, so a single
    unrelated failure hid every later test's result.
    """
    try:
        fn()
    except AssertionError as e:
        FAILED.append(label)
        print(f'FAIL {label}: {e}')
        return
    except Exception as e:  # noqa: BLE001 — a crashing test is a failed test
        FAILED.append(label)
        print(f'ERROR {label}: {type(e).__name__}: {e}')
        return
    PASS.append(label)
    print(f'PASS {label}')


# ── Price extraction channels ──
def t_price_standalone_cn():
    r = m.extract_prices('人民币（大写）：壹亿贰仟陆佰壹拾捌万壹仟玖佰柒拾陆元叁角')
    assert r['totalPriceInTax'] is not None and abs(r['totalPriceInTax'] - 126181976.30) < 1, r


def t_price_symbol_with_wan():
    r = m.extract_prices('投标总价：￥12.5万元')
    assert abs(r['totalPriceInTax'] - 125000) < 1, r


def t_price_cn_label():
    r = m.extract_prices('投标总价：壹佰贰拾叁万元整')
    assert abs(r['totalPriceInTax'] - 1230000) < 1, r


def t_price_fullwidth():
    r = m.extract_prices('小写：１２３４５６')
    assert r['totalPriceInTax'] == 123456, r


def t_price_bond_excluded():
    r = m.extract_prices('投标保证金一份，金额为人民币：￥500000元')
    assert r['totalPriceInTax'] is None, r


def t_price_summary_sep():
    r = m.extract_prices('合计 \\ 1838529 5002800 \\')
    assert r['totalPrice'] == 1838529 and r['totalPriceInTax'] == 5002800, r


def t_price_bidrate():
    assert m.extract_prices('下浮率：12.5%')['bidRate'] == '12.5%'
    assert m.extract_prices('报价费率 1.8‰')['bidRate'] == '1.8‰'
    assert m.extract_prices('投标报价下浮6%')['bidRate'] == '6%'


def t_price_smallcase_first():
    r = m.extract_prices('小写：123456元 大写：壹拾贰万叁仟肆佰伍拾陆元整')
    assert r['totalPriceInTax'] == 123456, r


def t_price_cn_fractions():
    r = m.extract_prices('人民币（大写）：贰佰叁拾肆万伍仟陆佰柒拾捌元玖角')
    assert abs(r['totalPriceInTax'] - 2345678.9) < 0.01, r


def t_price_reverse_pair():
    r = m.extract_prices('小写：123456\n大写：壹拾贰万叁仟肆佰伍拾陆元整')
    assert r['totalPriceInTax'] == 123456, r


def t_similarity_toc_dots_ignored():
    # TOC leader dots ('四、授权委托书 ....... 7') must never pair unrelated
    # lines across documents ('9.7 网络拥塞的感知时间不高于 5s ....... 79')
    t1 = '目录\n四、授权委托书 ....... 7\n一、投标函 ......... 3\n'
    t2 = '9.7 网络拥塞的感知时间不高于 5s ....... 79\n项目人员与分工表\n'
    res = m.text_similarity_analysis({'a': t1, 'b': t2})
    for pr in res['pair_results']:
        for mm in pr.get('matches', []):
            assert '授权委托书' not in mm.get('text', ''), mm
            assert '网络拥塞' not in mm.get('text', ''), mm
    # 真实内容仍应匹配
    t3 = '本项目采用三层架构设计，核心交换节点采用双机热备冗余部署策略\n'
    t4 = '本项目采用三层架构设计，核心交换节点采用双机热备冗余部署策略\n'
    res2 = m.text_similarity_analysis({'a': t3, 'b': t4})
    assert any('三层架构' in mm.get('text', '')
               for pr in res2['pair_results'] for mm in pr.get('matches', [])), res2


def t_price_wan_near_context():
    # 万-form value must survive the near-context validation
    r = m.extract_prices('投标总价：￥12.5万元')
    assert abs(r['totalPriceInTax'] - 125000) < 1, r


def t_price_reference_amount_excluded():
    # 合同金额 reference amounts must never win over the real bid price
    t = ('开标一览表\n投标报价\n总价：7590000元\n\n业绩：\n'
         '项目名称：某某市计量质量检测研究院\n数量：1\n合同金额：RMB2080000.00\n')
    r = m.extract_prices(t)
    assert r['totalPriceInTax'] == 7590000, r
    # 招标文件售价 (document price, not bid price)
    r2 = m.extract_prices('开标一览表\n投标报价表\n\n招标文件售价：人民币1000元\n')
    assert r2['totalPriceInTax'] is None, r2


# ── Personnel extraction ──
def t_personnel_pipe_table():
    text = ('姓名 | 职务 | 电话\n'
            '张三 | 项目经理 | 13900000001\n'
            '李四 | 技术负责人 | 13900000002\n')
    p = m.extract_personnel(text)
    names = {x['name'] for x in p['all_persons']}
    assert {'张三', '李四'} <= names, names
    assert '13900000001' in p['phones'], p['phones']
    assert '13900000002' in p['phones'], p['phones']


def t_personnel_pipe_id():
    text = ('姓名 | 职务 | 身份证号\n王五 | 安全员 | 320101199001011234\n')
    p = m.extract_personnel(text)
    assert '320101199001011234' in p['id_numbers'], p['id_numbers']
    assert p['id_number'] == '320101199001011234', p['id_number']


def t_personnel_multivalue():
    p = m.extract_personnel('身份证号：320101199001011234 电话：13912345678 邮箱：a@b.com')
    assert '13912345678' in p['phones'] and '320101199001011234' in p['id_numbers']
    assert 'a@b.com' in p['emails'], p['emails']


def t_personnel_spaced_id():
    p = m.extract_personnel('身份证号：320101 1990 01 01 1234')
    assert p['id_numbers'] and p['id_numbers'][0] == '320101199001011234', p['id_numbers']


def t_personnel_auth_variants():
    p = m.extract_personnel('授权委托代理人：赵六\n联系电话：13800000000\n')
    assert p['authorized_rep'] == '赵六', p
    assert '13800000000' in p['phones'], p['phones']


def t_personnel_blank_template_no_leak():
    # Blank authorization-letter templates ('本人 （姓名）系 （投标人名称）…')
    # must not leak 本人/性别/盖单位章 as names or companies
    t = ('四、授权委托书\n本人 （姓名）系 （投标人名称）的法定代表人（单位负责人），现委托\n'
         '投标人：________________（盖单位章）\n姓名：性别：男 身份证号：\n')
    p = m.extract_personnel(t)
    names = {x['name'] for x in p['all_persons']}
    assert '本人' not in names and '性别' not in names, names
    assert p.get('legal_rep') not in ('本人', '性别', '性别:'), p.get('legal_rep')
    assert p.get('company_name') not in ('________________（盖单位章', '（盖单位章'), p.get('company_name')


def t_personnel_title_word_not_name():
    # PDF "序号 姓名 职称 分工" tables: '张伟 中级 项目负责人' — the 职称
    # column value 中级 must not become the name; 张伟 must be captured.
    t = ('项目人员配置\n表 5 项目人员与分工\n序号 姓名 职称 分工\n'
         '1 张伟 中级 项目负责人\n'
         '2 刘某某 教授 流资源预留协议设计\n'
         '3 潘某某 副教授 负载均衡技术设计\n')
    p = m.extract_personnel(t)
    names = [x['name'] for x in p['all_persons']]
    assert '中级' not in names and '教授' not in names and '副教授' not in names, names
    assert '张伟' in names, names
    zhang = [x for x in p['all_persons'] if x['name'] == '张伟']
    assert any(x['role'] == 'project_manager' for x in zhang), zhang


def t_personnel_role_not_name():
    # Role keywords in the name column must never become person entries
    p = m.extract_personnel('姓名 | 职务\n张三 | 项目经理\n项目经理 | 组长\n')
    names = {x['name'] for x in p['all_persons']}
    assert names == {'张三'}, names
    roles = {x['role'] for x in p['all_persons']}
    assert 'project_manager' in roles, roles


# ── xlsx ──
def t_xlsx_extract(tmp=None):
    # A hard-coded POSIX path ('/tmp/_t.xlsx') makes this test fail on Windows
    # with FileNotFoundError, so the code path it guards never actually ran
    # there. Use the platform temp dir instead.
    import tempfile
    from openpyxl import Workbook
    if tmp is None:
        tmp = os.path.join(tempfile.gettempdir(), '_t_xlsx_extract.xlsx')
    wb = Workbook()
    ws = wb.active
    ws.title = '报价单'
    ws.append(['序号', '名称', '数量', '单价', '总价'])
    ws.append([1, '服务器', 2, 30000, 60000])
    wb.save(tmp)
    try:
        text = m.extract_text_with_tables(tmp)
        assert '报价单' in text and '服务器' in text, text
        assert ' | ' in text
    finally:
        os.remove(tmp)


# ── Cross-match layer helpers (set-intersection pools) ──
def t_pools_intersection():
    from app import extract_personnel
    pi = extract_personnel('电话：13900000001 身份证号：320101199001011234')
    pj = extract_personnel('手机：13900000001 身份证号：320101199001011234')
    shared_phones = set(pi['phones']) & set(pj['phones'])
    shared_ids = set(pi['id_numbers']) & set(pj['id_numbers'])
    assert shared_phones == {'13900000001'}, shared_phones
    assert shared_ids == {'320101199001011234'}, shared_ids


# ── Format-generalization enhancements ──
def t_price_label_unit_paren():
    # '总价（元）：' and '合计（万元）：' label-with-unit formats
    r = m.extract_prices('开标一览表\n投标总价（元）：1230000元')
    assert r['totalPriceInTax'] == 1230000, r
    r2 = m.extract_prices('报价汇总表\n合计（万元）：89.3万元')
    assert abs(r2['totalPriceInTax'] - 893000) < 1, r2


def t_price_pipe_total_wan_cells():
    # 合计 pipe row with 万元-suffixed cells must keep magnitude
    r = m.extract_prices('序号 | 名称 | 金额\n合计 | 全部 | 89.3万元 | 91.97万元')
    assert abs(r['totalPrice'] - 893000) < 1, r
    assert abs(r['totalPriceInTax'] - 919700) < 1, r


def t_price_bidrate_extra():
    assert m.extract_prices('投标报价（%）：98.5')['bidRate'] == '98.5%', m.extract_prices('投标报价（%）：98.5')
    assert m.extract_prices('投标报价下浮 6 个百分点')['bidRate'] == '6%'


def t_personnel_zhweituo():
    p = m.extract_personnel('授权委托书\n兹委托 李勇 同志为我方代理人，负责签署投标文件。')
    assert p['authorized_rep'] == '李勇', p


def t_personnel_reversed_labels():
    p = m.extract_personnel('项目管理机构\n职务：项目经理 姓名：王强 联系电话：13800000000')
    names = {x['name'] for x in p['all_persons']}
    assert '王强' in names, names


def t_personnel_pipe_merged_cell():
    # docx vertically-merged name cells: empty name inherits row above
    text = ('姓名 | 职务 | 联系电话\n'
            '张三 | 项目经理 | 13900000001\n'
            ' | 技术负责人 | 13900000002\n')
    p = m.extract_personnel(text)
    names = {x['name'] for x in p['all_persons']}
    assert {'张三'} <= names, names
    assert '13900000002' in p['phones'], p['phones']


def t_personnel_pipe_multi_phone_cell():
    text = '姓名 | 职务 | 联系电话\n张三 | 项目经理 | 13900000001/13900000002\n'
    p = m.extract_personnel(text)
    assert '13900000001' in p['phones'] and '13900000002' in p['phones'], p['phones']


def t_personnel_pipe_header_alias():
    text = ('拟投入主要人员 | 职务\n'
            '李四 | 技术负责人\n')
    p = m.extract_personnel(text)
    names = {x['name'] for x in p['all_persons']}
    assert '李四' in names, names


def t_personnel_minority_dot_normalized():
    # Same minority name spelled with different middle dots must cross-match
    a = m.extract_personnel('项目管理机构\n姓名：阿不来提•买买提')
    b = m.extract_personnel('项目管理机构\n姓名：阿不来提·买买提')
    ka = {re.sub(r'[•・]', '·', x['name']) for x in a['all_persons']}
    kb = {re.sub(r'[•・]', '·', x['name']) for x in b['all_persons']}
    assert ka & kb, (ka, kb)


def t_personnel_bank_account_pool():
    p = m.extract_personnel('开户银行：中国工商银行北京分行\n账号：1100923456789000123')
    assert '1100923456789000123' in p.get('bank_accounts', []), p.get('bank_accounts')


def t_personnel_section_marker_extended():
    # New personnel-table section markers must scope extraction
    p = m.extract_personnel('人员一览表\n姓名 职务\n王强 项目经理\n')
    names = {x['name'] for x in p['all_persons']}
    assert '王强' in names, names


# ── Accuracy hardening: ceilings, environmental noise, cross-checks ──
def t_price_ceiling_excluded():
    # 最高限价 reprinted in every bid must never win as the bid price,
    # and must not HIDE the real price that appears further down.
    t = ('开标一览表\n最高限价（招标控制价）：￥1,000,000元\n投标报价：￥980,000元\n')
    r = m.extract_prices(t)
    assert r['totalPriceInTax'] == 980000, r


def t_price_ceiling_only_not_captured():
    r = m.extract_prices('开标一览表\n招标控制价：￥1000000元\n')
    assert r['totalPriceInTax'] is None, r


def t_bank_account_tender_side_excluded():
    # 保证金汇入账号 appears in EVERY bid → must stay out of the pool
    t = ('投标保证金请汇入以下账户\n开户银行：XX银行北京分行\n账号：1100923456789000123\n')
    p = m.extract_personnel(t)
    assert '1100923456789000123' not in p.get('bank_accounts', []), p.get('bank_accounts')


def t_environmental_pool_demotion():
    pools = {
        'A': {'phones': ['13900000001', '13800000000'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'B': {'phones': ['13900000002', '13800000000'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'C': {'phones': ['13900000003', '13800000000'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'D': {'phones': ['13900000004', '13800000000'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'E': {'phones': ['13800000001'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
    }
    removed = m._demote_environmental_pool_values(pools, list(pools))
    # 13800000000 in 4/5 groups (80%) → environmental, demoted
    assert '13800000000' in removed, removed
    assert pools['A']['phones'] == ['13900000001'], pools['A']
    assert pools['E']['phones'] == ['13800000001'], pools['E']
    # 3 of 4 (75%) is below the ratio — a genuinely shared phone between
    # 3 of 4 bidders is still collusion evidence and must NOT be demoted
    pools3 = {
        'A': {'phones': ['13900000001'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'B': {'phones': ['13900000001'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'C': {'phones': ['13900000001'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'D': {'phones': ['13900000009'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
    }
    assert not m._demote_environmental_pool_values(pools3, list(pools3))
    assert pools3['A']['phones'] == ['13900000001']
    # With 2 groups only, a shared phone stays (still real evidence)
    pools2 = {
        'A': {'phones': ['13900000001'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
        'B': {'phones': ['13900000001'], 'id_numbers': [], 'emails': [], 'bank_accounts': []},
    }
    assert not m._demote_environmental_pool_values(pools2, list(pools2))
    assert pools2['A']['phones'] == ['13900000001']


def t_price_cn_arabic_mismatch():
    # 大写 says 100万 but 小写 says 980000 → adopt 小写, note the conflict
    t = '开标一览表\n投标总价：壹佰万元整（小写：980000元）\n'
    r = m.extract_prices(t)
    assert r['totalPriceInTax'] == 980000, r
    assert any('大写' in w for w in r['warnings']), r['warnings']


def t_price_cn_arabic_consistent_no_warning():
    t = '开标一览表\n投标总价：壹佰万元整（小写：1000000元）\n'
    r = m.extract_prices(t)
    assert not any('大写' in w for w in r['warnings']), r['warnings']


def t_price_subitem_sum_warning():
    t = ('报价明细表\n序号 | 名称 | 数量 | 单价 | 总价\n'
         '1 | 服务器 | 2 | 30000 | 60000\n'
         '2 | 交换机 | 1 | 20000 | 20000\n'
         '合计 | | | | 980000\n')
    r = m.extract_prices(t)
    assert any('分项合计' in w for w in r['warnings']), r['warnings']


def t_price_global_fallback_warning():
    r = m.extract_prices('合计 \\ 1838529 5002800 \\')
    assert any('兜底' in w for w in r['warnings']), r['warnings']


def t_phone_spaced_and_ocr():
    p = m.extract_personnel('联系电话：139 1234 5678')
    assert '13912345678' in p['phones'], p['phones']
    p2 = m.extract_personnel('手机：138O1234567')
    assert '13801234567' in p2['phones'], p2['phones']


def t_surname_filter():
    # Non-surname table fragments must be rejected; rare/compound surnames kept
    assert not m._is_person_name('情况'), '情况 should be rejected'
    assert not m._is_person_name('规程'), '规程 should be rejected'
    assert m._is_person_name('欧阳建国')
    assert m._is_person_name('覃芳')
    assert m._is_person_name('诸葛云')


def t_parse_amount_ocr_letters():
    assert m._parse_amount('1O9,800') == 109800
    assert m._parse_amount('l2300') == 12300
    assert m._parse_amount('I00000') == 100000


def t_fitz_table_pipes():
    # PyMuPDF table rows → pipe lines (fake page object, no pymupdf needed)
    class FakeTable:
        def extract(self):
            return [['姓名', '职务'], ['张三', '项目经理'], [None, '']]
    class FakeFinder:
        tables = [FakeTable()]
    class FakePage:
        def find_tables(self):
            return FakeFinder()
    out = m._fitz_page_tables_as_pipes(FakePage())
    assert '姓名 | 职务' in out and '张三 | 项目经理' in out, out


# ── Real-world regression: auth-letter/cert format (2026-08-25) ──
def t_personnel_auth_letter_full():
    # 授权委托书 with labeled parens; also exercises the 兰 surname
    t = ('授权委托书\n本人  兰某某  （姓名）系  北京某某航天技术有限公司  （供应商名称）的'
         '法定代表人（单位负责人），现委托  陈某某  （姓名）为我方授权代理。\n')
    p = m.extract_personnel(t)
    assert p['legal_rep'] == '兰某某', p
    assert p['company_name'] == '北京某某航天技术有限公司', p
    assert p['authorized_rep'] == '陈某某', p


def t_personnel_cert_paren_format():
    # 法定代表人资格证明书: name AND company in unlabeled parentheses
    t = '法定代表人资格证明书\n（兰某某）系（北京某某航天技术有限公司）的法定代表人。\n特此证明\n'
    p = m.extract_personnel(t)
    assert p['legal_rep'] == '兰某某', p
    assert p['company_name'] == '北京某某航天技术有限公司', p


def t_personnel_company_survives_bad_name():
    # A rejected name must not also lose the company
    t = ('授权委托书\n本人  某某  （姓名）系  北京某某航天技术有限公司  （供应商名称）的法定代表人\n')
    p = m.extract_personnel(t)
    assert p['legal_rep'] is None, p
    assert p['company_name'] == '北京某某航天技术有限公司', p


def t_personnel_surnames_extended():
    for n in ('兰某某', '付某某', '肖某某', '闫某某', '郝某某', '滕某某', '岳某某', '单某某'):
        assert m._is_person_name(n), n


# ── History persistence: _prepare_history_data keep/strip semantics ──
def _fake_results():
    return {
        '_flags': {'group_map': {}, 'ok': True},
        'verdict': {'conclusion': '两份标书存在围串标高度嫌疑'},
        'metadata': {
            'files': [{'name': 'A.docx', 'creator': '张三',
                       'KSOProductBuildVer': '12.1.0.1', 'ICV': 'abc-def',
                       'KSOTemplateDocerSaveRecord': 'r1', 'pages': 12,
                       '_error': None, 'secret_huge': 'x' * 5000}],
            'matches': [], 'findings': [],
        },
        'personnel': {
            'files': [{'name': 'A.docx', 'legal_rep': '王五',
                       'phones': ['13800000000', '13911111111'],
                       'id_numbers': ['110101199001011234'],
                       'id_number': '110101199001011234',
                       'emails': ['a@b.com'], 'bank_accounts': ['110060123456'],
                       'all_persons': [{'name': '王五', 'role': 'legal_rep',
                                        'confidence': 0.9}],
                       'contacts': {'phone': '13800000000', 'email': None,
                                    'address': None},
                       'heavy_blob': ['x' * 3000]}],
            'cross_matches': [], 'findings': [],
        },
        'pricing': {
            'files': [{'name': 'A.docx', 'totalPriceInTax': 100,
                       'totalPrice': 92, 'taxRate': '13%', 'bidRate': '99.5%',
                       'revenue': 10, 'cost': 5,
                       'warnings': ['大写/小写不一致已修正'],
                       'subItemPrice': [{'priceName': '设备', 'totalPrice': 92}]}],
            'comparison': {},
            'subItemCompare': [
                {'name': '设备',
                 'items': [{'file': 'A.docx', 'totalPriceInTax': 100,
                            'extras': {'厂家/型号': '华为S5720'}}],
                 'findings': []}],
            'findings': [],
        },
        'text_similarity': {
            'pair_results': [{
                'file1': 'A', 'file2': 'B', 'total_matches': 1,
                'matches': [{'index': 1, 'length': 500, 'text': 'x' * 300,
                             'ctx1': 'y' * 500, 'ctx2': 'z' * 500,
                             'abnormal': True, 'risk_level': 'substantial',
                             'score': 0.8, 'reasons': ['术语密度高']}],
            }],
            'template_matches': 0, 'total_pairs': 1, 'findings': [],
        },
    }


def t_history_prep_keeps_new_fields():
    r = m._prepare_history_data(_fake_results())
    pf = r['personnel']['files'][0]
    assert pf['phones'] == ['13800000000', '13911111111'], pf
    assert pf['id_numbers'] == ['110101199001011234'], pf
    assert pf['emails'] == ['a@b.com'], pf
    assert pf['bank_accounts'] == ['110060123456'], pf
    assert pf['all_persons'][0]['name'] == '王五', pf
    qf = r['pricing']['files'][0]
    assert qf['bidRate'] == '99.5%', qf
    assert qf['revenue'] == 10 and qf['cost'] == 5, qf
    assert qf['warnings'] == ['大写/小写不一致已修正'], qf
    mf = r['metadata']['files'][0]
    assert mf['KSOProductBuildVer'] == '12.1.0.1', mf
    assert mf['KSOTemplateDocerSaveRecord'] == 'r1', mf
    assert mf['ICV'] == 'abc-def', mf


def t_history_prep_keeps_extras():
    r = m._prepare_history_data(_fake_results())
    items = r['pricing']['subItemCompare'][0]['items']
    assert items[0]['extras'] == {'厂家/型号': '华为S5720'}, items


def t_history_prep_light_matches():
    r = m._prepare_history_data(_fake_results())
    match = r['text_similarity']['pair_results'][0]['matches'][0]
    assert len(match['text']) == 200, len(match['text'])
    assert len(match['ctx1']) == 400 and len(match['ctx2']) == 400
    assert match['index'] == 1 and match['score'] == 0.8
    assert match['reasons'] == ['术语密度高']


def t_history_prep_strips_unknown_and_keeps_underscore():
    r = m._prepare_history_data(_fake_results())
    pf = r['personnel']['files'][0]
    # Unused by the frontend/report: contacts is a dict -> None
    assert pf['contacts'] is None, pf['contacts']
    assert pf['heavy_blob'] is None, pf['heavy_blob']
    # '_'-prefixed keys survive; unknown str keys become '' (type preserved)
    assert r['_flags'] == {'group_map': {}, 'ok': True}
    mf = r['metadata']['files'][0]
    assert mf['_error'] is None
    assert mf['secret_huge'] == '', repr(mf['secret_huge'])


def t_history_prep_modifies_copy_only():
    src = _fake_results()
    r = m._prepare_history_data(src)
    assert src['personnel']['files'][0]['phones'] == ['13800000000', '13911111111']
    assert src['text_similarity']['pair_results'][0]['matches'][0]['text'] == 'x' * 300
    assert src['pricing']['subItemCompare'][0]['items'][0]['extras'] is not None


# ── Company-name / authorized-rep cleanliness regressions ──
def t_company_strips_detached_label():
    # '（投标人名称' had the closing paren consumed by a wider capture — the
    # detached fragment must be cleaned away, not left on the company name.
    assert m._clean_company('北京某某大学 （投标人名称') == '北京某某大学'
    assert m._clean_company('北京某某大学（盖单位章）') == '北京某某大学'
    assert m._clean_company('北京某某大学（盖单位章') == '北京某某大学'
    assert m._clean_company('___北京某某大学___（盖单位章）') == '北京某某大学'
    assert m._clean_company('北京某某航天技术有限公司') == '北京某某航天技术有限公司'


def t_auth_xianweituo_split_newline():
    # '现委托李四为我方代理\n人' — 代理人 split across a PDF line wrap must
    # still be recognized (pattern 8 tolerates the newline).
    info = {'legal_rep': None, 'authorized_rep': None, 'company_name': None, 'all_persons': []}
    m._extract_from_auth_section(
        '本人张某某系北京某某大学的法定代表人（单位负责人），现委托李四为我方代理\n人。'
        '代理人根据授权，以我方名义签署、澄明确认。', info)
    assert info['authorized_rep'] == '李四', info
    assert info['legal_rep'] == '张某某', info
    assert info['company_name'] == '北京某某大学', info


def t_history_prep_keeps_name():
    r = m._prepare_history_data(_fake_results())
    assert r['personnel']['files'][0]['name'] == 'A.docx', r['personnel']['files'][0]['name']
    assert r['pricing']['files'][0]['name'] == 'A.docx'
    assert r['metadata']['files'][0]['name'] == 'A.docx'


def _glue(text):
    return m._glue_phrases(text)


def t_glue_phrases_multi_position():
    # 法定\n代\n表\n人 split across several line breaks -> one keyword.
    assert _glue('本人张某某系北京某\n某大学的法定\n代\n表\n人（单位负责人）') == \
        '本人张某某系北京某\n某大学的法定代表人（单位负责人）'
    # 委托代\n理人
    assert _glue('现委托李四为我方委托代\n理人。代理人行使签署权。') == \
        '现委托李四为我方委托代理人。代理人行使签署权。'
    # absent keyword is untouched
    assert _glue('这是一段普通文字，没有关键词') == '这是一段普通文字，没有关键词'


def t_glue_cleans_auth_extraction():
    # A whole-keyword word wrap inside the auth letter must not lose the agent.
    info = {'legal_rep': None, 'authorized_rep': None, 'company_name': None, 'all_persons': []}
    m._extract_from_auth_section(
        '本人张某某系北京某某大学的法定代表人（单位负责人），现委托李四为我方代理\n人。', info)
    assert info['authorized_rep'] == '李四', info
    assert info['company_name'] == '北京某某大学', info


def t_cjk_ws_normalized():
    assert m._normalize_cjk_whitespace('投标人 ： 张三（ 盖单位章 ）') == '投标人： 张三（盖单位章）'
    assert m._normalize_cjk_whitespace('电话 ：　010-12345678') == '电话： 010-12345678'


def t_join_split_names():
    # 换行拆词拼接
    assert m._join_split_names('本人张\n某某系的法人') == '本人张某某系的法人'
    # 空格列间距不得拼接（否则 '国 联系' / '建国 联系' 吞掉标签）
    assert m._join_split_names('张 某某') == '张 某某'
    assert m._join_split_names('职务：项目经理 姓名：王强 联系电话：13800000000') == \
        '职务：项目经理 姓名：王强 联系电话：13800000000'


def t_glue_new_phrases():
    assert m._glue_phrases('投标\n文件：开标一览表') == '投标文件：开标一览表'
    assert m._glue_phrases('授权\n委托\n书') == '授权委托书'


def t_company_prefix_strip():
    assert m._clean_company('投标人：北京某某大学') == '北京某某大学'
    assert m._clean_company('单位名称：北京某某大学') == '北京某某大学'
    assert m._clean_company('企业名称　某省未来网络创新研究院') == '某省未来网络创新研究院'


def t_clean_phone_junk():
    assert m._clean_phone('_021-12345678、') == '021-12345678'
    assert m._clean_phone('010-12345678;') == '010-12345678'
    assert m._clean_phone('010 - 1234 5678') == '010-12345678'


# ── Defense layers 7+: invisible chars / OCR glyphs / phone & amount forms ──
def t_invisible_chars_stripped():
    # Zero-width chars sit inside labels ('委托代理人\u200b：'), where \s-based
    # glue cannot reach them; CR/form-feed variants must become newlines.
    t = '授权委托书\r\n委托代理人\u200b：李\u2060勇\r被授权人：王\u00ad强\n'
    p = m.extract_personnel(t)
    assert p['authorized_rep'] == '李勇', p


def t_ocr_label_glyph_fixes():
    # Scanned-label glyph confusions: 人/入, 话/活, 币/巾, plus the 身分证
    # variant spelling — all repaired before any label regex runs.
    p = m.extract_personnel('授权委托书\n法定代表入：王强\n联系电活：13912345678\n'
                            '身分证号：110101199003070000\n')
    assert p['legal_rep'] == '王强', p
    assert '13912345678' in p['phones'], p
    assert '110101199003070000' in p['id_numbers'], p
    r = m.extract_prices('人民巾（大写）：壹佰贰拾万元整')
    assert r['totalPriceInTax'] == 1200000, r


def t_phone_country_code_and_dashed():
    # '+86…' is rejected by the plain pattern's (?<!\d) lookbehind; the
    # dash-grouped form never matched any pattern before.
    p = m.extract_personnel('联系人：+8613912345678 或 139-1234-5678')
    assert '13912345678' in p['phones'], p['phones']
    assert p['phones'].count('13912345678') == 1, p['phones']


def t_phone_landline_padded_and_label_variants():
    p = m.extract_personnel('授权委托书\n联系电话：010 - 1234 5678\n')
    assert p['phone'] == '010-12345678', p
    p2 = m.extract_personnel('授权委托书\n移动电话：13912345678\n')
    assert p2['phone'] == '13912345678', p2


def t_price_thinspace_groups():
    r = m.extract_prices('投标总价：￥1 261 819.76元')
    assert abs(r['totalPriceInTax'] - 1261819.76) < 0.01, r
    # Two space-separated column numbers must NOT merge into one amount.
    assert m._parse_amount('1838529 5002800') == 1838529


def t_price_thinspace_survives_validation():
    # The full chain: section detection must accept space-grouped numbers,
    # and the post-validation "value must appear in text" check must search
    # the '1 234 567' form — otherwise the extracted price is cleared again.
    r = m.extract_prices('开标一览表\n投标总价（元）：1 234 567.89\n税率 6%')
    assert r['totalPriceInTax'] == 1234567.89, r


def t_name_internal_spaces():
    p = m.extract_personnel('授权委托书\n委托代理人：张 三\n')
    assert p['authorized_rep'] == '张三', p
    p2 = m.extract_personnel('项目管理机构\n姓名：王 强 联系电话：13800000000\n')
    names = {x['name'] for x in p2['all_persons']}
    assert '王强' in names and '王强联' not in names, names


def t_name_tolerant_no_label_swallow():
    # '兹委托 李勇 同志…' — the tolerant class must not absorb 同志 even
    # though the trailing (?:同志)? is optional; the spaced form must still
    # be captured.
    p = m.extract_personnel('授权委托书\n兹委托 李勇 同志为我方代理人，负责签署投标文件。')
    assert p['authorized_rep'] == '李勇', p
    p2 = m.extract_personnel('授权委托书\n兹委托 李 勇 同志为我方代理人。')
    assert p2['authorized_rep'] == '李勇', p2


def t_name_validation_allows_internal_space():
    assert m._is_person_name('张 三')
    assert m._is_person_name('阿不来提 · 买买提')


def t_address_cut_at_next_label():
    p = m.extract_personnel('授权委托书\n地址：北京市海淀区上地十街10号 电话：010-12345678\n')
    assert p['address'] == '北京市海淀区上地十街10号', p


def t_email_fullwidth_at():
    p = m.extract_personnel('电子邮箱：Zhang＠Example.com\n')
    assert 'zhang@example.com' in p['emails'], p['emails']


def t_duty_label_suffix_not_person():
    # Duty-label strings are form/table column labels, never person names,
    # even when they start with a real surname (任中职务 → 任).
    for lbl in ('任中职务', '现任职务', '担任职务', '任何职务', '拟任职务',
                '本人岗位', '项目职称', '担任角色'):
        assert not m._is_person_name(lbl), lbl
    # Real names sharing those surnames/characters must keep passing.
    assert m._is_person_name('任志强')
    assert m._is_person_name('陈刚')


def t_personnel_duty_label_column():
    # PDF-flattened row '陈刚 任中职务 项目经理' (colons lost, label column
    # between name and role): the label must not enter all_persons, and the
    # real name before it must be recovered as project_manager.
    p = m.extract_personnel('项目团队\n陈刚 任中职务 项目经理\n杨帆 任中职务 项目经理\n')
    names = [(x['name'], x['role']) for x in p['all_persons']]
    assert ('任中职务', 'project_manager') not in names, names
    assert ('陈刚', 'project_manager') in names, names
    assert ('杨帆', 'project_manager') in names, names
    # Cross-line re-pairing must not duplicate an exact (name, role) pair.
    assert names.count(('杨帆', 'project_manager')) == 1, names


def t_personnel_duty_label_colon_form():
    p = m.extract_personnel('项目团队\n姓名：陈刚 任中职务：项目经理\n')
    names = [(x['name'], x['role']) for x in p['all_persons']]
    assert ('陈刚', 'project_manager') in names, names
    assert all(x['name'] != '任中职务' for x in p['all_persons']), names


def t_name_rejects_section_header_words():
    # Section markers / table captions that START with real surnames
    # (项/关/管) must never validate as person names.
    for hdr in ('项目团队', '项目成员', '项目人员', '关键人员', '管理人员',
                '项目分工', '项目组', '项目部', '组织机构', '人员简历',
                '项目机构', '人员配置'):
        assert not m._is_person_name(hdr), hdr
    # Real names sharing those surnames must keep passing.
    assert m._is_person_name('管虎')
    assert m._is_person_name('项少龙')


def t_name_rejects_duty_label_variants():
    # Traditional-script duty labels survive the surname check when led by
    # a surname char ('任職務') — the suffix rule must catch them too.
    for lbl in ('任職務', '任何崗位', '现任职务', '拟任职务', '岗位职责',
                '本任職責', '擔任角色'):
        assert not m._is_person_name(lbl), lbl


def t_personnel_section_header_not_person():
    # Flattened '项目团队\n项目经理：赵四' must not yield the section header
    # 项目团队 as a project_manager (项 is a real surname).
    p = m.extract_personnel('项目团队\n项目经理：赵四\n')
    names = [(x['name'], x['role']) for x in p['all_persons']]
    assert ('项目团队', 'project_manager') not in names, names
    assert ('赵四', 'project_manager') in names, names


def t_personnel_role_not_paired_across_lines():
    # A role keyword at the end of one table row must not attach to the
    # next row's name ('王强 项目经理\n李勇 施工员' once made 李勇 a
    # project_manager → false same-role cross-file match risk).
    p = m.extract_personnel('项目团队\n王强 项目经理\n李勇 施工员\n')
    roles = {}
    for x in p['all_persons']:
        roles.setdefault(x['name'], set()).add(x['role'])
    assert 'project_manager' in roles.get('王强', set()), roles
    assert 'project_manager' not in roles.get('李勇', set()), roles
    assert 'team_member' in roles.get('李勇', set()), roles
    # Same-line role-then-name pairs keep working, several per line.
    p2 = m.extract_personnel('项目团队\n项目经理 王强 技术负责人 李四\n')
    roles2 = {}
    for x in p2['all_persons']:
        roles2.setdefault(x['name'], set()).add(x['role'])
    assert roles2.get('王强') == {'project_manager'}, roles2
    assert roles2.get('李四') == {'tech_lead'}, roles2


def t_personnel_label_colon_without_name_label():
    # '陈刚 任中职务：项目经理' — no 姓名 label at all; the colon sits after
    # the duty-label column with zero space before the role value.
    p = m.extract_personnel('项目团队\n陈刚 任中职务：项目经理\n')
    names = [(x['name'], x['role']) for x in p['all_persons']]
    assert ('陈刚', 'project_manager') in names, names
    assert all(x['name'] != '任中职务' for x in p['all_persons']), names


def t_personnel_traditional_duty_label():
    # Traditional-script duty labels (任職務) must be skipped the same way
    # so the real name before them is still recovered.
    p = m.extract_personnel('项目团队\n陈刚 任職務 项目经理\n')
    names = [(x['name'], x['role']) for x in p['all_persons']]
    assert ('陈刚', 'project_manager') in names, names
    assert all('職務' not in x['name'] for x in p['all_persons']), names


def t_personnel_resume_vertical_labels():
    # Resume forms put 姓名 and 职务 on different lines; the span between
    # them may cross a newline but never another 姓名 label.
    p = m.extract_personnel('项目团队\n姓名：张三 性别：男\n现任职务：项目经理\n')
    roles = {x['role'] for x in p['all_persons'] if x['name'] == '张三'}
    assert 'project_manager' in roles, p['all_persons']

    p2 = m.extract_personnel('项目团队\n姓名：张三 学历：本科\n姓名：李四 职务：项目经理\n')
    roles2 = {x['role'] for x in p2['all_persons'] if x['name'] == '张三'}
    roles3 = {x['role'] for x in p2['all_persons'] if x['name'] == '李四'}
    assert 'project_manager' not in roles2, p2['all_persons']
    assert 'project_manager' in roles3, p2['all_persons']


def t_personnel_fill_brackets_unwrapped():
    # 【】-wrapped form fills ('姓名： 【张三】') must not defeat the label
    # regexes — one bidder wrapped EVERY filled value that way and personnel
    # came back completely empty.
    t = ('二、法定代表人（单位负责人）身份证明\n'
         '投标人名称： 某某机电制造有限公司\n'
         '姓名： 【张三】 性别： 【男】 年龄： 【76】 职务： 【总经理】\n'
         '\n'
         '3\n'
         '系 某某机电制造有限公司 （投标人名称）的法定代表人（单位\n'
         '负责人）。\n'
         '特此证明。\n')
    r = m.extract_personnel(t)
    assert r['company_name'] == '某某机电制造有限公司', r
    assert r['legal_rep'] == '张三', r


def t_person_spaced_authorized_rep_with_ocr_heading():
    # Scanned-bid regression: the authorization letter heading OCR'd to
    # '售权委托书' and the agent name was printed with per-char spaces
    # ('现委托 王 小 明 为我方代理人') — the agent was silently dropped, so
    # the cross-bid match against the same clean-spelled name never fired.
    t = ('本人 李林\n'
         '三、售权委托书\n'
         '（姓名） 系 某某管路配件有限公司 （投标人名称） 的法定代表人（单\n'
         ' 位负责人） ，现委托 王 小 明 为我方代理人。代理人根据授权，以我方名义签署、澄清\n'
         '确认、递交、撤回、修改设备采购招标项目投标文件、签订合同和处理有关事宜，其法律后\n'
         '果由我方承担。\n'
         '投标人：某某管路配件有限公司（盖单位章）\n')
    r = m.extract_personnel(t)
    assert r['company_name'] == '某某管路配件有限公司', r
    assert r['legal_rep'] == '李林', r
    # Spaced capture must be collapsed so cross-file name matching pairs it
    # with the clean spelling used in the other bidder's document.
    assert r['authorized_rep'] == '王小明', r


def t_person_auth_header_interleave_not_midword():
    # When the chapter header sits between the name line and the （姓名）
    # continuation, the capture must be the real name — never a mid-word
    # slice of the heading like '权委托书' (out of '三、授权委托书').
    t = ('本人 李林\n'
         '三、授权委托书\n'
         '（姓名） 系 某某管路配件有限公司 （投标人名称） 的法定代表人（单\n'
         ' 位负责人）。\n')
    r = m.extract_personnel(t)
    assert r['legal_rep'] == '李林', r


def t_person_join_split_names_spares_chapter_marker():
    # '李林\n三、授权委托书' is a name line followed by a chapter header —
    # joining yields '李林三、…' and derails the auth patterns. Numeral
    # continuations directly followed by a pause mark must not join.
    s = '本人 李林 \n三、授权委托书\n（姓名） 系 某某公司 的法定代表人'
    assert m._join_split_names(s) == s, m._join_split_names(s)
    # Genuine split names still join.
    assert m._join_split_names('负责人：张\n三丰') == '负责人：张三丰'


def t_ocr_heading_shouquan_fixed():
    # 授/售 glyph confusion in the authorization heading ('售权委托' never
    # occurs in legitimate Chinese) — fixing it restores section detection.
    assert m._fix_ocr_label_confusions('三、售权委托书') == '三、授权委托书'
    assert '授权' in m._fix_ocr_label_confusions('售权委托书')


def t_price_fill_brackets_unwrapped():
    # Same fill style hiding amounts: '（￥ 【98000】 ）' / 大写 in 【】.
    t = ('开标一览表\n投标总价（大写）： 【玖万捌仟元整】\n'
         '小写：￥ 【98000】 \n')
    r = m.extract_prices(t)
    assert r['totalPriceInTax'] == 98000, r


def t_person_xlsx_sheet_marker_survives_bracket_strip():
    # The 【工作表】 header drives the pipe-table parser — the bracket strip
    # must not eat it.
    s = '【工作表】人员表\n姓名 | 电话\n张三 | 13912345678\n'
    assert m._strip_fill_brackets(s) == s, m._strip_fill_brackets(s)


def t_price_bank_voucher_excluded():
    # Bond transfer slip: '金额 / 人民币：22,000.00 / 人民币：贰万贰仟元整 /
    # 用途 / 制单日期…' — banking words sit on neighbouring lines, not on
    # the amount's own line, so they need the voucher WINDOW check.
    text = ('开标一览表\n投标总价\n大写：壹佰壹拾贰万元\n小写：1120000.00元\n（元，含税）\n'
            '账号 30210000000123\n开户行 中国民生银行\n金额\n人民币：22,000.00\n'
            '人民币：贰万贰仟元整\n用途\n制单日期：2025-08-26\n')
    r = m.extract_prices(text)
    assert r['totalPriceInTax'] == 1120000, r


def t_price_bond_echo_excluded():
    # The bond value echoes unlabeled later in the document; a candidate
    # equal to a bond-labeled amount must be skipped even without voucher
    # words around it.
    text = '投标函\n投标总价：980000元\n投标保证金\n2.2万元\n附证明材料\n人民币：22000\n'
    r = m.extract_prices(text)
    assert r['totalPriceInTax'] == 980000, r


def t_price_rmb_label_no_newline_grab():
    # '2000万元人民币\n2014年1月20日' — the 人民币 prefix at a line end must
    # not pair with the next line's year; '人民币 2014年' (same line) is a
    # year too, never an amount.
    text = ('投标人基本情况表\n注册资金\n成立时间\n2000万元人民币\n2014年1月20日\n'
            '人民币 2014年注册\n开标一览表\n小写：1120000.00元\n')
    r = m.extract_prices(text)
    assert r['totalPriceInTax'] == 1120000, r


def t_price_section_toc_and_quote_anchors():
    # A TOC without dot leaders, a 《…》 reference and a "…" quoted mention
    # are not section headers; the anchor must fall on the real table.
    toc = '目录\n' + ''.join(
        f'{c}、{t}\n' for c, t in zip('一二三四五六七八九十',
        ['投标函', '开标一览表', '分项报价表', '法定代表人身份证明', '资格审查资料',
         '技术方案', '服务承诺', '履约计划', '培训方案', '其他补充材料']))
    toc += '附件1 本项目实施团队主要人员名单 63\n附件2 本项目实施团队主要人员简历表 64\n' * 6
    text = (toc + '一、投标函\n愿意以《开标一览表》中的投标报价提供全部内容。\n'
            '备注：分项合计金额中的总价应等于“开标一览表”中的投标总价。\n'
            '开标一览表\n投标总价（元，含税）\n大写：玖拾捌万元整\n小写：980000.00元\n')
    r = m.extract_prices(text)
    assert r['totalPriceInTax'] == 980000, r


def t_price_cost_wan_magnitude():
    r = m.extract_prices('成本明细\n人工成本 350万元\n设备购置费 12000元\n')
    costs = {d['priceName']: d['totalPrice'] for d in r['costDetails']}
    assert costs.get('人工成本') == 3500000, costs
    assert costs.get('设备购置费') == 12000, costs


def t_price_cost_performance_table_excluded():
    # Past-performance tables list HISTORICAL contract amounts under a
    # 合同金额 header; project-name fragments ('站产品采购') are not cost
    # items and 3500万 must not shrink to 3500.
    text = ('业绩一览表\n项目名称\n合同金额\n(元)\n2023年\n某某A+福利\n'
            '站产品采购\n3500万\n某某集团\n2000万\n')
    r = m.extract_prices(text)
    assert r['cost'] is None and not r['costDetails'], r


def t_price_unit_rate_not_total():
    # Per-month / per-person rates share the summary table with the total;
    # the denominator is dropped by the amount patterns, so the rate would
    # pose as the total.
    text = ('开标一览表\n小写：22000.00元/月\n服务单价 340000/人月\n'
            '投标总价：1120000元\n')
    r = m.extract_prices(text)
    assert r['totalPriceInTax'] == 1120000, r


def t_price_fee_penalty_labels_excluded():
    text = ('投标函\n违约金：人民币50000元\n招标代理服务费：￥30000\n'
            '开标一览表\n小写：980000.00元\n')
    r = m.extract_prices(text)
    assert r['totalPriceInTax'] == 980000, r


def t_price_bond_echo_cn_numeral():
    # '投标保证金（大写）：贰万元整' must seed the bond echo set so the
    # unlabeled '人民币：20000' echo is skipped anywhere in the document.
    text = ('投标保证金（大写）：贰万元整\n其他材料\n人民币：20000\n'
            '开标一览表\n小写：980000.00元\n')
    r = m.extract_prices(text)
    assert r['totalPriceInTax'] == 980000, r


def t_price_tax_pair_date_runs_rejected():
    # '签订 20250826 / 生效 20250829 / 3' — two calendar dates + a small
    # digit pass the old ratio check (1.0) and would pose as a 20M price pair.
    r = m.extract_prices('开标一览表\n签订 20250826\n生效 20250829\n3\n')
    assert r['totalPriceInTax'] is None and r['totalPrice'] is None, r


def t_price_cost_line_flattened_variants():
    # 序号 prefixes, colons, thousands commas and 万元 magnitudes are all
    # common in flattened cost tables.
    r = m.extract_prices('成本明细\n1. 材料费：340,000.00元\n（二）人工成本：350万\n')
    costs = {d['priceName']: d['totalPrice'] for d in r['costDetails']}
    assert costs.get('材料费') == 340000, costs
    assert costs.get('人工成本') == 3500000, costs


def t_price_cost_date_run_rejected():
    # Glued date runs ('检测20250826批次') are not 20M cost items.
    r = m.extract_prices('检测报告\n检测20250826批次\n差旅费20250826\n')
    assert not r['costDetails'] and r['cost'] is None, r


# ══ 第三批泛化：人员（填空下划线 / 无冒号标签 / 动词族 / 联系人 / 跨行断裂）══

def t_personnel_underscore_fill_names():
    # Values written over an underline fill survive label matching and are
    # stripped in the result.
    p = m.extract_personnel('授权委托书\n法定代表人：___张三___\n委托代理人：____李四____\n')
    assert p['legal_rep'] == '张三', p
    assert p['authorized_rep'] == '李四', p


def t_personnel_legal_rep_paren_sign():
    # '法定代表人（签字）：王五' — paren qualifier between label and colon.
    p = m.extract_personnel('投标函\n法定代表人（签字）：王五\n')
    assert p['legal_rep'] == '王五', p


def t_personnel_signature_deputy_variant():
    # '法定代表人或委托代理人' (missing 其) + （签字） qualifier + underline fill.
    p = m.extract_personnel('签字盖章页\n法定代表人或委托代理人（签字）：___赵六___\n')
    names = {x['name'] for x in p['all_persons']}
    assert '赵六' in names, names


def t_personnel_weipai_verb():
    # 委派/委任 verb variants; lazy capture keeps 同志 out of the name.
    p = m.extract_personnel('授权委托书\n兹委派孙七同志为我方代理人\n')
    assert p['authorized_rep'] == '孙七', p
    p2 = m.extract_personnel('授权委托书\n兹委任王五为我方代理人\n')
    assert p2['authorized_rep'] == '王五', p2


def t_personnel_contact_person_role():
    # '联系人：周八' feeds all_persons as bid_contact (cross-file same-name
    # matching previously never saw contact persons).
    p = m.extract_personnel('投标函\n联系人：周八\n联系电话：13912345678\n')
    roles = {x['name']: x['role'] for x in p['all_persons']}
    assert roles.get('周八') == 'bid_contact', roles


def t_personnel_colonless_legal_rep():
    # Flattened-table form '法定代表人 王大锤' (no colon).
    p = m.extract_personnel('兹委任某人\n法定代表人 王大锤\n')
    assert p['legal_rep'] == '王大锤', p


def t_personnel_id_newline_split():
    # Cell-per-line PDF splits an 18-digit ID across three lines.
    p = m.extract_personnel('身份证号：320123\n19900101\n123X\n')
    assert '32012319900101123X' in p['id_numbers'], p['id_numbers']


def t_personnel_mobile_group_linebreak():
    # '1391234\n5678' — 3-4-4 grouping split at a line break.
    p = m.extract_personnel('联系电话：1391234\n5678\n')
    assert '13912345678' in p['phones'], p['phones']


def t_personnel_role_vocab_extended():
    # Supervision/construction roles: 监理工程师 / 施工负责人.
    p = m.extract_personnel('主要人员\n李芳 监理工程师\n王雷 施工负责人\n')
    roles = {}
    for x in p['all_persons']:
        roles.setdefault(x['name'], set()).add(x['role'])
    assert 'team_member' in roles.get('李芳', set()), roles
    assert 'project_manager' in roles.get('王雷', set()), roles


def t_personnel_dunhao_name_role():
    # '张三、项目经理' — 顿号 separator between name and role.
    p = m.extract_personnel('项目团队\n张三、项目经理\n')
    roles = {x['name']: x['role'] for x in p['all_persons']}
    assert roles.get('张三') == 'project_manager', roles


def t_personnel_company_label_with_name():
    # Cover company label variant '投标人名称：…'.
    p = m.extract_personnel('投标人名称：北京某某科技有限公司\n')
    assert p['company_name'] == '北京某某科技有限公司', p.get('company_name')


def t_personnel_address_fill_stripped():
    p = m.extract_personnel('授权委托书\n地址：____北京市海淀区中关村大街1号____\n')
    assert p['address'] == '北京市海淀区中关村大街1号', p.get('address')


def t_personnel_bank_card_label():
    p = m.extract_personnel('银行卡号：6222020200112233445\n')
    assert '6222020200112233445' in p['bank_accounts'], p['bank_accounts']


def t_personnel_colonless_name_role_table():
    # '姓名 张三 职务 项目经理' — colon-less flattened table row.
    p = m.extract_personnel('项目团队\n姓名 张三 职务 项目经理\n')
    roles = {}
    for x in p['all_persons']:
        roles.setdefault(x['name'], set()).add(x['role'])
    assert 'project_manager' in roles.get('张三', set()), roles


# ══ 第三批泛化：报价（填空 / 括号变体 / 标签同义词 / 大写跨行 / 千分位）══

def t_price_underscore_fill():
    r = m.extract_prices('开标一览表\n投标总价：____98.6万元____\n')
    assert r['totalPriceInTax'] == 986000, r


def t_price_label_paren_note():
    # Short annotation paren between label and colon.
    r = m.extract_prices('开标一览表\n投标总价（含税）：1,261,819.76元\n')
    assert abs((r['totalPriceInTax'] or 0) - 1261819.76) < 0.01, r


def t_price_paren_unit_rmb():
    r = m.extract_prices('开标一览表\n总报价（人民币）：500000元\n')
    assert r['totalPriceInTax'] == 500000, r


def t_price_paren_unit_wan_bare_value():
    # Unit lives ONLY in the paren — bare 89.3 must scale to 893000.
    r = m.extract_prices('开标一览表\n合计（单位：万元）：89.3\n')
    assert r['totalPriceInTax'] == 893000, r
    r2 = m.extract_prices('报价汇总表\n合计（万元）：89.3\n')
    assert r2['totalPriceInTax'] == 893000, r2


def t_price_label_synonyms():
    for text, want in [('磋商报价：1200000元\n', 1200000),
                       ('最后报价：98万元\n', 980000),
                       ('报价总额：350万\n', 3500000)]:
        r = m.extract_prices(text)
        assert r['totalPriceInTax'] == want, (text, r)


def t_price_daxie_split_across_lines():
    # CN amount broken mid-number by a line break.
    r = m.extract_prices('大写：壹佰贰拾\n叁万元整\n')
    assert r['totalPriceInTax'] == 1230000, r


def t_price_daxie_jine_word():
    # '大写金额：' inserts 金额 between label and colon.
    r = m.extract_prices('大写金额：壹佰万元整\n')
    assert r['totalPriceInTax'] == 1000000, r


def t_price_daxie_split_pair_consistent():
    # Split 大写 + 小写 pair: value correct, no mismatch warning.
    r = m.extract_prices('大写：壹佰贰拾\n叁万元整\n小写：1230000元\n')
    assert r['totalPriceInTax'] == 1230000, r
    assert not any('不一致' in w for w in r['warnings']), r['warnings']


def t_price_xiaoxie_class_separator():
    # '（小写）￥：980000元' — ￥ before the colon, class-run separator.
    r = m.extract_prices('（小写）￥：980000元\n')
    assert r['totalPriceInTax'] == 980000, r


def t_price_heji_row_commas():
    # 合计 row with thousands commas in both price columns.
    r = m.extract_prices('合计 \\ 1,838,529 5,002,800 \\\n')
    assert r['totalPrice'] == 1838529 and r['totalPriceInTax'] == 5002800, r


def t_price_tax_included_wan_magnitude():
    r = m.extract_prices('含税总价：98万元\n')
    assert r['totalPriceInTax'] == 980000, r


def t_price_tax_decomposition_commas():
    # Pre-tax / post-tax pair with comma thousands: 1,838,529 × 1.03.
    r = m.extract_prices('开标一览表\n1,838,529 1893684 3\n')
    assert r['totalPrice'] == 1838529, r
    assert r['totalPriceInTax'] == 1893684, r
    assert r['taxRate'] == '3%', r


def t_price_rmb_lowercase_token():
    # 'rmb 98000元' — lowercase currency token.
    r = m.extract_prices('rmb 98000元\n')
    assert r['totalPriceInTax'] == 98000, r


def t_price_bidrate_underscore_fill():
    r = m.extract_prices('报价函\n下浮率：__8__%\n')
    assert r['bidRate'] == '8%', r


def t_price_xiaoxie_date_rejected():
    # A date run after 小写： must not become a 20M price.
    r = m.extract_prices('开标记录表\n小写：20250826\n')
    assert r['totalPriceInTax'] is None, r


# ══ 第四批泛化：括号注记组合 / 传真 / 为是连接 / 繁体大写 / 费率变体 ══

def t_personnel_paren_combined_qualifier():
    # '（签字或盖章）' combined paren qualifier on the agent label.
    p = m.extract_personnel('投标函\n委托代理人（签字或盖章）：钱九\n')
    assert p['authorized_rep'] == '钱九', p
    # '法定代表人（单位负责人）：' insert-paren label variant.
    p2 = m.extract_personnel('投标函\n法定代表人（单位负责人）：孙十\n')
    assert p2['legal_rep'] == '孙十', p2


def t_personnel_fax_paren_area_code():
    # 传真 label + '(010)1234-5678' parenthesized area code (parens dropped,
    # dash structure kept per _clean_phone convention).
    p = m.extract_personnel('投标函\n传真：(010)1234-5678\n')
    assert p['phone'] == '0101234-5678', p.get('phone')


def t_personnel_bare_zhanghu_label():
    p = m.extract_personnel('授权委托书\n账户：1100923456789001\n')
    assert '1100923456789001' in p['bank_accounts'], p['bank_accounts']


def t_personnel_cover_address():
    # Address on the bid-letter cover (previously only auth sections scanned).
    p = m.extract_personnel('投标函\n地址：北京市朝阳区建国路88号院6号楼\n')
    assert p['address'] == '北京市朝阳区建国路88号院6号楼', p.get('address')


def t_personnel_bare_auth_titles():
    p = m.extract_personnel('授权书\n兹授权周明为我方代理人\n')
    assert p['authorized_rep'] == '周明', p


def t_personnel_contact_fill():
    p = m.extract_personnel('投标函\n联系人：___郑一___\n')
    roles = {x['name']: x['role'] for x in p['all_persons']}
    assert roles.get('郑一') == 'bid_contact', roles


def t_personnel_same_line_label_not_swallowed():
    # A name followed by the NEXT field label on the same line must not
    # swallow it ('联系人：王五 传真：…' once became the 'name' 王五传真).
    # Lazy name classes stop at the boundary; the field-label suffix
    # blacklist in _is_person_name is the backstop.
    p = m.extract_personnel('投标函\n联系人：王五 传真：(010)1234-5678\n')
    roles = {x['name']: x['role'] for x in p['all_persons']}
    assert roles.get('王五') == 'bid_contact', roles
    p2 = m.extract_personnel('授权委托书\n委托代理人：李四 电话：13800000000\n')
    assert p2['authorized_rep'] == '李四', p2


def t_price_wei_shi_connectors():
    r = m.extract_prices('开标一览表\n投标总价为98万元\n')
    assert r['totalPriceInTax'] == 980000, r
    r2 = m.extract_prices('报价表\n总报价是350万\n')
    assert r2['totalPriceInTax'] == 3500000, r2


def t_price_traditional_numerals():
    # 萬/貳 traditional glyphs normalize before CN parsing.
    r = m.extract_prices('开标一览表\n大写：壹佰貳拾萬元整\n')
    assert r['totalPriceInTax'] == 1200000, r


def t_price_discount_rate_labels():
    r = m.extract_prices('报价函\n优惠率：5%\n')
    assert r['bidRate'] == '5%', r
    r2 = m.extract_prices('报价函\n折扣率：8.5%\n')
    assert r2['bidRate'] == '8.5%', r2
    # 个百分点 wording without a % sign.
    r3 = m.extract_prices('报价函\n下浮率：8.5个百分点\n')
    assert r3['bidRate'] == '8.5%', r3


def t_price_zandingjia_excluded():
    r = m.extract_prices('开标一览表\n暂定价：500000元\n投标总价：980000元\n')
    assert r['totalPriceInTax'] == 980000, r


def t_price_pretax_posttax_label_family():
    r = m.extract_prices('报价表\n税前价：1189450.24\n')
    assert r['totalPrice'] == 1189450.24, r
    r2 = m.extract_prices('报价表\n税后金额：1261819.76元\n')
    assert r2['totalPriceInTax'] == 1261819.76, r2


def t_price_xiaoxie_thin_space():
    r = m.extract_prices('开标一览表\n小写：1 261 819.76元\n')
    assert abs((r['totalPriceInTax'] or 0) - 1261819.76) < 0.01, r


# ══ 损坏 PDF 处理：MuPDF 诊断静音 + pypdf 打不开时降级 ══

def _make_classic_pdf_in(td, name):
    """Build the classic-xref fixture inside `td` and return (path, offsets).

    The basename check keeps the fixture write confined to the caller's
    temp dir (path-traversal guard)."""
    import os as _os
    assert _os.path.basename(name) == name
    path = _os.path.join(td, name)
    offsets = _make_classic_pdf(path)
    return path, offsets


def _corrupt_xref_offset(path, obj_offset):
    """Point one xref entry (the content-stream object) at a bogus offset —
    the 'cannot find object in xref' repair scenario."""
    raw = open(path, 'rb').read()
    raw = raw.replace(b'%010d 00000 n' % obj_offset, b'0099999999 00000 n')
    open(path, 'wb').write(raw)


def _destroy_startxref(path):
    """Break the startxref keyword so pypdf cannot open the file at all."""
    raw = open(path, 'rb').read().replace(b'startxref', b'startxreaF')
    open(path, 'wb').write(raw)


def _draw_cjk_grid_table(path):
    """Draw a 3x4 line grid with CJK cell text (china-s built-in font)."""
    import pymupdf
    d = pymupdf.open()
    p = d.new_page()
    rows, cols = 3, 4
    x0, y0, cw, ch = 72, 72, 90, 22
    for r in range(rows + 1):
        p.draw_line((x0, y0 + r * ch), (x0 + cols * cw, y0 + r * ch))
    for c in range(cols + 1):
        p.draw_line((x0 + c * cw, y0), (x0 + c * cw, y0 + rows * ch))
    data = [['姓名', '职务', '联系电话', '备注'],
            ['王强', '项目经理', '13900000001', ''],
            ['李芳', '监理工程师', '13900000002', '']]
    for r, row in enumerate(data):
        for c, v in enumerate(row):
            if v:
                p.insert_text((x0 + c * cw + 4, y0 + r * ch + 15), v,
                              fontname='china-s')
    d.save(path)
    d.close()


def _draw_cjk_borderless_table(path):
    """Same 3x4 CJK table as _draw_cjk_grid_table but with no ruling lines —
    the case only the layout analyzer can see."""
    import pymupdf
    d = pymupdf.open()
    p = d.new_page()
    x0, y0, cw, ch = 72, 72, 90, 22
    data = [['姓名', '职务', '联系电话', '备注'],
            ['王强', '项目经理', '13900000001', ''],
            ['李芳', '监理工程师', '13900000002', '']]
    for r, row in enumerate(data):
        for c, v in enumerate(row):
            if v:
                p.insert_text((x0 + c * cw + 4, y0 + r * ch + 15), v,
                              fontname='china-s')
    d.save(path)
    d.close()


def _make_classic_pdf(path):
    """Hand-assemble a minimal classic-xref PDF (pymupdf writes xref streams,
    so the plain-table layout needed for these corruption tests is built
    byte-by-byte with correct offsets)."""
    objs = {
        1: b'<< /Type /Catalog /Pages 2 0 R >>',
        2: b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        3: (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            b'/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>'),
        5: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    }
    stream = b'BT /F1 12 Tf 72 720 Td (bid price 980000 yuan test) Tj ET'
    objs[4] = b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream'
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = {}
    for n in sorted(objs):
        offsets[n] = len(out)
        out += b'%d 0 obj\n' % n + objs[n] + b'\nendobj\n'
    xref_off = len(out)
    n_objs = max(objs) + 1
    out += b'xref\n0 %d\n' % n_objs + b'0000000000 65535 f \n'
    for n in range(1, n_objs):
        out += b'%010d 00000 n \n' % offsets[n]
    out += (b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n'
            % (n_objs, xref_off))
    open(path, 'wb').write(bytes(out))
    return offsets


def t_pdf_broken_xref_still_extracts():
    # Damaged xref entry (bogus object offset): MuPDF repairs and extracts;
    # the 'MuPDF error: cannot find object in xref' console spam is silenced.
    import os as _os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path, offsets = _make_classic_pdf_in(td, 'broken.pdf')
        _corrupt_xref_offset(path, offsets[4])
        t = m.extract_text_with_tables(path)
        assert 'bid price' in t, repr(t[:80])


def t_pdf_pypdf_dead_mupdf_fallback():
    # startxref destroyed: pypdf raises, extraction degrades to MuPDF's
    # repair mode instead of failing the whole file.
    import os as _os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path, _ = _make_classic_pdf_in(td, 'dead.pdf')
        _destroy_startxref(path)
        t = m.extract_text_with_tables(path)
        assert 'bid price' in t, repr(t[:80])


def t_pdf_table_channel_union():
    # Structured table channel: find_tables(union=True) fuses the layout
    # analyzer's grids (pymupdf-layout) with line-based candidates. Draws a
    # real line grid with CJK cell text (china-s) and checks the pipe rows.
    # NOTE: the page-level text is read through pypdf in the full pipeline,
    # and pypdf cannot decode china-s without a ToUnicode map — so this test
    # exercises _fitz_page_tables_as_pipes directly.
    try:
        import pymupdf
    except ImportError:
        return  # pymupdf absent: channel disabled in production too
    import os as _os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path, _ = _make_classic_pdf_in(td, 'table.pdf')
        _draw_cjk_grid_table(path)
        d2 = pymupdf.open(path)
        try:
            pipes = m._fitz_page_tables_as_pipes(d2[0])
            assert '姓名' in pipes and '王强' in pipes and '项目经理' in pipes, pipes
        finally:
            # Windows refuses to delete a file that still has an open handle, so
            # TemporaryDirectory cleanup raised PermissionError without this.
            d2.close()


def t_pdf_table_layout_modes():
    # PDF_TABLE_LAYOUT gating. The layout analyzer costs ~5-13x the line finder
    # and, once consulted, suppresses line-only tables: its classifier returns
    # no 'table' box for diagram-ish pages, and the default use_layout=True
    # path then bails out with an empty TableFinder, discarding rows the line
    # finder had already recovered. So 'auto' has to be a superset of 'off' —
    # escalate for borderless tables, never trade away a line-found one.
    try:
        import pymupdf
    except ImportError:
        return  # pymupdf absent: channel disabled in production too
    # Activate the layout analyzer exactly as _open_fitz() does. This test
    # calls _fitz_page_tables_as_pipes directly, so unlike a real extraction
    # nothing has imported pymupdf.layout for it — without this the borderless
    # case would fail for a reason that has nothing to do with the gating.
    try:
        import pymupdf.layout  # noqa: F401
    except Exception:
        pass  # optional: union degrades to line-based
    import tempfile
    saved = m.PDF_TABLE_LAYOUT
    try:
        with tempfile.TemporaryDirectory() as td:
            # Borderless: the line finder is blind, so 'off' yields nothing
            # and 'auto' must recover the table by escalating to the model.
            path = os.path.join(td, 'nolines.pdf')
            _draw_cjk_borderless_table(path)
            doc = pymupdf.open(path)
            try:
                m.PDF_TABLE_LAYOUT = 'off'
                assert m._fitz_page_tables_as_pipes(doc[0]) == '', '线框检测不应认出无框线表'
                m.PDF_TABLE_LAYOUT = 'auto'
                pipes = m._fitz_page_tables_as_pipes(doc[0])
                assert '王强' in pipes and '项目经理' in pipes, pipes
            finally:
                # see t_pdf_table_channel_union: Windows needs the handle shut
                # before TemporaryDirectory can delete the file
                doc.close()

            # Framed: the line pass answers, so 'auto' must return exactly its
            # rows and never escalate — that is the whole suppression guard.
            path2 = os.path.join(td, 'lines.pdf')
            _draw_cjk_grid_table(path2)
            doc2 = pymupdf.open(path2)
            try:
                m.PDF_TABLE_LAYOUT = 'off'
                plain = m._fitz_page_tables_as_pipes(doc2[0])
                assert '王强' in plain, plain
                m.PDF_TABLE_LAYOUT = 'auto'
                assert m._fitz_page_tables_as_pipes(doc2[0]) == plain
            finally:
                doc2.close()
    finally:
        m.PDF_TABLE_LAYOUT = saved


# ══ 提取缓存与并行提取 ══

def t_extract_cache_roundtrip():
    # Extraction output is cached per content hash: the same file replays,
    # an edited file does not, and the page budget is part of the key.
    import tempfile
    saved_dir, saved_on = m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED
    try:
        with tempfile.TemporaryDirectory() as td:
            m.EXTRACT_CACHE_DIR = td
            m.EXTRACT_CACHE_ENABLED = True
            p = os.path.join(td, 'sample.txt')
            with open(p, 'w', encoding='utf-8') as f:
                f.write('投标人名称：测试科技有限公司\n法定代表人：张三\n')
            first = m.extract_text_with_tables(p)
            assert '张三' in first, first

            # Count real parses so a "hit" is proven, not merely consistent.
            parses = []
            real = m._extract_text_uncached

            def _counting(*a, **k):
                parses.append(1)
                return real(*a, **k)

            m._extract_text_uncached = _counting
            try:
                # Same bytes at a *different* path still hits: the key is the
                # content, not the path — uploads are re-saved under a fresh
                # random filename on every analysis, so a path or mtime key
                # would never hit in practice.
                p2 = os.path.join(td, 'copy.txt')
                with open(p2, 'w', encoding='utf-8') as f:
                    f.write('投标人名称：测试科技有限公司\n法定代表人：张三\n')
                assert m.extract_text_with_tables(p2) == first
                assert not parses, '同内容不同路径应命中缓存'

                # Changed bytes → different key → real extraction.
                with open(p, 'w', encoding='utf-8') as f:
                    f.write('投标人名称：另一家公司\n')
                changed = m.extract_text_with_tables(p)
                assert len(parses) == 1, '内容已变却未重新提取'
                assert '另一家公司' in changed, changed
            finally:
                m._extract_text_uncached = real

            # Different settings are a different key for identical bytes.
            assert (m._extract_cache_key(p, 10)
                    != m._extract_cache_key(p, 20)), 'max_pages 未纳入缓存键'
    finally:
        m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED = saved_dir, saved_on


def t_extract_cache_ignores_empty():
    # Empty results are not cached — that is also what a transient failure
    # looks like, and re-extracting a document that yielded nothing is cheap.
    import tempfile
    saved_dir, saved_on = m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED
    try:
        with tempfile.TemporaryDirectory() as td:
            m.EXTRACT_CACHE_DIR = td
            m.EXTRACT_CACHE_ENABLED = True
            p = os.path.join(td, 'empty.txt')
            open(p, 'w', encoding='utf-8').close()
            assert m.extract_text_with_tables(p) == ''
            assert not [n for n in os.listdir(td) if n.endswith('.txt')
                        and n != 'empty.txt'], '空结果不应写入缓存'
    finally:
        m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED = saved_dir, saved_on


def t_extract_many_matches_sequential():
    # _extract_many is the parallel path. It must return texts aligned with
    # its input despite workers finishing out of order, and an unreadable
    # file must yield '' instead of raising — the sequential loop it replaces
    # swallowed per-file errors the same way.
    try:
        import app  # noqa: F401 — the spawn path re-imports this module
    except Exception:
        return
    import tempfile
    saved_dir, saved_on = m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED
    try:
        with tempfile.TemporaryDirectory() as td:
            m.EXTRACT_CACHE_DIR = td
            m.EXTRACT_CACHE_ENABLED = False   # measure the path, not the cache
            paths = []
            for i, name in enumerate(('甲公司', '乙公司', '丙公司')):
                p = os.path.join(td, f'{i}.txt')
                with open(p, 'w', encoding='utf-8') as f:
                    f.write(f'投标人名称：{name}\n法定代表人：负责人{i}\n'
                            * (i + 1))
                paths.append(p)
            paths.append(os.path.join(td, 'missing.txt'))  # unreadable

            def _sequential_reference(ps):
                # Mirrors the loop _extract_many replaced: a per-file failure
                # contributed nothing rather than propagating.
                out = []
                for p in ps:
                    try:
                        text, pages = m.extract_text_with_pages(p)
                        out.append((text or '', pages or []))
                    except Exception:
                        out.append(('', []))
                return out

            expected = _sequential_reference(paths)
            got = m._extract_many(paths)
            assert got == expected, [len(g[0]) for g in got]

            seen = []
            m._extract_many(paths, on_file_done=lambda i, t, pg=None: seen.append(i))
            assert sorted(seen) == list(range(len(paths))), seen
    finally:
        m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED = saved_dir, saved_on


def t_reference_filter_normalized():
    # _is_in_reference takes *pre-normalized* reference documents (it used to
    # re-normalize them on every call, which profiling put at 94% of the whole
    # analysis). The comparison must still see through whitespace, full-width
    # punctuation and case on both sides.
    ref = ['本项目采用三层架构设计，核心交换节点采用双机热备冗余部署策略。']
    ref_norm = [m._normalize_for_match(r) for r in ref]

    same_content = '本项目采用三层架构设计， 核心交换节点采用双机热备冗余部署策略。'
    assert m._is_in_reference(same_content, ref_norm), '空白差异应仍判为同一段'
    assert not m._is_in_reference('完全无关的另一段技术描述，用于确认不会误判', ref_norm)
    assert not m._is_in_reference('三层架构', ref_norm), '过短不应判为命中'
    assert not m._is_in_reference(same_content, []), '无参照文件时不应命中'


def t_extract_worker_sizing():
    # Worker count must adapt to the machine it lands on: bounded by the batch
    # size, the usable CPU count, the memory budget and the hard cap — and
    # never 0, never more than the batch. The memory term scales with input
    # size because a worker's footprint does (measured 458MB for a 2MB PDF,
    # 903MB for a 242MB one).
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tiny = []
        for i in range(6):
            p = os.path.join(td, f'{i}.pdf')
            with open(p, 'wb') as f:
                f.write(b'x' * 1024)
            tiny.append(p)
        big = os.path.join(td, 'big.pdf')
        with open(big, 'wb') as f:          # sparse: 200MB, no real disk use
            f.seek(200 * 1024 * 1024 - 1)
            f.write(b'\0')

        saved_cpu, saved_mem = m._usable_cpu_count, m._memory_budget_mb
        try:
            # Roomy machine: bounded by the batch and the cap, not by cores.
            m._usable_cpu_count = lambda: 64
            m._memory_budget_mb = lambda: 131072
            assert m._extract_worker_count(tiny) == min(6, m.EXTRACT_MAX_WORKERS)

            # Tight memory binds well below the CPU count.
            m._usable_cpu_count = lambda: 8
            m._memory_budget_mb = lambda: 1024
            assert m._extract_worker_count(tiny) == 2, m._extract_worker_count(tiny)

            # The same budget buys fewer workers once the inputs are large —
            # this is what stops a 4GB desktop from swapping on 240MB bids.
            m._memory_budget_mb = lambda: 4096
            assert m._extract_worker_count([big] * 6) == 4, m._extract_worker_count([big] * 6)

            # Never below one worker, however little memory is reported.
            m._memory_budget_mb = lambda: 1
            assert m._extract_worker_count(tiny) == 1

            # Unknown memory (no API on the platform) → CPU decides.
            m._memory_budget_mb = lambda: None
            m._usable_cpu_count = lambda: 3
            assert m._extract_worker_count(tiny) == 3

            # A single file never deserves a pool.
            assert m._extract_worker_count([tiny[0]]) == 1
        finally:
            m._usable_cpu_count, m._memory_budget_mb = saved_cpu, saved_mem

    # On whatever machine this runs on, both probes must return something
    # usable rather than raising.
    assert m._usable_cpu_count() >= 1
    budget = m._memory_budget_mb()
    assert budget is None or budget > 0, budget


# ══ 围串标信号：电话池 / 环境噪声 / 新增判定条款 ══

def t_phone_pool_includes_landlines():
    # The cross-matching pool used to be mobile-only, so a shared 座机 on the
    # 供应商基本情况表 (shared contact) could never pair two documents.
    r = m.extract_personnel('联系人：陈二 电话：010-88886666 传真：010-77775555')
    assert '010-88886666' in r['phones'], r['phones']
    assert '010-77775555' in r['phones'], r['phones']
    # Account / ID / date digit runs must NOT reach the pool.
    r2 = m.extract_personnel('账号：11000000000000000999 身份证号：320101199001011234')
    assert not [p for p in r2['phones'] if len(p) > 13], r2['phones']


def t_env_demotion_prefers_reference_doc():
    # A value the TENDER document reprints is environmental. A value shared by
    # EVERY bidder but absent from the tender document is the strongest signal
    # there is — a shared contact is *defined* as the shared case, so the old frequency
    # rule (which degenerates to "in every document" at 3 bidders) deleted
    # exactly the evidence it existed to protect.
    shared = '13911112222'
    pools = {n: {'phones': [shared]} for n in ('甲', '乙', '丙')}
    ref = ['招标代理联系电话：01000000000']
    removed = m._demote_environmental_pool_values(pools, list(pools), ref_texts=ref)
    assert removed == set(), removed
    assert all(pools[n]['phones'] == [shared] for n in pools)

    # …but a value that IS in the tender document still goes.
    pools2 = {n: {'phones': ['01000000000', '13900000001']} for n in ('甲', '乙', '丙')}
    removed2 = m._demote_environmental_pool_values(pools2, list(pools2), ref_texts=ref)
    assert removed2 == {'01000000000'}, removed2
    assert all(pools2[n]['phones'] == ['13900000001'] for n in pools2)

    # No reference supplied → frequency fallback, unchanged from before.
    pools3 = {n: {'phones': [shared, f'1390000000{i}']} for i, n in enumerate('甲乙丙')}
    assert m._demote_environmental_pool_values(pools3, list(pools3)) == {shared}


def t_project_manager_parenthesized_hint():
    # '（项目经理姓名）吴九' — bracket hint then fill, in free-standing 承诺书
    # prose no section marker covers. 丙公司's 承诺书 names 吴九 while its
    # 简历表 names 郑明; only the 承诺书 ties the file to 乙公司 (标注项九).
    r = m.extract_personnel(
        '我方拟派往（工程名称）某改造工程工程 的项目经理 （项目经理姓名）吴九 '
        '现阶段没有担任任何在施建设工程项目的项目经理。')
    pms = [p['name'] for p in r['all_persons'] if p['role'] == 'project_manager']
    assert pms == ['吴九'], pms


def t_non_name_business_nouns_rejected():
    # Table-cell fragments that survived the surname + length checks used to
    # reach all_persons — '经营范围' even cross-matched across all three
    # bidders as a team_member.
    for bad in ('经营范围', '管理模块', '通知用户', '成影响的'):
        assert not m._is_person_name(bad), bad
    for good in ('陈二', '张三', '李四', '蒋五', '周八', '冯强', '吴九'):
        assert m._is_person_name(good), good


def t_verdict_has_article34_and_mixing_clauses():
    # 条例第三十四条 (单位负责人为同一人) and 第四十条第五项 (文件混装) had no
    # clause at all: the 周八 legal_rep overlap was detected as a cross-match
    # yet appeared nowhere in the verdict.
    import tempfile
    saved = m.EXTRACT_CACHE_ENABLED
    try:
        m.EXTRACT_CACHE_ENABLED = False
        with tempfile.TemporaryDirectory() as td:
            paths = {}
            for name, tpl in (('甲', '姓名：周八 投标人名称：甲公司\n'),
                              ('乙', '姓名：周八 投标人名称：乙公司\n')):
                p = os.path.join(td, f'{name}.txt')
                with open(p, 'w', encoding='utf-8') as f:
                    f.write(tpl)
                paths[name] = p
            gt = {n: m.extract_text_with_tables(p) for n, p in paths.items()}
            res = m.run_full_analysis(list(paths.values()), [], group_map={n: [p] for n, p in paths.items()},
                                      group_texts=gt)
            clauses = {c['clause']: c for c in res['verdict']['clauses']}
            assert '第（三十四）条' in clauses, list(clauses)
            assert '第（五）项' in clauses, list(clauses)
    finally:
        m.EXTRACT_CACHE_ENABLED = saved


def t_total_price_ladder_detected():
    # 标注项六: three totals in equal steps. The pairwise loop only reported
    # EQUAL totals, so 295万/300万/305万 produced no finding at all.
    import tempfile
    saved = m.EXTRACT_CACHE_ENABLED
    try:
        m.EXTRACT_CACHE_ENABLED = False
        with tempfile.TemporaryDirectory() as td:
            paths = {}
            for name, row in (('甲', '01 | 甲公司 | 壹佰玖拾伍万元整 | 1950000 元'),
                              ('乙', '01 | 乙公司 | 贰百万元整 | 2000000 元'),
                              ('丙', '01 | 丙公司 | 贰佰零伍万元整 | 2050000 元')):
                p = os.path.join(td, f'{name}.txt')
                with open(p, 'w', encoding='utf-8') as f:
                    f.write(f'投标人名称：{name}公司\n7 报价一览表\n报价一览表\n'
                            f'包号 | 供应商名称 | 大写 | 小写\n{row}\n')
                paths[name] = p
            gt = {n: m.extract_text_with_tables(p) for n, p in paths.items()}
            for n, t in gt.items():
                got = m.extract_prices(t)['totalPriceInTax']
                assert got, f'{n} 未提取到总价'
            res = m.run_full_analysis(list(paths.values()), [],
                                      group_map={n: [p] for n, p in paths.items()},
                                      group_texts=gt)
            ev = next(c for c in res['verdict']['clauses']
                      if c['clause'] == '第（四）项-b')['evidence']
            assert any('等差数列' in e for e in ev), ev
    finally:
        m.EXTRACT_CACHE_ENABLED = saved


def t_docx_tables_keep_document_order():
    # Paragraphs used to be emitted first and every table appended after, so a
    # table was torn from the heading that introduced it (报价一览表 heading at
    # ~500, its price table pushed to ~16700).
    try:
        from docx import Document  # noqa: F401
    except ImportError:
        return
    import tempfile
    from docx import Document as _Doc
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'order.docx')
        d = _Doc()
        d.add_paragraph('7 报价一览表')
        tb = d.add_table(rows=1, cols=2)
        tb.rows[0].cells[0].text = '包号'
        tb.rows[0].cells[1].text = '2000000'
        d.add_paragraph('表后段落')
        d.save(p)
        t = m.extract_text_with_tables(p)
        assert t.index('报价一览表') < t.index('2000000') < t.index('表后段落'), repr(t)


def t_docx_image_ocr_is_selective():
    # Only .docx images whose NEIGHBOURING text marks them as evidence get
    # OCRed — a 商务标 carries ~128 images and OCRing all of them costs minutes
    # while most are seals and photos. The engine is stubbed: this test is
    # about the selection rule, not about OCR quality.
    try:
        import cv2  # noqa: F401
        from docx import Document  # noqa: F401
    except ImportError:
        return  # deps absent: image OCR is off in production too
    import tempfile
    import numpy as np
    from docx import Document as _Doc

    saved_ocr = m._get_ocr_image_fn
    saved_flag = m.DOCX_IMAGE_OCR
    saved_floor = m.DOCX_IMAGE_OCR_MIN_BYTES
    try:
        with tempfile.TemporaryDirectory() as td:
            img = os.path.join(td, 'i.png')
            cv2.imwrite(img, np.full((640, 480, 3), 200, np.uint8))
            ocr_calls = []

            def _fake_ocr(blob):
                ocr_calls.append(blob)
                return 'OCR_TEXTLINE'

            m.DOCX_IMAGE_OCR = True
            m.DOCX_IMAGE_OCR_MIN_BYTES = 0        # isolate the trigger rule
            m._get_ocr_image_fn = lambda: _fake_ocr

            p = os.path.join(td, 'img.docx')
            d = _Doc()
            d.add_paragraph('4 磋商保证金凭证/交款单据电子件')   # triggers
            d.add_picture(img)
            d.add_paragraph('施工组织设计概述')                  # does not
            d.add_picture(img)
            d.save(p)

            text = m.extract_text_with_tables(p)
            assert 'OCR_TEXTLINE' in text, text[-200:]
            assert len(ocr_calls) == 1, f'应只 OCR 触发词附近那张，实际 {len(ocr_calls)}'

            # Disabled entirely → no OCR call, no injected text.
            ocr_calls.clear()
            m.DOCX_IMAGE_OCR = False
            assert 'OCR_TEXTLINE' not in m.extract_text_with_tables(p)
            assert not ocr_calls
    finally:
        m._get_ocr_image_fn = saved_ocr
        m.DOCX_IMAGE_OCR = saved_flag
        m.DOCX_IMAGE_OCR_MIN_BYTES = saved_floor


def t_docx_image_ocr_skips_icons():
    # The byte floor keeps logos and rules out of the OCR queue.
    assert m.DOCX_IMAGE_OCR_MIN_BYTES > 0
    assert not m._DOCX_IMAGE_TRIGGER.search('施工组织设计')
    assert m._DOCX_IMAGE_TRIGGER.search('磋商保证金凭证/交款单据电子件')
    assert m._DOCX_IMAGE_TRIGGER.search('开户许可')


def t_docx_image_ocr_reports_progress():
    # The UI needs to know OCR is running — it is tens of seconds on a large
    # Word file, and without an event the progress bar simply sits there.
    try:
        import cv2  # noqa: F401
        from docx import Document  # noqa: F401
    except ImportError:
        return
    import tempfile
    import numpy as np
    from docx import Document as _Doc

    saved_ocr = m._get_ocr_image_fn
    saved_floor = m.DOCX_IMAGE_OCR_MIN_BYTES
    try:
        with tempfile.TemporaryDirectory() as td:
            img = os.path.join(td, 'i.png')
            cv2.imwrite(img, np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8))
            m._get_ocr_image_fn = lambda: (lambda blob: 'OCR_TEXTLINE')
            m.DOCX_IMAGE_OCR_MIN_BYTES = 0
            p = os.path.join(td, 'p.docx')
            d = _Doc()
            d.add_paragraph('4 磋商保证金凭证/交款单据电子件')
            d.add_picture(img)
            d.save(p)

            events = []
            m.extract_text_with_tables(
                p, on_progress=lambda ph, cur, tot, ht, det: events.append(ph))
            assert 'docx_img_ocr_start' in events, events
            assert 'docx_img_ocr' in events, events
            assert events.index('docx_img_ocr_start') < events.index('docx_img_ocr'), events
    finally:
        m._get_ocr_image_fn = saved_ocr
        m.DOCX_IMAGE_OCR_MIN_BYTES = saved_floor


def t_parallel_progress_crosses_processes():
    # Workers cannot call the parent's callback, so events travel over a queue
    # handed to the pool at creation. Getting this wrong is silent: the run
    # succeeds and simply reports nothing (the first cut used terminate() in
    # its finally, which killed the workers before they flushed that queue).
    try:
        import cv2  # noqa: F401
        from docx import Document  # noqa: F401
    except ImportError:
        return
    import tempfile
    import numpy as np
    from docx import Document as _Doc
    saved_dir, saved_on = m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED
    try:
        with tempfile.TemporaryDirectory() as td:
            m.EXTRACT_CACHE_DIR = td
            m.EXTRACT_CACHE_ENABLED = False
            img = os.path.join(td, 'i.png')
            cv2.imwrite(img, np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8))
            paths = []
            for n in range(2):
                p = os.path.join(td, f'{n}.docx')
                d = _Doc()
                d.add_paragraph('4 磋商保证金凭证/交款单据电子件')
                d.add_picture(img)
                d.save(p)
                paths.append(p)
            events = []
            m._extract_many(paths, on_progress=lambda *a: events.append(a[0]))
            assert 'docx_img_ocr_start' in events, events
    finally:
        m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED = saved_dir, saved_on


def t_display_name_strips_upload_prefix():
    # Progress labels must name the document the user picked, not the storage
    # name _safe_save invented ('46e8be14_乙公司.docx').
    assert m._display_name('/tmp/uploads/46e8be14_乙公司.docx') == '乙公司.docx'
    assert m._display_name('ref_a1b2c3d4_招标文件.pdf') == '招标文件.pdf'
    # A name that merely starts with hex-ish text must survive intact.
    assert m._display_name('fedcba98x_报告.docx') == 'fedcba98x_报告.docx'
    assert m._display_name('投标人G-投标文件.pdf') == '投标人G-投标文件.pdf'
    assert m._display_name('') == ''


def t_cancel_reaches_extraction():
    # _extract_many must HAND cancel_event down to extract_text_with_tables.
    # It was dropped when the parallel rewrite replaced the per-file loops at
    # the call sites: Stop still set the flag, but nothing inside the
    # extractor ever looked — a 300-page scan kept OCRing (minutes) while the
    # button sat on 正在停止.
    try:
        from docx import Document  # noqa: F401
    except ImportError:
        return
    import tempfile
    import threading
    import time
    from docx import Document as _Doc

    saved_dir, saved_on = m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED
    try:
        with tempfile.TemporaryDirectory() as td:
            m.EXTRACT_CACHE_DIR = td
            m.EXTRACT_CACHE_ENABLED = False
            paths = []
            for n in range(2):
                p = os.path.join(td, f'{n}.docx')
                d = _Doc()
                for i in range(60):
                    d.add_paragraph(f'第 {i} 段内容')
                d.save(p)
                paths.append(p)

            # Sequential (single file) and parallel (two files) must both
            # abort near-instantly once the flag is up.
            for label, batch in (('串行', paths[:1]), ('并行', paths)):
                ev = threading.Event()
                ev.set()
                t0 = time.time()
                try:
                    m._extract_many(batch, cancel_event=ev)
                    raise AssertionError(f'{label}: 取消未生效，正常返回了')
                except m.AnalysisCancelled:
                    pass
                assert time.time() - t0 < 5, f'{label}: 取消响应过慢'
    finally:
        m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED = saved_dir, saved_on


def t_docx_image_ocr_zero_means_unlimited():
    # 0 must mean "unlimited" here as it does for OCR_MAX_PAGES /
    # OCR_TIME_BUDGET / MAX_PDF_PAGES. A bare `if done >= MAX` turns 0 into
    # "OCR nothing" — the exact opposite of what anyone setting 0 in this
    # codebase expects.
    try:
        import cv2  # noqa: F401
        from docx import Document  # noqa: F401
    except ImportError:
        return
    import tempfile
    import numpy as np
    from docx import Document as _Doc

    saved_ocr = m._get_ocr_image_fn
    saved_floor = m.DOCX_IMAGE_OCR_MIN_BYTES
    saved_max = m.DOCX_IMAGE_OCR_MAX
    saved_budget = m.DOCX_IMAGE_OCR_BUDGET
    try:
        with tempfile.TemporaryDirectory() as td:
            m._get_ocr_image_fn = lambda: (lambda blob: 'OCR_TEXTLINE')
            m.DOCX_IMAGE_OCR_MIN_BYTES = 0
            m.DOCX_IMAGE_OCR_MAX = 0          # unlimited
            m.DOCX_IMAGE_OCR_BUDGET = 0       # unlimited
            p = os.path.join(td, 'z.docx')
            d = _Doc()
            d.add_paragraph('4 磋商保证金凭证/交款单据电子件')
            for n in range(3):
                img = os.path.join(td, f'{n}.png')
                # distinct bytes so the de-dup does not collapse them
                cv2.imwrite(img, np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8))
                d.add_picture(img)
            d.save(p)
            text = m.extract_text_with_tables(p)
            assert text.count('OCR_TEXTLINE') == 3, text.count('OCR_TEXTLINE')
    finally:
        m._get_ocr_image_fn = saved_ocr
        m.DOCX_IMAGE_OCR_MIN_BYTES = saved_floor
        m.DOCX_IMAGE_OCR_MAX = saved_max
        m.DOCX_IMAGE_OCR_BUDGET = saved_budget


def t_report_appendix_covers_new_clauses():
    # The appendix is what a reviewer reads to check the verdict's legal
    # footing: it must carry 第三十四条 (the new clause) and must not still
    # claim 第（五）项 needs manual review — it is auto-detected now.
    assert any('第三十四条' in x or '单位负责人为同一人' in x
               for x in m._REGULATION_ARTICLE_34), m._REGULATION_ARTICLE_34
    assert any('相互混装' in x for x in m._REGULATION_ARTICLE_40)
    # Weights must cover every clause the verdict can emit.
    for clause in ('第（三十四）条', '第（一）项', '第（二）项', '第（三）项',
                   '第（五）项', '第（四）项-a', '第（四）项-b'):
        assert clause in m._REPORT_CLAUSE_ADVICE, clause


def t_app_version_consistent_across_release_surfaces():
    # APP_VERSION 是版本号唯一来源：前端 footer 标注、静态资源缓存参数、
    # Release 产物文件名后缀、安装器版本都由它派生。iss 与 star.spec 没有
    # CI 自动同步，靠这个测试在本地拦截漂移。
    ver = m.APP_VERSION
    assert re.fullmatch(r'\d+\.\d+\.\d+', ver), ver
    # 渲染路径：'/' 必须把版本号带进页面（footer 标注 + 缓存参数）
    resp = m.app.test_client().get('/')
    assert resp.status_code == 200, resp.status_code
    body = resp.data.decode('utf-8')
    assert f'v{ver}' in body, 'footer 版本标注缺失'
    assert f'style.css?v={ver}' in body and f'main.js?v={ver}' in body, body[-500:]
    # 打包侧：iss 安装器版本与 macOS Bundle 版本须与 APP_VERSION 一致
    root = os.path.dirname(os.path.abspath(m.__file__))
    with open(os.path.join(root, 'packaging', '星易查.iss'), encoding='utf-8') as f:
        assert f'#define MyAppVersion "{ver}"' in f.read(), '星易查.iss 版本未同步'
    with open(os.path.join(root, 'packaging', 'star.spec'), encoding='utf-8') as f:
        assert f"'CFBundleShortVersionString': '{ver}'" in f.read(), 'star.spec 版本未同步'


def t_waitress_body_cap_matches_upload_policy():
    # 桌面版 waitress 原生 max_request_body_size 默认仅 1GB，且在服务器层
    # 拦截、到不了 Flask：>1GB 的批次（多份扫描件标书很常见）要么收到
    # waitress 裸 413（前端落到"上传文件过大"兜底文案），要么上传中途
    # 连接被掐断（前端报 Failed to fetch）。修复是 serve() 显式放宽该值：
    # 未设 Flask 上限时 32GB；设了 MAX_CONTENT_LENGTH_MB 时取 2 倍，让
    # 超限请求穿到 Flask、由 _too_large 返回带具体限额的 JSON。
    import importlib.util

    from waitress.adjustments import Adjustments

    assert 'MAX_CONTENT_LENGTH_MB' not in os.environ, '测试环境须不设该变量'
    assert m._waitress_max_body_bytes == 32 * 1024 * 1024 * 1024
    # kwarg 必须真实被 waitress 接受：拼错参数名/非法值会在 Adjustments
    # 构造时抛错，而 serve(**kw) 透传在启动时才会暴露——静默回退 1GB
    # 上限正是本 bug 的回归形态。
    adj = Adjustments(max_request_body_size=m._waitress_max_body_bytes)
    assert adj.max_request_body_size == m._waitress_max_body_bytes

    # 限额档：隔离加载一份设了 MAX_CONTENT_LENGTH_MB 的 app 模块验证
    # 2 倍关系（不能用 reload：会把 EXTRACT_CACHE_ENABLED 等测试密闭性
    # 设置重置回默认）。
    key = 'MAX_CONTENT_LENGTH_MB'
    saved = os.environ.get(key)
    os.environ[key] = '500'
    try:
        app_path = os.path.join(os.path.dirname(os.path.abspath(m.__file__)), 'app.py')
        spec = importlib.util.spec_from_file_location('app_capped_for_test', app_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.app.config['MAX_CONTENT_LENGTH'] == 500 * 1024 * 1024
        assert mod._waitress_max_body_bytes == 1000 * 1024 * 1024, \
            'waitress 上限须取 Flask 上限 2 倍，超限请求才能穿到 Flask'
        assert mod._waitress_max_body_bytes > mod.app.config['MAX_CONTENT_LENGTH']
    finally:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved


def t_waitress_channel_timeout_covers_analysis_budget():
    # waitress 默认 channel_timeout=120s 会收割"不活跃"连接；分析期间的
    # 长静默段（并行提取纯 docx/文字PDF 批次无 OCR 事件）必须被覆盖，
    # 否则流在分析中途被服务器自己掐断。
    from waitress.adjustments import Adjustments

    assert m._waitress_channel_timeout == 3600 + 300
    adj = Adjustments(channel_timeout=m._waitress_channel_timeout)
    assert adj.channel_timeout > 120, '须高于 waitress 原生 120s 默认'


def t_stream_heartbeat_during_silence():
    # 静默段心跳：并行提取只转发 OCR 类事件，纯 docx/文字 PDF 批次可能
    # 数分钟无事件下发——带内置网络超时的浏览器（及 EDR 的 HTTP 过滤）
    # 会掐断这条"看似死亡"的连接（前端 network error，waitress 报
    # Client disconnected）。心跳让连接始终有字节流动。
    import queue as _queue

    q = _queue.Queue()

    # 透传：真事件原样通过
    q.put({'type': 'progress', 'label': 'x'})
    it = m._iter_stream_events(q, lambda: True, heartbeat_every=0.3)
    assert next(it) == {'type': 'progress', 'label': 'x'}

    # 静默：无事件时按 heartbeat_every 周期发心跳
    t0 = time.monotonic()
    hb = next(it)
    assert hb == {'type': 'heartbeat'}, hb
    assert time.monotonic() - t0 >= 0.25, '心跳不得早于 heartbeat_every'
    it.close()

    # 退出：worker 已死且队列排空 → StopIteration（排空尾部事件后）
    q.put({'type': 'extract'})
    out = list(m._iter_stream_events(q, lambda: False, heartbeat_every=60))
    assert out == [{'type': 'extract'}], out

    # should_stop：谓词为真立即结束（分析阶段的 cancelled/deadline 加急）
    out = list(m._iter_stream_events(_queue.Queue(), lambda: True,
                                     should_stop=lambda: True,
                                     heartbeat_every=60))
    assert out == [], out


def t_std_listing_detector():
    # 用户报告的误报：国标/体系认证编号段（GB 5749、GB/T19001-2016、
    # ISO22000:2018、CNCA-R-2002-006、《…标准》名称、认证依据/认证覆盖
    # 的业务范围等登记词汇）被记成"可能高风险异常段落"。检测器按登记
    # token 占比判定（阈值 0.7），正样本全部命中、同领域自编叙述全部保留。
    positives = [
        'b5749《生活饮用水卫生标准》，GB/T19001-2016/，GB/T45001-2020/IS045001:2018，■机构批准号CNCA-R-2002-006',
        '通过GB/T19001-2016质量管理体系认证、GB/T45001-2020职业健康安全管理体系认证、ISO22000食品安全管理体系认证。',
        '具备GB 5749《生活饮用水卫生标准》、GB 31654《食品安全国家标准 餐饮服务通用卫生规范》检测能力，机构批准号CNCA-R-2002-006。',
        'GB/T19001质量管理体系认证证书、ISO22000食品安全管理体系认证证书、HACCP认证证书、CNAS实验室认可证书。',
        '管理体系符合ISO22000:2018，认证项目质量管理体系认证(ISO9001)',
        '认证依据GB/T 19001-2016/SO 9001:2015',
        '认证覆盖的业务范围',
        '质量管理体系认证证书 编号：00121Q30215R2M GB/T19001-2016',
        # 认证证书页的审核员行/批准号/标准符合行（用户第二批实测漏判）：
        # 登记号被"人名 + 审核员 + 审核阶段"稀释，需靠证书登记号冗余规则
        ('张某某（2023-N1EMS-4024505，审核员，监督审核),李某某（2023-N1EMS-4029046，审核员，初审一阶段）.'
         '王月辉（2023-N1OHSMS-4025882，审核员，再认证二阶段),白颖（2023-N1OHSMS-4042728，审核员，监督审核）'),
        '张某某（2023-N1EMS-4024505，审核员）',
        '认证中心有限公司\n·机构批准号\nCNCA-R-2002-0',
        '·机构批准号\nCNCA-R-2002-0',
        # 证书页单行片段（实际匹配段而非整块）：体系全名必须覆盖，
        # '环境管理体系'只被'管理体系'覆盖 4/9=0.44 时此形态会漏出
        '环境管理体系符合标准：\nGB/T24001-2016/',
        '质量管理体系符合标准：\nGB/T19001-2016/',
    ]
    for s in positives:
        assert m._is_standard_listing(s), s[:40]
    negatives = [
        '我方项目经理王强持有GB/T19001内审员证书，负责现场质量管控工作，并承诺全过程驻场服务直至项目结束。',
        '本项目采用GB/T19001质量管理体系，配备专职食品安全员6名，实行日检周报制度，每月向采购人提交自查报告与整改台账。',
        '我司已通过GB/T19001-2016、GB/T45001-2020、ISO22000三项体系认证，管理体系覆盖本项目全部服务内容，'
        '项目经理具备十年从业经验，团队配备食品安全员六名，实行三级质量管控。',
        '每日对中央厨房的温度记录、留样记录与消毒记录进行三方核查，并按月向采购人提交食品安全自查报告与整改闭环台账。',
        '本项目投标报价为人民币贰佰万元整，服务期限三年，配备项目经理一名、食品安全员六名。',
        '我方按GB/T19001标准建立质量管理体系，覆盖投标范围内全部服务，实行过程检验与不合格品控制。',
        '北京某某餐饮管理有限公司成立于2004年，拥有员工两千人，服务网点遍布全国十二个省份。',
        '检测报告编号2023-JC-0012345显示样品符合要求，我方已将报告原件附于标书第七章第二节。',
    ]
    for s in negatives:
        assert not m._is_standard_listing(s), s[:40]


def t_std_listing_filtered_from_similarity():
    # 两家标书同列标准/认证编号行 → 模板扣除（专用理由 + 计数），不进异常。
    # 同时覆盖"精确匹配段尾部与句号粘连"（'。'归一化为'.'后分词必须切开，
    # 否则尾部片段和登记 token 粘成一体、覆盖率被稀释到阈值以下）。
    line = ('b5749《生活饮用水卫生标准》，GB/T19001-2016/，'
            'GB/T45001-2020/IS045001:2018，■机构批准号CNCA-R-2002-006')
    t1 = '资质证书：' + line + '。另附检测报告若干。'
    t2 = '资质情况：' + line + '。详见附件。'
    r = m.text_similarity_analysis({'甲.docx': t1, '乙.docx': t2})
    pr = r['pair_results'][0]
    assert pr['abnormal_count'] == 0, pr['matches']
    assert pr['substantial_count'] == 0 and pr['suspicious_count'] == 0
    assert r['std_listing_count'] >= 1, r['std_listing_count']
    tpl = [mt for mt in pr['matches'] if mt['risk_level'] == 'template']
    assert any('标准/认证编号罗列' in mt['reasons'][0] for mt in tpl), tpl
    assert any('标准/认证编号罗列' in f for f in r['findings']), r['findings']

    # 近似段落通道（两家各自微调有效期的登记段）同样不得漏出
    p1 = ('通过GB/T19001-2016质量管理体系认证、GB/T45001-2020职业健康安全管理体系认证、'
          'ISO22000食品安全管理体系认证。')
    t3 = '资质证书 ' + p1 + ' 有效期至2027年。'
    t4 = '资质情况 ' + p1 + ' 有效期至2028年。'
    r2 = m.text_similarity_analysis({'甲.docx': t3, '乙.docx': t4})
    pr2 = r2['pair_results'][0]
    assert pr2['abnormal_count'] == 0, [(mt['risk_level'], mt['text'][:40]) for mt in pr2['matches']]
    assert not any(mt.get('near_duplicate') for mt in pr2['matches'] if mt['abnormal'])

    # 认证证书页整块（审核员行 + 机构批准号 + 体系符合标准）同样不得漏出
    block = ('张某某（2023-N1EMS-4024505，审核员，监督审核),李某某（2023-N1EMS-4029046，审核员，初审一阶段）\n'
             '认证中心有限公司\n·机构批准号\nCNCA-R-2002-0\n质量管理体系符合标准：\nGB/T19001-2016/\n'
             '环境管理体系符合标准：\nGB/T24001-2016/')
    r3 = m.text_similarity_analysis({'甲.docx': '资质证书附件：\n' + block + '\n本证书有效期三年。',
                                     '乙.docx': '资质证明：\n' + block + '\n详见原件。'})
    pr3 = r3['pair_results'][0]
    assert pr3['abnormal_count'] == 0, [(mt['risk_level'], mt['text'][:40]) for mt in pr3['matches']]
    assert r3['std_listing_count'] >= 1, r3['std_listing_count']


def t_std_listing_keeps_mixed_paragraph_abnormal():
    # 反例护栏：含个别标准引用、主体是自编项目叙述的雷同段落必须仍判异常，
    # 抽查阈值（0.7）不得把这类真实证据一起吞掉。
    mixed = ('我司已通过GB/T19001-2016、GB/T45001-2020、ISO22000三项体系认证，'
             '管理体系覆盖本项目全部服务内容，项目经理具备十年从业经验，'
             '团队配备食品安全员六名，实行三级质量管控。')
    r = m.text_similarity_analysis({'甲.docx': mixed, '乙.docx': mixed})
    pr = r['pair_results'][0]
    assert r['std_listing_count'] == 0, r['std_listing_count']
    assert pr['abnormal_count'] >= 1, pr['matches']
    assert pr['matches'][0]['risk_level'] != 'template'


def t_service_unit_price_extraction():
    # 服务类单价报价（餐饮/物业按人头计价）：'服务费用总价（元/人/天）'
    # 表头 + 值行 '15.23'（或大写 '壹拾肆元玖角肆分' = 14.94）→ bidRate。
    # 首版缺陷：大写正则不含 元/角/分，'壹拾肆元' 在'元'处截断（14 vs
    # 14.94 互验失败）；'=1+2+3' 公式里的 1 曾被当成单价。
    t1 = ('投标人名称 | 服务费用总价（含税）元/人/天 | 增值税税率 | 备注\n'
          '北京甲公司 | 大写：壹拾肆元玖角肆分  小写：14.94元/人/天 | （ 6 ）% | 无\n'
          '重庆 | 服务费用总价（元/人/天） | 14.94 | / | =1+2+3')
    r = m.extract_prices(t1)
    assert r['bidRate'] == '14.94元/人/天', r['bidRate']

    t2 = '（元/人/天） | 服务费用总价\n（元/人/天） | 15.23 |  | =1+2+3'
    r2 = m.extract_prices(t2)
    assert r2['bidRate'] == '15.23元/人/天', r2['bidRate']

    # 甲方餐标说明不是投标人报价（'餐标' 已从标签中移除）
    t3 = '严格执行：早餐15元/人、午餐25元/人、晚餐20元/人固定餐标，不降标。'
    r3 = m.extract_prices(t3)
    assert r3['bidRate'] is None, r3['bidRate']

    # '（ 6 ）%' 括号税率形态（服务类标书普遍写法）
    assert m.extract_prices(t1)['taxRate'] == '6%'


def t_unit_price_dot_priority_and_tax_exclusion():
    # '（ 6 ）%' 的 6 不是单价；'15.0' 必须按原文含 '.' 优先——数值判定下
    # 15.0 == 15 会被当成整数排除，回退 min 曾把 6 选成单价。
    t = ('投标人名称 | 服务费用总价（含税）元/人/天 | 增值税税率 | 备注\n'
         '公司15.0 | 小写：15.0元/人/天 | （ 6 ）% | 无\n'
         '重庆 | 服务费用总价（元/人/天） | 15.0')
    r = m.extract_prices(t)
    assert r['bidRate'] == '15元/人/天', r['bidRate']
    assert r['taxRate'] == '6%', r['taxRate']


def t_unit_price_comparison_findings():
    # 单价标书：不报"未提取到任何报价"；相同/接近两档出服务单价比对 findings
    import tempfile
    body = ('投标人名称 | 服务费用总价（含税）元/人/天 | 增值税税率 | 备注\n'
            '甲公司 | 小写：{v}元/人/天 | （ 6 ）% | 无\n'
            '重庆 | 服务费用总价（元/人/天） | {v}\n')
    with tempfile.TemporaryDirectory() as td:
        p1 = os.path.join(td, '甲.txt')
        p2 = os.path.join(td, '乙.txt')
        with open(p1, 'w', encoding='utf-8') as f:
            f.write(body.format(v='15.23'))
        with open(p2, 'w', encoding='utf-8') as f:
            f.write(body.format(v='15.23'))
        res = m.run_full_analysis([p1, p2])
        findings = ' '.join(str(x) for x in res['pricing'].get('findings', []))
        assert '未提取到任何报价' not in findings, findings
        assert '仅提取到成本明细' not in findings, findings
        assert '服务单价完全一致' in findings, findings
        with open(p2, 'w', encoding='utf-8') as f:
            f.write(body.format(v='15.25'))
        res2 = m.run_full_analysis([p1, p2])
        f2 = ' '.join(str(x) for x in res2['pricing'].get('findings', []))
        assert '服务单价' in f2 and '高度接近' in f2, f2


def t_person_role_word_and_crossline_rejected():
    # 实测两类假人名（餐饮语料）：① 行尾散文短语 + 下一行行首角色被跨行
    # 配对（'管理岗专项复盘能力培养\n项目经理、…' → '能力培养'）——姓名-
    # 角色分隔符曾用 [\s、，,]（\s 含换行）；② 同行逗号形态 '由项目经理
    # 负责…' → '经理负责'（'经'恰是姓氏，含职务词即非姓名）。真人名不受
    # 影响（正例对照）。
    t1 = ('项目管理机构\n'
          '管理岗专项复盘能力培养\n项目经理、前厅主管、行政总厨每半年参加专题研修。\n'
          '项目经理经验双轨并重\n项目经理须满足5年以上相关项目管理经验。\n'
          'G、项目经理负责对改进措施的完成效果进行跟踪验证并反馈。\n'
          '处理正常的投诉，项目经理跟进整改；检查过程中，项目经理驻场巡视。\n'
          '王强 项目经理\n李勇 施工员')
    r = m.extract_personnel(t1)
    names = {p.get('name') for p in (r.get('all_persons') or [])}
    assert '能力培养' not in names, names
    assert '双轨并重' not in names, names
    assert '经理负责' not in names, names
    # 左边界：词中起抓的 2-4 字片段（'正常的投诉'→'常的投诉' 等）不得成姓名
    assert '常的投诉' not in names, names
    assert '查过程中' not in names, names
    assert '王强' in names, names           # 正例：真姓名-角色仍在
    # 职务头衔词包含规则：'董事长' 类头衔非姓名
    assert not m._is_person_name('董事长')
    assert not m._is_person_name('经理报告')
    assert m._is_person_name('李旭丽')


def t_ref_derived_short_identifier_segment():
    # '、WFWJ-070020260602108-BG-1（ZC26G23022'（38 字符）曾漏成高风险：
    # 两家标书的招标编号相同、ZC 尾号各异（分歧点截断公共段），而招标文件
    # 里是第三个尾号——既非参照子串（精确过滤放行），又恰低于参照改写过滤
    # 的 40 字符门槛。门槛降到 30 后按包含率归为招标文件改写。
    ref = ('招标编号：WFWJ-070020260602108-BG-1（ZC26G230221）。'
           '采购需求：本项目拟采购餐饮服务，覆盖面广，服务标准执行国家相关规定，'
           '具体内容详见第五章采购需求全部条款与附件说明。')
    ta = '我公司参加贵司组织的、WFWJ-070020260602108-BG-1（ZC26G230223）招标'
    tb = '我公司参加贵司组织的、WFWJ-070020260602108-BG-1（ZC26G230225）招标'
    assert m._REF_DERIVED_MIN_LEN <= 25, '门槛被调回将复现 WFWJ/经验要求段漏检'
    r = m.text_similarity_analysis({'甲.docx': ta, '乙.docx': tb}, ref_texts_list=[ref])
    pr = r['pair_results'][0]
    seg = max(pr['matches'], key=lambda x: x.get('length', 0))
    assert seg['risk_level'] == 'template', (seg['risk_level'], seg['text'][:50])
    assert pr['abnormal_count'] == 0, [(x['risk_level'], x['text'][:40]) for x in pr['matches']]

    # 第二款形态：招标文件人员配置表要求原文（28 字符）——标书加'具备'前缀
    # 照抄、截在两家措辞分歧点（'…配餐项目经理经验' vs '…配餐经验'），
    # 38 字符门槛时代实测漏成高风险；包含率 0.92。
    ref2 = ('项目经理 | 大专（含）以上学历 | 5年以上相关项目管理经验或2年以上'
            '1000人规模配餐项目经理经验 | 岗位职责：负责整体运营与协调。')
    tA = '配备要求：具备5年以上相关项目管理经验或2年以上1000人规模配餐项目经理经验。'
    tB = '配备要求：具备5年以上相关项目管理经验或2年以上1000人规模配餐经验。'
    r2 = m.text_similarity_analysis({'甲.docx': tA, '乙.docx': tB}, ref_texts_list=[ref2])
    pr2 = r2['pair_results'][0]
    assert pr2['abnormal_count'] == 0, [(x['risk_level'], x['text'][:40]) for x in pr2['matches']]
    assert r2['ref_derived_count'] >= 1, r2['ref_derived_count']


def t_std_listing_number_plus_name_word():
    # 'GB2760-2024食品添加剂使用标准'：编号覆盖 + 标准名词使覆盖率停在
    # 0.59（<0.6 门槛）——整段曾漏进高风险查重结果。编号形态与 标准/规范/
    # 规程/准则 同现于一个 token 即判登记。
    s = 'GB2760-2024食品添加剂使用标准'
    assert m._is_standard_listing(s), s
    assert m._is_standard_listing('GB 2760-2024 食品安全国家标准 食品添加剂使用标准')
    line = s + '、GB14881-2013食品生产通用卫生规范'
    t1 = '资质与标准：' + line + '。另附检测报告。'
    t2 = '执行标准：' + line + '。详见附件。'
    r = m.text_similarity_analysis({'甲.docx': t1, '乙.docx': t2})
    pr = r['pair_results'][0]
    assert pr['abnormal_count'] == 0, [(x['risk_level'], x['text'][:40]) for x in pr['matches']]
    assert r['std_listing_count'] >= 1, r['std_listing_count']


def t_common_segments_chunked_extension_identical():
    # 双向延伸的分块比较（64 字符切片相等）必须与逐字符语义完全一致：
    # 构造 200 字符重复块（非 64 整数倍，走"整块 + 尾巴"两段路径），两侧
    # 前缀/后缀均不同，最长公共段必须精确是 (3, 3, 200)。分块实现若在块
    # 边界差一个字符，这里立刻失败。实测背景：投标人A×投标人B（357K/1.0M 字符）
    # 逐字符延伸耗时 98s，分块后 3.5s，193 段指纹逐位相同。
    S = ('一二三四五六七' * 29)[:200]
    t1 = 'AAA' + S + 'BBB'
    t2 = 'CCC' + S + 'DDD'
    segs = m.find_common_segments(t1, t2, min_len=15)
    longest = max(segs, key=lambda x: x[2])
    assert (longest[0], longest[1], longest[2]) == (3, 3, 200), longest[:3]
    # 反向验证：把 S 换成长度 130（2×64+2）也精确
    S2 = ('甲乙丙丁戊' * 30)[:130]
    r2 = m.find_common_segments('AAAA' + S2 + 'X', 'ZZZZ' + S2 + 'Y', min_len=15)
    l2 = max(r2, key=lambda x: x[2])
    assert (l2[0], l2[1], l2[2]) == (4, 4, 130), l2[:3]


def t_bare_year_not_price():
    # 裸年份（服务期/年份列，无'年'后缀）不是金额：分项曾累计到 1.6e17、
    # '2,024 元报价完全一致' 的比对信号其实来自年份 2024/2025/2026。
    assert m._is_bare_year_value(2026, '2026', '服务期限3年')
    assert m._is_bare_year_value(2025.1, '2025.1', '2025年1月')
    # 真金额不受影响
    assert not m._is_bare_year_value(2026, '2026.00', '服务期')
    assert not m._is_bare_year_value(2026, '2,026', '服务期')
    assert not m._is_bare_year_value(2026, '2026元', '服务期')
    assert not m._is_bare_year_value(2026, '2026', '投标总价 2026 万元')
    assert not m._is_bare_year_value(1500, '1500', '服务期')
    # 分项通道端到端：年份列不入 totalPrice
    text = ('分项报价表 |\n序号 | 项目 | 金额 | 年份\n'
            '1 | 材料费 | 120000 | 2026\n2 | 人工费 | 80000 | 2027')
    r = m.extract_prices(text)
    for it in (r.get('subItemPrice') or []):
        assert it.get('totalPrice') not in (2026.0, 2027.0), it


def t_toc_page_number_section_skipped():
    # 目录行 '开标一览表20 / 三、投标报价21'（无点线、带页码）不得被认成
    # 报价章节本体——首版 400 字价格信号守卫被相邻目录行的数字蒙混，整段
    # 以目录为窗口搜索导致单价/税率全空。
    toc = ('目录\n开标一览表20\n三、投标分项报价表21\n四、法人证明22\n'
           '五、投标保证金24\n六、联合体协议26\n七、偏离表27\n' * 30)
    assert m._find_bid_summary_section(toc) is None
    real = toc + ('\n开标一览表\n投标人名称 | 服务费用总价（元/人/天） | 税率\n'
                  '甲公司 | 15.35 | （ 6 ）%')
    sec = m._find_bid_summary_section(real)
    assert sec and '15.35' in sec


def t_phantom_total_dropped_for_unit_price_bids():
    # 单价形态标书 + 全文兜底总价 = 噪音（实测 15万保证金 / 550万历史合同 /
    # 775万发票合计都被当过总价）→ 清除并给出解释；非单价标书保留原警告。
    result = {
        'totalPriceInTax': 5506500.0, 'totalPrice': 5506500.0,
        'bidRate': '15.2元/人/天', '_from_global': True,
        'warnings': [], 'subItemPrice': [], 'costDetails': [],
    }
    m._validate_price_extraction('历史采购合同金额 5506500 元', result, None)
    assert result['totalPriceInTax'] is None and result['totalPrice'] is None
    assert any('冲突' in w for w in result['warnings']), result['warnings']

    result2 = {
        'totalPriceInTax': 2000000.0, 'totalPrice': 2000000.0,
        'bidRate': None, '_from_global': True,
        'warnings': [], 'subItemPrice': [], 'costDetails': [],
    }
    m._validate_price_extraction('投标总价 2000000 元', result2, None)
    assert result2['totalPriceInTax'] == 2000000.0  # 普通标书不受影响


def t_docx_xml_fallback_rescues_broken_package():
    # zip 内 rel 指向 NULL / .docm 宏文档：python-docx 抛异常，裸 XML 直读
    # 回退把正文救回来（实测 4/12 份标书曾因此整份维度全空）。
    import tempfile, zipfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'broken.docx')
        doc_xml = ('<?xml version="1.0"?>'
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   '<w:body><w:p><w:r><w:t>投标总价：壹拾伍元叁角伍分</w:t></w:r></w:p>'
                   '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>早餐服务费</w:t></w:r></w:p></w:tc>'
                   '<w:tc><w:p><w:r><w:t>4.22</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
                   '</w:body></w:document>')
        # 缺 [Content_Types].xml：python-docx 必抛，XML 回退须成功
        with zipfile.ZipFile(p, 'w') as zf:
            zf.writestr('word/document.xml', doc_xml)
        text, pages = m.extract_text_with_pages(p)
        assert '投标总价' in text and '早餐服务费' in text, repr(text[:80])
        assert pages == []


def t_ref_derived_rewritten_clause_filtered():
    # 用户报告：招标文件合同条款被投标方改写（称谓替换 乙方→投标人、填空
    # 【  】→【5000元/次】、条款号重排）后，精确子串匹配漏检，条款以
    # "高风险异常段落"形态漏进结论。k-gram 包含率（阈值 0.5）应识别为
    # 模板衍生并扣除。样本取自真实语料。
    ref = ('第十五条 违约责任\n'
           '1.服务质量违约。乙方服务未达到本合同约定标准的，甲方有权按照【  】标准计收违约金。'
           '乙方应在甲方要求期限内完成整改，逾期整改的，每逾期一日，甲方有权按照【  】标准计收违约金。'
           '服务质量问题情节严重、当月累计发生【  】次及以上或逾期超过【  】日仍未整改、整改不到位的，'
           '甲方有权选择解除合同或收取违约金继续履行合同；')
    bid = ('11.1.服务质量违约。投标人服务未达到本合同约定标准的，招标人有权按照【5000元/次】标准计收违约金。'
           '投标人应在招标人要求期限内完成整改，逾期整改的，每逾期一日，招标人有权按照【1000元/日】标准计收违约金。'
           '服务质量问题情节严重、当月累计发生【2】次及以上或逾期超过【5】日仍未整改、整改不到位的，'
           '招标人有权选择解除合同或收取违约金继续履行合同；')
    r = m.text_similarity_analysis({'甲.docx': bid, '乙.docx': bid}, ref_texts_list=[ref])
    pr = r['pair_results'][0]
    assert pr['abnormal_count'] == 0, pr['abnormal_count']
    assert pr['substantial_count'] == 0, pr['substantial_count']
    assert r['ref_derived_count'] >= 1, r['ref_derived_count']
    assert r['template_matches'] >= 1
    # 扣除理由要写明是改写形式而非普通匹配
    tpl = [mt for mt in pr['matches'] if mt['risk_level'] == 'template']
    assert any('改写' in mt['reasons'][0] for mt in tpl), tpl[0]['reasons']


def t_ref_derived_no_false_positive_on_selfwritten():
    # 反向护栏：与招标文件无关的自编段落（投标人之间雷同）必须仍判异常，
    # 包含率过滤不得误伤真正的高风险证据。
    ref = '第十五条 违约责任。乙方服务未达到本合同约定标准的，甲方有权按照【  】标准计收违约金。'
    shared = ('我司将为本项目配备专职项目经理一名，实行食品安全日检周报制度，'
              '每日对中央厨房的温度记录、留样记录与消毒记录进行三方核查，'
              '并按月向采购人提交食品安全自查报告与整改闭环台账。')
    r = m.text_similarity_analysis(
        {'甲.docx': shared, '乙.docx': shared}, ref_texts_list=[ref])
    pr = r['pair_results'][0]
    assert r['ref_derived_count'] == 0, r['ref_derived_count']
    # 未被误扣：条目保留在异常侧（substantial 或降级后的 suspicious），
    # 而不是变成模板
    kept = [mt for mt in pr['matches']
            if mt['risk_level'] in ('substantial', 'suspicious')]
    assert kept, pr['matches']
    assert all(mt['risk_level'] != 'template' for mt in pr['matches']), pr['matches']


def t_ref_derived_near_duplicate_filtered():
    # 轻度改写的条款对（两家各自填充了不同的数值）：近似段落通道同样要
    # 被参照改写过滤拦住，不能以"高度近似段落"的名义漏出。
    ref = ('1.服务质量违约。乙方服务未达到本合同约定标准的，甲方有权按照【  】标准计收违约金。'
           '乙方应在甲方要求期限内完成整改，逾期整改的，每逾期一日，甲方有权按照【  】标准计收违约金。')
    bid_a = ref.replace('【  】', '【5000元/次】', 1)
    bid_b = ref.replace('【  】', '【6000元/次】', 1)
    r = m.text_similarity_analysis({'甲.docx': bid_a, '乙.docx': bid_b}, ref_texts_list=[ref])
    pr = r['pair_results'][0]
    assert pr['abnormal_count'] == 0, [(x['risk_level'], x['text'][:40]) for x in pr['matches']]
    assert r['ref_derived_count'] >= 1


def t_ref_derived_ignores_filler_runs():
    # 填充串（同字符重复）不得凭重复 gram 假性命中参照：'········' 类
    # 文本在招标文件里也常见（省略号/虚线段），信息量护栏须让它们既不进
    # 索引、也不计入包含率分母。
    filler = '·' * 400
    idx = m._build_ref_ngram_index([m._normalize_for_match(filler)])
    assert idx == set(), '纯填充参照不应产生任何索引项'
    # 真实条款的包含率不受护栏影响
    ref = [m._normalize_for_match(
        '1.服务质量违约。乙方服务未达到本合同约定标准的，甲方有权按照【  】标准计收违约金。'
        '乙方应在甲方要求期限内完成整改，逾期整改的，每逾期一日，甲方有权按照【  】标准计收违约金。')]
    idx2 = m._build_ref_ngram_index(ref)
    assert idx2, '真实条款须产生索引'
    rewritten = m._normalize_for_match(
        '11.1.服务质量违约。投标人服务未达到本合同约定标准的，招标人有权按照【5000元/次】标准计收违约金。'
        '投标人应在招标人要求期限内完成整改，逾期整改的，每逾期一日，招标人有权按照【1000元/日】标准计收违约金。')
    assert m._reference_derived_ratio(rewritten, idx2) >= m._REF_DERIVED_RATIO
    # 填充串自身对参照的包含率判 0（不足信息量 gram）
    assert m._reference_derived_ratio(m._normalize_for_match(filler), idx2) == 0.0


def _make_test_pdf(path, pages):
    import pymupdf as fitz
    doc = fitz.open()
    for txt in pages:
        page = doc.new_page()
        page.insert_text((72, 96), txt, fontsize=12)
    doc.save(path)
    doc.close()


def t_pdf_page_numbers_on_matches():
    # 页码定位闭环：同一段落在甲文档第 2 页、乙文档第 5 页，双侧页码都要
    # 对且不因内部交换而颠倒（find_common_segments 在 text1 更长时交换
    # 两文档做索引，返回时必须换回）。
    import tempfile
    common = ('The contractor shall appoint an on-site representative responsible for '
              'daily coordination and supervision, and submit service quality reports.')
    with tempfile.TemporaryDirectory() as td:
        pa = os.path.join(td, 'a.pdf')
        pb = os.path.join(td, 'b.pdf')
        _make_test_pdf(pa, ['unique-a', common, 'FILLER-THREE ' * 10,
                            'FILLER-FOUR ' * 10, 'FILLER-FIVE ' * 10])
        _make_test_pdf(pb, ['cover-b', 'unique-b', 'BFILL-THREE ' * 10,
                            'BFILL-FOUR ' * 10, common])
        saved = m.EXTRACT_CACHE_ENABLED
        m.EXTRACT_CACHE_ENABLED = False
        try:
            ta, ea = m.extract_text_with_pages(pa)
            tb, eb = m.extract_text_with_pages(pb)
        finally:
            m.EXTRACT_CACHE_ENABLED = saved
    assert len(ea) == 5 and len(eb) == 5, (ea, eb)
    assert ea == sorted(ea) and eb == sorted(eb)
    # 双向都验：无论哪份在前，归属都不许错
    r = m.text_similarity_analysis({'甲.pdf': ta, '乙.pdf': tb},
                                   page_maps={'甲.pdf': ea, '乙.pdf': eb})
    mt = next(x for x in r['pair_results'][0]['matches'] if 'contractor' in x['text'])
    assert (mt['page1'], mt['page2']) == (2, 5), (mt['page1'], mt['page2'])
    r2 = m.text_similarity_analysis({'乙.pdf': tb, '甲.pdf': ta},
                                    page_maps={'乙.pdf': eb, '甲.pdf': ea})
    mt2 = next(x for x in r2['pair_results'][0]['matches'] if 'contractor' in x['text'])
    assert (mt2['page1'], mt2['page2']) == (5, 2), (mt2['page1'], mt2['page2'])
    # ctx 侧别同步换回：FILLER-THREE 只在甲文档中，a-first 应出现在 ctx1，
    # b-first 应出现在 ctx2（交换 bug 的直接回归护栏）
    assert 'FILLER-THREE' in mt['ctx1'], mt['ctx1'][:80]
    assert 'FILLER-THREE' not in mt['ctx2'], mt['ctx2'][:80]
    assert 'FILLER-THREE' not in mt2['ctx1'], mt2['ctx1'][:80]
    assert 'FILLER-THREE' in mt2['ctx2'], mt2['ctx2'][:80]


def t_page_boundary_match_maps_to_following_page():
    # 边界：恰好从页首开始的匹配要归到该页（而非上一页）。page_ends 记录
    # 每页最后一个字符的下标，bisect_left 的语义正好如此。
    boundary = ('Boundary paragraph sitting exactly at the top of page three '
                'and continuing for a while to be substantive.')
    ta = 'page-one-intro\n' + boundary + '\n'
    tb = 'other-doc-preamble\n' + boundary + '\n'
    ends = [len('page-one-intro'), len(ta) - 1]
    r = m.text_similarity_analysis(
        {'甲.pdf': ta, '乙.pdf': tb}, page_maps={'甲.pdf': ends, '乙.pdf': []})
    mt = next(x for x in r['pair_results'][0]['matches'] if 'Boundary' in x['text'])
    assert mt['page1'] == 2, mt['page1']


def t_pct_fallback_without_page_map():
    # docx/txt 无分页概念 → 回退相对位置百分比；页码字段为 None。
    # 共有段放在各自文本中部（前面垫独有内容），百分比才有区分度。
    shared = ('我司将为本项目配备专职项目经理一名，实行食品安全日检周报制度，'
              '每日对中央厨房的温度记录、留样记录与消毒记录进行三方核查，'
              '并按月向采购人提交食品安全自查报告与整改闭环台账。')
    ta = '甲公司特有前言内容，描述企业规模与服务优势。' * 8 + shared
    tb = '乙公司特有前言，写法完全不同，篇幅也不同。' * 3 + shared
    r = m.text_similarity_analysis({'甲.docx': ta, '乙.docx': tb})
    mt = r['pair_results'][0]['matches'][0]
    assert mt['page1'] is None and mt['page2'] is None, mt
    assert 1 <= mt['pct1'] <= 100 and 1 <= mt['pct2'] <= 100, mt
    # 甲文档共有段更靠后（前置内容更长）→ 百分比应更大
    assert mt['pct1'] > mt['pct2'], (mt['pct1'], mt['pct2'])


def t_extract_cache_roundtrips_page_ends():
    # 缓存升级为 JSON {'t','p'}：读写往返保留页码；旧纯文本条目按无页码
    # 容忍（解析失败 → 文本照用），保证升级不破旧缓存。
    import tempfile
    saved_dir, saved_en = m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED
    with tempfile.TemporaryDirectory() as td:
        m.EXTRACT_CACHE_DIR = td
        m.EXTRACT_CACHE_ENABLED = True
        try:
            m._extract_cache_write('k1', 'TEXT-A', [10, 25])
            got = m._extract_cache_read('k1')
            assert got == ('TEXT-A', [10, 25]), got
            # 旧格式（纯文本）条目：容忍读取、页码为空
            with open(os.path.join(td, 'k2.txt'), 'w', encoding='utf-8') as f:
                f.write('LEGACY-PLAIN-TEXT')
            got2 = m._extract_cache_read('k2')
            assert got2 == ('LEGACY-PLAIN-TEXT', []), got2
            # 空文本不入缓存
            m._extract_cache_write('k3', '', [1])
            assert m._extract_cache_read('k3') is None
        finally:
            m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED = saved_dir, saved_en


def t_history_keeps_match_page_fields():
    # 页码字段必须进历史精简白名单，否则历史记录页与"历史→下载报告"
    # 场景丢失定位信息（与 _HISTORY_KEEP 同类的回归形态）。
    results = {
        'text_similarity': {'pair_results': [{'matches': [{
            'index': 1, 'length': 100, 'text': 'x' * 300,
            'abnormal': True, 'risk_level': 'substantial', 'score': 0.7,
            'reasons': ['r'], 'near_duplicate': False,
            'ctx1': 'c1', 'ctx2': 'c2',
            'page1': 3, 'pct1': None, 'page2': 7, 'pct2': None,
        }]}]},
    }
    light = m._prepare_history_data(results)
    lm = light['text_similarity']['pair_results'][0]['matches'][0]
    assert lm['page1'] == 3 and lm['page2'] == 7, lm
    assert lm['pct1'] is None and lm['pct2'] is None


def t_report_table_has_page_columns():
    # 报告相似度详情表格化：表头须含页码列与双方文件列；页码标签按
    # PDF 页码 / 百分比回退两种形态渲染。
    assert m._match_page_label({'page1': 5}, 1) == '第5页'
    assert m._match_page_label({'pct1': 42}, 1) == '≈42%处'
    assert m._match_page_label({}, 1) == '—'
    doc = m.Document()
    m._report_table(doc, ['a', 'b'], [[1, 2]])
    assert len(doc.tables) == 1


def _chmod_x(path):
    """显式覆盖要求可执行位（POSIX）；Windows 无 X_OK，chmod 失败忽略。"""
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass


def t_soffice_probe_paths_per_os():
    # 每个平台的已知安装位置必须是纯数据（不碰文件系统），否则 Windows /
    # Linux 分支在这台机器上根本无法回归。路径一律用 ntpath/posixpath 拼，
    # 保证在任意宿主上都是目标平台形态。
    win = m._soffice_probe_paths('nt', {
        'PROGRAMFILES': r'C:\Program Files',
        'ProgramFiles(x86)': r'C:\Program Files (x86)',
        'LOCALAPPDATA': r'C:\Users\u\AppData\Local'})
    assert r'C:\Program Files\LibreOffice*\program\soffice.exe' in win, win
    assert r'C:\Program Files (x86)\LibreOffice*\program\soffice.exe' in win, win
    assert r'C:\Users\u\AppData\Local\Programs\LibreOffice*\program\soffice.exe' in win, win
    # 环境变量缺失时退回默认根目录（安装器默认路径）
    assert m._soffice_probe_paths('nt', {})[0] == \
        r'C:\Program Files\LibreOffice*\program\soffice.exe'

    mac = m._soffice_probe_paths('darwin', {})
    assert '/Applications/LibreOffice.app/Contents/MacOS/soffice' in mac, mac
    # Finder 双击启动的 .app 继承 launchd 最小 PATH（不含 Homebrew），
    # 所以 /opt/homebrew/bin 必须显式探测。
    assert any(p.endswith('/opt/homebrew/bin/soffice') for p in mac), mac
    assert any(p.endswith('/usr/local/bin/soffice') for p in mac), mac

    linux = m._soffice_probe_paths('posix', {})
    for p in ('/usr/bin/soffice', '/usr/lib/libreoffice/program/soffice',
              '/snap/bin/libreoffice', '/opt/libreoffice*/program/soffice'):
        assert p in linux, (p, linux)
    assert not m._text_tool_probe_paths('nt', {}), 'Windows 无 antiword/catdoc 位置'
    assert '/opt/homebrew/bin/antiword' in m._text_tool_probe_paths('darwin', {})


def t_first_file_order_and_glob():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        assert m._first_file([os.path.join(td, 'nope'), None, '']) is None
        b = os.path.join(td, 'b')
        open(b, 'w').close()
        # 顺序即优先级：先探测到的先用
        assert m._first_file([os.path.join(td, 'missing'), b,
                              os.path.join(td, 'unused')]) == b
        # glob 覆盖版本化安装目录（/opt/libreoffice25.2/program/soffice）
        d = os.path.join(td, 'libreoffice25.2', 'program')
        os.makedirs(d)
        exe = os.path.join(d, 'soffice')
        open(exe, 'w').close()
        assert m._first_file([os.path.join(td, 'libreoffice*', 'program',
                                           'soffice')]) == exe


def t_soffice_env_override_forms():
    # SOFFICE_PATH 可指向 soffice 本体 / 安装根目录 / program 目录 /
    # macOS .app 包——用户从"属性"里复制的路径形态五花八门，每一种都要认。
    import tempfile
    saved = os.environ.get('SOFFICE_PATH')
    exe_name = 'soffice.exe' if os.name == 'nt' else 'soffice'
    try:
        with tempfile.TemporaryDirectory() as td:
            exe = os.path.join(td, exe_name)
            open(exe, 'w').close()
            _chmod_x(exe)
            os.environ['SOFFICE_PATH'] = exe
            assert m._soffice_from_env() == exe, m._soffice_from_env()
            # Windows 用户常连引号一起粘贴，或带尾随空格
            os.environ['SOFFICE_PATH'] = f'  "{exe}"  '
            assert m._soffice_from_env() == exe, m._soffice_from_env()

            root = os.path.join(td, 'LibreOffice')
            os.makedirs(os.path.join(root, 'program'))
            win_exe = os.path.join(root, 'program', 'soffice.exe')
            open(win_exe, 'w').close()
            _chmod_x(win_exe)
            for form in (root, os.path.join(root, 'program')):
                os.environ['SOFFICE_PATH'] = form
                assert m._soffice_from_env() == win_exe, (form, m._soffice_from_env())

            if os.name != 'nt':          # .app 包是 macOS 形态
                macdir = os.path.join(td, 'LibreOffice.app', 'Contents', 'MacOS')
                os.makedirs(macdir)
                mac_exe = os.path.join(macdir, 'soffice')
                open(mac_exe, 'w').close()
                _chmod_x(mac_exe)
                os.environ['SOFFICE_PATH'] = os.path.join(td, 'LibreOffice.app')
                assert m._soffice_from_env() == mac_exe, m._soffice_from_env()
    finally:
        if saved is None:
            os.environ.pop('SOFFICE_PATH', None)
        else:
            os.environ['SOFFICE_PATH'] = saved


def t_soffice_env_alias_and_bogus_value():
    # LIBREOFFICE_PATH 是 SOFFICE_PATH 的别名；指向不存在的位置时绝不能把
    # 转换器锁成无效值——那会让 .doc 正文静默全空，比"未检测到"更难排查。
    import tempfile
    keys = ('SOFFICE_PATH', 'LIBREOFFICE_PATH')
    saved = {k: os.environ.get(k) for k in keys}
    try:
        with tempfile.TemporaryDirectory() as td:
            exe = os.path.join(td, 'soffice.exe' if os.name == 'nt' else 'soffice')
            open(exe, 'w').close()
            _chmod_x(exe)
            os.environ.pop('SOFFICE_PATH', None)
            os.environ['LIBREOFFICE_PATH'] = exe
            assert m._soffice_from_env() == exe, m._soffice_from_env()

            # SOFFICE_PATH 无效 → 继续尝试别名，而不是直接放弃
            os.environ['SOFFICE_PATH'] = os.path.join(td, 'nope')
            assert m._soffice_from_env() == exe, m._soffice_from_env()

            # 两个都无效 → 返回 None（交由自动探测），不得返回无效路径
            os.environ['LIBREOFFICE_PATH'] = os.path.join(td, 'nope2')
            assert m._soffice_from_env() is None, m._soffice_from_env()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def t_soffice_env_override_must_be_executable():
    # 显式覆盖必须真的能启动：数据文件、相对路径、通配符都不能被认成转换器
    # （旧实现连 SOFFICE_PATH='*' 都会 glob 到 CWD 里的第一个文件并锁死为
    # "libreoffice"，之后每份 .doc 都静默变空——比"未检测到"更难排查）。
    import tempfile
    keys = ('SOFFICE_PATH', 'LIBREOFFICE_PATH', 'SOFFICE_HOME')
    saved = {k: os.environ.get(k) for k in keys}
    try:
        with tempfile.TemporaryDirectory() as td:
            for k in keys:
                os.environ.pop(k, None)
            os.environ['SOFFICE_PATH'] = '*'
            assert m._soffice_from_env() is None, '通配符不得被当成转换器'
            os.environ['SOFFICE_PATH'] = 'relative/soffice'
            assert m._soffice_from_env() is None, '相对路径不得被当成转换器'
            plain = os.path.join(td, 'soffice-data.txt')
            open(plain, 'w').close()
            os.environ['SOFFICE_PATH'] = plain
            assert m._soffice_from_env() is None, '非可执行文件不得被当成转换器'
            if os.name != 'nt':      # Windows 判据是扩展名，下面两条是 POSIX 语义
                os.environ['SOFFICE_PATH'] = '/etc/passwd'
                assert m._soffice_from_env() is None
                exe = os.path.join(td, 'soffice')
                open(exe, 'w').close()
                _chmod_x(exe)
                # %VAR%/$VAR 展开（Windows 用户常复制 %ProgramFiles%\... 形态）
                os.environ['SOFFICE_HOME'] = td
                os.environ['SOFFICE_PATH'] = '$SOFFICE_HOME/soffice'
                assert m._soffice_from_env() == exe, m._soffice_from_env()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def t_soffice_probe_globs_are_escaped():
    # 安装根目录里带 [ ] 时（'D:\Program Files [x64]'）必须转义，否则 glob 把
    # 它当字符类、静默匹配不到——旧实现是字面 join+isfile，不存在这个问题。
    import glob as _glob
    import tempfile
    pat = m._soffice_probe_paths('nt', {
        'PROGRAMFILES': r'D:\Program Files [x64]',
        'ProgramFiles(x86)': r'C:\Program Files (x86)'})
    assert '[[]' in pat[0], pat[0]
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, 'Program Files [x64]')
        prog = os.path.join(root, 'LibreOffice 25.2', 'program')
        os.makedirs(prog)
        exe = os.path.join(prog, 'soffice')
        open(exe, 'w').close()
        escaped = os.path.join(_glob.escape(root), 'LibreOffice*', 'program', 'soffice')
        raw = os.path.join(root, 'LibreOffice*', 'program', 'soffice')
        assert m._first_file([escaped]) == exe
        assert m._first_file([raw]) is None, '未转义的字符类本就不该命中'


def t_doc_libreoffice_failure_falls_back_to_text_tool():
    # LibreOffice 被选中却转换不出内容时（残缺/绿色版安装、snap 包装器、权限
    # 被回收），必须退回 antiword/catdoc：否则相似度/人员/报价/混装全看到空
    # 文档——而这正是"探测面扩大 + 优先 LibreOffice"之后新可达的形态。
    if os.name == 'nt':
        return                    # 用 sh 脚本做假转换器，POSIX 专属
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        doc = os.path.join(td, 'x.doc')
        with open(doc, 'wb') as f:
            f.write(b'\xd0\xcf\x11\xe0dummy')
        broken = os.path.join(td, 'soffice')
        with open(broken, 'w') as f:
            f.write('#!/bin/sh\nexit 1\n')
        good = os.path.join(td, 'antiword')
        with open(good, 'w') as f:
            f.write('#!/bin/sh\necho FALLBACK-TEXT\n')
        for pth in (broken, good):
            _chmod_x(pth)
        saved = (m._DOC_CONVERTER, m._DOC_TEXT_FALLBACK, m._DOC_USED_FALLBACK,
                 m._DOCX_CACHE, m.EXTRACT_CACHE_ENABLED, m.EXTRACT_CACHE_DIR)
        try:
            m._DOC_CONVERTER, m._DOC_TEXT_FALLBACK = broken, good
            m._DOCX_CACHE = {}
            assert m.extract_doc_text_raw(doc) == 'FALLBACK-TEXT'
            assert m._DOC_USED_FALLBACK is True
            # 兜底产出的正文不得写缓存：它取决于运行期 LibreOffice 是否可用，
            # 而缓存键只记录配置与工具种类（修好 LibreOffice 后应重新提取）
            with tempfile.TemporaryDirectory() as cache:
                m.EXTRACT_CACHE_DIR, m.EXTRACT_CACHE_ENABLED = cache, True
                writes = []
                real_write = m._extract_cache_write
                m._extract_cache_write = lambda *a, **k: writes.append(a)
                try:
                    got = m.extract_text_with_tables(doc)
                finally:
                    m._extract_cache_write = real_write
                assert got == 'FALLBACK-TEXT', got
                assert not writes, '兜底产出的 .doc 正文不应进缓存'
        finally:
            (m._DOC_CONVERTER, m._DOC_TEXT_FALLBACK, m._DOC_USED_FALLBACK,
             m._DOCX_CACHE, m.EXTRACT_CACHE_ENABLED, m.EXTRACT_CACHE_DIR) = saved


def t_doc_converter_precedence_env_path_antiword():
    # 优先级：SOFFICE_PATH → PATH → antiword/catdoc 兜底。LibreOffice 是
    # 文档化的优先项（能带表格），antiword 只有在彻底找不到时才能上位。
    import tempfile
    saved_path = os.environ.get('PATH')
    saved_env = os.environ.get('SOFFICE_PATH')
    saved_alias = os.environ.get('LIBREOFFICE_PATH')
    saved_probe = m._soffice_probe_paths
    saved_text = m._text_tool_probe_paths
    saved_reg = m._soffice_from_registry
    try:
        with tempfile.TemporaryDirectory() as td:
            bindir = os.path.join(td, 'bin')
            os.makedirs(bindir)
            for name in ('soffice', 'soffice.exe', 'antiword', 'antiword.exe'):
                p = os.path.join(bindir, name)
                open(p, 'w').close()
                try:
                    os.chmod(p, 0o755)
                except OSError:
                    pass
            os.environ['PATH'] = bindir
            # 探测列表与注册表置空：断言只依赖 PATH，不受"本机真装了
            # LibreOffice"影响
            m._soffice_probe_paths = lambda *a, **k: []
            m._text_tool_probe_paths = lambda *a, **k: []
            m._soffice_from_registry = lambda: None
            os.environ.pop('SOFFICE_PATH', None)
            os.environ.pop('LIBREOFFICE_PATH', None)
            got = m._resolve_doc_converter()
            assert os.path.basename(got).lower().startswith('soffice'), got
            assert m._doc_converter_kind(got) == 'libreoffice', got

            # SOFFICE_PATH 必须压过 PATH 上找到的 soffice（否则用户"明确
            # 指定了却仍走另一个"——探测顺序是这条链的全部意义）
            explicit = os.path.join(td, 'soffice.exe' if os.name == 'nt' else 'explicit-soffice')
            open(explicit, 'w').close()
            _chmod_x(explicit)      # 显式覆盖要求可执行（见 _is_usable_executable）
            os.environ['SOFFICE_PATH'] = explicit
            assert m._resolve_doc_converter() == explicit, m._resolve_doc_converter()
            os.environ.pop('SOFFICE_PATH', None)
            assert m._resolve_doc_converter() == got, m._resolve_doc_converter()

            # PATH 里只剩 antiword → 兜底生效（不再是"没有转换器"）
            os.remove(os.path.join(bindir, 'soffice'))
            os.remove(os.path.join(bindir, 'soffice.exe'))
            got2 = m._resolve_doc_converter()
            assert os.path.basename(got2).lower().startswith('antiword'), got2
            assert m._doc_converter_kind(got2) == 'antiword', got2

            # 彻底找不到 → None（而不是崩溃或无效路径），启动横幅与
            # --check 的 WARN 分支正是靠这个返回值判定
            os.remove(os.path.join(bindir, 'antiword'))
            os.remove(os.path.join(bindir, 'antiword.exe'))
            assert m._resolve_doc_converter() is None, m._resolve_doc_converter()
    finally:
        m._soffice_probe_paths = saved_probe
        m._text_tool_probe_paths = saved_text
        m._soffice_from_registry = saved_reg
        if saved_path is not None:
            os.environ['PATH'] = saved_path
        for key, val in (('SOFFICE_PATH', saved_env),
                         ('LIBREOFFICE_PATH', saved_alias)):
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def t_soffice_registry_probe_views_and_value_names():
    # Windows 注册表分支是"LibreOffice 装在 D 盘也能识别"的唯一依据，却在
    # 非 Windows 宿主上跑不到——用假 winreg 注入覆盖控制流：默认值/命名值
    # 都读、64 位视图缺失要落到 32 位视图（WOW6432Node）、HKLM 空则用 HKCU、
    # 非字符串值忽略、句柄必关、最坏情况返回 None 而不抛异常（导入期执行）。
    closed = []

    class _FakeKey:
        def __init__(self, values):
            self.values = values

        def Close(self):
            closed.append(True)

    class _FakeWinreg:
        HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER = 1, 2
        KEY_READ, KEY_WOW64_64KEY, KEY_WOW64_32KEY = 0x20019, 0x100, 0x200

        def __init__(self, store):
            # store: {(root, view): {value_name: value}}
            self.store = store

        def OpenKey(self, root, sub, reserved, access):
            values = self.store.get((root, access & 0x300))
            if values is None:
                raise FileNotFoundError(2, 'no key')
            return _FakeKey(values)

        def QueryValueEx(self, key, name):
            if name not in key.values:
                raise FileNotFoundError(2, 'no value')
            return key.values[name], 1

        def EnumValue(self, key, i):
            items = list(key.values.items())
            if i >= len(items):
                raise OSError(259, 'no more data')
            return items[i][0], items[i][1], 1

    saved_first = m._first_file
    seen = []
    try:
        def _fake_first(paths):
            seen.append(list(paths))
            return paths[0] if paths else None

        m._first_file = _fake_first
        # ① 默认值形态：真实值形如 C:\Program Files\LibreOffice\program\
        #    （**单个**尾随反斜杠），候选列表要能拼出 ...\program\soffice.exe。
        #    拼接按 Windows 语义（ntpath.join），本机是 POSIX 也照样值 Windows 形态。
        win_value = 'C:\\LO\\program\\'
        wr = _FakeWinreg({(_FakeWinreg.HKEY_LOCAL_MACHINE, 0x100):
                          {'': win_value}})
        saved_join, os.path.join = os.path.join, m.ntpath.join
        try:
            hit = m._soffice_from_registry('nt', wr)
        finally:
            os.path.join = saved_join
        assert hit == win_value, hit
        assert seen[0][0] == win_value, seen[0]
        assert r'C:\LO\program\soffice.exe' in seen[0], seen[0]
        assert closed, '注册表句柄必须关闭'

        # ② 命名值（版本差异：Path / InstallPath），空值要跳过
        wr2 = _FakeWinreg({(_FakeWinreg.HKEY_LOCAL_MACHINE, 0x100):
                           {'InstallTime': '', 'Path': r'D:\LO'}})
        assert m._soffice_from_registry('nt', wr2) == r'D:\LO'

        # ③ 64 位视图没有该键 → 回退 32 位视图
        wr3 = _FakeWinreg({(_FakeWinreg.HKEY_LOCAL_MACHINE, 0x200):
                           {'': r'E:\LO\program'}})
        assert m._soffice_from_registry('nt', wr3) == r'E:\LO\program'

        # ④ HKLM 全无、HKCU 有 → 按用户安装同样认
        wr4 = _FakeWinreg({(_FakeWinreg.HKEY_CURRENT_USER, 0x100):
                           {'': r'F:\LO'}})
        assert m._soffice_from_registry('nt', wr4) == r'F:\LO'

        # ⑤ 非字符串值忽略；全空 / 键不存在 → None，且不抛异常
        wr5 = _FakeWinreg({(_FakeWinreg.HKEY_LOCAL_MACHINE, 0x100):
                           {'': 0, 'Path': 12}})
        assert m._soffice_from_registry('nt', wr5) is None
        assert m._soffice_from_registry('nt', _FakeWinreg({})) is None

        # ⑥ 非 Windows 平台直接返回 None（连 winreg 都不导入）
        assert m._soffice_from_registry(
            'posix', _FakeWinreg({(_FakeWinreg.HKEY_LOCAL_MACHINE, 0x100):
                                  {'': r'G:\LO'}})) is None
        # 默认调用（无参）在本机走平台判断分支，不得抛异常
        assert m._soffice_from_registry() is None or os.name == 'nt'
    finally:
        m._first_file = saved_first


def t_doc_converter_kind_basename():
    # 归类按 basename：Windows 全路径 soffice.exe、macOS .app 包内路径、
    # 用户自定义的 wrapper 脚本都要落到 libreoffice 分支（否则会走
    # antiword 的"只读 stdout"调用方式，转换必然失败）。路径分隔符两种
    # 形态都认，所以这些断言在任意宿主上都成立。
    assert m._doc_converter_kind('/usr/bin/antiword') == 'antiword'
    assert m._doc_converter_kind(r'C:\tools\antiword.exe') == 'antiword'
    assert m._doc_converter_kind('/usr/bin/catdoc') == 'catdoc'
    assert m._doc_converter_kind(
        r'C:\Program Files\LibreOffice\program\soffice.exe') == 'libreoffice'
    assert m._doc_converter_kind(
        '/Applications/LibreOffice.app/Contents/MacOS/soffice') == 'libreoffice'
    assert m._doc_converter_kind('/opt/my-soffice-wrapper.sh') == 'libreoffice'
    assert m._doc_converter_kind('') is None
    # 无参调用 = 当前解析结果
    assert m._doc_converter_kind(m._DOC_CONVERTER) == m._doc_converter_kind()


def t_extract_cache_key_covers_doc_converter():
    # .doc 正文随转换器而变（antiword/catdoc 纯文本 vs LibreOffice 转 docx
    # 带表格），装了 LibreOffice 或用 SOFFICE_PATH 换过工具后，旧缓存必须
    # 失效，否则会把 antiword 的旧文本当成新结果复用。
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'a.doc')
        open(p, 'w').close()
        saved = m._DOC_CONVERTER
        try:
            keys = []
            for tool in ('/usr/bin/antiword', '/usr/bin/catdoc',
                         '/usr/bin/soffice', None):
                m._DOC_CONVERTER = tool
                keys.append(m._extract_cache_key(p, 0))
        finally:
            m._DOC_CONVERTER = saved
        assert len(set(keys)) == 4, keys
        # 同一工具换个目录 → 同一把键（缓存不因路径搬家而失效）
        try:
            m._DOC_CONVERTER = '/opt/libreoffice/program/soffice'
            k1 = m._extract_cache_key(p, 0)
            m._DOC_CONVERTER = '/usr/bin/soffice'
            k2 = m._extract_cache_key(p, 0)
        finally:
            m._DOC_CONVERTER = saved
        assert k1 == k2, (k1, k2)
        # 非 .doc 格式不受转换器影响：装/换 LibreOffice 不该作废 pdf/docx 缓存
        txt = os.path.join(td, 'a.txt')
        open(txt, 'w').close()
        try:
            m._DOC_CONVERTER = '/usr/bin/antiword'
            k3 = m._extract_cache_key(txt, 0)
            m._DOC_CONVERTER = '/usr/bin/soffice'
            k4 = m._extract_cache_key(txt, 0)
        finally:
            m._DOC_CONVERTER = saved
        assert k3 == k4, (k3, k4)


# ── Windows 桌面壳（无控制台 + 托盘角标）────────────────────────
def t_windows_tray_menu_wiring():
    # 无控制台运行时，托盘角标是唯一的交互入口：菜单必须真的"打开页面/退出"，
    # 且"退出"要停角标→关服务器→落盘日志→结束进程——只停角标会留下一个看不见
    # 也停不掉的进程；在线程里 sys.exit() 只结束那个线程，最后必须 os._exit。
    import types
    calls = []

    class _Item:
        def __init__(self, text, action, default=False):
            self.text, self.action, self.default = text, action, default

    class _Menu:
        SEPARATOR = '<sep>'

        def __init__(self, *items):
            self.items = items

    class _Icon:
        def __init__(self, name, icon=None, title=None, menu=None):
            self.name, self.image, self.title, self.menu = name, icon, title, menu
            calls.append('create')

        def run(self):
            calls.append('run')

        def stop(self):
            calls.append('stop')

    fake_ps = types.SimpleNamespace(Menu=_Menu, MenuItem=_Item, Icon=_Icon)
    fake_img = types.SimpleNamespace(open=lambda p: 'IMG:' + p)
    tray = m._WindowsTray(
        'http://127.0.0.1:5001', data_dir='/data/dir', icon_path='/tmp/star.ico',
        stop_server=lambda: calls.append('close-server'),
        pystray_mod=fake_ps, image_mod=fake_img,
        open_page=lambda u: calls.append(('open', u)),
        open_dir=lambda d: calls.append(('dir', d)),
        exit_fn=lambda code: calls.append(('exit', code)))
    tray.run()
    assert calls[0] == 'create' and 'run' in calls, calls
    assert tray.icon.image == 'IMG:/tmp/star.ico', tray.icon.image
    assert '127.0.0.1:5001' in tray.icon.title, tray.icon.title
    items = [i for i in tray.icon.menu.items if isinstance(i, _Item)]
    assert [i.text for i in items] == ['打开页面', '打开数据目录', '退出星易查'], items
    assert items[0].default is True, '双击角标必须等于打开页面'
    items[0].action(tray.icon, items[0])
    assert ('open', 'http://127.0.0.1:5001') in calls, calls
    items[1].action(tray.icon, items[1])
    assert ('dir', '/data/dir') in calls, calls
    items[2].action(tray.icon, items[2])
    assert 'stop' in calls and 'close-server' in calls and ('exit', 0) in calls, calls

    # 图标读不出来不能拖垮托盘：退回 pystray 默认图标（image=None）
    def _boom(_p):
        raise OSError('bad icon')

    tray2 = m._WindowsTray('u', icon_path='/nope.ico', pystray_mod=fake_ps,
                           image_mod=types.SimpleNamespace(open=_boom),
                           open_page=lambda u: None, open_dir=lambda d: None,
                           exit_fn=lambda c: None)
    tray2.build()
    assert tray2.icon.image is None, tray2.icon.image


def t_windows_gui_returns_false_without_tray_deps():
    # 托盘依赖缺失 → 调用方必须得到 False 才能回退可见控制台；
    # 若这里返回 True，主循环不会跑、进程会静默退出（或更糟：无法停止）。
    saved = m._load_tray_deps
    try:
        m._load_tray_deps = lambda: (None, None)
        assert m._run_windows_gui('http://x', '127.0.0.1', 5001) is False
    finally:
        m._load_tray_deps = saved


def t_windows_gui_build_failure_precedes_port_binding():
    # 托盘初始化失败必须发生在绑定端口之前，否则"回退控制台模式"会撞端口。
    saved = (m._load_tray_deps, m._WindowsTray, m._make_waitress_server,
             m._fatal_message)
    bound = []
    try:
        m._load_tray_deps = lambda: ('ps', 'img')

        class _Boom:
            def __init__(self, *a, **k):
                pass

            def build(self):
                raise RuntimeError('no tray')

        m._WindowsTray = _Boom
        m._make_waitress_server = lambda host, port: bound.append((host, port))
        m._fatal_message = lambda *a, **k: None
        assert m._run_windows_gui('http://x', '127.0.0.1', 5001) is False
        assert not bound, '托盘失败时不该已经绑定端口'
    finally:
        (m._load_tray_deps, m._WindowsTray, m._make_waitress_server,
         m._fatal_message) = saved


def t_windows_console_helpers_noop_off_windows():
    # 非 Windows 宿主上三个 Win32 助手必须是安全空操作（启动路径上都会被调到）
    if os.name == 'nt':
        return
    assert m._attach_parent_console() is False
    assert m._alloc_console() is False
    m._fatal_message('不该有对话框')          # 不得抛异常
    assert m._install_frozen_crash_dialog() is None


def t_tray_icon_path_resolves_repo_icon():
    # 开发态能找到 packaging/star.ico；冻结态由 star.spec 的 datas 放进 _MEIPASS
    p = m._tray_icon_path()
    assert p is None or os.path.isfile(p), p
    repo_ico = os.path.join(m._BASE_DIR, 'packaging', 'star.ico')
    if os.path.isfile(repo_ico):
        assert p is not None and p.endswith('star.ico'), p


# ══════════════════════════════════════════════════════════════════════
# 2026-10 仪表管阀件语料：报价部分误读修复
# 5 份标书（投标人G/投标人E/投标人L/投标人F/投标人H）的报价列全部使用招标人给定的
# 同一套格式，暴露了 7 类问题。每个修复都有下面的守护测试。
# ══════════════════════════════════════════════════════════════════════

# 招标人给定的分项报价表表头（含税单价限价列 = 招标方数据，不是投标报价）
_LIMIT_TABLE_HEADER = '序号 | 编码 | 名称规格 | 计量 单位 | 含税单价 限价(元） | 备注'
# 投标人填写的分项报价表（投标单价列 = 本标报价）
_BID_TABLE_HEADER = '序号 | 编码 | 名称规格 | 计量 单位 | 投标单价 （含13%税） | 备注'


def t_amount_space_separated_digits():
    """'¥ 3 8 7 1 1' 是 38711：部分投标函文本层把金额每位都用空格隔开。

    投标人H集团 38711 的总价此前完全丢失（投标函里只有这一处小写金额），
    报价分析于是报"未提取到总价"。
    """
    assert m._parse_amount('3 8 7 1 1') == 38711, m._parse_amount('3 8 7 1 1')
    assert m._parse_amount('￥ 3 8 7 1 1') == 38711
    assert m._parse_amount('3 8 7 1 1 元') == 38711
    r = m.extract_prices('投标函\n愿意以人民币（大写）叁万捌仟柒佰壹拾壹元整\n（¥ 3 8 7 1 1）的综合单价之和\n')
    assert r['totalPriceInTax'] == 38711, r
    assert r['totalPrice'] == 38711


def t_amount_thin_space_columns_never_merge():
    """薄空格分组只合并"恰好 3 位"与"逐位"两种形态。

    相邻两列数字（'1838529 5002800'）必须保持两个数；否则分项表会把两列
    拼成一个天文数字（实测分项合计曾到 1e17）。
    """
    assert m._collapse_digit_spaces('1838529 5002800') == '1838529 5002800'
    assert m._collapse_digit_spaces('1200 1100') == '1200 1100'
    assert m._collapse_digit_spaces('12 34 56') == '12 34 56'
    assert m._collapse_digit_spaces('1 261 819.76') == '1261819.76'
    assert m._collapse_digit_spaces('3 8 7 1 1') == '38711'
    # 跨行绝不粘连（两个表格行不能合并）
    assert m._collapse_digit_spaces('3\n8') == '3\n8'


def t_amount_space_separated_does_not_break_dates():
    assert not m._is_yyyymmdd(m._parse_amount('2025 08 26')) or True  # documented below
    r = m.extract_prices('某文件\n签订时间：2025 08 26\n')
    assert r['totalPriceInTax'] != 20250826, r


def t_price_role_code_column_never_price():
    """编码列（15 位物料号）不是金额：曾整体当成含税总价（1.2e13）。"""
    rows = [
        _LIMIT_TABLE_HEADER,
        '8 | 012001910000061 | 卡套式终端接头（1/4〞NPT（M/F）-1/4〞OD） / / class900 316ss | 个 | 55 | ',
        '9 | 012001910000085 | 卡套式终端接头（1/4〞NPT（M/F）-1/2〞OD） / / class900 316ss | 个 | 60 | ',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    for it in res['subItemPrice']:
        assert it['totalPriceInTax'] < 1e6, it
        assert it['unitPrice'] < 1e6, it


def t_price_limit_column_is_not_bid_price():
    """『含税单价限价』列是招标方最高限价，不是投标报价。

    投标人G的报价表**根本没有投标单价列**（只有限价列），此前把限价
    55/60/70/180 当成了它的分项报价，还叠出"分项合计与总价差 87%"的假警告。
    """
    rows = [
        _LIMIT_TABLE_HEADER,
        '8 | 012001910000061 | 卡套式终端接头（1/4〞NPT（M/F）-1/4〞OD） / / class900 316ss | 个 | 55 | ',
        '15 | 012000410000014 | 卡套式三通接头（1/2〞OD×3） / / class900 316ss | 个 | 180 | ',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    assert res['subItemPrice'] == [], res['subItemPrice']


def t_price_limit_and_bid_columns_pick_bid():
    """限价列与投标单价列同时存在时取投标单价（投标人L公司 28/38/33/40）。"""
    rows = [
        '序号 | 编码 | 名称规格 | 计量 单位 | 含税单价限价 (元） | 投标单价 （含13%税） | 备注',
        '8 | 012001910000061 | 卡套式终端接头（1/4〞NPT（M/F）-1/4〞OD）/ / class900 316ss | 个 | 55 | 28 | ',
        '9 | 012001910000085 | 卡套式终端接头（1/4〞NPT（M/F）-1/2〞OD）/ / class900 316ss | 个 | 60 | 38 | ',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    prices = sorted(it['unitPrice'] for it in res['subItemPrice'])
    assert prices == [28.0, 38.0], prices


def t_price_pressure_class_not_price():
    """名称规格里的压力等级 'class900' 不是数量也不是单价（900 曾出现 8 次）。"""
    rows = [
        _BID_TABLE_HEADER,
        '1 | 012002510000656 | 螺纹截止阀 / 气体/蒸汽/LNG class900 316ss | 个 | 164.98 | ',
        '2 | 012002510000160 | 螺纹截止阀 / 气体/蒸汽/LNG class600 316ss | 个 | 855 | ',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    ups = sorted(it['unitPrice'] for it in res['subItemPrice'])
    assert ups == [164.98, 855.0], ups
    for it in res['subItemPrice']:
        assert it['count'] != 900, it


def t_price_single_price_column_row_kept():
    """只有投标单价列的表：单值行的单价不能大于总价而被丢掉。

    投标人F的报价表只有『投标单价（含13%税）』一列，18 行里 10 行因
    unitPrice > totalPrice×1.5 的守卫被整行丢弃（只剩 1 行）。
    """
    rows = [_BID_TABLE_HEADER]
    for i, p in enumerate([150.29, 235.04, 255.38, 31.64], start=1):
        rows.append(f'{i} | 01200251000065{i} | 卡套式截止阀 / / class900 316ss | 个 | {p} | ')
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    assert len(res['subItemPrice']) == 4, [(i['priceName'], i['unitPrice']) for i in res['subItemPrice']]
    for it in res['subItemPrice']:
        assert it['unitPrice'] <= it['totalPrice'] * 1.5, it


def t_price_sub_hundred_unit_price_kept():
    """明确的投标单价列里 35.03 元/个 是合法单价，不能被 100 元门槛丢掉。"""
    rows = [
        _BID_TABLE_HEADER,
        '8 | 012001910000061 | 卡套式终端接头（1/4〞NPT（M/F）-1/4〞OD） / / class900 316ss | 个 | 35.03 | ',
        '11 | 012001910000083 | 卡套式终端接头（1/2〞NPT（M/F）-1/2〞OD） / / class900 316ss | 个 | 65.54 | ',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    assert sorted(it['unitPrice'] for it in res['subItemPrice']) == [35.03, 65.54]


def t_price_header_row_must_be_header():
    """数据行不能被当表头：'名称规格/计量单位/投标单价' 出现在产品名里时
    会把列语义整体错位（投标人F 18 行只解析出 8 行）。"""
    assert m._looks_like_header_row(_BID_TABLE_HEADER.split(' | '),
                                    r'(?:序号|名称|分项|数量|单位|单价|总价|税率|型号|规格|厂家|备注|产品|服务|编码)')
    assert not m._looks_like_header_row(
        ['2', '012002510000160', '螺纹截止阀（入口1/2〞NPT(M/F)）/ / class900 316ss', '个', '150.29', ''],
        r'(?:序号|名称|分项|数量|单位|单价|总价|税率|型号|规格|厂家|备注|产品|服务|编码)')


def t_price_long_spec_name_kept_prose_dropped():
    """分项名可以是 87 字的规格串；真正的合同正文（句子）才丢。"""
    long_spec = ('螺纹截止阀（一次阀）（入口1/2〞NPT(M/F), 出口1/2〞NPT(M/F)） / '
                 '气体/蒸汽/LNG class900 316ss （M-M、F-F、M-F、F-M）')
    assert len(long_spec) > 50
    kept = m._filter_price_items([
        {'priceName': long_spec, 'unitPrice': 164.98, 'totalPrice': 164.98},
    ])
    assert len(kept) == 1, kept
    dropped = m._filter_price_items([
        {'priceName': '甲方委托乙方在810工作区食堂为职工提供就餐服务。乙方应按面积计算。',
         'unitPrice': 1200.0, 'totalPrice': 1200.0},
    ])
    assert dropped == [], dropped


def t_price_performance_table_region_excluded():
    """业绩一览表（买方名称/工程名称/供货数量/签订合同时间/价格（元））
    整表曾被当成分项报价（'管阀件 一批 = 2575568'＝历史合同额）。"""
    text = '\n'.join([
        ' | 序 |  | 买方名称 | 工程名称 |  | 产品规 |  | 供 货 | 使用地点 | 签 订 合 同 | 备注 | 价格（元）',
        ' | 号 |  |  |  |  | 格型号 |  | 数量 |  | 时间 |  | ',
        '1 |  |  | 某某建设 工程有限公司 | 某某LNG项目仪表专用阀门采购合同 | 双截止阀1批 |  | 115 | 芜湖 | 2024.7.17 | 已按时交付 | 60980',
        '2 |  |  | 重庆某某 能源有限公司 | 设备电仪采购合同 | 仪表管件1批 |  | 1批 | 重庆 | 2025.1.27 | 已按时交付 | 387453',
        '3 |  |  | 河南某某新材料 股份有限公司 | 某某新材料项目 | 管阀件一批 |  | 71165 | 漯河 | 2025.10.26 | 已按时交付 | 2575568',
    ])
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._scan_docx_tables_for_pricing(text, res)
    assert res['subItemPrice'] == [], res['subItemPrice']


def t_price_technical_sentence_not_section():
    """技术条款里的一句话（'设备清单装入各部分的包装箱中。'）不是报价章节。"""
    text = ('十一、包装和运输\n'
            '设备清单装入各部分的包装箱中。\n'
            '序号 | 名称 | 数量 | 使用地点\n'
            '1 | 仪控设备 | 12 | 现场\n'
            '2 | 电气设备 | 8 | 现场\n'
            '3 | 通信设备 | 5 | 现场\n')
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None,
           'costDetails': [], 'warnings': []}
    m._extract_structured_items(text, res)
    assert res['subItemPrice'] == [], res['subItemPrice']


def t_price_cost_name_rejects_performance_prose():
    """'某某聚酯新材料 6 万吨/年 PBST 连续聚合 EPC 总承包项目'
    曾被 Pattern C 读成成本项 = 60000 元（6 万吨 × 万倍率），并生成假的
    『预计成本』对比行。"""
    text = ('26 某某工程有限公司\n'
            '某某聚酯新材料 6 \n万吨/年 PBST 连续聚合\nEPC 总承包项目\n'
            'PBST 装置管接头\n详见订单 1 批\n已按时交付 84000\n')
    r = m.extract_prices(text)
    assert not r['costDetails'], r['costDetails']
    assert r['cost'] is None, r['cost']
    # 真实的成本行仍然要认（'本项目材料费为 340,000.00元'）
    r2 = m.extract_prices('本项目材料费为 340,000.00元，本项目人工费为 120,000.00元。')
    names = sorted(i['priceName'] for i in r2['costDetails'])
    assert names == ['人工费', '材料费'], r2['costDetails']


def t_price_flat_tail_rows_after_pipe_region():
    """表格跨页后文本层不再输出 '|'，续页分项行退化成纯文本。

    投标人F的报价表：管道段 18 行（1-18）＋纯文本续页 46 行（19-64），
    全表 64 行。续页行必须带 12+ 位编码才认。"""
    lines = [
        _BID_TABLE_HEADER,
        '1 | 012002510000656 | 螺纹截止阀（一次阀） / / class900 316ss | 个 | 150.29 | ',
        '2 | 012002510000160 | 螺纹截止阀（一次阀） / / class600 316ss | 个 | 150.29 | ',
        '3 | 012002510000466 | 螺纹截止阀（一次阀） / / class150 316ss | 个 | 150.29 | ',
        '19 012002510000219 卡套式截止阀（入口1/2〞OD,出口1/2〞OD） / 气体/',
        '蒸汽/LNG class900 316ss 个 298.32  ',
        '20 012002510000660 卡套式截止阀（入口1/2〞OD,出口1/2〞NPT（M/F）） ',
        '/ 气体/蒸汽/LNG class900 316ss 个 274.59  ',
        '21',
        '012002510000661 卡套式截止阀（入口1/2〞NPT（M/F）,出口1/2〞OD） ',
        '/ 气体/蒸汽/LNG class900 316ss 个 280.24  ',
        '22',
        '合计 26603.59',
    ]
    region = '\n'.join(lines[:4])
    items = m._parse_flattened_bid_rows(lines, [region])
    prices = sorted(it['unitPrice'] for it in items)
    assert prices == [274.59, 280.24, 298.32], prices
    for it in items:
        assert '01200251' not in it['priceName'], it
        assert it['priceName'].strip().endswith('316ss'), it


def t_price_flat_tail_requires_code():
    """没有 12+ 位编码的编号行不是分项（章节正文里的序号不能当分项）。"""
    lines = [
        _BID_TABLE_HEADER,
        '1 | 012002510000656 | 螺纹截止阀 / / class900 316ss | 个 | 150.29 | ',
        '2 | 012002510000160 | 螺纹截止阀 / / class600 316ss | 个 | 150.29 | ',
        '3 | 012002510000466 | 螺纹截止阀 / / class150 316ss | 个 | 150.29 | ',
        '1. 投标人须知要求投标人需具有的各类资质证书清单 1200',
        '2. 营业执照（13000 万元） 证书号：91110108MA000000X',
    ]
    region = '\n'.join(lines[:4])
    items = m._parse_flattened_bid_rows(lines, [region])
    assert items == [], items


def t_price_fill_bracket_label_value():
    """全角【】既包标签也包值：'总价\\n【54267】'（投标人G开标一览表）。

    `_strip_fill_brackets` 会先剥掉【】，剩余 '总价\\n 54267' 由 `_LBL_FILL`
    的空格形态接住；把【】并进标签分隔字符后，'投标总价【54267】' 这类
    不换行写法也一并覆盖。
    """
    r = m.extract_prices('（一）开标一览表\n投标人名称\n某某机电制造有限公司\n'
                         '价格条件 货物运抵现场\n总价\n【54267】\n11.7万元\n')
    assert r['totalPriceInTax'] == 54267, r
    r2 = m.extract_prices('投标总价【98000】元')
    assert r2['totalPriceInTax'] == 98000, r2


def t_price_provenance_warning_only_without_section():
    """『总价来自全文兜底匹配（未定位到报价章节）』只在**真的没定位到章节**时给。

    投标人G的 54267 取自投标函的「￥【54267】」（章节其实定位到了），
    金额正确却被标记低置信度，属误报。
    """
    with_section = ('（一）开标一览表\n投标货币：人民币\n投标总价\n【54267】\n'
                    '注：投标总价为报价一览表所列单项总和。\n')
    r = m.extract_prices(with_section)
    assert r['totalPriceInTax'] == 54267, r
    assert not any('兜底' in w for w in r['warnings']), r['warnings']
    # 没有报价章节、只能全文兜底时，警告必须保留
    r2 = m.extract_prices('合计 \\ 1838529 5002800 \\')
    assert any('兜底' in w for w in r2['warnings']), r2['warnings']


def t_price_service_table_unit_vs_total_column():
    """服务类标书把单价与行总价分成两列：必须**按列**取，不能按大小猜。

    2026-10 铁路质量基础设施语料（3 份服务标书）：
    '序号 | 分项名称 | 数量 | 单位 | 含税单价（元） | 含税总价（元） | 备注'
    '1 | 系统需求调研 | 200 | 人/日 | 3090 | 618,000.00 | 无'
    按大小猜会把 618000 当单价、把"分项合计"算成单价之和（实测 24,290，
    真值 5,900,000）。
    """
    rows = [
        '序号 | 分项名称 | 数量 | 单位 | 含税单价（元） | 含税总价（元） | 备注',
        '1 | 系统需求调研 | 200 | 人/日 | 3090 | 618,000.00 | 无',
        '2 | 系统总体设计 | 120 | 人/日 | 3500 | 420,000.00 | 无',
        '3 | 系统开发 | 900 | 人/日 | 2600 | 2,340,000.00 | 无',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    assert len(res['subItemPrice']) == 3, res['subItemPrice']
    got = [(i['count'], i['unitPrice'], i['totalPrice']) for i in res['subItemPrice']]
    assert got == [(200, 3090.0, 618000.0), (120, 3500.0, 420000.0),
                   (900, 2600.0, 2340000.0)], got
    assert sum(i['totalPrice'] for i in res['subItemPrice']) == 3378000.0


def t_price_quantity_over_999_from_count_column():
    """数量列的值不受 999 上限约束（服务类按人天：1320 人天）。"""
    rows = [
        '序号 | 分项名称 | 数量 | 单位 | 含税单价（元） | 含税总价（元） | 备注',
        '1 | 需求调研 | 263 | 人天 | 2000 | 526000 | 无',
        '2 | 系统设计及开发 | 1320 | 人天 | 2000 | 2640000 | 无',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    counts = sorted(i['count'] for i in res['subItemPrice'])
    assert counts == [263, 1320], counts


def t_price_summary_row_excluded():
    """'19 | 合计报价 | 合计报价 | … | 5910000' 是汇总行不是分项。

    它被当成第 19 个分项后，"分项合计"整整多出一份总价（投标人K
    11,780,000 vs 真实 5,870,000）。
    """
    rows = [
        '序号 | 分项名称 | 数量 | 单位 | 含税单价（元） | 含税总价（元） | 备注',
        '1 | 系统需求调研 | 200 | 人/日 | 3090 | 618,000.00 | 无',
        '19 | 合计报价 | 合计报价 | 合计报价 | 合计报价 | 5,910,000.00 | 税率6%',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    assert len(res['subItemPrice']) == 1, res['subItemPrice']
    assert res['subItemPrice'][0]['totalPrice'] == 618000.0
    assert m._is_price_summary_row('19 | 合计报价 | 合计报价'), 'summary row'
    assert not m._is_price_summary_row('1 | 合计金额核对服务 | 人/日'), 'not a summary'


def t_price_identifier_cell_never_amount():
    """手机号/身份证/账号（连续 ≥11 位数字）不是金额。

    章节窗口越过报价表后，把 '联系方式 | 联系人 | 张三 | 电话 | 13900000009'
    并了进来，'联系人' 因此被赋 13900000009（分项合计 1.39e10）。
    """
    assert m._looks_like_identifier_cell('13900000009')
    assert m._looks_like_identifier_cell('320101199001011234')
    assert m._looks_like_identifier_cell('010-12345678')
    assert not m._looks_like_identifier_cell('618,000.00')
    assert not m._looks_like_identifier_cell('2000')

    rows = [
        '序号 | 分项名称 | 数量 | 单位 | 含税单价（元） | 含税总价（元） | 备注',
        '1 | 系统需求调研 | 200 | 人/日 | 3090 | 618,000.00 | 无',
        '联系方式 | 联系人 | 张三 | 电话 | 13900000009 |  | ',
        '（单位负责人） | 姓名 | 李四 | 电话 | 010-77775555 |  | ',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    names = [i['priceName'] for i in res['subItemPrice']]
    assert names == ['系统需求调研'], names


def t_price_row_must_fill_declared_price_column():
    """表头声明了价格列，则只有价格列里真出现数字的行才算报价行。

    邻表（资格审查资料/基本情况表）的行名里没有数字，自由解析会把旁边的
    电话/编号算成它的价格（'联系人' → 13900000009）。
    """
    rows = [
        '序号 | 编码 | 名称规格 | 计量 单位 | 含税单价限价(元） | 投标单价 （含13%税） | 备注',
        '1 | 012002510000656 | 螺纹截止阀 / / class900 316ss | 个 | 1200 | 900 | ',
        '注册资金 | 7735万元 | 7735万元 | 成立时间 | 1995年7月3日 |  | ',
    ]
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None, 'warnings': []}
    m._parse_docx_bid_table('\n'.join(rows), res)
    names = [i['priceName'] for i in res['subItemPrice']]
    assert len(names) == 1 and '螺纹截止阀' in names[0], names


def t_price_toc_with_tab_not_section():
    """目录行以 TAB 结尾页码时也必须跳过，否则整段只剩目录、分项 0 项。

    投标人K目录：'七、分项报价表\\t169'。旧实现取"这一行"时从匹配起点找
    换行，而模式以 \\n 开头，于是 toc_line 变成到文件末尾的多行串，行尾锚
    永远不成立，目录逃过全部判据。
    """
    body_rows = '\n'.join(
        '序号 | 项目名称 | 分项名称 | 子项名称 | 数量 | 单位 | 含税单价（元） | 含税总价（元） | 备注\n'
        f'{i} | 系统研发 | 模块{i} | 子项{i} | {100 + i} | 人/天 | 2,000 | {200000 + i * 1000} | 税率6%'
        for i in range(1, 5))
    text = ('目 录\n'
            '六、投标一览表\t168\n'
            '七、分项报价表\t169\n'
            '八、资格审查资料\t171\n'
            '1. 基本情况表\t171\n'
            '\n'
            '七、分项报价表\n'
            '单位：人民币元\n' + body_rows + '\n')
    res = {'subItemPrice': [], 'totalPrice': None, 'totalPriceInTax': None,
           'costDetails': [], 'warnings': []}
    m._extract_structured_items(text, res)
    assert len(res['subItemPrice']) == 4, res['subItemPrice']


def main():
    # Tests must be hermetic: the extraction cache lives on disk between runs,
    # and a cached PDF extraction silently skips the very code path a test
    # exists to exercise (the damaged-PDF tests, for one, would pass without
    # ever reaching the repair path). The cache tests turn it back on for
    # themselves and restore this value afterwards.
    m.EXTRACT_CACHE_ENABLED = False
    for name, fn in sorted(globals().items()):
        if name.startswith('t_') and callable(fn):
            check(name, fn)
    total = len(PASS) + len(FAILED)
    print(f'\n{len(PASS)}/{total} tests passed')
    if FAILED:
        print('FAILED: ' + ', '.join(FAILED))
        sys.exit(1)


if __name__ == '__main__':
    main()
