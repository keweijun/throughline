"""Builds the course library the README screenshots are taken in (see README.md here).

    python docs/screenshots/build.py <en|zh-CN> <out> [--package <file>]

With --package the screenshot course is imported from a saved package, taught already; without it the course is built
from src/ untaught, for teaching it again (drive.mjs). Either way six more courses with covers fill the library."""
import html
import json
import re
import os
import shutil
import subprocess
import sys
from pathlib import Path

from throughline.api import execute

HERE = Path(__file__).resolve().parent
lang, out = sys.argv[1], Path(sys.argv[2]).resolve()
package = Path(sys.argv[sys.argv.index('--package') + 1]).resolve() if '--package' in sys.argv else None
zh = lang == 'zh-CN'
if out.exists():
    shutil.rmtree(out)
library = out / 'library'
config = out / 'config'
config.mkdir(parents=True)
(config / 'seen.json').write_text(json.dumps({'seen': [
    'welcome', 'studio-intro', 'launcher', 'studio-access', 'hint-citation', 'hint-recorded-help', 'hint-select-passage']}))


def op(course, request):
    return execute(course, request)


def pages(name):
    """Each page of a source HTML file as Markdown with LaTeX, as a page reading would transcribe it."""
    text = (HERE / 'src' / f'{name}.html').read_text(encoding='utf-8')
    text = re.sub(r'<script.*?</script>|<svg.*?</svg>|<figcaption>.*?</figcaption>|<head>.*?</head>', '', text, flags=re.S)
    result = []
    for chunk in text.split('<div class="page">')[1:]:
        chunk = re.sub(r'<h1>(.*?)</h1>', r'# \1\n', chunk)
        chunk = re.sub(r'<h2>(.*?)</h2>', r'## \1\n', chunk)
        chunk = re.sub(r'<h3>(.*?)</h3>', r'### \1\n', chunk)
        chunk = re.sub(r'</?b>', '**', chunk)
        chunk = re.sub(r'</?i>', '*', chunk)
        chunk = re.sub(r'<li>', '- ', chunk)
        chunk = re.sub(r'</p>|</li>|</div>', '\n', chunk)
        chunk = html.unescape(re.sub(r'<[^>]+>', '', chunk))
        result.append(re.sub(r'\n{3,}', '\n\n', chunk).strip())
    return result


def add_source(course, name):
    inputs = course / 'inputs'
    inputs.mkdir(exist_ok=True)
    target = inputs / (('lecture-notes' if name.startswith('notes') else 'problem-set-1') + '.pdf')
    shutil.copy(out / 'pdf' / f'{name}.pdf', target)
    source = op(course, {'op': 'source.register', 'path': str(target)})['source']
    readings = [{'page': n + 1, 'text': t} for n, t in enumerate(pages(name))]
    op(course, {'op': 'source.readings.save', 'source_id': source['id'], 'readings': readings})
    return source


def ref(source, page, **extra):
    return {'source_id': source['id'], 'revision': source['revision'], 'unit_id': f'page-{page}', **extra}


