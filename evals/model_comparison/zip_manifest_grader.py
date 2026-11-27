"""Standalone oracle: build a ZIP and measure its file manifest with the stdlib."""

import io
import json
from pathlib import Path
import sys
import zipfile


def main():
    case = json.load(sys.stdin)['case']
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for item in case['oracle']['entries']:
            archive.writestr(item['name'], item['text'].encode('utf-8'))
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        files = [info for info in archive.infolist() if not info.is_dir()]
        expected = {'files': [{'name': info.filename, 'bytes': info.file_size} for info in files],
                    'total_bytes': sum(info.file_size for info in files)}
    # Python considers False == 0; byte counts require actual JSON integers.
    observed = case['response']
    counts_valid = isinstance(observed, dict) and type(observed.get('total_bytes')) is int
    files = observed.get('files') if isinstance(observed, dict) else None
    counts_valid = counts_valid and isinstance(files, list) and all(
        isinstance(row, dict) and type(row.get('bytes')) is int for row in files)
    score = float(counts_valid and observed == expected)
    Path('grade.json').write_text(json.dumps({'case_id': case['case_id'], 'expected': expected,
        'actual': case['response'], 'score': score}, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'score': score, 'artifact_paths': ['grade.json'], 'cost_usd': 0}))


if __name__ == '__main__':
    main()
