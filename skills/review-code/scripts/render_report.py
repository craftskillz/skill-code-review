#!/usr/bin/env python3
"""Valide le JSON d'une revue et génère un rapport HTML autonome (bibliothèque standard seule)."""
import argparse
import html
import json
from pathlib import Path
import re
import sys

ROLES = {'review-behavior', 'review-tests', 'review-challenger', 'fix-finding'}
ROLE_STATUS = {'completed': 'Terminé', 'partial': 'Partiel', 'failed': 'Échec', 'not_run': 'Non exécuté'}
OUTCOMES = {'fixed', 'human_decision', 'dismissed'}
DECISION_REASONS = {
    'sensitive_area': 'Zone sensible : la correction relève d’une décision humaine',
    'business_ambiguity': 'Le contrat ne tranche pas : c’est une décision métier',
    'not_reproducible': 'Pas de test reproduisant le défaut',
    'uncertain': 'La contre-vérification n’a pas tranché',
    'fix_failed': 'La correction automatique n’a pas abouti',
}
CHECK_LABELS = {'observed': 'Lecture', 'passed': 'Test réussi', 'failed': 'Test en échec', 'not_run': 'Test non exécuté'}
SEVERITY = {'P1': 'Impact élevé', 'P2': 'Impact modéré', 'P3': 'Impact mineur'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(obj, keys, where):
    require(isinstance(obj, dict), f'{where} doit être un objet')
    for key in keys:
        require(isinstance(obj.get(key), str) and obj[key].strip(), f'{where}.{key} doit être un texte non vide')


def validate_agents(data):
    ids = []
    for agent in data['agents']:
        strings(agent, ('id', 'label', 'status', 'summary'), 'agent')
        ids.append(agent['id'])
        require(agent['status'] in ROLE_STATUS, 'Statut d’agent invalide')
        for key in ('requested_model', 'observed_model'):
            require(key in agent, f'{key} doit être présent, éventuellement null')
            value = agent[key]
            require(value is None or (isinstance(value, str) and value.strip()), f'{key} doit être un texte non vide ou null')
        if agent['requested_model'] is None:
            require(agent['status'] == 'not_run' and data['limitations'],
                    'Une configuration inconnue exige not_run et une limite explicite')
        require(agent['status'] != 'not_run' or agent['observed_model'] is None,
                'Un rôle non exécuté ne peut pas avoir de modèle observé')
        if agent['observed_model'] and agent['observed_model'] != agent['requested_model']:
            require(data['limitations'], 'Expliquer le changement de modèle dans limitations')
    require(len(ids) == len(ROLES) and set(ids) == ROLES, 'Chaque rôle doit figurer une seule fois')
    readers = [a for a in data['agents'] if a['id'] != 'fix-finding']
    require(data['status'] != 'completed' or all(a['status'] == 'completed' for a in readers),
            'Un rôle de revue incomplet impose un rapport partial')
    require(data['status'] != 'partial' or data['limitations'], 'Un rapport partial doit expliquer ses limites')


def validate_finding(finding, data, statuses):
    strings(finding, ('id', 'severity', 'title', 'file', 'trigger', 'impact', 'evidence', 'recommendation', 'outcome'), 'constat')
    where = f"Constat {finding['id']}"
    require(finding['severity'] in SEVERITY, f'{where} : priorité invalide')
    require(type(finding.get('line')) is int and finding['line'] > 0, f'{where} : ligne invalide')
    require(type(finding.get('sensitive')) is bool, f'{where} : sensitive doit être un booléen')
    require(finding['outcome'] in OUTCOMES, f'{where} : issue invalide')
    require(isinstance(finding.get('reviewers'), list) and finding['reviewers'] and
            all(r in ROLES and statuses.get(r) in ('completed', 'partial') for r in finding['reviewers']),
            f'{where} : provenance invalide ou rôle sans résultat')
    challenge = finding.get('challenge')
    if challenge is None:
        # Sans contre-vérification, rien ne peut être corrigé ni écarté.
        require(finding['outcome'] == 'human_decision', f'{where} : sans contre-vérification, seule la décision humaine est possible')
    else:
        strings(challenge, ('verdict', 'reason'), f'{where}.challenge')
        require(challenge['verdict'] in ('confirmed', 'refuted', 'uncertain'), f'{where} : verdict invalide')
    verdict = challenge and challenge['verdict']
    if finding['outcome'] == 'fixed':
        require(verdict == 'confirmed', f'{where} : seul un constat confirmé peut être corrigé')
        require(not finding['sensitive'], f'{where} : une zone sensible ne se corrige pas automatiquement')
        require(data.get('fix_branch'), f'{where} : corrigé sans branche de corrections')
        require(statuses.get('fix-finding') in ('completed', 'partial'), f'{where} : corrigé alors que fix-finding n’a pas abouti')
        fix = finding.get('fix')
        strings(fix, ('commit', 'test', 'red', 'green', 'diff', 'summary'), f'{where}.fix')
        require(re.fullmatch(r'[0-9a-f]{7,40}', fix['commit']), f'{where} : commit invalide')
        review = fix.get('review')
        strings(review, ('verdict', 'reason'), f'{where}.fix.review')
        require(review['verdict'] == 'approved', f'{where} : une correction non approuvée ne peut pas être livrée comme corrigée')
    elif finding['outcome'] == 'human_decision':
        decision = finding.get('decision')
        strings(decision, ('reason', 'question', 'recommendation'), f'{where}.decision')
        require(decision['reason'] in DECISION_REASONS, f'{where} : motif de décision invalide')
        options = decision.get('options')
        require(isinstance(options, list) and len(options) >= 2, f'{where} : proposer au moins deux options')
        for option in options:
            strings(option, ('label', 'consequence'), f'{where}.decision.option')
    else:
        require(verdict == 'refuted', f'{where} : seul un constat réfuté peut être écarté')


def validate(data):
    require(isinstance(data, dict), 'Le rapport doit être un objet')
    require(type(data.get('schema_version')) is int and data['schema_version'] == 2, 'schema_version doit être 2')
    strings(data, ('title', 'repository', 'headline'), 'rapport')
    require(type(data.get('demo')) is bool, 'demo doit être un booléen')
    require(data.get('demo_note') is None or isinstance(data['demo_note'], str), 'demo_note doit être un texte')
    require(data.get('status') in ('completed', 'partial'), 'status invalide')
    strings(data.get('scope'), ('base', 'head', 'base_sha', 'head_sha'), 'scope')
    for key in ('agents', 'findings', 'checks', 'limitations'):
        require(isinstance(data.get(key), list), f'{key} doit être une liste')
    require(all(isinstance(x, str) and x.strip() for x in data['limitations']), 'Chaque limite doit être un texte non vide')
    if data.get('fix_branch') is not None:
        strings(data['fix_branch'], ('name', 'head_sha'), 'fix_branch')
    awareness = data.get('awareness')
    strings(awareness, ('summary',), 'awareness')
    require(isinstance(awareness.get('changes'), list) and isinstance(awareness.get('watch'), list), 'awareness incomplet')
    for change in awareness['changes']:
        strings(change, ('area', 'before', 'after'), 'awareness.changes')
    require(all(isinstance(x, str) and x.strip() for x in awareness['watch']), 'awareness.watch doit contenir des textes')
    validate_agents(data)
    statuses = {a['id']: a['status'] for a in data['agents']}
    ids = [f.get('id') for f in data['findings']]
    require(len(ids) == len(set(ids)), 'Identifiant de constat dupliqué')
    for finding in data['findings']:
        validate_finding(finding, data, statuses)
    for check in data['checks']:
        strings(check, ('label', 'kind', 'status', 'detail'), 'vérification')
        require((check['kind'] == 'inspection' and check['status'] == 'observed') or
                (check['kind'] == 'test' and check['status'] in ('passed', 'failed', 'not_run')),
                'Distinguer inspection (observed) et test (passed, failed, not_run)')
    return data


def esc(value):
    return html.escape(str(value), quote=True)


def by_severity(findings):
    return sorted(findings, key=lambda f: f['severity'])


def code_block(text, label):
    return f'<figure class="term"><figcaption>{esc(label)}</figcaption><pre>{esc(text)}</pre></figure>'


def render_diff(text):
    lines = []
    for line in text.splitlines():
        kind = ('add' if line.startswith('+') and not line.startswith('+++') else
                'del' if line.startswith('-') and not line.startswith('---') else
                'hunk' if line.startswith('@@') else '')
        lines.append(f'<span class="{kind}">{esc(line) or " "}</span>')
    return f'<pre class="diff">{"".join(lines)}</pre>'


def copy_button(text):
    return f'<button type="button" class="copy" data-copy="{esc(text)}">Copier</button>'


def finding_head(f):
    return (f'<div class="card-top"><span class="sev {f["severity"]}" title="{SEVERITY[f["severity"]]}">{f["severity"]}</span>'
            f'<span class="fid">{esc(f["id"])}</span><code class="loc">{esc(f["file"])}:{f["line"]}</code></div>'
            f'<h3>{esc(f["title"])}</h3>')


def facts(f):
    rows = (('Situation', f['trigger']), ('Conséquence', f['impact']), ('Preuve', f['evidence']))
    return '<dl class="facts">' + ''.join(f'<div><dt>{t}</dt><dd>{esc(v)}</dd></div>' for t, v in rows) + '</dl>'


def provenance(f):
    text = 'Relevé par ' + ' + '.join(f['reviewers'])
    if f.get('challenge'):
        text += f" · Contre-vérification : {esc(f['challenge']['reason'])}"
    return f'<p class="prov">{esc(text) if not f.get("challenge") else text}</p>'


def render_decision(f):
    d = f['decision']
    options = ''.join(f'<li><b>{esc(o["label"])}</b><span>{esc(o["consequence"])}</span></li>' for o in d['options'])
    patch = ''
    if d.get('proposed_patch'):
        patch = f'<details><summary>Voir le correctif proposé, non appliqué</summary>{render_diff(d["proposed_patch"])}</details>'
    return f'''<article class="card decision" data-search data-severity="{f['severity']}">{finding_head(f)}
<p class="why">{esc(DECISION_REASONS[d['reason']])}</p>
<p class="question">{esc(d['question'])}</p><ul class="options">{options}</ul>
<p class="reco"><b>Recommandation des agents</b> {esc(d['recommendation'])}</p>
<details><summary>Comprendre le constat</summary>{facts(f)}{provenance(f)}</details>{patch}</article>'''


def render_fix(f):
    fix = f['fix']
    return f'''<article class="card fixed" data-search data-severity="{f['severity']}">{finding_head(f)}
<p class="fix-summary">{esc(fix['summary'])}</p>
<div class="proof">{code_block(fix['red'], 'Avant la correction · le test échoue')}{code_block(fix['green'], 'Après la correction · le test passe')}</div>
<p class="commit"><code>{esc(fix['commit'][:10])}</code> · test <code>{esc(fix['test'])}</code> · relu par review-challenger : {esc(fix['review']['reason'])}</p>
<details><summary>Voir le diff de la correction</summary>{render_diff(fix['diff'])}</details>
<details><summary>Comprendre le constat</summary>{facts(f)}{provenance(f)}</details></article>'''


def render_dismissed(f):
    return f'''<li><span class="sev {f['severity']}">{f['severity']}</span> <b>{esc(f['title'])}</b>
<code class="loc">{esc(f['file'])}:{f['line']}</code><p>{esc(f['challenge']['reason'])}</p></li>'''


def render_agent(a):
    warning = ''
    if a['observed_model'] and a['observed_model'] != a['requested_model']:
        warning = '<p class="warn">Modèle différent de celui demandé</p>'
    return f'''<article class="agent"><div class="agent-top"><code>{esc(a['id'])}</code><span class="pill {a['status']}">{ROLE_STATUS[a['status']]}</span></div>
<h3>{esc(a['label'])}</h3><p>{esc(a['summary'])}</p>
<dl class="models"><dt>Modèle demandé</dt><dd>{esc(a['requested_model'] or 'Configuration indisponible')}</dd>
<dt>Modèle observé</dt><dd>{esc(a['observed_model'] or 'Non confirmé par l’environnement')}</dd></dl>{warning}</article>'''


def render_pipeline(counts):
    steps = [('Proposés', counts['total'], 'par les sous-agents de revue', ''),
             ('Corrigés', counts['fixed'], 'test rouge puis vert, sur la branche dédiée', 'ok'),
             ('À décider', counts['decision'], 'par votre équipe', 'todo'),
             ('Écartés', counts['dismissed'], 'réfutés par la contre-vérification', 'off')]
    first = steps[0]
    head = f'<div class="flow-start"><b>{first[1]}</b><span>{first[0]}</span><small>{first[2]}</small></div><div class="flow-arrow" aria-hidden="true">→</div>'
    rest = ''.join(f'<a class="flow-step {c}" href="#{a}"><b>{n}</b><span>{t}</span><small>{s}</small></a>'
                   for (t, n, s, c), a in zip(steps[1:], ('fixes', 'decisions', 'dismissed')))
    return f'<div class="flow" role="group" aria-label="Devenir des constats">{head}<div class="flow-ends">{rest}</div></div>'


def render_merge(data):
    branch = data.get('fix_branch')
    if not branch:
        return '<p class="muted">Aucune branche de corrections n’a été créée pour cette revue.</p>'
    head, name = data['scope']['head'], branch['name']
    commands = [('Relire les corrections', f"git log --stat {data['scope']['head_sha'][:10]}..{name}"),
                ('Les intégrer à la branche relue', f'git switch {head} && git merge --ff-only {name}')]
    rows = ''.join(f'<li><span>{esc(t)}</span><code>{esc(c)}</code>{copy_button(c)}</li>' for t, c in commands)
    return f'''<p>Les corrections sont sur <code>{esc(name)}</code>. La branche <code>{esc(head)}</code> n’a pas bougé. Rien n’est fusionné sans votre décision.</p><ul class="commands">{rows}</ul>'''


def render(data):
    validate(data)
    by_outcome = {key: by_severity([f for f in data['findings'] if f['outcome'] == key]) for key in OUTCOMES}
    counts = {'total': len(data['findings']), 'fixed': len(by_outcome['fixed']),
              'decision': len(by_outcome['human_decision']), 'dismissed': len(by_outcome['dismissed'])}
    changes = ''.join(f'<tr><th scope="row">{esc(c["area"])}</th><td>{esc(c["before"])}</td><td>{esc(c["after"])}</td></tr>'
                      for c in data['awareness']['changes'])
    watch = ''.join(f'<li>{esc(item)}</li>' for item in data['awareness']['watch'])
    checks = ''.join(f'''<li><span class="check-state {c['status']}">{CHECK_LABELS[c['status']]}</span>
<b>{esc(c['label'])}</b><p>{esc(c['detail'])}</p></li>''' for c in data['checks'])
    limits = ''.join(f'<li>{esc(item)}</li>' for item in data['limitations'])
    empty = '<p class="empty">{}</p>'
    note = data.get('demo_note') or 'Données fictives, aucune revue réelle ni exécution de modèles.'
    scope = data['scope']
    replacements = {
        'TITLE': esc(data['title']), 'REPOSITORY': esc(data['repository']), 'HEADLINE': esc(data['headline']),
        'DEMO': f'<div class="demo">DÉMONSTRATION · {esc(note)}</div>' if data['demo'] else '',
        'STATUS_CLASS': data['status'],
        'STATUS': 'Couverture réalisée' if data['status'] == 'completed' else 'Couverture partielle',
        'SCOPE': f'{esc(scope["base"])} ({esc(scope["base_sha"][:7])}) → {esc(scope["head"])} ({esc(scope["head_sha"][:7])})',
        'PIPELINE': render_pipeline(counts),
        'N_DECISIONS': str(counts['decision']), 'N_FIXES': str(counts['fixed']), 'N_DISMISSED': str(counts['dismissed']),
        'AWARENESS': esc(data['awareness']['summary']),
        'CHANGES': changes or '<tr><td colspan="3">Aucun changement de comportement relevé.</td></tr>',
        'WATCH': watch or '<li>Aucun point de vigilance déclaré.</li>',
        'DECISIONS': ''.join(render_decision(f) for f in by_outcome['human_decision']) or empty.format('Aucune décision en attente.'),
        'FIXES': ''.join(render_fix(f) for f in by_outcome['fixed']) or empty.format('Aucune correction automatique dans cette revue.'),
        'DISMISSED': ''.join(render_dismissed(f) for f in by_outcome['dismissed']) or '<li>Aucun constat écarté.</li>',
        'MERGE': render_merge(data),
        'AGENTS': ''.join(render_agent(a) for a in data['agents']),
        'CHECKS': checks or '<li>Aucune vérification renseignée.</li>',
        'LIMITATIONS': limits or '<li>Aucune limite supplémentaire déclarée. Cette revue ne prouve pas l’absence de défauts.</li>',
    }
    template = Path(__file__).resolve().parent.parent / 'assets' / 'report.html'
    return re.sub(r'\{\{([A-Z0-9_]+)\}\}', lambda m: replacements[m.group(1)], template.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true', help='Valider le JSON sans écrire de HTML')
    args = parser.parse_args()
    if not args.check and args.output is None:
        parser.error('--output est requis sauf avec --check')
    try:
        data = validate(json.loads(args.input.read_text(encoding='utf-8')))
        if args.check:
            print('Structure du rapport valide ; les faits restent à vérifier.')
        else:
            result = render(data)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as output:
                output.write(result)
            print(args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f'Rapport non généré : {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