# The course the screenshots follow.
T = {
    'title': ('量子力学（上）', 'Quantum Mechanics I'),
    'cover': ('量子', 'QM'),
    'chapters': [
        ('wavefunction', ('波函数', 'The wavefunction'), ('波函数如何给出测量结果的概率。', 'How a wavefunction gives the probabilities of measurement results.'), [
            ('born', ('玻恩规则', 'The Born rule'), ('波函数告诉我们粒子会在哪里被找到吗？', 'What does the wavefunction say about where the particle will be found?'),
             ('由波函数计算粒子出现在某个区间内的概率', 'Compute the probability of finding a particle in an interval from its wavefunction'), [1]),
            ('normalization', ('波函数的归一化', 'Normalizing a wavefunction'), ('为什么波函数必须归一化，又该如何归一化？', 'Why must a wavefunction be normalized, and how do you do it?'),
             ('求归一化常数，并判断一个函数能否表示物理状态', 'Find a normalization constant and tell whether a function can be a physical state'), [1]),
            ('expectation', ('期望值', 'Expectation values'), ('多次测量的平均结果是多少？', 'What is the average of many measurements?'),
             ('计算 ⟨x⟩、⟨p⟩ 和 σ_x', 'Compute ⟨x⟩, ⟨p⟩ and σ_x'), [2]),
        ]),
        ('superposition', ('叠加与干涉', 'Superposition and interference'), ('两条路径的概率幅为什么会相消。', 'Why the amplitudes of two paths can cancel.'), [
            ('amplitudes', ('概率幅相加', 'Adding amplitudes'), ('为什么两条路径有时会相互抵消，而不是相加？', 'Why do two paths sometimes cancel instead of adding up?'),
             ('由两条路径的概率幅预测干涉结果', 'Predict an interference pattern from two path amplitudes'), [3]),
            ('double-slit', ('双缝干涉', 'The double slit'), ('双缝条纹的位置由什么决定？', 'What sets where the double-slit fringes fall?'),
             ('由缝距和波长求亮纹、暗纹位置和条纹间距', 'Find bright and dark fringes and their spacing from the slit separation and wavelength'), [4]),
            ('phase', ('整体相位与相对相位', 'Global and relative phase'), ('哪些相位可以被观测到？', 'Which phases can be observed?'),
             ('区分不可观测的整体相位和可观测的相对相位', 'Tell an unobservable global phase from an observable relative phase'), [4]),
        ]),
        ('observables', ('可观测量', 'Observables'), ('测量对应算符，算符的本征值就是可能的结果。', 'Measurements correspond to operators whose eigenvalues are the possible results.'), [
            ('operators', ('算符与本征值', 'Operators and eigenvalues'), ('测量会得到哪些结果？', 'What results can a measurement give?'),
             ('由本征态展开求测量结果及其概率', 'Find measurement results and their probabilities from an expansion in eigenstates'), [5]),
            ('commutators', ('对易子', 'Commutators'), ('两个可观测量能否同时确定？', 'Can two observables be definite at once?'),
             ('计算对易子并判断两个可观测量能否同时确定', 'Compute commutators and tell whether two observables can be definite together'), [5]),
            ('uncertainty', ('不确定性原理', 'The uncertainty principle'), ('位置和动量的弥散之间有什么限制？', 'What limits the spreads of position and momentum?'),
             ('由对易子推出不确定关系，并检验具体的态', 'Derive an uncertainty relation from a commutator and check it for a state'), [6]),
        ]),
        ('schrodinger', ('薛定谔方程', 'The Schrödinger equation'), ('定态与无限深方势阱中的能级。', 'Stationary states and the energy levels of the infinite well.'), [
            ('stationary', ('定态', 'Stationary states'), ('什么样的态不随时间改变？', 'Which states do not change in time?'),
             ('分离变量得到定态薛定谔方程，并判断一个态是否为定态', 'Separate variables to get the time-independent equation and tell whether a state is stationary'), [7]),
            ('square-well', ('无限深方势阱', 'The infinite square well'), ('受限粒子的能量为什么是量子化的？', 'Why are the energies of a confined particle quantized?'),
             ('求无限深方势阱的本征函数和能级', 'Find the eigenfunctions and energy levels of the infinite square well'), [8]),
            ('spectra', ('能级与光谱', 'Energy levels and spectra'), ('跃迁会放出什么频率的光？', 'What light does a transition emit?'),
             ('由能级差求光子的能量和波长', 'Find photon energies and wavelengths from level differences'), [8]),
        ]),
    ],
}
# Problem set parts: (label, page, latest section, required sections).
EXERCISES = [
    ('1(a)', 1, 'normalization', ['born', 'normalization'], '1'), ('1(b)', 1, 'expectation', ['expectation'], '1'),
    ('1(c)', 1, 'normalization', ['born', 'normalization'], '1'), ('2', 1, 'expectation', ['expectation'], None),
    ('3(a)', 1, 'amplitudes', ['amplitudes'], '3'), ('3(b)', 1, 'amplitudes', ['amplitudes'], '3'), ('3(c)', 1, 'amplitudes', ['amplitudes'], '3'),
    ('4', 1, 'double-slit', ['double-slit'], None), ('5', 1, 'phase', ['phase'], None), ('6', 2, 'commutators', ['commutators'], None),
    ('7(a)', 2, 'square-well', ['operators', 'square-well'], '7'), ('7(b)', 2, 'square-well', ['square-well'], '7'),
    ('7(c)', 2, 'square-well', ['stationary', 'square-well'], '7'), ('8', 2, 'uncertainty', ['uncertainty'], None), ('9', 2, 'spectra', ['spectra'], None),
]
pick = (lambda pair: pair[0]) if zh else (lambda pair: pair[1])
suffix = 'zh' if zh else 'en'

# The other courses first, so the screenshot course is the one studied last.
OTHERS = [
    ('p-chem', ('物理化学', 'Physical Chemistry'), ('物化', 'P-Chem'), 'orbits', ('异核双原子分子：HF 与 CO', 'Heteronuclear molecules: HF and CO')),
    ('algorithms', ('数据结构与算法', 'Data Structures and Algorithms'), ('数据结构', 'DS'), 'branches', ('线性时间归约与下界', 'Linear-time reductions and lower bounds')),
    ('linear-algebra', ('线性代数', 'Linear Algebra for Physicists'), ('线代', 'Lin Alg'), 'grid', ('特征值与特征向量', 'Eigenvalues and eigenvectors')),
    ('thermo', ('热力学与统计物理', 'Thermodynamics'), ('热统', 'Thermo'), 'contours', ('熵与热力学第二定律', 'Entropy and the second law')),
    ('signals', ('信号与系统', 'Signals and Systems'), ('信号', 'S&S'), 'field', ('傅里叶变换的性质', 'Properties of the Fourier transform')),
    ('micro', ('中级微观经济学', 'Intermediate Microeconomics'), ('微观', 'Micro'), 'scatter', ('生产与成本', 'Production and cost')),
]
for folder, title, cover, pattern, section in OTHERS:
    course = library / folder
    op(course, {'op': 'course.init', 'title': pick(title)})
    op(course, {'op': 'cover.save', 'name': pick(cover), 'pattern': pattern})
    ids = [f's{i}' for i in range(1, 9)]
    concepts = [{'id': i, 'title': f'{pick(section)}' if i == 's4' else f'Section {i[1:]}'} for i in ids]
    op(course, {'op': 'curriculum.save', 'concepts': concepts, 'route': ids, 'coverage': []})
    op(course, {'op': 'mainline.enter', 'concept_id': 's4', 'goal': pick(section), 'next_step': 'Continue', 'request_id': 'r'})

