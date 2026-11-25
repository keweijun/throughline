"""Saves the formula sheet the scripted Studio chat says it wrote: python docs/screenshots/sheet.py <course> <en|zh-CN>."""
import sys
from throughline.api import execute
course, lang = sys.argv[1], sys.argv[2]
if lang == 'zh-CN':
    title = '公式页 · 第 1–2 章'
    md = r'''> [!IMPORTANT]
> **归一化：** $\psi = Af$，先算 $I = \int_{-\infty}^{\infty}|f|^2\,dx$，再取 $|A| = 1/\sqrt{I}$。$1/I$ 是 $|A|^2$，不是 $A$。

## 第 1 章 · 波函数

| 内容 | 公式 | 成立条件 |
| --- | --- | --- |
| 玻恩规则 | $P(a\le x\le b) = \int_a^b |\psi|^2\,dx$ | $\psi$ 已归一化 |
| 归一化 | $\int_{-\infty}^{\infty}|\psi|^2\,dx = 1$ | $0 < I < \infty$ |
| 位置期望值 | $\langle x\rangle = \int x|\psi|^2\,dx$ | 积分存在 |
| 动量期望值 | $\langle p\rangle = \int \psi^*(-i\hbar\,\partial_x\psi)\,dx$ | 先求导，再乘 $\psi^*$ |
| 弥散 | $\sigma_x^2 = \langle x^2\rangle - \langle x\rangle^2$ | $\langle x^2\rangle$ 有限 |

## 第 2 章 · 叠加与干涉

- 不可区分的路径：$P = |\psi_1+\psi_2|^2 = |\psi_1|^2 + |\psi_2|^2 + 2\,\mathrm{Re}(\psi_1^*\psi_2)$
- 幅值 $r_1, r_2$，相位差 $\phi$：$P(\phi) = r_1^2 + r_2^2 + 2r_1r_2\cos\phi$
- 有路径记录（即使没人看）：干涉项消失，$P = |\psi_1|^2 + |\psi_2|^2$'''
else:
    title = 'Formula sheet · Chapters 1–2'
    md = r'''> [!IMPORTANT]
> **Normalizing:** for $\psi = Af$, compute $I = \int_{-\infty}^{\infty}|f|^2\,dx$, then $|A| = 1/\sqrt{I}$. $1/I$ is $|A|^2$, not $A$.

## Chapter 1 · The wavefunction

| Idea | Formula | Holds when |
| --- | --- | --- |
| Born rule | $P(a\le x\le b) = \int_a^b |\psi|^2\,dx$ | $\psi$ is normalized |
| Normalization | $\int_{-\infty}^{\infty}|\psi|^2\,dx = 1$ | $0 < I < \infty$ |
| Mean position | $\langle x\rangle = \int x|\psi|^2\,dx$ | the integral exists |
| Mean momentum | $\langle p\rangle = \int \psi^*(-i\hbar\,\partial_x\psi)\,dx$ | differentiate, then multiply by $\psi^*$ |
| Spread | $\sigma_x^2 = \langle x^2\rangle - \langle x\rangle^2$ | $\langle x^2\rangle$ is finite |

## Chapter 2 · Superposition and interference

- Indistinguishable paths: $P = |\psi_1+\psi_2|^2 = |\psi_1|^2 + |\psi_2|^2 + 2\,\mathrm{Re}(\psi_1^*\psi_2)$
- Magnitudes $r_1, r_2$, phase difference $\phi$: $P(\phi) = r_1^2 + r_2^2 + 2r_1r_2\cos\phi$
- A path record (even unread) removes the interference term: $P = |\psi_1|^2 + |\psi_2|^2$'''
print(execute(course, {'op': 'sheet.save', 'id': 'formula-sheet-ch1-2', 'title': title, 'markdown': md, 'scope': {'chapter_ids': ['wavefunction', 'superposition'], 'concept_ids': []}}))
