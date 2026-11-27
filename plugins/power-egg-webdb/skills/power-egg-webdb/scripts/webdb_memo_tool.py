"""Standard-library-only helper embedded in the specification. Experimental build."""
import argparse
import base64
import copy
import hashlib
import io
import json
import pathlib
import re
import xml.etree.ElementTree as ET
import zipfile


def put(parent, name, value):
    node = parent.find(name)
    if node is None:
        node = ET.SubElement(parent, name)
    node.text = str(value).lower() if isinstance(value, bool) else str(value)
    return node


def remove(parent, *names):
    for name in names:
        for child in list(parent.findall(name)):
            parent.remove(child)


def payload(memo, name):
    text = pathlib.Path(memo).read_text(encoding='utf-8-sig')
    pattern = r'BEGIN_PAYLOAD ' + re.escape(name) + r' SHA256=([0-9a-f]{64})\s+([A-Za-z0-9+/=\s]+?)\s+END_PAYLOAD ' + re.escape(name)
    match = re.search(pattern, text)
    if not match:
        raise ValueError('Missing payload: ' + name)
    data = base64.b64decode(re.sub(r'\s+', '', match[2]), validate=True)
    if hashlib.sha256(data).hexdigest() != match[1]:
        raise ValueError('Payload SHA256 mismatch')
    return data