qm = library / ('liangzi' if zh else 'quantum')
if package:
    env = {**os.environ, 'THROUGHLINE_HOME': str(library)}
    subprocess.run([sys.executable, '-m', 'throughline', 'import', str(package), '--name', qm.name], env=env, check=True, stdout=subprocess.DEVNULL)
else:
    # The lecture notes and problem set as PDFs, printed from src/ by Chromium.
    subprocess.run(['node', str(HERE / 'pdf.mjs'), str(out / 'pdf')], check=True)
    op(qm, {'op': 'course.init', 'title': pick(T['title'])})
    if zh:
        op(qm, {'op': 'preferences.save', 'language': 'zh-CN'})
    op(qm, {'op': 'cover.save', 'name': pick(T['cover']), 'pattern': 'waves'})
    op(qm, {'op': 'course.profile.save', 'profile': {
        'goal': pick(('一月份期末考试', 'Final exam in January')), 'depth': 'standard',
        'prerequisites': [{'topic': pick(('复数', 'Complex numbers')), 'level': 'solid'}, {'topic': pick(('微积分', 'Calculus')), 'level': 'solid'},
                          {'topic': pick(('波动光学', 'Wave optics')), 'level': 'some'}],
        'focus': pick(('考试风格的计算题', 'Exam-style problems'))}})
    op(qm, {'op': 'memory.save', 'id': 'intake-1', 'kind': 'preference', 'text': pick(('每个新概念之前先给一个算例', 'A worked example before each new idea'))})
    op(qm, {'op': 'memory.confirm', 'id': 'intake-1'})
    op(qm, {'op': 'memory.save', 'id': 'intake-2', 'kind': 'preference', 'text': pick(('推导写完整，不要跳步', 'Write derivations out in full, without skipping steps'))})
    op(qm, {'op': 'memory.confirm', 'id': 'intake-2'})
    op(qm, {'op': 'widgets.save', 'ids': ['plot']})
    notes = add_source(qm, f'notes-{suffix}')
    problems = add_source(qm, f'problems-{suffix}')
    op(qm, {'op': 'curriculum.outline', 'chapters': [{'id': cid, 'title': pick(title), 'summary': pick(summary)} for cid, title, summary, _ in T['chapters']]})
    previous = []
    for cid, _, _, sections in T['chapters']:
        concepts, coverage = [], []
        for sid, title, question, objective, note_pages in sections:
            exercises = []
            for label, page, home, needs, part_of in EXERCISES:
                if home != sid:
                    continue
                item = ref(problems, page, question=label, required_concepts=needs)
                if part_of:
                    others = [{'question': l, 'concept_id': h} for l, _, h, _, p in EXERCISES if p == part_of and l != label]
                    item.update(part_of=part_of, other_parts=others)
                exercises.append(item)
            concepts.append({'id': sid, 'title': pick(title), 'core_question': pick(question), 'objective': pick(objective),
                             'prerequisites': previous[-1:], 'links': [ref(notes, p) for p in note_pages] + [ref(problems, p) for p in sorted({int(e['unit_id'][5:]) for e in exercises})],
                             'exercises': exercises})
            previous.append(sid)
        units = sorted({p for s in sections for p in s[4]})
        checked = {'verification': 'verified', 'verification_note': pick(('核对过：本页内容由映射的小节讲授。', 'Checked: the mapped sections teach this page.'))}
        coverage = [{**ref(notes, p), 'disposition': 'mapped', 'concept_ids': [s[0] for s in sections if p in s[4]], **checked} for p in units]
        for p in sorted({int(e['unit_id'][5:]) for c in concepts for e in c['exercises']}):
            coverage.append({**ref(problems, p), 'disposition': 'mapped', 'concept_ids': [c['id'] for c in concepts if any(e['unit_id'] == f'page-{p}' for e in c['exercises'])], **checked})
        op(qm, {'op': 'curriculum.chapter.save', 'chapter_id': cid, 'concepts': concepts, 'coverage': coverage})
    op(qm, {'op': 'mainline.enter', 'concept_id': 'born', 'goal': pick(T['chapters'][0][3][0][3]), 'next_step': 'Start the lesson', 'request_id': 'start'})

    # What the scripted Studio chat says it wrote (studio-scripts.json).
    subprocess.run([sys.executable, str(HERE / 'sheet.py'), str(qm), lang], check=True, stdout=subprocess.DEVNULL)
print(qm)
