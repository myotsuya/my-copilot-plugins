"""Offline WebDB candidate builder and byte-exact two-file ZIP packager.

These checks cannot establish POWER EGG import compatibility.
Python 3.9+, standard library only. No network or POWER EGG access.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import webdb_memo_tool as helper

SKILL = Path(__file__).resolve().parent.parent
MEMO = SKILL / 'sources/POWER_EGG_WebDB_仕様.md'
ORDER = ('ExportVersion Database Fields ListViews ScreenViews Queries Summaries '
         'FieldRelations FieldLinks DBReferences Notices SubTableXmlWrappers ActionLimit').split()
TYPES = {'1', '2', '5', '6', '9', '11', '20', '21', '22', '23', '31', '51', '52'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(obj, allowed, context):
    require(isinstance(obj, dict), context + ': expected object')
    require(not set(obj) - set(allowed), context + ': unsupported keys ' + str(sorted(set(obj) - set(allowed))))


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + ': nonempty string required')


def check_request(config):
    keys(config, ('database_name', 'notes', 'fields', 'filters', 'summaries'), 'request')
    text(config.get('database_name'), 'database_name')
    if 'notes' in config:
        require(isinstance(config['notes'], str), 'notes must be a string')
    require(isinstance(config.get('fields'), list) and 1 <= len(config['fields']) <= 100, 'fields: 1..100 custom fields')
    names = set()
    for field in config['fields']:
        keys(field, ('name', 'type', 'required', 'reusable', 'choices', 'max_length', 'decimals', 'unit', 'default_login'), 'field')
        text(field.get('name'), 'field.name')
        require(field['name'] not in names, 'duplicate field name')
        names.add(field['name'])
        typ = str(field.get('type'))
        require(typ in TYPES, 'unsupported type in basic builder: ' + typ)
        for k in ('required', 'reusable', 'default_login'):
            if k in field:
                require(type(field[k]) is bool, k + ' must be boolean')
        applicable = {'choices': {'21', '22', '23'}, 'max_length': {'1', '2', '11'},
                      'decimals': {'2'}, 'unit': {'2'}, 'default_login': {'52'}}
        for key, types in applicable.items():
            require(key not in field or typ in types, key + ' is not applicable to type ' + typ)
        for k in ('max_length', 'decimals'):
            if k in field:
                require(type(field[k]) is int, k + ' must be an integer')
        if 'choices' in field:
            require(isinstance(field['choices'], list), 'choices must be an array')
        if 'unit' in field:
            text(field['unit'], 'unit')
    for section, allowed in (
        ('filters', ('name', 'field', 'value', 'login_employee')),
        ('summaries', ('name', 'group_by', 'method', 'field', 'display')),
    ):
        require(isinstance(config.get(section, []), list), section + ' must be an array')
        for item in config.get(section, []):
            keys(item, allowed, section)
            text(item.get('name'), section + '.name')
            if section == 'filters':
                text(item.get('field'), 'filter.field')
                if 'login_employee' in item:
                    require(type(item['login_employee']) is bool, 'login_employee must be boolean')
                require(not (item.get('login_employee') and 'value' in item), 'login filter must omit value')
                if not item.get('login_employee'):
                    text(item.get('value'), 'filter.value')
            else:
                text(item.get('group_by'), 'summary.group_by')
                require(item.get('method', 'count') in ('count', 'sum'), 'only count/sum are supported')
                require(item.get('display', 'table') in ('table', 'pie', 'line', 'vertical_bar', 'horizontal_bar'), 'unsupported display')
                require(item.get('method', 'count') == 'sum' or 'field' not in item, 'count must omit field')
                if item.get('method') == 'sum':
                    text(item.get('field'), 'summary.field')


def check_xml(xml):
    require(xml.startswith(b'<?xml'), 'XML declaration required, UTF-8 without BOM')
    xml.decode('utf-8')
    require(b'<!DOCTYPE' not in xml.upper() and b'<!ENTITY' not in xml.upper(), 'DTD/entities are not supported')
    root = ET.fromstring(xml)
    require(root.tag == 'DatabaseXmlWrapper', 'unexpected XML root')
    require([e.tag for e in root] == ORDER, 'root elements missing, duplicated, or out of observed order')
    text(root.findtext('ExportVersion'), 'ExportVersion')
    text(root.findtext('Database/DatabaseName'), 'DatabaseName')
    scopes = [root] + root.findall('.//SubTableXmlWrapper')
    for scope in scopes:
        fields = scope.findall('./Fields/Field')
        require(bool(fields) and len(fields) <= 300, 'invalid field count in scope')
        ids = [f.findtext('Id') for f in fields]
        require(None not in ids and len(set(ids)) == len(ids), 'missing or duplicate field ID in scope')
        owner = scope.findtext('Database/Id') if scope is root else scope.findtext('SubTable/Id')
        if owner:
            require(all(f.findtext('DatabaseId') == owner for f in fields), 'field DatabaseId mismatch')
        # Cross-WebDB references have separate meanings. Only inspect known local paths.
        for item in scope.findall('./ListViews/ListView/ListItems/ListItem'):
            require(item.findtext('FieldId') in ids, 'dangling list field')
        for item in scope.findall('./ScreenViews/ScreenView/Layouts/Layout/LayoutCells/LayoutCell/LayoutItems/LayoutItem'):
            if item.findtext('ItemType') == '0':
                require(item.findtext('FieldId') in ids, 'dangling screen field')
        for view in scope.findall('./ListViews/ListView'):
            if view.findtext('ListType') == '0':
                actual = [i.findtext('FieldId') for i in sorted(view.findall('ListItems/ListItem'), key=lambda i: int(i.findtext('DispOrder')))]
                systems = {f.findtext('FieldType'): f.findtext('Id') for f in fields if f.findtext('ItemClass') == '0'}
                standard = [systems.get(t) for t in ('85', '86', '87', '88', '89') if systems.get(t)]
                custom = [f.findtext('Id') for f in sorted(fields, key=lambda f: int(f.findtext('DispOrder'))) if f.findtext('ItemClass') == '1']
                # Parent all-items order is explicitly user-confirmed. Detail table differs.
                if scope is root:
                    require(actual == standard + custom, 'parent all-items list order does not match documented rule')
    return root


def candidate_bytes(xml):
    check_xml(xml)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('databasedef.xml', xml)
        z.writestr('certificate.txt', hashlib.md5(xml).hexdigest().encode('ascii'))
    return buffer.getvalue()


def check_zip(data, basic=False):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        require(z.namelist() == ['databasedef.xml', 'certificate.txt'], 'candidate ZIP must contain exactly the two root files')
        require(z.testzip() is None, 'ZIP CRC mismatch')
        xml = z.read('databasedef.xml')
        require(z.read('certificate.txt') == hashlib.md5(xml).hexdigest().encode('ascii'), 'certificate mismatch')
    root = check_xml(xml)
    if basic:
        helper.validate(data)
    return root


def save(data, output, basic=False):
    root = check_zip(data, basic)
    output = Path(output)
    require(not output.exists(), 'output already exists; choose a new path')
    parts = output.with_name(output.stem + '-files')
    report_path = output.with_name(output.stem + '-validation.json')
    require(not parts.exists() and not report_path.exists(), 'associated output paths already exist')
    output.parent.mkdir(parents=True, exist_ok=True)
    parts.mkdir()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in ('databasedef.xml', 'certificate.txt'):
            (parts / name).write_bytes(z.read(name))
    output.write_bytes(data)
    report = {'database_name': root.findtext('Database/DatabaseName'),
              'export_version': root.findtext('ExportVersion'), 'zip_sha256': hashlib.sha256(data).hexdigest(),
              'files': ['databasedef.xml', 'certificate.txt'],
              'local_checks': 'basic-builder-reference-and-layout' if basic else 'limited-xml-structure-and-byte-integrity',
              'power_egg_import_tested': False, 'status': 'experimental_candidate',
              'remaining': ['POWER EGGで取込・動作確認', 'フォルダ・DB・画面の権限確認', '環境依存の組織・参照先・通知設定確認']}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for action, input_name in (('build', 'request'), ('pack', 'xml')):
        sub = subs.add_parser(action)
        sub.add_argument(input_name)
        sub.add_argument('output')
    sub = subs.add_parser('validate')
    sub.add_argument('zip')
    sub.add_argument('--basic', action='store_true')
    args = parser.parse_args()
    if args.command == 'build':
        config = json.loads(Path(args.request).read_text(encoding='utf-8-sig'))
        check_request(config)
        save(helper.build(MEMO, config), args.output, basic=True)
    elif args.command == 'pack':
        save(candidate_bytes(Path(args.xml).read_bytes()), args.output)
    else:
        data = Path(args.zip).read_bytes()
        check_zip(data, args.basic)
        print('Local checks passed; POWER EGG import NOT tested. SHA256=' + hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    main()