def validate_archive(data):
    """Byte/container checks for original library archives; no product semantic validation."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC error')
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entries')
        if 'databasedef.xml' not in names or 'certificate.txt' not in names:
            raise ValueError('Missing root entries')
        for name in names:
            path = pathlib.PurePosixPath(name.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in name:
                raise ValueError('Unsafe ZIP entry path')
        xml = z.read('databasedef.xml')
        if z.read('certificate.txt') != hashlib.md5(xml).hexdigest().encode('ascii'):
            raise ValueError('Certificate does not match observed MD5 rule')
        root = ET.fromstring(xml)
    if root.tag != 'DatabaseXmlWrapper':
        raise ValueError('Unexpected XML root')
    return root


def validate(data):
    """Additional checks only for the simple generated candidate structure."""
    root = validate_archive(data)
    if root.findtext('ExportVersion') != '2.91':
        raise ValueError('Candidate helper supports version 2.91 only')
    dbid = root.findtext('./Database/Id')
    fields = {e.findtext('Id'): e for e in root.findall('./Fields/Field')}
    if not fields or len(fields) > 300:
        raise ValueError('Invalid field count')
    for tag in ('Field', 'ListView', 'ListItem', 'ScreenView', 'Layout', 'LayoutCell',
                'LayoutItem', 'Query', 'QueryBlock', 'QueryItem', 'Summary',
                'SummaryItem', 'FieldRelation', 'FieldRelationValue'):
        values = [e.findtext('id' if tag == 'QueryItem' else 'Id') for e in root.iter(tag)]
        if None in values or len(values) != len(set(values)):
            raise ValueError('Missing or duplicate typed ID: ' + tag)
    for e in root.iter():
        if e.tag == 'DatabaseId' and e.text != dbid:
            raise ValueError('Database reference mismatch')
        if e.tag in ('FieldId', 'fieldId', 'Key1FieldId', 'Key2FieldId', 'Key3FieldId',
                     'CrossKeyFieldId', 'SortFieldId1', 'SortFieldId2', 'SortFieldId3',
                     'LimitFieldId') and e.text not in fields:
            raise ValueError('Dangling field reference: ' + e.tag + '=' + str(e.text))
    checks = [('ListView', 'ListItems/ListItem', 'ListId'),
              ('ScreenView', 'Layouts/Layout', 'ScreenId'),
              ('Layout', 'LayoutCells/LayoutCell', 'LayoutId'),
              ('LayoutCell', 'LayoutItems/LayoutItem', 'CellId'),
              ('Query', 'QueryBlocks/QueryBlock', 'QueryId'),
              ('QueryBlock', 'QueryItems/QueryItem', 'blockId'),
              ('Summary', 'SummaryItems/SummaryItem', 'SummaryDefId'),
              ('FieldRelation', 'FieldRelationValues/FieldRelationValue', 'FieldRelationID')]
    for tag, path, ref in checks:
        for parent in root.iter(tag):
            for child in parent.findall(path):
                if child.findtext(ref) != parent.findtext('Id'):
                    raise ValueError('Parent reference mismatch: ' + ref)
    for layout in root.iter('Layout'):
        rows, cols = int(layout.findtext('MaxRows')), int(layout.findtext('MaxCols'))
        if not (1 <= rows <= 50 and 1 <= cols <= 15):
            raise ValueError('Layout size outside documented range')
        occupied = set()
        for cell in layout.findall('./LayoutCells/LayoutCell'):
            r, c = int(cell.findtext('RowIndex')), int(cell.findtext('ColIndex'))
            rs, cs = int(cell.findtext('Rowspan')), int(cell.findtext('Colspan'))
            if r < 0 or c < 0 or rs < 1 or cs < 1 or r + rs > rows or c + cs > cols:
                raise ValueError('Cell outside layout')
            points = {(a, b) for a in range(r, r+rs) for b in range(c, c+cs)}
            if occupied & points:
                raise ValueError('Overlapping cells')
            occupied |= points
    for summary in root.iter('Summary'):
        keys = [summary.findtext('Key%dFieldId' % i) for i in (1, 2, 3)]
        if not keys[0] or len([k for k in keys if k]) != len({k for k in keys if k}):
            raise ValueError('Missing or duplicate summary keys')
        measures = [i for i in summary.findall('./SummaryItems/SummaryItem')
                    if i.findtext('SummaryType') not in ('1', '2', '3')]
        if not measures:
            raise ValueError('Missing summary measure')
        if summary.findtext('DisplayType') == '1' and len(measures) != 1:
            raise ValueError('Pie requires one measure')
        if summary.findtext('CrossSummary') == 'true' and summary.findtext('DisplayType') != '0':
            raise ValueError('Cross summary requires table')
        for item in measures:
            fid, typ = item.findtext('FieldId'), item.findtext('SummaryType')
            if typ == '80' and fid is not None:
                raise ValueError('Record count must omit FieldId')
            if typ == '40' and (fid is None or fid in keys):
                raise ValueError('Invalid SUM target')
    return root


def build(memo, spec):
    """Build an unsupported import candidate from observed field/record structures."""
    root = validate(payload(memo, 'xdb_exp5.zip'))
    original = copy.deepcopy(root)
    if not spec.get('database_name') or not isinstance(spec.get('fields'), list) or not spec['fields']:
        raise ValueError('database_name and nonempty fields required')
    if len(spec['fields']) > 100:
        raise ValueError('Helper supports up to 100 custom fields')
    reserved = {'No', '登録者', '登録日時', '最終更新者', '最終更新日時', '関連情報 URL', '明細行フォルダ名'}
    fieldnames = [x['name'] for x in spec['fields']]
    if any(not n or n in reserved for n in fieldnames) or len(set(fieldnames)) != len(fieldnames):
        raise ValueError('Empty, duplicate, or reserved field name')
    db = root.find('Database')
    put(db, 'DatabaseName', spec['database_name'])
    put(db, 'Notes', spec.get('notes', ''))
    # Keep database identity and system metadata as in the seed. Importer remapping is unverified.
    fields = root.find('Fields')
    systems = [copy.deepcopy(f) for f in fields if f.findtext('ItemClass') == '0']
    seeds = {f.findtext('FieldType'): copy.deepcopy(f) for f in fields}
    for archive in ('xdb_exp1.zip', 'xdb_exp16.zip', 'xdb_exp17.zip'):
        extra = validate_archive(payload(memo, archive))
        for f in extra.findall('./Fields/Field'):
            seeds.setdefault(f.findtext('FieldType'), copy.deepcopy(f))
    fields.clear()
    mapping = {}
    for i, config in enumerate(spec['fields'], 1):
        typ = str(config['type'])
        if typ not in ('1', '2', '5', '6', '9', '11', '20', '21', '22', '23', '31', '51', '52'):
            raise ValueError('Unobserved field type for helper: ' + typ)
        field = copy.deepcopy(seeds[typ])
        remove(field, 'DefaultValue')
        put(field, 'Id', 4000+i)
        put(field, 'DatabaseId', db.findtext('Id'))
        put(field, 'DBColumnName', 'C%011d' % (4000+i))
        put(field, 'FieldName', config['name'])
        put(field, 'DispOrder', i)
        put(field, 'Required', bool(config.get('required', False)))
        put(field, 'Reusable', bool(config.get('reusable', False)))
        put(field, 'UpdateCounter', 1)
        if typ in ('21', '22', '23'):
            choices = config.get('choices', [])
            if not choices or any(not isinstance(c, str) or not c or '\n' in c or '\r' in c for c in choices) or len(set(choices)) != len(choices):
                raise ValueError('Invalid choices')
            put(field, 'Choices', '\n'.join(choices))
        if typ in ('1', '2', '11'):
            length = int(config.get('max_length', 12 if typ == '2' else 4000))
            if not 1 <= length <= {'1': 4000, '2': 20, '11': 9999}[typ]:
                raise ValueError('Invalid max_length')
            put(field, 'InputMaxLength', length)
        if typ == '2':
            decimals = int(config.get('decimals', 0))
            if not 0 <= decimals <= 5 or decimals >= length:
                raise ValueError('Invalid decimals')
            put(field, 'DecimalPoint', decimals)
            remove(field, 'UnitDispPlace', 'UnitText')
            if config.get('unit'):
                put(field, 'UnitDispPlace', 1)
                put(field, 'UnitText', config['unit'])
        if typ == '11':
            put(field, 'DisplayRows', 3)
        if config.get('default_login'):
            if typ != '52':
                raise ValueError('default_login requires employee field 52')
            put(field, 'DefaultValue', '@login')
        fields.append(field)
        mapping[config['name']] = field.findtext('Id')
    fields.extend(systems)
    mapping.update({f.findtext('FieldName'): f.findtext('Id') for f in systems})
    allfields = list(fields)
    # Regenerate every list item and every screen cell; do not retain dangling seed fields/images.
    lists = root.find('ListViews')
    keep_lists = [copy.deepcopy(lists[0]), copy.deepcopy(lists[-1])]
    lists.clear()
    listseed = copy.deepcopy(keep_lists[0].find('./ListItems/ListItem'))
    for j, view in enumerate(keep_lists):
        remove(view, 'SortFieldId1', 'SortFieldId2', 'SortFieldId3', 'SortType1', 'SortType2', 'SortType3')
        put(view, 'ListName', '一覧' if j == 0 else '（全項目）')
        put(view, 'DisplayOrder', j+1)
        items = view.find('ListItems'); items.clear()
        listfields = allfields
        if view.findtext('ListType') == '0':
            # User-confirmed all-items list: five system columns, then field-setting order.
            standard_order = {'85': 0, '86': 1, '87': 2, '88': 3, '89': 4}
            standard_fields = sorted(systems, key=lambda f: standard_order[f.findtext('FieldType')])
            custom_fields = sorted((f for f in allfields if f.findtext('ItemClass') == '1'),
                                   key=lambda f: int(f.findtext('DispOrder')))
            listfields = standard_fields + custom_fields
        for i, field in enumerate(listfields, 1):
            item = copy.deepcopy(listseed)
            put(item, 'Id', 20000+j*1000+i)
            put(item, 'ListId', view.findtext('Id'))
            put(item, 'FieldId', field.findtext('Id'))
            put(item, 'DispOrder', i)
            items.append(item)
        lists.append(view)
    screens = root.find('ScreenViews')
    layoutseed = copy.deepcopy(screens[0].find('./Layouts/Layout'))
    cellseed = copy.deepcopy(layoutseed.find('./LayoutCells/LayoutCell'))
    inputseed = copy.deepcopy(layoutseed.find('./LayoutCells/LayoutCell/LayoutItems/LayoutItem'))
    for j, screen in enumerate(screens):
        put(screen, 'ScreenName', '入力画面' if j == 0 else '（全項目）')
        put(screen, 'DisplayOrder', j+1)
        layouts = screen.find('Layouts'); layouts.clear()
        # Split into blocks of at most 50 rows, two cells per row.
        for block, start in enumerate(range(0, len(allfields), 100)):
            subset = allfields[start:start+100]
            lid = 30000+j*100+block
            layout = copy.deepcopy(layoutseed)
            put(layout, 'Id', lid); put(layout, 'ScreenId', screen.findtext('Id'))
            put(layout, 'DispOrder', block+1)
            put(layout, 'MaxCols', 2); put(layout, 'MaxRows', (len(subset)+1)//2)
            cells = layout.find('LayoutCells'); cells.clear()
            for i, field in enumerate(subset):
                cid = 40000+j*1000+start+i
                cell = copy.deepcopy(cellseed)
                put(cell, 'Id', cid); put(cell, 'LayoutId', lid)
                put(cell, 'RowIndex', i//2); put(cell, 'ColIndex', i%2)
                put(cell, 'HeadTitle', field.findtext('FieldName'))
                items = cell.find('LayoutItems'); items.clear()
                item = copy.deepcopy(inputseed)
                put(item, 'Id', 50000+j*1000+start+i); put(item, 'CellId', cid)
                put(item, 'FieldId', field.findtext('Id'))
                put(item, 'UsageClass', 2 if field.findtext('ItemClass') == '0' else 1)
                items.append(item); cells.append(cell)
            layouts.append(layout)
    queries = root.find('Queries')
    default_query = copy.deepcopy(queries[0]); queries.clear(); queries.append(default_query)
    queryseed = original.find('./Queries/Query[2]')
    for i, config in enumerate(spec.get('filters', []), 1):
        fid = mapping[config['field']]
        field = next(f for f in fields if f.findtext('Id') == fid)
        login = config.get('login_employee', False)
        if login:
            if field.findtext('FieldType') not in ('52', '87', '89'):
                raise ValueError('login_employee requires employee field')
        elif field.findtext('FieldType') not in ('22', '23') or config['value'] not in field.findtext('Choices').splitlines():
            raise ValueError('Helper filters support literal choices or login employee equality')
        query = copy.deepcopy(queryseed)
        put(query, 'Id', 60000+i); put(query, 'AuthorityId', 61000+i)
        put(query, 'DispOrder', i+1); put(query, 'QueryName', config['name'])
        block = query.find('./QueryBlocks/QueryBlock')
        put(block, 'Id', 62000+i); put(block, 'QueryId', 60000+i)
        item = block.find('./QueryItems/QueryItem')
        put(item, 'id', 63000+i); put(item, 'blockId', 62000+i)
        put(item, 'fieldId', fid)
        put(item, 'compareTarget', 0 if login else 1)
        put(item, 'conditionValue', '@login' if login else config['value'])
        queries.append(query)
    summaries = root.find('Summaries'); summaries.clear()
    summaryseed = original.find('./Summaries/Summary[2]')
    for i, config in enumerate(spec.get('summaries', []), 1):
        key = mapping[config['group_by']]
        keyfield = next(f for f in fields if f.findtext('Id') == key)
        if keyfield.findtext('FieldType') not in ('22', '23'):
            raise ValueError('Helper summary keys support radio/dropdown only')
        display = {'table': 0, 'pie': 1, 'line': 2, 'vertical_bar': 3, 'horizontal_bar': 4}[config.get('display', 'table')]
        summary = copy.deepcopy(summaryseed)
        put(summary, 'Id', 70000+i); put(summary, 'AuthorityId', 71000+i)
        put(summary, 'DispOrder', i); put(summary, 'SummaryName', config['name'])
        put(summary, 'Key1FieldId', key); put(summary, 'DisplayType', display)
        items = summary.find('SummaryItems')
        for k, item in enumerate(items, 1):
            put(item, 'Id', 72000+i*10+k); put(item, 'SummaryDefId', 70000+i)
            if item.findtext('SummaryType') == '1':
                put(item, 'FieldId', key)
        measure = items[-1]
        method = config.get('method', 'count')
        if method == 'sum':
            target = mapping[config['field']]
            targetfield = next(f for f in fields if f.findtext('Id') == target)
            if targetfield.findtext('FieldType') != '2' or target == key:
                raise ValueError('SUM requires another numeric field')
            put(measure, 'SummaryType', 40); put(measure, 'FieldId', target)
        elif method != 'count':
            raise ValueError('Only count/sum supported')
        summaries.append(summary)
    for tag in ('FieldRelations', 'FieldLinks', 'DBReferences', 'Notices', 'SubTableXmlWrappers'):
        root.find(tag).clear()
    # Serialize once, hash those exact bytes, then store the same bytes in ZIP.
    ET.indent(root, space='    ')
    xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(root, encoding='utf-8')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('databasedef.xml', xml)
        z.writestr('certificate.txt', hashlib.md5(xml).hexdigest().encode('ascii'))
    data = buffer.getvalue()
    validate(data)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['restore', 'build', 'validate', 'validate-archive', 'inspect', 'field-example'])
    parser.add_argument('memo_or_zip')
    parser.add_argument('argument', nargs='?')
    parser.add_argument('output', nargs='?')
    args = parser.parse_args()
    if args.action == 'restore':
        data = payload(args.memo_or_zip, args.argument)
        validate_archive(data)
        pathlib.Path(args.output).write_bytes(data)
        print('Restored original ZIP, SHA256=' + hashlib.sha256(data).hexdigest())
    elif args.action == 'build':
        config = json.loads(pathlib.Path(args.argument).read_text(encoding='utf-8-sig'))
        data = build(args.memo_or_zip, config)
        pathlib.Path(args.output).write_bytes(data)
        print('EXPERIMENTAL candidate; local structural checks passed; POWER EGG import NOT tested.')
    elif args.action == 'field-example':
        text = pathlib.Path(args.memo_or_zip).read_text(encoding='utf-8-sig')
        for name in re.findall(r'^BEGIN_PAYLOAD (\S+) SHA256=', text, re.M):
            root = validate_archive(payload(args.memo_or_zip, name))
            field = next((f for f in root.findall('.//Fields/Field')
                          if f.findtext('FieldType') == args.argument), None)
            if field is not None:
                print('SOURCE=' + name)
                print(ET.tostring(field, encoding='unicode'))
                break
        else:
            raise ValueError('Field type not observed in embedded corpus')
    else:
        data = pathlib.Path(args.memo_or_zip).read_bytes()
        root = validate(data) if args.action == 'validate' else validate_archive(data)
        if args.action == 'inspect':
            print(ET.tostring(root, encoding='unicode'))
        else:
            print('Local structural checks passed; this does not establish POWER EGG import compatibility.')


if __name__ == '__main__':
    main()
