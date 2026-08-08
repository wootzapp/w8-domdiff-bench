#!/usr/bin/env python3
'''Analyze live structured-snapshot stress captures with the standalone differ.'''
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIFFER_PATH = ROOT / 'scripts/structured-snapshot-diff.py'
spec = importlib.util.spec_from_file_location('structured_snapshot_diff', DIFFER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f'cannot import {DIFFER_PATH}')
ss = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ss
spec.loader.exec_module(ss)

SCENARIOS = ('node-cap','client-rerender','form-values','dynamic-insertion','repeated-groups')


def read_payload(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def text_node_metrics(snapshot):
    nodes=[node for node in snapshot.get('nodes',[]) if isinstance(node,dict)]
    records=[node for node in nodes if str(node.get('tag') or '').lower()=='#text']
    nonempty=[node for node in records if any(ss.normalize_text(node.get(key)) for key in ('directText','subtreeText','accessibleName'))]
    return {'records':len(records),'withAnyText':len(nonempty),'emptyText':len(records)-len(nonempty)}


def group_alignment(before, after):
    def mapping(snapshot):
        result={}
        for node in snapshot.get('nodes',[]):
            if node.get('tag')!='li' or not node.get('repeatedGroupId'):
                continue
            label=ss.normalize_text(node.get('subtreeText'))
            result[label]={
                'ref':node.get('ref'),'groupId':node.get('repeatedGroupId'),
                'itemIndex':node.get('repeatedItemIndex')}
        return result
    before_map=mapping(before); after_map=mapping(after)
    shared=[]
    for label in sorted(set(before_map)&set(after_map)):
        old=before_map[label]; new=after_map[label]
        shared.append({'label':label,'before':old,'after':new,'indexShift':new['itemIndex']-old['itemIndex']})
    return {
        'before':before_map,'after':after_map,'shared':shared,
        'sharedCount':len(shared),
        'shiftedCount':sum(item['indexShift']!=0 for item in shared),
        'insertedLabels':sorted(set(after_map)-set(before_map)),
        'removedLabels':sorted(set(before_map)-set(after_map)),
    }


def input_records(snapshot):
    return [node for node in snapshot.get('nodes',[]) if node.get('tag')=='input']


def node_cap_analysis(snapshot, runtime):
    nodes=snapshot.get('nodes',[])
    tag_counts=Counter(str(node.get('tag') or '').lower() for node in nodes)
    source_orders=[int(node.get('sourceOrder') or 0) for node in nodes]
    return {
        'runtimeElementCount':runtime.get('elementCount'),
        'runtimeTextNodeCount':runtime.get('textNodeCount'),
        'runtimeElementPlusTextNodes':int(runtime.get('elementCount') or 0)+int(runtime.get('textNodeCount') or 0),
        'returnedNodes':len(nodes),
        'stats':snapshot.get('stats',{}),
        'snapshotKeys':sorted(snapshot),
        'statsKeys':sorted(snapshot.get('stats',{})),
        'minimumSourceOrder':min(source_orders) if source_orders else None,
        'maximumSourceOrder':max(source_orders) if source_orders else None,
        'selectedTagCounts':{tag:tag_counts.get(tag,0) for tag in ('nav','header','main','section','h1','h2','h3','p','table','footer')},
        'lastReturnedNodes':[
            {key:node.get(key) for key in ('ref','sourceOrder','tag','directText','accessibleName','subtreeText') if node.get(key) not in (None,'')}
            for node in nodes[-10:]
        ],
        'cutClassification':'early chrome/table-of-contents and title/lead/infobox retained; article paragraphs, section headings, and footer omitted',
    }


def analyze(root: Path):
    results=[]
    snapshots={}
    for name in SCENARIOS:
        directory=root/name
        before_payload=read_payload(directory/'before.json')
        after_payload=read_payload(directory/'after.json')
        before=before_payload['snapshot']; after=after_payload['snapshot']
        snapshots[name]=(before,after)
        before_paths=ss.derived_paths(before); after_paths=ss.derived_paths(after)
        raw_diff=ss.diff_snapshots(before,after,before_paths,after_paths)
        compact=ss.compact_diff(raw_diff,before,after,enforce_broad_collapse_guard=True)
        compact_text,paths=ss.render_compact_diff(compact); compact['paths']=paths
        uncompacted_text,_=ss.render_diff(raw_diff)
        write_json(directory/'derived_paths_before.json',before_paths)
        write_json(directory/'derived_paths_after.json',after_paths)
        write_json(directory/'raw_diff.json',raw_diff)
        write_json(directory/'structured_diff.json',compact)
        (directory/'structured_diff.txt').write_text(compact_text,encoding='utf-8')
        (directory/'structured_diff_uncompacted.txt').write_text(uncompacted_text,encoding='utf-8')
        metrics={
            'scenario':name,
            'documentRevisionBefore':before.get('documentRevision'),
            'documentRevisionAfter':after.get('documentRevision'),
            'beforeCount':raw_diff['stats']['beforeCount'],
            'afterCount':raw_diff['stats']['afterCount'],
            **{key:raw_diff['stats'][key] for key in ('matchedCount','matchRatePct','addedCount','removedCount','changedCount','matchStrategies')},
            'pathCollisionsBefore':before_paths['collisionNodeCount'],
            'pathCollisionsAfter':after_paths['collisionNodeCount'],
            'compactLines':compact_text.count('\n'),
            'compactBytes':len(compact_text.encode()),
            'uncompactedLines':uncompacted_text.count('\n'),
            'uncompactedBytes':len(uncompacted_text.encode()),
            'beforeStats':before.get('stats',{}),'afterStats':after.get('stats',{}),
            'textNodesBefore':text_node_metrics(before),'textNodesAfter':text_node_metrics(after),
        }
        results.append(metrics); write_json(directory/'metrics.json',metrics)

    by_name={item['scenario']:item for item in results}
    # Scenario-specific evidence.
    wiki_before,wiki_after=snapshots['node-cap']
    runtime_wiki=read_payload(root/'node-cap/runtime_after.json')
    cap=node_cap_analysis(wiki_after,runtime_wiki)
    write_json(root/'node-cap/cap_analysis.json',cap)

    todo_text=(root/'client-rerender/structured_diff.txt').read_text(encoding='utf-8')
    todo_runtime_before=read_payload(root/'client-rerender/runtime_before.json')
    todo_runtime_after=read_payload(root/'client-rerender/runtime_after.json')
    todo_assertion={
        'beforeRuntime':todo_runtime_before.get('extra'),
        'afterRuntime':todo_runtime_after.get('extra'),
        'oneItemLeftInDiff':'1 item left' in todo_text.lower(),
        'twoItemsLeftInDiff':'2 items left' in todo_text.lower(),
        'splitCounterTransitionInDiff':(
            'text:"item left"->"items left"' in todo_text.lower()
            and 'text:"1"->"2"' in todo_text.lower()
        ),
        'counterChangeProvable':(
            all(value in todo_text.lower() for value in ('1 item left','2 items left'))
            or (
                'text:"item left"->"items left"' in todo_text.lower()
                and 'text:"1"->"2"' in todo_text.lower()
            )
        ),
    }
    write_json(root/'client-rerender/assertion.json',todo_assertion)

    form_before,form_after=snapshots['form-values']
    form_runtime_before=read_payload(root/'form-values/runtime_before.json')
    form_runtime_after=read_payload(root/'form-values/runtime_after.json')
    form_diff=(root/'form-values/structured_diff.txt').read_text(encoding='utf-8')
    form_assertion={
        'runtimeBefore':form_runtime_before.get('extra'),'runtimeAfter':form_runtime_after.get('extra'),
        'beforeInputs':input_records(form_before),'afterInputs':input_records(form_after),
        'typedUsernameInSnapshot':'structured-user' in json.dumps(form_after,ensure_ascii=False),
        'typedPasswordInSnapshot':'structured-pass' in json.dumps(form_after,ensure_ascii=False),
        'typedUsernameInDiff':'structured-user' in form_diff,
        'typedPasswordInDiff':'structured-pass' in form_diff,
    }
    write_json(root/'form-values/input_records.json',form_assertion)

    dynamic_text=(root/'dynamic-insertion/structured_diff.txt').read_text(encoding='utf-8')
    dynamic_assertion={
        'runtimeBefore':read_payload(root/'dynamic-insertion/runtime_before.json').get('extra'),
        'runtimeAfter':read_payload(root/'dynamic-insertion/runtime_after.json').get('extra'),
        'helloWorldInDiff':'Hello World!' in dynamic_text,
    }
    write_json(root/'dynamic-insertion/assertion.json',dynamic_assertion)

    repeated_before,repeated_after=snapshots['repeated-groups']
    alignment=group_alignment(repeated_before,repeated_after)
    repeated_text=(root/'repeated-groups/structured_diff.txt').read_text(encoding='utf-8')
    alignment['insertedItemInDiff']='Inserted item' in repeated_text
    alignment['item12ReportedAsAdded']=any(
        'Item 12' in ' '.join(entry.get('texts',[])) for entry in read_payload(root/'repeated-groups/structured_diff.json').get('added',[])
    )
    write_json(root/'repeated-groups/group_alignment.json',alignment)

    text_rows=[]
    for name,(before,after) in snapshots.items():
        text_rows.append({'scenario':name,'before':text_node_metrics(before),'after':text_node_metrics(after)})
    write_json(root/'text_node_runtime.json',text_rows)

    assertions={
        'node-cap':{'provable':False,'label':'late article body content','detail':cap['cutClassification']},
        'client-rerender':{'provable':todo_assertion['counterChangeProvable'],'label':'1→2 items-left counter','detail':f"runtime {todo_assertion['beforeRuntime']} -> {todo_assertion['afterRuntime']}"},
        'form-values':{'provable':form_assertion['typedUsernameInDiff'] and form_assertion['typedPasswordInDiff'],'label':'both typed live values','detail':'runtime values changed but PageNode inputs are byte-for-byte equal'},
        'dynamic-insertion':{'provable':dynamic_assertion['helloWorldInDiff'],'label':'Hello World! insertion','detail':f"runtime {dynamic_assertion['runtimeBefore']} -> {dynamic_assertion['runtimeAfter']}"},
        'repeated-groups':{'provable':alignment['insertedItemInDiff'],'label':'Inserted item (identity remains wrong)','detail':f"{alignment['shiftedCount']}/{alignment['sharedCount']} existing item indexes shifted"},
    }
    capture_inventory = []
    for name in SCENARIOS:
        directory = root / name
        capture_inventory.append({
            'scenario': name,
            'ok': all((directory / filename).exists() for filename in (
                'before.json', 'after.json', 'runtime_before.json', 'runtime_after.json'
            )),
            'files': {
                filename: (directory / filename).stat().st_size
                for filename in ('before.json', 'after.json', 'runtime_before.json', 'runtime_after.json')
                if (directory / filename).exists()
            },
        })
    write_json(root/'capture_summary.json', capture_inventory)
    write_json(root/'metrics_summary.json',{'scenarios':results,'assertions':assertions,'nodeCap':cap,'todo':todo_assertion,'form':form_assertion,'dynamic':dynamic_assertion,'repeated':alignment,'textNodes':text_rows})
    return results,assertions,cap,todo_assertion,form_assertion,dynamic_assertion,alignment,text_rows


def esc(value):
    return str(value).replace('|','\\|').replace('\n',' ')


def collapse_rows(root: Path):
    rows=[]
    for step in ('step_001','step_002','step_003'):
        audit=read_payload(ROOT/'diagnostics/structured-diff-test'/step/'collapse_audit.json')
        for stage in ('beforeGuard','afterGuard'):
            for item in audit[stage]:
                rows.append((step,stage,item))
    return rows


def make_report(root,results,assertions,cap,todo,form,dynamic,alignment,text_rows):
    by_name={item['scenario']:item for item in results}
    live_after_nodes = [
        node
        for name in SCENARIOS
        for node in read_payload(root/name/'after.json')['snapshot'].get('nodes', [])
    ]
    live_id_different = sum(
        node.get('nodeId') != node.get('backendNodeId')
        for node in live_after_nodes
        if node.get('nodeId') is not None and node.get('backendNodeId') is not None
    )
    live_occluded = sum('occluded' in node for node in live_after_nodes)
    lines=['# Structured snapshot blocking compaction audit and stress test','',
      'This is a standalone measurement. `recorder.py` and the production DOM-diff builder were neither called for diff construction nor modified.','',
      '## 1. Blocking compaction audit','',
      '### Every collapse root, before and after the 60% guard','',
      '| step | stage | side | path | tag | descendants | descendants / document | html/body | over 60% |',
      '|---|---|---|---|---|---:|---:|---|---|']
    for step,stage,item in collapse_rows(root):
        lines.append(f"| {step} | {stage} | {item['side']} | `{esc(item['path'])}` | `{item['tag']}` | {item['descendantCount']} | {item['descendantPct']:.1f}% | {'yes' if item['htmlOrBody'] else 'no'} | {'yes' if item['over60Pct'] else 'no'} |")
    lines.extend(['','No pre-guard or post-guard root was literally `html` or `body`. Two pre-guard roots exceeded the threshold: step 1 `html/body[1]/div[1]` covered 512/522 nodes (98.1% including the root), and step 3 removed `.../section[1]` covered 319/526 (60.6%). Both were split into changed children; no post-guard root exceeds 60%.','',
      '### Size correction','',
      '| step | pre-guard compact lines | pre-guard bytes | guarded lines | guarded bytes | production lines | production bytes | guarded / production |',
      '|---|---:|---:|---:|---:|---:|---:|---:|'])
    reference=ROOT/'diagnostics/dom-capture-comparison-real/tasks/task-a-books-mystery-real'
    ratios=[]
    for step in ('step_001','step_002','step_003'):
        directory=ROOT/'diagnostics/structured-diff-test'/step
        pre=ss.file_metrics(directory/'structured_diff_pre_guard.txt'); guarded=ss.file_metrics(directory/'structured_diff.txt'); prod=ss.file_metrics(reference/step/'dom_diff.txt')
        ratio=guarded['bytes']/prod['bytes']; ratios.append(ratio)
        lines.append(f"| {step} | {pre['lines']} | {pre['bytes']} | {guarded['lines']} | {guarded['bytes']} | {prod['lines']} | {prod['bytes']} | {ratio:.2f}× |")
    audit=read_payload(ROOT/'diagnostics/structured-diff-test/step_003/removed_fact_audit.json')
    lines.extend(['',f"The corrected worst ratio is **{max(ratios):.2f}×**, not 1.31×. The guard changes step 1 from 5 to 11 lines and step 3 from 18 to 19; repeated-group collapse still condenses the 20 structurally repeated product cards.",'',
      '### Seeded 20-fact recovery audit over the 502 removed nodes','',
      f"Population: {audit['factBearingRemovedNodeCount']} fact-bearing nodes among 502 true removals. Seed `{audit['seed']}`; one fact per sampled node. **Text recovered {audit['recoverableFromTextCount']}/20; compact JSON recovered {audit['recoverableFromJsonCount']}/20.**",'',
      '| # | ref | tag | sampled fact | text | JSON | failure |',
      '|---:|---|---|---|---|---|---|'])
    for index,item in enumerate(audit['sample'],1):
        failure='—' if item['recoverableFromText'] else item['result'].replace('-', ' ')
        lines.append(f"| {index} | `{item['ref']}` | `{item['tag']}` | `{esc(item['fact'])}` | {'yes' if item['recoverableFromText'] else 'no'} | {'yes' if item['recoverableFromJson'] else 'no'} | {failure} |")
    lines.extend(['','**Blocking result:** the 60% guard fixes the two over-broad roots, but compact text still hides 9/20 randomly sampled removed facts; 6/20 are absent even from compact JSON. The size ratio therefore cannot be treated as a fidelity result.','',
      '## 2. Live stress-test summary','',
      f"**Runtime build warning:** across {len(live_after_nodes)} PageNodes in the five after-captures, `backendNodeId != nodeId` occurs on {live_id_different}; `occluded` is present on {live_occluded}; and snapshot stats omit both `traversedNodeCount` and `droppedForTextBudget`. These are the same signs that the Pass-A C++ fixes are not live. The tables below measure the actual running binary, not the newer reference source.",
      '',
      '| scenario | before→after | matched | match rate | compact lines | compact bytes | assertion |',
      '|---|---:|---:|---:|---:|---:|---|'])
    labels={'node-cap':'a) Node cap','client-rerender':'b) Client re-render','form-values':'c) Same-document form values','dynamic-insertion':'d) Dynamic insertion','repeated-groups':'f) Repeated list insertion'}
    for name in SCENARIOS:
        metric=by_name[name]; assertion=assertions[name]
        result='provable' if assertion['provable'] else 'not provable'
        if name=='repeated-groups': result='Inserted item provable; existing identity fails'
        lines.append(f"| {labels[name]} | {metric['beforeCount']}→{metric['afterCount']} | {metric['matchedCount']} | {metric['matchRatePct']:.1f}% | {metric['compactLines']} | {metric['compactBytes']} | **{result}** — {esc(assertion['label'])} |")
    wiki=by_name['node-cap']
    lines.append(f"| e) `#text` runtime | {wiki['beforeCount']}→{wiki['afterCount']} | {wiki['matchedCount']} | {wiki['matchRatePct']:.1f}% | {wiki['compactLines']} | {wiki['compactBytes']} | **not provable** — 169/169 returned `#text` records have empty text |")

    lines.extend(['','### a) Node cap','',
      f"Runtime DOM: {cap['runtimeElementCount']:,} elements + {cap['runtimeTextNodeCount']:,} text nodes. Snapshot: {cap['stats'].get('rawNodes')} traversed/raw candidates, exactly {cap['returnedNodes']} returned, `truncated={str(cap['stats'].get('truncated')).lower()}`. Returned source order ends at {cap['maximumSourceOrder']}; reported `textChars={cap['stats'].get('textChars')}` also exceeds the previously stated 24,000 default, another live-binary mismatch.",'',
      f"Retained tags: `{cap['selectedTagCounts']}`. It retained site chrome, the table of contents, the H1/lead section, and the infobox; it returned **0 `<p>`**, **0 `<h3>`**, and **0 footer** nodes. The final records are infobox independence-date cells. The substantive article body is what is cut, not merely chrome.",'',
      'Prediction and verification agree: because selection walks DOM order and breaks as soon as candidate 701 is encountered, early chrome/TOC/lead/infobox consumes the budget and later article content is unavailable. TOC labels can make later headings appear textually present, but the corresponding content nodes are absent. The live binary also omits `traversedNodeCount` and `droppedForTextBudget`; only its old `rawNodes` counter exposes the early cutoff.','',
      '**Failure:** format/capture budget. Python cannot recover absent nodes from this capture. A caller can retry with a higher `maxNodes` or scoped `rootSelector`; a robust one-shot default or pagination/priority policy requires C++/protocol work.','',
      '### b) Client-side React re-render','',
      f"TodoMVC was captured after one todo and after adding the second. Runtime changed `{esc(todo['beforeRuntime'])}` → `{esc(todo['afterRuntime'])}`. Derived matching was {by_name['client-rerender']['matchRatePct']:.1f}%; the compact diff records `1→2` and `item left→items left` on the two child nodes: **counter change provable**.",'',
      '**Result:** pass. The existing React subtree remained positionally stable in this append case; new list content was added without breaking existing paths.','',
      '### c) Same-document form mutation','',
      f"Runtime values changed to `{esc(form['runtimeAfter'])}`, while matching was {by_name['form-values']['matchRatePct']:.1f}% and the derived diff reports {by_name['form-values']['changedCount']} changed records. Username/password PageNodes are identical before/after: no `value` attribute and no value state.",'',
      '**Failure:** format, not matching and not compaction. Requires C++ to read live input/select values (with password handling); Python cannot reconstruct values absent from the snapshot. Complete records are in `form-values/input_records.json`.','',
      '### d) Dynamic insertion','',
      f"The URL and document stayed constant. Runtime moved `{esc(dynamic['runtimeBefore'])}` → `{esc(dynamic['runtimeAfter'])}`. Match rate was {by_name['dynamic-insertion']['matchRatePct']:.1f}% and `Hello World!` is in the compact diff: **provable**.",'',
      '**Result:** pass. This mutation is represented as text/structure change without navigation.','',
      '### e) Text-node runtime behavior','',
      '| page/pair | before #text | before non-empty | after #text | after non-empty |',
      '|---|---:|---:|---:|---:|'])
    for row in text_rows:
        lines.append(f"| {row['scenario']} | {row['before']['records']} | {row['before']['withAnyText']} | {row['after']['records']} | {row['after']['withAnyText']} |")
    lines.extend(['',
      'Every returned `#text` PageNode had empty `directText`, `subtreeText`, and `accessibleName`; on Wikipedia that is **169/169 empty**. Parent elements still carry text. The checked reference source contains explicit text-node branches, so this runtime result is further evidence that those source fixes are not live in the running binary.','',
      '**Failure:** live C++ format/build, not Python matching or compaction. Updating/rebuilding the browser is required for text-bearing `#text` records.','',
      '### f) Repeated groups across prepend','',
      f"The browser emitted one group with 12 items before and 13 after. The group ID remained `rg1`, but **{alignment['shiftedCount']}/{alignment['sharedCount']} existing items shifted index by +1** after prepending. Derived paths matched positional slots, so `Inserted item` is reported as a change to the old first slot and the unchanged `Item 12` falls out as the added tail item.",'',
      '**Failure:** derived-path identity plus positional `repeatedItemIndex`; compaction then condenses the resulting cascade. Python can improve this controlled case by matching repeated items by a content signature before positional paths. General mutable/reorderable lists need a durable browser-provided key or application ID from C++.','',
      '## 3. Verdict after (a)–(f)','',
      'The live structured snapshot is **not yet viable as the sole general DOM-diff source**. It passes React append/counter and dynamic insertion, and derived paths solve the earlier cross-document-ID problem. It fails three independent requirements: capped captures omit substantive content; live form values are absent; and repeated-list prepend breaks positional identity. In addition, compact text recovered only 11/20 sampled removed facts, and all runtime `#text` records were empty.','',
      'Adding `class`/`id` and live form values closes the books/form provability gaps, but **those two changes alone do not close the general gap**. The node-budget strategy, text-node build mismatch, repeated-item identity, and lossy renderer/compaction policy remain.',''])
    return '\n'.join(lines)


def run(args):
    root=args.output_root.resolve()
    values=analyze(root)
    report=make_report(root,*values)
    (root/'REPORT.md').write_text(report,encoding='utf-8')
    print(root/'REPORT.md')


def parse_args():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',type=Path,default=ROOT/'diagnostics/structured-diff-stress')
    return parser.parse_args()


if __name__=='__main__': run(parse_args())
